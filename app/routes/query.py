from fastapi import APIRouter

from app.schemas import QueryRequest, QueryResponse
from app.services.query_service import answer_query

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    return await answer_query(request)
