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
    email: str | None = None
    display_name: str | None = None
    is_admin: bool = False
    auth_type: str = "demo"

    @property
    def scope_hash(self) -> str:
        """Deterministic permission scope hash used to key the semantic cache and audit events."""
        key = "|".join(sorted(self.team_ids))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _firebase_auth_app() -> Any:
    try:
        return get_app()
    except ValueError:
        options: dict[str, Any] = {}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id
        return initialize_app(credentials.ApplicationDefault(), options=options)


def _principal_from_firebase_token(token: str) -> Principal:
    try:
        claims = auth.verify_id_token(token, app=_firebase_auth_app())
    except (FirebaseError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase identity token") from exc

    user_id = claims.get("uid")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Firebase token has no valid user ID")

    email = claims.get("email")
    display_name = claims.get("name")
    is_admin = bool(claims.get("admin") or claims.get("is_admin"))

    # Critical security rule: team_ids come ONLY from trusted custom claims assigned by an admin.
    raw_teams = claims.get("team_ids", ())
    if not isinstance(raw_teams, (list, tuple)) or not all(
        isinstance(team_id, str) and team_id.strip() for team_id in raw_teams
    ):
        raise HTTPException(status_code=401, detail="Firebase token has invalid team claims")

    # Shared administrator-managed membership is the primary source when enabled.
    # Verified custom claims remain a safe fallback for environments not using Firestore.
    if settings.profile_store.lower() == "firestore":
        from app.services.membership_service import membership_store
        membership_teams = membership_store.get_teams(user_id)
        if membership_teams is not None:
            raw_teams = membership_teams
            is_admin = membership_store.is_admin(user_id)

    return Principal(
        user_id=user_id,
        team_ids=tuple(sorted(set(team_id.strip() for team_id in raw_teams))),
        email=email if isinstance(email, str) else None,
        display_name=display_name if isinstance(display_name, str) else None,
        is_admin=is_admin,
        auth_type="firebase",
    )


async def get_principal(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> Principal:
    """Resolve a principal from verified Firebase claims or server-controlled demo configuration.

    Security constraints:
      - Permission scopes are NEVER accepted from client request bodies or query parameters.
      - Profile designation, department, and keywords NEVER grant access to records.
      - In production, demo auth is completely disabled; only verified Bearer tokens are accepted.
      - Missing or invalid identity immediately fails closed (HTTP 401).
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="Invalid authorization header: Use a Bearer token")
        return _principal_from_firebase_token(token.strip())

    # Production environment check: never allow demo auth in production
    if settings.app_env.lower() == "production":
        raise HTTPException(
            status_code=401,
            detail="Production environment requires a verified Firebase Bearer token",
        )

    # When Firebase auth is explicitly enforced
    if settings.firebase_auth_enabled:
        raise HTTPException(
            status_code=401,
            detail="Firebase authentication is enabled; provide an Authorization Bearer token",
        )

    # Local development demo authentication
    if not settings.demo_auth_enabled:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required and demo auth is disabled",
        )

    demo_user = x_demo_user.strip() if x_demo_user else None
    if not demo_user:
        raise HTTPException(
            status_code=401,
            detail="Provide X-Demo-User header for local development authentication (e.g., 'emp-alice', 'emp-bob', 'emp-carol', 'emp-admin')",
        )

    # Check for admin-managed membership overrides if local membership service exists
    from app.services.membership_service import membership_store

    teams = membership_store.get_teams(demo_user)
    is_admin = membership_store.is_admin(demo_user)

    if teams is None:
        # Fall back to server-configured demo principals in settings
        configured_teams = settings.demo_principals.get(demo_user)
        if configured_teams is None:
            raise HTTPException(
                status_code=401,
                detail=f"Unknown local demo user '{demo_user}'. Configured demo users: {list(settings.demo_principals.keys())}",
            )
        teams = list(configured_teams)
        is_admin = demo_user in settings.demo_admin_users

    return Principal(
        user_id=demo_user,
        team_ids=tuple(sorted(set(teams))),
        email=f"{demo_user}@example.com",
        display_name=demo_user.replace("emp-", "").capitalize() if demo_user.startswith("emp-") else demo_user,
        is_admin=is_admin,
        auth_type="demo",
    )


async def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """FastAPI dependency to ensure the principal has administrator permissions."""
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Administrator permissions required")
    return principal
