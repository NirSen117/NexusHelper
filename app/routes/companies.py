from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (CompanyCreateRequest, CompanyMemberUpdateRequest,
                         InvitationAcceptRequest, InvitationCreateRequest)
from app.security import Principal, get_principal, require_company_owner
from app.services.company_service import get_company_store

router = APIRouter(prefix="/companies", tags=["companies"])


def _firebase(principal: Principal) -> None:
    if principal.auth_type != "firebase":
        raise HTTPException(status_code=401, detail="Sign in with a verified company account")


@router.get("")
async def list_companies(principal: Principal = Depends(get_principal)) -> list[dict]:
    if principal.auth_type == "demo":
        return [{"id": "demo", "name": "NexusHelper Demo", "role": principal.role,
                 "team_ids": list(principal.team_ids)}]
    try:
        return get_company_store().memberships(principal.user_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Company directory is unavailable") from exc


@router.post("")
async def create_company(body: CompanyCreateRequest, principal: Principal = Depends(get_principal)) -> dict:
    _firebase(principal)
    if not principal.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email address before creating a company")
    try:
        return get_company_store().create_company(principal.user_id, body.name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Company could not be created") from exc


@router.post("/invitations/accept")
async def accept_invitation(body: InvitationAcceptRequest, principal: Principal = Depends(get_principal)) -> dict:
    _firebase(principal)
    if not principal.email_verified or not principal.email:
        raise HTTPException(status_code=403, detail="Verify your email address before joining a company")
    try:
        return get_company_store().accept_invitation(principal.user_id, principal.email, body.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Invitation could not be accepted") from exc


@router.post("/{company_id}/invitations")
async def create_invitation(company_id: str, body: InvitationCreateRequest,
                            principal: Principal = Depends(require_company_owner)) -> dict:
    if principal.company_id != company_id:
        raise HTTPException(status_code=403, detail="Select this company before managing its invitations")
    try:
        return get_company_store().create_invitation(principal.user_id, company_id, body.email,
                                                       body.team_ids, body.expires_in_days)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Invitation could not be created") from exc


@router.get("/{company_id}/members")
async def list_members(company_id: str, principal: Principal = Depends(require_company_owner)) -> list[dict]:
    if principal.company_id != company_id:
        raise HTTPException(status_code=403, detail="Select this company before viewing its members")
    try:
        return get_company_store().list_members(principal.user_id, company_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Company members are unavailable") from exc


@router.put("/{company_id}/members/{user_id}")
async def update_member(company_id: str, user_id: str, body: CompanyMemberUpdateRequest,
                        principal: Principal = Depends(require_company_owner)) -> dict:
    if principal.company_id != company_id:
        raise HTTPException(status_code=403, detail="Select this company before updating its members")
    if user_id == principal.user_id and body.role != "owner":
        raise HTTPException(status_code=400, detail="A company owner cannot remove their own ownership")
    try:
        return get_company_store().update_member(principal.user_id, company_id, user_id,
                                                  body.team_ids, body.role, body.expires_in_days)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Company membership could not be updated") from exc
