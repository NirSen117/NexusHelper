from fastapi import APIRouter, Depends, HTTPException, Request

from app.security import Principal, get_principal
from app.services.graph import GraphUnavailable
from app.services.company_service import graph_for_company

router = APIRouter(tags=["workspace"])


@router.get("/workspace")
async def workspace_overview(request: Request, principal: Principal = Depends(get_principal)) -> dict:
    """Return graph-backed workspace data scoped to the verified user's team memberships."""
    identity = {"user_id": principal.user_id, "email": principal.email,
                "display_name": principal.display_name, "team_ids": list(principal.team_ids),
                "company_id": principal.company_id, "role": principal.role}
    if not principal.company_id:
        return {"services": [], "sources": [], "people": [], "identity": identity,
                "connected": False, "graph_configured": False}
    try:
        data = graph_for_company(request, principal).workspace_overview(principal)
    except (GraphUnavailable, Exception):
        return {"services": [], "sources": [], "people": [], "identity": identity,
                "connected": False, "graph_configured": False}
    return {
        **data,
        "identity": identity,
        "connected": True,
        "graph_configured": True,
    }
