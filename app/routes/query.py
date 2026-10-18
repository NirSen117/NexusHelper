from fastapi import APIRouter, Depends, HTTPException, Request

from app.security import Principal, get_principal
from app.services.graph import GraphUnavailable
from app.services.company_service import graph_for_company
from app.schemas import QueryRequest, QueryResponse
from app.services.query_service import answer_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    http_request: Request,
    principal: Principal = Depends(get_principal),
) -> QueryResponse:
    graph = None
    if principal.company_id:
        try:
            graph = graph_for_company(http_request, principal)
        except GraphUnavailable:
            # A graph improves company-specific answers, but should not block
            # general questions from a verified user.
            graph = None
    return await answer_query(request, principal, graph)
