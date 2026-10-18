from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)


class Evidence(BaseModel):
    node_id: str
    label: str
    summary: str
    node_type: str = "document"
    source_url: str | None = None
    status: str = "unverified"
    confidence: float = 1.0
    valid_to: int | None = None
    superseded_by: list[str] = Field(default_factory=list)
    contradicted_by: list[str] = Field(default_factory=list)
    visibility: str = "public"


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    status: str | None = None
    confidence: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class SubGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class Expert(BaseModel):
    id: str
    name: str
    role: str
    service_id: str
    service_name: str
    level: str


class QueryTrace(BaseModel):
    tier: int
    tier_name: str
    agents_run: list[str]
    model_calls: int
    latency_ms: float
    cache_hit: bool
    escalations: int = 0
    reasons: list[str] = Field(default_factory=list)
    entities_detected: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    evidence: list[Evidence] = Field(default_factory=list)
    subgraph: SubGraph = Field(default_factory=SubGraph)
    experts: list[Expert] = Field(default_factory=list)
    trace: QueryTrace
    abstained: bool = False
    abstention_reason: str | None = None
    unverified_claims: list[str] = Field(default_factory=list)
    is_synthetic: bool = True


class ProfileUpdate(BaseModel):
    designation: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=20)


class ProfileResponse(BaseModel):
    user_id: str
    designation: str
    department: str
    keywords: list[str]
    team_ids: list[str]
    company_id: str | None = None
    role: str = "member"
    profile_setup_required: bool
    saved: bool = True
    message: str


class FeedbackRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    solution_id: str = Field(min_length=1)
    confirmed: bool = True
    comment: str | None = None


class FeedbackResponse(BaseModel):
    success: bool
    solution_id: str
    status: str
    confidence: float
    message: str


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    team_ids: list[str] = Field(default_factory=list, max_length=30)
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class InvitationAcceptRequest(BaseModel):
    code: str = Field(min_length=20, max_length=128)


class CompanyMemberUpdateRequest(BaseModel):
    team_ids: list[str] = Field(default_factory=list)
    role: str = "member"
    expires_in_days: int | None = Field(default=None, ge=1, le=90)


class SetupStatusResponse(BaseModel):
    app_name: str = "NexusHelper"
    version: str = "0.1.0"
    app_env: str
    firebase_configured: bool
    firebase_project_id: str | None
    demo_auth_active: bool
    demo_users: list[dict[str, Any]]
    falkordb_connected: bool
    model_provider: str
    is_synthetic_mode: bool = True


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "NexusHelper"
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    ready: bool
    app: str = "NexusHelper"
    checks: dict[str, bool]
    details: dict[str, str]
