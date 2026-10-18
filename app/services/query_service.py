from __future__ import annotations

import time
from typing import Any

from app.security import Principal
from app.schemas import Evidence, Expert, QueryRequest, QueryResponse, QueryTrace, SubGraph, GraphNode, GraphEdge
from app.services.graph import BaseGraphRepository, GraphUnavailable
from app.services.model_provider import MockModelProvider, ModelOutput, model_provider
from app.services.router import classify
from app.services.verifier import verify_claims


def _epoch(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def answer_query(request: QueryRequest, principal: Principal,
                       graph: BaseGraphRepository) -> QueryResponse:
    started = time.perf_counter()
    route = classify(request.query)
    evidence: list[Evidence] = []
    services: list[str] = []
    incidents: list[dict[str, Any]] = []
    lower_query = request.query.lower()
    owner_query = any(term in lower_query for term in ("who owns", "owner of", "owning team"))
    expert_query = any(term in lower_query for term in ("who knows", "expert", "who can help"))
    try:
        services = graph.match_services(request.query)
        documents = graph.find_documents(principal, services) if services and not (owner_query or expert_query) else []
        # Keep simple runbook lookup cheap; invoke history and model only for richer questions.
        incidents = graph.find_incidents(principal, services) if services and route.tier >= 2 and not (owner_query or expert_query) else []

        for row in documents:
            evidence.append(Evidence(
                node_id=str(row.get("id", "document:unknown")),
                label=str(row.get("title") or "Document"),
                summary=str(row.get("summary") or ""),
                node_type="document",
                status=str(row.get("status") or "unverified"),
                confidence=float(row.get("confidence") or 0.0),
                valid_to=_epoch(row.get("valid_to")),
                visibility=str(row.get("visibility") or "public"),
                source_url=row.get("source_url"),
            ))
        solution_ids: list[str] = []
        for row in incidents:
            iid = str(row.get("id") or "")
            if iid:
                evidence.append(Evidence(
                    node_id=iid,
                    label=str(row.get("title") or "Incident"),
                    summary=str(row.get("summary") or ""),
                    node_type="incident",
                    status=str(row.get("status") or "unverified"),
                    confidence=float(row.get("confidence") or 0.0),
                    visibility=str(row.get("visibility") or "public"),
                    source_url=row.get("source_url"),
                ))
            sid = row.get("solution_id")
            if sid:
                sid = str(sid)
                solution_ids.append(sid)
                evidence.append(Evidence(
                    node_id=sid,
                    label=str(row.get("solution_title") or "Resolution"),
                    summary=str(row.get("solution_detail") or ""),
                    node_type="solution",
                    status=str(row.get("solution_status") or "unverified"),
                    confidence=float(row.get("solution_confidence") or 0.0),
                    valid_to=_epoch(row.get("solution_valid_to")),
                    visibility=str(row.get("solution_visibility") or row.get("visibility") or "public"),
                    source_url=row.get("source_url"),
                ))

        fact_docs = [row for row in documents if row.get("status") in ("human_confirmed", "approved", "verified")]
        fact_incidents = [row for row in incidents if row.get("status") in ("human_confirmed", "approved", "verified")]
        owners_raw = graph.find_owners(principal, services) if owner_query and services else []
        experts_raw = graph.find_experts(principal, services) if (expert_query or (not evidence and not owner_query)) and services else []
        owners = [row for row in owners_raw if row.get("id")]
        experts = [row for row in experts_raw if row.get("id")]
        if owner_query:
            for row in owners:
                evidence.append(Evidence(node_id=str(row["id"]), label=str(row.get("name", "Team")), summary=f"Owning team for {row.get('service_name', 'service')}", node_type="team", confidence=0.9, status="directory_verified"))
        elif expert_query:
            for row in experts:
                evidence.append(Evidence(node_id=str(row["id"]), label=str(row.get("name", "Employee")), summary=str(row.get("role", "Verified team expertise")), node_type="employee", confidence=0.8, status="directory_verified"))
        facts = {"documents": fact_docs, "incidents": fact_incidents, "services": services}

        # Ownership and expertise use deterministic scoped directory data. Model APIs handle synthesis tiers only.
        if owner_query and owners:
            clauses = [f"{row.get('service_name', 'Service')} is owned by {row.get('name', 'a team')} [{row['id']}]" for row in owners]
            output = ModelOutput(answer="\n".join(clauses), cited_node_ids=[str(row["id"]) for row in owners], model_calls=0, confidence=0.9)
        elif expert_query and experts:
            clauses = [f"{row.get('name', 'A colleague')} ({row.get('role', 'team member')}) is listed as a verified expert for {row.get('service_name', 'this service')} [{row['id']}]" for row in experts]
            output = ModelOutput(answer="\n".join(clauses), cited_node_ids=[str(row["id"]) for row in experts], model_calls=0, confidence=0.8)
        else:
            # Deterministic lookup for straightforward questions; model APIs only for synthesis tiers.
            provider = model_provider if route.tier >= 2 else MockModelProvider()
            output = await provider.synthesize(request.query, route.name, facts, principal.user_id)
        checks = graph.check_verification(principal, list(dict.fromkeys(solution_ids))) if solution_ids else []
        verification = verify_claims(output.answer, output.cited_node_ids, evidence, checks)
        answer = output.answer
        abstained = output.abstained or verification.should_abstain
        if verification.should_abstain and output.answer:
            answer = "I found related records, but I can't provide a reliable answer from the available verified evidence."
        if verification.stale_citations:
            answer += "\n\nSome cited records may be out of date; verify them before acting."

        graph_data = graph.find_subgraph(principal, services, [str(r["id"]) for r in incidents if r.get("id")]) if services else {"nodes": [], "edges": []}
        experts = [Expert(
            id=str(row.get("id", "")), name=str(row.get("name", "")), role=str(row.get("role", "")),
            service_id=str(row.get("service_id", "")), service_name=str(row.get("service_name", "")), level=str(row.get("level", "")),
        ) for row in experts_raw if row.get("id")]
        return QueryResponse(
            answer=answer,
            confidence=0.0 if abstained else verification.confidence,
            evidence=evidence,
            subgraph=SubGraph(
                nodes=[GraphNode(**node) for node in graph_data.get("nodes", [])],
                edges=[GraphEdge(**edge) for edge in graph_data.get("edges", [])],
            ),
            experts=experts,
            trace=QueryTrace(
                tier=route.tier,
                tier_name=route.name,
                agents_run=list(route.agents),
                model_calls=output.model_calls,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
                cache_hit=False,
                reasons=["Deterministic routing", "Permission-scoped evidence retrieval", "Citation verification"],
                entities_detected=services,
            ),
            abstained=abstained,
            abstention_reason=verification.abstention_reason or output.abstention_reason,
            unverified_claims=verification.unverified_claims,
            is_synthetic=graph.__class__.__name__ == "SyntheticGraphRepository",
        )
    except GraphUnavailable:
        return QueryResponse(
            answer="The knowledge graph is unavailable, so NexusHelper can't safely answer right now.",
            confidence=0.0,
            evidence=[],
            trace=QueryTrace(
                tier=route.tier, tier_name=route.name, agents_run=list(route.agents),
                model_calls=0, latency_ms=round((time.perf_counter() - started) * 1000, 1),
                cache_hit=False, reasons=["Knowledge graph unavailable"], entities_detected=services,
            ),
            abstained=True,
            abstention_reason="Knowledge graph unavailable",
        )
