from dataclasses import dataclass
import hashlib
from typing import Any

from fastapi import Depends, Header, HTTPException
from firebase_admin import auth, credentials, get_app, initialize_app
from firebase_admin.exceptions import FirebaseError

from app.settings import settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    team_ids: tuple[str, ...]
    company_id: str | None = None
    graph_name: str | None = None
    role: str = "member"
    email: str | None = None
    display_name: str | None = None
    auth_type: str = "firebase"
    email_verified: bool = False

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def scope_hash(self) -> str:
        key = f"{self.company_id or ''}|" + "|".join(sorted(self.team_ids))
        return hashlib.sha1(key.encode()).hexdigest()[:16]


def _firebase_auth_app() -> Any:
    try:
        return get_app()
    except ValueError:
        options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else {}
        return initialize_app(credentials.ApplicationDefault(), options=options)


def _firebase_principal(token: str, company_header: str | None) -> Principal:
    try:
        claims = auth.verify_id_token(token, app=_firebase_auth_app())
    except (FirebaseError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase identity token") from exc
    user_id = claims.get("uid")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Firebase token has no valid user ID")
    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    display_name = claims.get("name") if isinstance(claims.get("name"), str) else None

    if settings.profile_store.lower() != "firestore":
        return Principal(user_id=user_id, team_ids=(), email=email, display_name=display_name,
                         email_verified=bool(claims.get("email_verified")))

    from app.services.company_service import get_company_store
    memberships = get_company_store().memberships(user_id)
    chosen = next((m for m in memberships if m["id"] == company_header), None) if company_header else None
    if company_header and chosen is None:
        raise HTTPException(status_code=403, detail="You do not belong to the selected company")
    if not company_header and len(memberships) == 1:
        chosen = memberships[0]
    if chosen is None:
        return Principal(user_id=user_id, team_ids=(), email=email, display_name=display_name,
                         email_verified=bool(claims.get("email_verified")))
    return Principal(
        user_id=user_id, team_ids=tuple(chosen.get("team_ids", [])),
        company_id=chosen.get("id"), graph_name=chosen.get("graph_name"),
        role=chosen.get("role", "member"), email=email, display_name=display_name,
        email_verified=bool(claims.get("email_verified")),
    )


async def get_principal(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    x_company_id: str | None = Header(default=None),
) -> Principal:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="Use an Authorization Bearer token")
        return _firebase_principal(token.strip(), x_company_id)
    if settings.app_env.lower() == "production" or not settings.demo_auth_enabled or settings.firebase_auth_enabled:
        raise HTTPException(status_code=401, detail="Sign in with your verified company account")
    if not x_demo_user or x_demo_user not in settings.demo_principals:
        raise HTTPException(status_code=401, detail="Choose a valid local demo identity")
    return Principal(
        user_id=x_demo_user,
        team_ids=tuple(settings.demo_principals[x_demo_user]),
        company_id="demo", graph_name=settings.falkordb_graph,
        role="owner" if x_demo_user == "emp-alice" else "member",
        email=f"{x_demo_user}@example.com", display_name=x_demo_user,
        auth_type="demo",
        email_verified=True,
    )


async def require_company(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.company_id or not principal.graph_name:
        raise HTTPException(status_code=403, detail="Create a company or join one with an invitation")
    return principal


async def require_company_owner(principal: Principal = Depends(require_company)) -> Principal:
    if not principal.is_owner:
        raise HTTPException(status_code=403, detail="Only a company owner can manage this company")
    return principal
