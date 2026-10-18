from fastapi import APIRouter, Depends, HTTPException

from app.security import Principal, get_principal
from app.schemas import ProfileUpdate
from app.services.profile_service import Profile, get_profile_repository, normalize_keywords

router = APIRouter(tags=["profile"])
profile_repo = get_profile_repository()


def _stored_profile(principal: Principal) -> Profile | None:
    try:
        return profile_repo.get(principal.user_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Profile storage is unavailable") from exc


@router.get("/me")
async def my_profile(principal: Principal = Depends(get_principal)) -> dict:
    profile = _stored_profile(principal)
    return {
        "user_id": principal.user_id,
        "designation": profile.designation if profile else "",
        "department": profile.department if profile else "",
        "keywords": profile.keywords if profile else [],
        "team_ids": list(principal.team_ids),
        "is_admin": principal.is_admin,
        "profile_setup_required": profile is None,
        "saved": profile is not None,
        "message": "Profile loaded." if profile else "Complete your profile to help coworkers find your expertise.",
    }


@router.put("/me/profile")
async def update_profile(body: ProfileUpdate, principal: Principal = Depends(get_principal)) -> dict:
    # Validate through the shared API schema, and keep profile text separate from ACL claims.
    profile = Profile(
        user_id=principal.user_id,
        designation=body.designation.strip(),
        department=body.department.strip(),
        keywords=normalize_keywords(body.keywords),
    )
    try:
        saved = profile_repo.save(profile)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Profile storage is unavailable") from exc
    return {
        **saved.to_dict(),
        "team_ids": list(principal.team_ids),
        "is_admin": principal.is_admin,
        "profile_setup_required": False,
        "saved": True,
        "message": "Profile saved. Your self-entered designation and keywords do not grant data access.",
    }
