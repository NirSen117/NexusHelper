from app.schemas import Evidence, QueryRequest, QueryResponse, QueryTrace
from app.services.router import classify


async def answer_query(request: QueryRequest) -> QueryResponse:
    """Safe demo stub. Replace fixture with scoped FalkorDB retrieval before model use."""
    route = classify(request.query)
    # No external records are returned by the scaffold. This makes the absence of
    # integrations explicit and prevents demo data from implying real evidence.
    return QueryResponse(
        answer=(
            "The Company Brain starter is running, but no knowledge graph is connected yet. "
            "Configure FalkorDB and add permission-scoped retrieval to answer this query."
        ),
        confidence=0.0,
        evidence=[Evidence(
            node_id="starter:no-graph",
            label="Starter status",
            summary="No graph retrieval or company evidence has been configured.",
            status="unverified",
        )],
        trace=QueryTrace(
            tier=route.tier,
            tier_name=route.name,
            agents_invoked=list(route.agents),
            model_calls=0,
            latency_ms=0,
            cache_hit=False,
        ),
        abstained=True,
    )
