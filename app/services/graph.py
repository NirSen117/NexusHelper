from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.security import Principal
from app.settings import Settings, settings

logger = logging.getLogger(__name__)


class GraphUnavailable(Exception):
    pass


class BaseGraphRepository(ABC):
    @abstractmethod
    def match_services(self, query_text: str) -> list[str]:
        pass

    @abstractmethod
    def find_documents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def find_incidents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def find_subgraph(
        self, principal: Principal, service_ids: list[str], incident_ids: list[str]
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def check_verification(self, principal: Principal, solution_ids: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def find_experts(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def find_owners(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def workspace_overview(self, principal: Principal) -> dict[str, Any]:
        pass

    @abstractmethod
    def confirm_solution(
        self, principal: Principal, incident_id: str, solution_id: str
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class GraphRepository(BaseGraphRepository):
    """FalkorDB graph repository. Parameterized queries enforce permission filtering at query time."""

    def __init__(
        self,
        host: str,
        port: int,
        graph_name: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
    ):
        from falkordb import FalkorDB

        self.client = FalkorDB(
            host=host, port=port, username=username, password=password, ssl=use_tls,
            socket_timeout=8, socket_connect_timeout=5,
        )
        self.graph = self.client.select_graph(graph_name)

    @classmethod
    def from_settings(cls, config: Settings) -> BaseGraphRepository:
        """Connect to FalkorDB if reachable; fall back to SyntheticGraphRepository in dev/test."""
        try:
            repo = cls(
                config.falkordb_host,
                config.falkordb_port,
                config.falkordb_graph,
                config.falkordb_username,
                config.falkordb_password,
                config.falkordb_use_tls,
            )
            # Ping test with lightweight query
            repo._run("RETURN 1 AS ping", {})
            logger.info("Connected to FalkorDB at %s:%s", config.falkordb_host, config.falkordb_port)
            return repo
        except Exception as exc:
            if config.app_env.lower() == "production":
                logger.error("Failed to connect to FalkorDB in production: %s", exc)
                raise GraphUnavailable("FalkorDB connection failed in production") from exc
            logger.info(
                "FalkorDB not connected locally (%s). Using local SyntheticGraphRepository for development.",
                exc,
            )
            return SyntheticGraphRepository()

    def close(self) -> None:
        connection = getattr(self.client, "connection", None)
        if connection is not None and hasattr(connection, "close"):
            connection.close()

    @staticmethod
    def _visible(node_alias: str) -> str:
        """FalkorDB-compatible safe predicate; private records are withheld until scoped matching."""
        # Older/demo graph imports omit visibility; treat those seed records as public.
        # New restricted imports must set visibility explicitly before being loaded.
        return f"coalesce({node_alias}.visibility, 'public') = 'public'"

    def match_services(self, query_text: str) -> list[str]:
        text = query_text.strip().lower()
        if not text:
            return []
        rows = self._run(
            "MATCH (s:Service) "
            "WHERE any(a IN coalesce(s.aliases, []) WHERE $query CONTAINS toLower(a)) "
            "   OR $query CONTAINS toLower(s.name) "
            "RETURN s.id AS id LIMIT 10",
            {"query": text},
        )
        return [row["id"] for row in rows if row.get("id")]

    def find_documents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        if not service_ids:
            return []
        query = f"""
        MATCH (d:Document)-[:DESCRIBES]->(s:Service)
        WHERE s.id IN $service_ids AND {self._visible('d')}
          AND coalesce(d.status, 'unverified') <> 'deprecated'
          AND (d.valid_to IS NULL OR d.valid_to > $now)
        RETURN d.id AS id, d.title AS title, d.body AS summary,
               d.confidence AS confidence, d.status AS status,
               'document' AS node_type, d.valid_to AS valid_to,
               d.visibility AS visibility
        ORDER BY d.confidence DESC LIMIT 5
        """
        return self._run(
            query,
            {
                "service_ids": service_ids,
                "scope": list(principal.team_ids),
                "now": int(time.time()),
            },
        )

    def find_incidents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        if not service_ids:
            return []
        query = f"""
        MATCH (i:Incident)-[:AFFECTS]->(s:Service)
        WHERE s.id IN $service_ids AND {self._visible('i')}
        OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
        WITH i, s, sol
        WHERE sol IS NULL OR {self._visible('sol')}
        OPTIONAL MATCH (sol)-[:SUPPORTED_BY]->(e:Evidence)
        WITH i, s, sol, e
        WHERE e IS NULL OR {self._visible('e')}
        OPTIONAL MATCH (e)-[:EXTRACTED_FROM]->(src:Source)
        RETURN DISTINCT i.id AS id, i.title AS title, i.summary AS summary,
               i.status AS status, i.confidence AS confidence,
               sol.id AS solution_id, sol.title AS solution_title,
               sol.detail AS solution_detail, sol.status AS solution_status,
               sol.confidence AS solution_confidence, sol.valid_to AS solution_valid_to,
               e.id AS evidence_id, e.summary AS evidence,
               src.url AS source_url, i.visibility AS visibility
        ORDER BY i.confidence DESC LIMIT 20
        """
        return self._run(query, {"service_ids": service_ids, "scope": list(principal.team_ids)})

    def find_subgraph(
        self, principal: Principal, service_ids: list[str], incident_ids: list[str]
    ) -> dict[str, Any]:
        """Fetch bounded 1-2 hop evidence subgraph filtered strictly by principal scope."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []

        query = f"""
        MATCH (i:Incident)
        WHERE i.id IN $incident_ids AND {self._visible('i')}
        OPTIONAL MATCH (i)-[:AFFECTS]->(s:Service)
        OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
        WITH i, s, sol
        WHERE sol IS NULL OR {self._visible('sol')}
        OPTIONAL MATCH (sol)-[:SUPPORTED_BY]->(e:Evidence)
        WITH i, s, sol, e
        WHERE e IS NULL OR {self._visible('e')}
        OPTIONAL MATCH (e)-[:EXTRACTED_FROM]->(src:Source)
        RETURN i.id AS incident_id, i.title AS incident_title, i.status AS incident_status,
               s.id AS service_id, s.name AS service_name,
               sol.id AS sol_id, sol.title AS sol_title, sol.status AS sol_status,
               e.id AS ev_id, e.summary AS ev_summary,
               src.id AS src_id, src.url AS src_url
        """
        rows = self._run(query, {"incident_ids": incident_ids, "scope": list(principal.team_ids)})

        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()

        for r in rows:
            inc_id = r.get("incident_id")
            if inc_id and inc_id not in seen_nodes:
                seen_nodes.add(inc_id)
                nodes.append({
                    "id": inc_id,
                    "label": r.get("incident_title", inc_id),
                    "type": "incident",
                    "status": r.get("incident_status"),
                })

            svc_id = r.get("service_id")
            if svc_id:
                if svc_id not in seen_nodes:
                    seen_nodes.add(svc_id)
                    nodes.append({"id": svc_id, "label": r.get("service_name", svc_id), "type": "service"})
                if inc_id and (inc_id, svc_id, "AFFECTS") not in seen_edges:
                    seen_edges.add((inc_id, svc_id, "AFFECTS"))
                    edges.append({"source": inc_id, "target": svc_id, "type": "AFFECTS"})

            sol_id = r.get("sol_id")
            if sol_id:
                if sol_id not in seen_nodes:
                    seen_nodes.add(sol_id)
                    nodes.append({
                        "id": sol_id,
                        "label": r.get("sol_title", sol_id),
                        "type": "solution",
                        "status": r.get("sol_status"),
                    })
                if inc_id and (inc_id, sol_id, "RESOLVED_BY") not in seen_edges:
                    seen_edges.add((inc_id, sol_id, "RESOLVED_BY"))
                    edges.append({"source": inc_id, "target": sol_id, "type": "RESOLVED_BY"})

            ev_id = r.get("ev_id")
            if ev_id:
                if ev_id not in seen_nodes:
                    seen_nodes.add(ev_id)
                    nodes.append({
                        "id": ev_id,
                        "label": r.get("ev_summary", ev_id)[:40],
                        "type": "evidence",
                    })
                if sol_id and (sol_id, ev_id, "SUPPORTED_BY") not in seen_edges:
                    seen_edges.add((sol_id, ev_id, "SUPPORTED_BY"))
                    edges.append({"source": sol_id, "target": ev_id, "type": "SUPPORTED_BY"})

            src_id = r.get("src_id")
            if src_id:
                if src_id not in seen_nodes:
                    seen_nodes.add(src_id)
                    nodes.append({
                        "id": src_id,
                        "label": r.get("src_url", src_id),
                        "type": "source",
                    })
                if ev_id and (ev_id, src_id, "EXTRACTED_FROM") not in seen_edges:
                    seen_edges.add((ev_id, src_id, "EXTRACTED_FROM"))
                    edges.append({"source": ev_id, "target": src_id, "type": "EXTRACTED_FROM"})

        return {"nodes": nodes, "edges": edges}

    def check_verification(self, principal: Principal, solution_ids: list[str]) -> list[dict[str, Any]]:
        if not solution_ids:
            return []
        query = f"""
        MATCH (sol:Solution) WHERE sol.id IN $solution_ids AND {self._visible('sol')}
        OPTIONAL MATCH (newer:Solution)-[:SUPERSEDES]->(sol)
        WITH sol, newer WHERE newer IS NULL OR {self._visible('newer')}
        OPTIONAL MATCH (sol)-[:CONTRADICTS]-(c:Solution)
        WITH sol, newer, c WHERE c IS NULL OR {self._visible('c')}
        RETURN sol.id AS id, sol.status AS status, sol.valid_to AS valid_to,
               collect(DISTINCT newer.id) AS superseded_by,
               collect(DISTINCT c.id) AS contradicted_by
        """
        return self._run(query, {"solution_ids": solution_ids, "scope": list(principal.team_ids)})

    def find_experts(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        if not service_ids:
            return []
        query = f"""
        MATCH (e:Employee)-[x:EXPERT_IN]->(s:Service)
        MATCH (e)-[:MEMBER_OF]->(expert_team:Team)
        WHERE s.id IN $service_ids AND expert_team.id IN $scope
        RETURN e.id AS id, e.name AS name, e.role AS role,
               s.id AS service_id, s.name AS service_name, x.level AS level
        ORDER BY x.level DESC
        """
        return self._run(query, {"service_ids": service_ids, "scope": list(principal.team_ids)})

    def find_owners(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        if not service_ids:
            return []
        query = f"""
        MATCH (team:Team)-[:OWNS]->(s:Service)
        WHERE s.id IN $service_ids
        RETURN DISTINCT team.id AS id, team.name AS name, s.id AS service_id, s.name AS service_name
        ORDER BY s.name
        """
        return self._run(query, {"service_ids": service_ids, "scope": list(principal.team_ids)})

    def workspace_overview(self, principal: Principal) -> dict[str, Any]:
        scope = list(principal.team_ids)
        services = self._run(
            "MATCH (s:Service) "
            "OPTIONAL MATCH (t:Team)-[:OWNS]->(s) "
            "RETURN DISTINCT s.id AS id, s.name AS name, t.id AS team_id, t.name AS team_name "
            "ORDER BY s.name LIMIT 100", {"scope": scope})
        people = self._run(
            "MATCH (e:Employee)-[:MEMBER_OF]->(t:Team) WHERE t.id IN $scope "
            "RETURN DISTINCT e.id AS id, e.name AS name, e.role AS role, t.id AS team_id, t.name AS team_name "
            "ORDER BY e.name LIMIT 100", {"scope": scope}) if scope else []
        sources = self._run(
            f"MATCH (i:Incident)-[:AFFECTS]->(s:Service) WHERE {self._visible('i')} AND {self._visible('s')} "
            "OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution) "
            "OPTIONAL MATCH (sol)-[:SUPPORTED_BY]->(e:Evidence)-[:EXTRACTED_FROM]->(src:Source) "
            "WITH i, sol, e, src WHERE (sol IS NULL OR " + self._visible('sol') + ") "
            "AND (e IS NULL OR " + self._visible('e') + ") "
            "RETURN DISTINCT src.id AS id, src.type AS type, src.url AS url "
            "ORDER BY src.id LIMIT 100", {"scope": scope})
        return {"services": services, "people": people, "sources": [r for r in sources if r.get("id")]}

    def confirm_solution(
        self, principal: Principal, incident_id: str, solution_id: str
    ) -> dict[str, Any]:
        query = f"""
        MATCH (i:Incident {{id:$incident_id}})-[:RESOLVED_BY]->(sol:Solution {{id:$solution_id}})
        WHERE {self._visible('i')} AND {self._visible('sol')}
        SET sol.status = 'human_confirmed',
            sol.confidence = CASE WHEN sol.confidence + 0.1 > 1.0 THEN 1.0 ELSE sol.confidence + 0.1 END,
            sol.last_confirmed = $ts
        RETURN sol.id AS id, sol.status AS status, sol.confidence AS confidence
        """
        rows = self._run(
            query,
            {
                "incident_id": incident_id,
                "solution_id": solution_id,
                "scope": list(principal.team_ids),
                "ts": int(time.time()),
            },
        )
        if not rows:
            raise GraphUnavailable("Solution not found or access restricted")
        return rows[0]

    def _run(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            result = self.graph.query(query, params)
            # Recent FalkorDB Python clients expose each header as a
            # ``[column_name, column_type]`` pair; older versions returned
            # pairs whose order can vary, while older versions returned plain
            # column-name strings. Select the name and normalize both shapes.
            headers = [
                (
                    next((part for part in header if isinstance(part, str)), header[0])
                    if isinstance(header, (list, tuple)) and header
                    else header
                )
                for header in result.header
            ]
            return [dict(zip(headers, row)) for row in result.result_set]
        except Exception as exc:
            raise GraphUnavailable(f"Graph query failed: {exc}") from exc


class SyntheticGraphRepository(BaseGraphRepository):
    """In-memory synthetic graph implementation strictly enforcing the schema and security boundary.

    Used for deterministic local testing and zero-dependency local runs.
    """

    def __init__(self) -> None:
        self.now = int(time.time())
        # Teams
        self.teams = {
            "team-platform": {"id": "team-platform", "name": "Platform"},
            "team-security": {"id": "team-security", "name": "Security"},
            "team-payments": {"id": "team-payments", "name": "Payments"},
        }
        # Services
        self.services = {
            "svc-a": {
                "id": "svc-a",
                "name": "Service A",
                "aliases": ["service a", "svc-a", "payments-api"],
                "version": "2.4.1",
                "visibility": "public",
                "owner": "team-payments",
            },
            "svc-auth": {
                "id": "svc-auth",
                "name": "Auth Service",
                "aliases": ["auth service", "auth-svc", "authentication service", "auth"],
                "version": "5.1.0",
                "visibility": "public",
                "owner": "team-security",
            },
            "svc-gw": {
                "id": "svc-gw",
                "name": "API Gateway",
                "aliases": ["api gateway", "gateway", "gw"],
                "version": "3.0.2",
                "visibility": "public",
                "owner": "team-platform",
            },
        }
        # Employees & Expertise
        self.employees = {
            "emp-alice": {
                "id": "emp-alice",
                "name": "Alice Rao",
                "role": "SRE",
                "team": "team-platform",
                "experts": [("svc-a", "high"), ("svc-gw", "high")],
            },
            "emp-bob": {
                "id": "emp-bob",
                "name": "Bob Mehta",
                "role": "Backend Engineer",
                "team": "team-payments",
                "experts": [("svc-a", "high")],
            },
            "emp-carol": {
                "id": "emp-carol",
                "name": "Carol Iyer",
                "role": "Security Engineer",
                "team": "team-security",
                "experts": [("svc-auth", "high")],
            },
        }
        # Documents
        self.documents = {
            "doc-deploy-a": {
                "id": "doc-deploy-a",
                "title": "Service A deployment procedure",
                "body": "1. Freeze merges. 2. Run migrations. 3. Canary at 5 percent. 4. Verify auth token refresh. 5. Roll out.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "valid_from": 1740000000,
                "valid_to": None,
                "confidence": 0.95,
                "service_id": "svc-a",
            }
        }
        # Incidents
        # Notice: inc-104 is RESTRICTED to team-security!
        self.incidents = {
            "inc-101": {
                "id": "inc-101",
                "title": "Service A 502s after deploy v2.3.0",
                "summary": "Token validation timeouts against Auth Service after rollout.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "valid_from": 1738000000,
                "valid_to": None,
                "confidence": 0.8,
                "services": ["svc-a", "svc-auth"],
                "solution_id": "sol-1",
            },
            "inc-102": {
                "id": "inc-102",
                "title": "Service A login loop after deploy v2.4.0",
                "summary": "Expired signing keys cached by Service A; auth rejected refreshes.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "valid_from": 1739000000,
                "valid_to": None,
                "confidence": 0.85,
                "services": ["svc-a", "svc-auth"],
                "solution_id": "sol-2",
            },
            "inc-103": {
                "id": "inc-103",
                "title": "Service A 401 spike after deploy v2.4.1",
                "summary": "JWKS cache TTL longer than key rotation interval.",
                "visibility": "public",
                "visible_to": [],
                "status": "unverified",
                "valid_from": 1741000000,
                "valid_to": None,
                "confidence": 0.6,
                "services": ["svc-a", "svc-auth"],
                "solution_id": "sol-3",
            },
            "inc-104": {
                "id": "inc-104",
                "title": "Auth key rotation exposed signing key in logs",
                "summary": "Signing key material appeared in debug logs during rotation. Rotated and purged.",
                "visibility": "restricted",
                "visible_to": ["team-security"],
                "status": "human_confirmed",
                "valid_from": 1741000000,
                "valid_to": None,
                "confidence": 0.9,
                "services": ["svc-auth"],
                "solution_id": None,
            },
        }
        # Solutions
        self.solutions = {
            "sol-1": {
                "id": "sol-1",
                "title": "Restart Service A pods after deploy",
                "detail": "Restart clears cached keys. Temporary only.",
                "visibility": "public",
                "visible_to": [],
                "status": "deprecated",
                "valid_from": 1738000000,
                "valid_to": 1739500000,
                "confidence": 0.4,
                "superseded_by": ["sol-2"],
                "contradicted_by": [],
                "evidence_id": "ev-1",
            },
            "sol-2": {
                "id": "sol-2",
                "title": "Refresh JWKS cache on deploy hook",
                "detail": "Add a post-deploy hook that forces a JWKS refresh before traffic shifts.",
                "visibility": "public",
                "visible_to": ["team-platform"],
                "status": "human_confirmed",
                "valid_from": 1739500000,
                "valid_to": None,
                "confidence": 0.88,
                "superseded_by": ["sol-3"],
                "contradicted_by": [],
                "evidence_id": "ev-2",
            },
            "sol-3": {
                "id": "sol-3",
                "title": "Align JWKS cache TTL with key rotation interval",
                "detail": "Set Service A cache TTL below the rotation interval. Pending confirmation.",
                "visibility": "public",
                "visible_to": ["team-payments"],
                "status": "unverified",
                "valid_from": 1741000000,
                "valid_to": None,
                "confidence": 0.6,
                "superseded_by": [],
                "contradicted_by": [],
                "evidence_id": "ev-3",
            },
        }
        # Evidence
        self.evidence = {
            "ev-1": {
                "id": "ev-1",
                "summary": "Slack thread: pods restarted, 502s stopped for a day.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "source_id": "src-slack-1",
            },
            "ev-2": {
                "id": "ev-2",
                "summary": "OPS-101: post-deploy JWKS refresh stopped login loops across two releases.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "source_id": "src-jira-1",
            },
            "ev-3": {
                "id": "ev-3",
                "summary": "SEC-77: key rotation every 6h, Service A cache TTL is 24h.",
                "visibility": "public",
                "visible_to": [],
                "status": "human_confirmed",
                "source_id": "src-jira-2",
            },
        }
        # Sources
        self.sources = {
            "src-slack-1": {"id": "src-slack-1", "url": "https://example.slack.com/archives/C01/p1"},
            "src-jira-1": {"id": "src-jira-1", "url": "https://example.atlassian.net/browse/OPS-101"},
            "src-doc-1": {"id": "src-doc-1", "url": "https://example.com/docs/deploy-service-a"},
            "src-jira-2": {"id": "src-jira-2", "url": "https://example.atlassian.net/browse/SEC-77"},
        }

    def _is_visible(self, node: dict[str, Any], principal: Principal) -> bool:
        if node.get("visibility") == "public":
            return True
        node_teams = node.get("visible_to", [])
        return any(t in principal.team_ids for t in node_teams)

    def match_services(self, query_text: str) -> list[str]:
        q = query_text.lower().replace("?", " ").replace(",", " ")
        terms = [p for p in q.split() if p]
        matched: list[str] = []
        for sid, s in self.services.items():
            s_name = s["name"].lower()
            aliases = [a.lower() for a in s.get("aliases", [])]
            if s_name in q or any(a in q for a in aliases):
                matched.append(sid)
            elif any(t in s_name or any(t == a for a in aliases) for t in terms):
                matched.append(sid)
        return list(dict.fromkeys(matched))

    def find_documents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        now = int(time.time())
        for doc in self.documents.values():
            if doc.get("service_id") in service_ids and self._is_visible(doc, principal):
                if doc.get("status") != "deprecated":
                    valid_to = doc.get("valid_to")
                    if valid_to is None or valid_to > now:
                        results.append({
                            "id": doc["id"],
                            "title": doc["title"],
                            "summary": doc["body"],
                            "confidence": doc.get("confidence", 1.0),
                            "status": doc.get("status", "unverified"),
                            "node_type": "document",
                            "valid_to": valid_to,
                            "visibility": doc.get("visibility", "public"),
                        })
        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    def find_incidents(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for inc in self.incidents.values():
            if any(s in service_ids for s in inc.get("services", [])) and self._is_visible(inc, principal):
                sol_id = inc.get("solution_id")
                sol = self.solutions.get(sol_id) if sol_id else None
                if sol and not self._is_visible(sol, principal):
                    sol = None

                ev = None
                src_url = None
                if sol:
                    ev_id = sol.get("evidence_id")
                    ev = self.evidence.get(ev_id) if ev_id else None
                    if ev and not self._is_visible(ev, principal):
                        ev = None
                    if ev:
                        src_id = ev.get("source_id")
                        src = self.sources.get(src_id) if src_id else None
                        src_url = src.get("url") if src else None

                results.append({
                    "id": inc["id"],
                    "title": inc["title"],
                    "summary": inc["summary"],
                    "status": inc.get("status", "unverified"),
                    "confidence": inc.get("confidence", 0.5),
                    "solution_id": sol["id"] if sol else None,
                    "solution_title": sol["title"] if sol else None,
                    "solution_detail": sol["detail"] if sol else None,
                    "solution_status": sol["status"] if sol else None,
                    "solution_confidence": sol.get("confidence", 0.5) if sol else None,
                    "solution_valid_to": sol.get("valid_to") if sol else None,
                    "evidence_id": ev["id"] if ev else None,
                    "evidence": ev["summary"] if ev else None,
                    "source_url": src_url,
                    "visibility": inc.get("visibility", "public"),
                })
        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    def find_subgraph(
        self, principal: Principal, service_ids: list[str], incident_ids: list[str]
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        seen_nodes: set[str] = set()

        # Add visible services
        for sid in service_ids:
            svc = self.services.get(sid)
            if svc and self._is_visible(svc, principal) and sid not in seen_nodes:
                seen_nodes.add(sid)
                nodes.append({"id": sid, "label": svc["name"], "type": "service"})

        # Add visible incidents and linked solutions/evidence
        for inc_id in incident_ids:
            inc = self.incidents.get(inc_id)
            if not inc or not self._is_visible(inc, principal):
                continue
            if inc_id not in seen_nodes:
                seen_nodes.add(inc_id)
                nodes.append({
                    "id": inc_id,
                    "label": inc["title"],
                    "type": "incident",
                    "status": inc.get("status"),
                })
            for sid in inc.get("services", []):
                if sid in seen_nodes:
                    edges.append({"source": inc_id, "target": sid, "type": "AFFECTS"})

            sol_id = inc.get("solution_id")
            if sol_id:
                sol = self.solutions.get(sol_id)
                if sol and self._is_visible(sol, principal):
                    if sol_id not in seen_nodes:
                        seen_nodes.add(sol_id)
                        nodes.append({
                            "id": sol_id,
                            "label": sol["title"],
                            "type": "solution",
                            "status": sol.get("status"),
                        })
                    edges.append({"source": inc_id, "target": sol_id, "type": "RESOLVED_BY"})

                    ev_id = sol.get("evidence_id")
                    if ev_id:
                        ev = self.evidence.get(ev_id)
                        if ev and self._is_visible(ev, principal):
                            if ev_id not in seen_nodes:
                                seen_nodes.add(ev_id)
                                nodes.append({
                                    "id": ev_id,
                                    "label": ev["summary"][:45] + "...",
                                    "type": "evidence",
                                })
                            edges.append({"source": sol_id, "target": ev_id, "type": "SUPPORTED_BY"})

                            src_id = ev.get("source_id")
                            if src_id:
                                src = self.sources.get(src_id)
                                if src and src_id not in seen_nodes:
                                    seen_nodes.add(src_id)
                                    nodes.append({
                                        "id": src_id,
                                        "label": src["url"],
                                        "type": "source",
                                    })
                                    edges.append({"source": ev_id, "target": src_id, "type": "EXTRACTED_FROM"})

        return {"nodes": nodes, "edges": edges}

    def check_verification(self, principal: Principal, solution_ids: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for sid in solution_ids:
            sol = self.solutions.get(sid)
            if sol and self._is_visible(sol, principal):
                results.append({
                    "id": sol["id"],
                    "status": sol.get("status", "unverified"),
                    "valid_to": sol.get("valid_to"),
                    "superseded_by": [sid for sid in sol.get("superseded_by", []) if sid in self.solutions and self._is_visible(self.solutions[sid], principal)],
                    "contradicted_by": [sid for sid in sol.get("contradicted_by", []) if sid in self.solutions and self._is_visible(self.solutions[sid], principal)],
                })
        return results

    def find_experts(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        experts: list[dict[str, Any]] = []
        for emp in self.employees.values():
            for sid, level in emp.get("experts", []):
                if sid in service_ids:
                    svc = self.services.get(sid)
                    # Verify user can view this service! Never leak restricted services!
                    if svc and self._is_visible(svc, principal) and emp.get("team") in principal.team_ids:
                        experts.append({
                            "id": emp["id"],
                            "name": emp["name"],
                            "role": emp["role"],
                            "service_id": sid,
                            "service_name": svc["name"],
                            "level": level,
                        })
        return experts

    def find_owners(self, principal: Principal, service_ids: list[str]) -> list[dict[str, Any]]:
        owners: list[dict[str, Any]] = []
        for sid in service_ids:
            service = self.services.get(sid)
            team = self.teams.get(service.get("owner")) if service else None
            if service and team and self._is_visible(service, principal):
                owners.append({"id": team["id"], "name": team["name"], "service_id": sid, "service_name": service["name"]})
        return owners

    def workspace_overview(self, principal: Principal) -> dict[str, Any]:
        services = []
        for service in self.services.values():
            if self._is_visible(service, principal):
                team = self.teams.get(service.get("owner"), {})
                services.append({"id": service["id"], "name": service["name"], "team_id": team.get("id"), "team_name": team.get("name")})
        people = []
        if principal.team_ids:
            for employee in self.employees.values():
                if employee.get("team") in principal.team_ids:
                    team = self.teams.get(employee["team"], {})
                    people.append({"id": employee["id"], "name": employee["name"], "role": employee["role"], "team_id": employee["team"], "team_name": team.get("name")})
        visible_incidents = [inc for inc in self.incidents.values() if self._is_visible(inc, principal)]
        visible_solutions = [self.solutions[inc["solution_id"]] for inc in visible_incidents
                             if inc.get("solution_id") in self.solutions
                             and self._is_visible(self.solutions[inc["solution_id"]], principal)]
        source_ids = {self.evidence.get(sol.get("evidence_id"), {}).get("source_id")
                      for sol in visible_solutions if sol.get("evidence_id")}
        sources = [{"id": source_id, **self.sources[source_id]} for source_id in sorted(source_ids) if source_id in self.sources]
        return {"services": services, "people": people, "sources": sources}

    def confirm_solution(
        self, principal: Principal, incident_id: str, solution_id: str
    ) -> dict[str, Any]:
        inc = self.incidents.get(incident_id)
        if not inc or not self._is_visible(inc, principal):
            raise GraphUnavailable("Incident not found or restricted")
        sol = self.solutions.get(solution_id)
        if not sol or not self._is_visible(sol, principal):
            raise GraphUnavailable("Solution not found or restricted")

        sol["status"] = "human_confirmed"
        sol["confidence"] = min(1.0, round(sol.get("confidence", 0.5) + 0.1, 2))
        sol["last_confirmed"] = int(time.time())
        return {
            "id": sol["id"],
            "status": sol["status"],
            "confidence": sol["confidence"],
        }

    def close(self) -> None:
        pass
