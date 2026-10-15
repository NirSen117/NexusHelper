from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    # Demo-only field. Production scope must come from authenticated identity.
    demo_permission_scope: str = Field(default="demo:public", min_length=1)


class Evidence(BaseModel):
    node_id: str
    label: str
    summary: str
    source_url: str | None = None
    status: str


class QueryTrace(BaseModel):
    tier: int
    tier_name: str
    agents_invoked: list[str]
    model_calls: int
    latency_ms: int
    cache_hit: bool


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    evidence: list[Evidence]
    trace: QueryTrace
    abstained: bool = False
