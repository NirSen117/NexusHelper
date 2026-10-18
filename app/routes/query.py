from fastapi import APIRouter, Depends, HTTPException, Request

from app.security import Principal, get_principal
from app.schemas import QueryRequest, QueryResponse
from app.services.query_service import answer_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    http_request: Request,
    principal: Principal = Depends(get_principal),
) -> QueryResponse:
    graph = getattr(http_request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Knowledge graph is not configured")
    return await answer_query(request, principal, graph)
