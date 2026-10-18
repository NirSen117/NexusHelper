from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.schemas import Evidence


@dataclass
class VerificationResult:
    is_valid: bool
    confidence: float
    unverified_claims: list[str] = field(default_factory=list)
    stale_citations: list[str] = field(default_factory=list)
    superseded_citations: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    should_abstain: bool = False
    abstention_reason: str | None = None
    notes: list[str] = field(default_factory=list)


def verify_claims(
    answer: str,
    cited_node_ids: list[str],
    evidence_items: list[Evidence],
    solution_checks: list[dict[str, Any]] | None = None,
) -> VerificationResult:
    """Deterministically verifies claims and citations in the generated answer against accessible evidence.

    Rules:
      1. Every bracketed citation [node_id] in the answer must exist in the user's accessible evidence.
      2. If any cited node is expired (valid_to < now), flag as stale.
      3. If a solution is superseded, flag if the superseding solution was not adopted.
      4. If contradictions exist, reduce confidence.
      5. If ungrounded citations or zero valid evidence exist, abstain.
    """
    now = int(time.time())
    accessible_node_ids = {e.node_id: e for e in evidence_items}

    # Extract all [node-id] patterns in answer text
    bracketed_matches = re.findall(r"\[([a-zA-Z0-9_\-]+)\]", answer)
    all_cited = list(dict.fromkeys(cited_node_ids + bracketed_matches))

    unverified: list[str] = []
    stale: list[str] = []
    superseded: list[str] = []
    contradictions: list[str] = []
    notes: list[str] = []

    if not all_cited:
        return VerificationResult(
            is_valid=False,
            confidence=0.0,
            should_abstain=True,
            abstention_reason="The answer did not cite any evidence records",
        )

    for node_id in all_cited:
        if node_id not in accessible_node_ids:
            unverified.append(node_id)
        else:
            ev = accessible_node_ids[node_id]
            # Freshness / temporal validity check
            if ev.valid_to and ev.valid_to < now:
                stale.append(f"{node_id} (expired at {ev.valid_to})")

            # Deprecation check
            if ev.status == "deprecated":
                notes.append(f"Solution [{node_id}] is deprecated.")

    # Check supersession and contradictions from graph metadata
    if solution_checks:
        for check in solution_checks:
            sid = check["id"]
            if sid in all_cited:
                superseded_by = check.get("superseded_by", [])
                if superseded_by:
                    for newer in superseded_by:
                        superseded.append(f"[{sid}] is superseded by [{newer}]")

                contradicted_by = check.get("contradicted_by", [])
                if contradicted_by:
                    for contra in contradicted_by:
                        contradictions.append(f"[{sid}] contradicts [{contra}]")

    # Base confidence from evidence
    ev_confidences = [e.confidence for e in evidence_items if e.node_id in all_cited]
    avg_conf = sum(ev_confidences) / len(ev_confidences) if ev_confidences else 0.5

    # Penalties
    if unverified:
        avg_conf -= 0.3 * len(unverified)
    if stale:
        avg_conf -= 0.2 * len(stale)
    if contradictions:
        avg_conf -= 0.25 * len(contradictions)

    final_confidence = max(0.0, min(1.0, round(avg_conf, 2)))
    should_abstain = False
    abstention_reason = None

    if unverified:
        should_abstain = True
        abstention_reason = f"Answer cited {len(unverified)} unverified or inaccessible node(s): {', '.join(unverified)}"
    elif final_confidence < 0.4:
        should_abstain = True
        abstention_reason = "Aggregate evidence confidence is too low (< 0.40) to provide a reliable answer."

    return VerificationResult(
        is_valid=not unverified and not should_abstain,
        confidence=final_confidence,
        unverified_claims=unverified,
        stale_citations=stale,
        superseded_citations=superseded,
        contradictions=contradictions,
        should_abstain=should_abstain,
        abstention_reason=abstention_reason,
        notes=notes,
    )
