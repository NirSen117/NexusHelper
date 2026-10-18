from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.settings import settings


class MembershipStore:
    """Admin-managed team membership store.

    CRITICAL SECURITY REQUIREMENT:
      Self-entered user profiles (designation, department, keywords) NEVER grant
      access to company records. Authorization MUST come strictly from verified
      identity custom claims or trusted administrator-managed memberships.
    """

    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or os.path.join(settings.data_dir, "memberships.json")
        self._memberships: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        # Prepopulate with server-configured demo principals
        default_memberships: dict[str, dict[str, Any]] = {}
        for uid, teams in settings.demo_principals.items():
            default_memberships[uid] = {
                "user_id": uid,
                "team_ids": list(teams),
                "is_admin": uid in settings.demo_admin_users,
            }

        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for uid, entry in data.items():
                            if isinstance(entry, dict) and "team_ids" in entry:
                                default_memberships[uid] = {
                                    "user_id": uid,
                                    "team_ids": list(entry.get("team_ids", [])),
                                    "is_admin": bool(entry.get("is_admin", False)),
                                }
            except Exception:
                pass

        self._memberships = default_memberships

    def _persist(self) -> None:
        try:
            Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._memberships, f, indent=2)
        except Exception:
            pass

    def get_teams(self, user_id: str) -> list[str] | None:
        entry = self._memberships.get(user_id)
        if entry:
            return list(entry.get("team_ids", []))
        return None

    def is_admin(self, user_id: str) -> bool:
        entry = self._memberships.get(user_id)
        if entry:
            return bool(entry.get("is_admin", False))
        return user_id in settings.demo_admin_users

    def list_memberships(self) -> list[dict[str, Any]]:
        return list(self._memberships.values())

    def set_membership(
        self, user_id: str, team_ids: list[str], is_admin: bool | None = None
    ) -> dict[str, Any]:
        normalized_teams = sorted({t.strip().lower() for t in team_ids if t.strip()})
        current = self._memberships.get(user_id, {
            "user_id": user_id,
            "team_ids": [],
            "is_admin": False,
        })
        current["team_ids"] = normalized_teams
        if is_admin is not None:
            current["is_admin"] = is_admin
        self._memberships[user_id] = current
        self._persist()
        return current


class FirestoreMembershipStore:
    """Shared administrator-managed memberships; client profile fields never grant scope."""
    def __init__(self, collection_name: str | None = None):
        from google.cloud import firestore  # type: ignore
        project = settings.firestore_project_id or settings.firebase_project_id
        self.db = firestore.Client(project=project) if project else firestore.Client()
        self.collection = self.db.collection(collection_name or settings.firestore_memberships_collection)

    def _get(self, user_id: str) -> dict[str, Any] | None:
        snapshot = self.collection.document(user_id).get()
        if not snapshot.exists:
            return None
        value = snapshot.to_dict() or {}
        return {"user_id": user_id, "team_ids": list(value.get("team_ids", [])), "is_admin": bool(value.get("is_admin", False))}

    def get_teams(self, user_id: str) -> list[str] | None:
        entry = self._get(user_id)
        return sorted({str(team).strip() for team in entry["team_ids"] if str(team).strip()}) if entry else None

    def is_admin(self, user_id: str) -> bool:
        entry = self._get(user_id)
        return bool(entry and entry["is_admin"])

    def list_memberships(self) -> list[dict[str, Any]]:
        return [self._get(doc.id) for doc in self.collection.stream() if doc.exists]

    def set_membership(self, user_id: str, team_ids: list[str], is_admin: bool | None = None) -> dict[str, Any]:
        current = self._get(user_id) or {"user_id": user_id, "team_ids": [], "is_admin": False}
        current["team_ids"] = sorted({team.strip().lower() for team in team_ids if team.strip()})
        if is_admin is not None:
            current["is_admin"] = is_admin
        self.collection.document(user_id).set(current)
        return current


def get_membership_store() -> MembershipStore | FirestoreMembershipStore:
    if settings.profile_store.lower() == "firestore":
        return FirestoreMembershipStore()
    if settings.app_env.lower() == "production":
        raise RuntimeError("Production requires PROFILE_STORE=firestore for shared memberships")
    return MembershipStore()


membership_store = get_membership_store()
