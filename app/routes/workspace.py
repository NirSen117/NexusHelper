from fastapi import APIRouter, Depends, HTTPException, Request

from app.security import Principal, require_company
from app.services.graph import GraphUnavailable
from app.services.company_service import graph_for_company

router = APIRouter(tags=["workspace"])


@router.get("/workspace")
async def workspace_overview(request: Request, principal: Principal = Depends(require_company)) -> dict:
    """Return graph-backed workspace data scoped to the verified user's team memberships."""
    try:
        data = graph_for_company(request, principal).workspace_overview(principal)
    except GraphUnavailable as exc:
        raise HTTPException(status_code=503, detail="The company knowledge graph is unavailable") from exc
    return {
        **data,
        "identity": {"user_id": principal.user_id, "email": principal.email,
                     "display_name": principal.display_name, "team_ids": list(principal.team_ids),
                     "company_id": principal.company_id, "role": principal.role},
        "connected": True,
    }
