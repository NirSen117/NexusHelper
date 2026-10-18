from fastapi import APIRouter, Depends, HTTPException, Request

from app.security import Principal, require_company
from app.services.company_service import graph_for_company
from app.schemas import QueryRequest, QueryResponse
from app.services.query_service import answer_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    http_request: Request,
    principal: Principal = Depends(require_company),
) -> QueryResponse:
    try:
        graph = graph_for_company(http_request, principal)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The company knowledge graph is unavailable") from exc
    if graph is None:
        raise HTTPException(status_code=503, detail="Knowledge graph is not configured")
    return await answer_query(request, principal, graph)
