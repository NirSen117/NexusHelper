from fastapi import APIRouter, Depends, HTTPException, Path

from app.schemas import MembershipResponse, MembershipUpdateRequest
from app.security import Principal, require_admin
from app.services.membership_service import membership_store

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/memberships", response_model=list[MembershipResponse])
async def list_memberships(_: Principal = Depends(require_admin)) -> list[dict]:
    try:
        return membership_store.list_memberships()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Membership storage is unavailable") from exc


@router.put("/users/{user_id}/membership", response_model=MembershipResponse)
async def update_membership(
    payload: MembershipUpdateRequest,
    user_id: str = Path(min_length=1, max_length=128),
    _: Principal = Depends(require_admin),
) -> dict:
    try:
        return membership_store.set_membership(user_id, payload.team_ids, payload.is_admin)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Membership storage is unavailable") from exc
