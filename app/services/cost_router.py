"""
NexusHelper: cost-tiered query router.

Design goals
  * Deterministic and free by default (regex + entity linking, no LLM).
  * Small-model fallback ONLY when the rules are genuinely ambiguous.
  * Permission scope comes from the authenticated session, never from the
    query text or an LLM. The cache is keyed by that scope.
  * Escalate to a deeper tier when retrieval confidence is low, instead of
    guessing up front.
  * Every decision is recorded in a Trace the UI can show.

No third-party dependencies.
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional


# ----------------------------------------------------------------------------
# Core types
# ----------------------------------------------------------------------------
class Tier(IntEnum):
    CACHE = 0
    LOOKUP = 1
    CONTEXTUAL = 2
    INVESTIGATION = 3


# Logical agents per tier. Several are deterministic (no model call).
PIPELINES: dict[Tier, list[str]] = {
    Tier.CACHE: ["cache"],
    Tier.LOOKUP: ["access", "context", "response"],
    Tier.CONTEXTUAL: ["access", "context", "history", "response"],
    Tier.INVESTIGATION: ["access", "context", "history", "investigation",
                         "verification", "response"],
}

# Upper bound of LLM calls per tier (the demo's efficiency number).
MAX_LLM_CALLS: dict[Tier, int] = {
    Tier.CACHE: 0, Tier.LOOKUP: 1, Tier.CONTEXTUAL: 1, Tier.INVESTIGATION: 3,
}


@dataclass(frozen=True)
class UserContext:
    """Built by the backend from the auth token. Never from request input."""
    user_id: str
    team_ids: tuple[str, ...]

    @property
    def scope_hash(self) -> str:
        key = "|".join(sorted(self.team_ids))
        return hashlib.sha1(key.encode()).hexdigest()[:16]


@dataclass
class QueryPlan:
    tier: Tier
    agents: list[str]
    max_llm_calls: int
    entities: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    cache_answer: Optional[object] = None
    used_fallback_model: bool = False

    @property
    def cache_hit(self) -> bool:
        return self.tier == Tier.CACHE


@dataclass
class Trace:
    """Rendered in the demo's trace panel."""
    query: str
    tier: str = ""
    agents_run: list[str] = field(default_factory=list)
    llm_calls: int = 0
    escalations: int = 0
    reasons: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)
    latency_ms: float = 0.0

    def finish(self) -> "Trace":
        self.latency_ms = round((time.perf_counter() - self.started) * 1000, 1)
        return self


# ----------------------------------------------------------------------------
# Entity linker: "auth-svc" / "Auth Service" -> svc-auth
# In production, build the alias index from Service.aliases in FalkorDB.
# ----------------------------------------------------------------------------
class EntityLinker:
    def __init__(self, alias_to_id: dict[str, str]):
        # Longest aliases first so "api gateway" wins over "gateway".
        self._patterns = [
            (re.compile(rf"(?<![\w-]){re.escape(a.lower())}(?![\w-])"), eid)
            for a, eid in sorted(alias_to_id.items(), key=lambda kv: -len(kv[0]))
        ]

    @classmethod
    def from_graph_rows(cls, rows: list[tuple[str, list[str]]]) -> "EntityLinker":
        """rows: [(service_id, [aliases...]), ...] from
        MATCH (s:Service) RETURN s.id, s.aliases"""
        index = {a: sid for sid, aliases in rows for a in aliases}
        return cls(index)

    def link(self, text: str) -> list[str]:
        text, found, seen = text.lower(), [], set()
        for pattern, eid in self._patterns:
            if eid not in seen and pattern.search(text):
                found.append(eid)
                seen.add(eid)
        return found


# ----------------------------------------------------------------------------
# Semantic cache (scope-keyed, entity-tagged for invalidation)
# ----------------------------------------------------------------------------
def _normalise(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", "", q.lower())).strip()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class _CacheEntry:
    norm: str
    vec: Optional[list[float]]
    answer: object
    entities: set[str]
    expires: float


class SemanticCache:
    """Exact-match first, then embedding similarity. Entries live in a bucket
    per permission scope, so a cached answer can never cross scopes."""

    def __init__(self, embed_fn: Optional[Callable[[str], list[float]]] = None,
                 threshold: float = 0.92, ttl_s: float = 3600):
        self.embed_fn, self.threshold, self.ttl_s = embed_fn, threshold, ttl_s
        self._buckets: dict[str, list[_CacheEntry]] = {}

    def get(self, scope_hash: str, query: str):
        now, norm = time.time(), _normalise(query)
        live = [e for e in self._buckets.get(scope_hash, []) if e.expires > now]
        self._buckets[scope_hash] = live
        for e in live:
            if e.norm == norm:
                return e.answer
        if self.embed_fn and live:
            qv = self.embed_fn(query)
            best = max(live, key=lambda e: _cosine(qv, e.vec) if e.vec else -1)
            if best.vec and _cosine(qv, best.vec) >= self.threshold:
                return best.answer
        return None

    def put(self, scope_hash: str, query: str, answer: object,
            entities: list[str]) -> None:
        vec = self.embed_fn(query) if self.embed_fn else None
        self._buckets.setdefault(scope_hash, []).append(_CacheEntry(
            _normalise(query), vec, answer, set(entities),
            time.time() + self.ttl_s))

    def invalidate_entity(self, entity_id: str) -> int:
        """Call after graph write-back that touches a service or incident."""
        dropped = 0
        for scope, entries in self._buckets.items():
            keep = [e for e in entries if entity_id not in e.entities]
            dropped += len(entries) - len(keep)
            self._buckets[scope] = keep
        return dropped


# ----------------------------------------------------------------------------
# Feature extraction + scoring
# ----------------------------------------------------------------------------
_CUES = {
    "why":       re.compile(r"\b(why|root cause|what caused|cause of)\b"),
    "failure":   re.compile(r"\b(fail(s|ed|ing|ure|ures)?|broke(n)?|crash(es|ed)?|"
                            r"outage|regress(ed|ion)?|intermittent|error|errors|spike)\b"),
    "repeat":    re.compile(r"\b(again|keeps?|repeated(ly)?|recurring|every time|"
                            r"multiple|several|\d+|two|three|four|separate)\b"),
    "relation":  re.compile(r"\b(relat(e|es|ed|ion)|connect(ed|ion)?|depends? on|"
                            r"impact(s|ed)?|affect(s|ed)?|linked|because of)\b"),
    "temporal":  re.compile(r"\b(recent(ly)?|changed|last (week|month|deploy)|"
                            r"since|latest|yesterday)\b"),
    "lookup":    re.compile(r"\b(how (do|to|can) (i|we)|procedure|runbook|steps?|"
                            r"guide|process|policy|what is|where is)\b"),
    "ownership": re.compile(r"\b(who owns?|owner|who (knows|is responsible)|contact)\b"),
}


def extract_features(query: str, entities: list[str]) -> dict[str, int]:
    q = query.lower()
    hit = {name: int(bool(p.search(q))) for name, p in _CUES.items()}
    multi_entity = int(len(entities) >= 2)

    investigation = (2 * hit["why"] + hit["failure"] + hit["repeat"]
                     + hit["relation"] + multi_entity)
    contextual = (hit["relation"] + hit["temporal"] + hit["ownership"]
                  + multi_entity)
    lookup = hit["lookup"] + (1 if len(entities) == 1 else 0)
    return {"investigation": investigation, "contextual": contextual,
            "lookup": lookup, **{f"cue_{k}": v for k, v in hit.items()}}


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
# Optional small-model fallback: takes the query, returns 1, 2 or 3.
FallbackClassifier = Callable[[str], int]


class QueryRouter:
    def __init__(self, linker: EntityLinker, cache: Optional[SemanticCache] = None,
                 fallback: Optional[FallbackClassifier] = None,
                 default_tier: Tier = Tier.CONTEXTUAL):
        self.linker, self.cache = linker, cache
        self.fallback, self.default_tier = fallback, default_tier

    # -- planning ------------------------------------------------------------
    def plan(self, user: UserContext, query: str) -> QueryPlan:
        entities = self.linker.link(query)

        if self.cache:
            hit = self.cache.get(user.scope_hash, query)
            if hit is not None:
                return self._make(Tier.CACHE, entities, ["semantic cache hit"],
                                  {}, cache_answer=hit)

        f = extract_features(query, entities)
        inv, ctx, lk = f["investigation"], f["contextual"], f["lookup"]
        reasons: list[str] = []

        if inv >= 3:
            tier = Tier.INVESTIGATION
            reasons.append(f"investigation score {inv} >= 3")
        elif inv == 2 and (f["cue_why"] or ctx >= 2):
            tier = Tier.INVESTIGATION
            reasons.append(f"investigation score {inv} with causal/relational signal")
        elif ctx >= 2 or (ctx >= 1 and lk == 0):
            tier = Tier.CONTEXTUAL
            reasons.append(f"contextual score {ctx}")
        elif lk >= 1 and inv == 0 and ctx == 0:
            tier = Tier.LOOKUP
            reasons.append(f"plain lookup (score {lk}, no causal or relational cues)")
        else:
            tier, used = self._resolve_ambiguity(query, reasons)
            return self._make(tier, entities, reasons, f, used_fallback=used)

        if not entities:
            reasons.append("no known entity matched: retrieval will rely on vector search")
        return self._make(tier, entities, reasons, f)

    def _resolve_ambiguity(self, query: str, reasons: list[str]):
        if self.fallback:
            try:
                tier = Tier(max(1, min(3, int(self.fallback(query)))))
                reasons.append(f"ambiguous, small model chose tier {int(tier)}")
                return tier, True
            except Exception as exc:  # fall through to the safe default
                reasons.append(f"fallback model failed ({exc!r})")
        reasons.append(f"ambiguous, defaulted to tier {int(self.default_tier)}")
        return self.default_tier, False

    @staticmethod
    def _make(tier, entities, reasons, scores, cache_answer=None,
              used_fallback=False) -> QueryPlan:
        return QueryPlan(tier=tier, agents=list(PIPELINES[tier]),
                         max_llm_calls=MAX_LLM_CALLS[tier], entities=entities,
                         reasons=reasons, scores=scores, cache_answer=cache_answer,
                         used_fallback_model=used_fallback)

    # -- escalation ----------------------------------------------------------
    @staticmethod
    def escalate(plan: QueryPlan, retrieval_confidence: float,
                 min_confidence: float = 0.6) -> Optional[QueryPlan]:
        """Call after retrieval. If the evidence is weak, move up one tier
        rather than letting a cheap path produce a shaky answer. Returns None
        if already at the top (caller should abstain and route to an expert)."""
        if retrieval_confidence >= min_confidence or plan.tier >= Tier.INVESTIGATION:
            return None
        new_tier = Tier(plan.tier + 1)
        return QueryRouter._make(
            new_tier, plan.entities,
            plan.reasons + [f"escalated: retrieval confidence "
                            f"{retrieval_confidence:.2f} < {min_confidence}"],
            plan.scores, used_fallback=plan.used_fallback_model)

    # -- trace ---------------------------------------------------------------
    @staticmethod
    def new_trace(query: str, plan: QueryPlan) -> Trace:
        return Trace(query=query, tier=f"{int(plan.tier)}:{plan.tier.name}",
                     reasons=list(plan.reasons))


# ----------------------------------------------------------------------------
# Scope helper: the ONLY place scope is turned into query parameters
# ----------------------------------------------------------------------------
def cypher_params(user: UserContext, **extra) -> dict:
    """Merge extra params with the session-derived scope. Callers cannot
    override 'scope' (it is applied last)."""
    return {**extra, "scope": list(user.team_ids)}


# ----------------------------------------------------------------------------
# Demo / self-test
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    linker = EntityLinker.from_graph_rows([
        ("svc-a",    ["service a", "svc-a", "payments-api"]),
        ("svc-auth", ["auth service", "auth-svc", "authentication service", "auth"]),
        ("svc-gw",   ["api gateway", "gateway", "gw"]),
    ])
    router = QueryRouter(linker, cache=SemanticCache())

    alice = UserContext("emp-alice", ("team-platform",))
    carol = UserContext("emp-carol", ("team-security",))

    demo = [
        "What is the deployment procedure for Service A?",
        "Why has Service A failed after three separate deployments, "
        "and how does this relate to the authentication service?",
        "Who owns the auth service and what changed recently?",
        "How do I roll back the API Gateway?",
        "Tell me about the roadmap",
    ]
    for q in demo:
        p = router.plan(alice, q)
        print(f"[T{int(p.tier)} {p.tier.name:<13}] llm<={p.max_llm_calls} "
              f"entities={p.entities}\n   {q}\n   -> {p.reasons}\n")

    # Cache is scope-keyed: Alice's cached answer must not serve Carol.
    router.cache.put(alice.scope_hash, demo[0], "cached answer", ["svc-a"])
    assert router.plan(alice, demo[0]).cache_hit
    assert not router.plan(carol, demo[0]).cache_hit
    print("cache: hit for same scope, miss for different scope  OK")

    # Write-back invalidates entries tagged with the touched entity.
    assert router.cache.invalidate_entity("svc-a") == 1
    assert not router.plan(alice, demo[0]).cache_hit
    print("cache: invalidated after write-back on svc-a  OK")

    # Escalation on weak retrieval.
    p1 = router.plan(alice, demo[0])
    p2 = router.escalate(p1, retrieval_confidence=0.3)
    print(f"escalation: T{int(p1.tier)} -> T{int(p2.tier)}  {p2.reasons[-1]}")
