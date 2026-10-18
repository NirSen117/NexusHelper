from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.settings import settings


ALLOWED_DEPARTMENTS = (
    "Engineering",
    "Platform",
    "Security",
    "Payments",
    "Product",
    "Operations",
    "Human Resources",
    "Finance",
    "Customer Support",
    "Other",
)


def normalize_department(dept: str) -> str:
    cleaned = dept.strip()
    for allowed in ALLOWED_DEPARTMENTS:
        if cleaned.lower() == allowed.lower():
            return allowed
    return cleaned[:100]


def normalize_keywords(keywords: list[str]) -> list[str]:
    cleaned_set: set[str] = set()
    for item in keywords:
        # Split on commas in case user passed comma-separated strings inside list
        parts = item.split(",")
        for part in parts:
            norm = re.sub(r"[^\w\s-]", "", part.strip().lower())
            norm = re.sub(r"\s+", " ", norm).strip()
            if norm and len(norm) <= 40:
                cleaned_set.add(norm)
    return sorted(list(cleaned_set))[:20]


@dataclass
class Profile:
    user_id: str
    designation: str
    department: str
    keywords: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        return cls(
            user_id=str(data["user_id"]),
            designation=str(data.get("designation", "")),
            department=normalize_department(str(data.get("department", "Engineering"))),
            keywords=normalize_keywords(list(data.get("keywords", []))),
            updated_at=float(data.get("updated_at", time.time())),
        )


class ProfileRepository(ABC):
    """Abstract storage boundary for user profiles."""

    @abstractmethod
    def get(self, user_id: str) -> Profile | None:
        pass

    @abstractmethod
    def save(self, profile: Profile) -> Profile:
        pass


class LocalProfileRepository(ProfileRepository):
    """File-backed profile repository for local development with zero external dependencies."""

    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or os.path.join(settings.data_dir, "profiles.json")
        self._profiles: dict[str, Profile] = {}
        self._load()

    def _load(self) -> None:
        # Seed default profiles for demo principals
        default_profiles: dict[str, Profile] = {
            "emp-alice": Profile(
                user_id="emp-alice",
                designation="Site Reliability Engineer",
                department="Platform",
                keywords=["kubernetes", "canary", "deployments", "monitoring"],
            ),
            "emp-bob": Profile(
                user_id="emp-bob",
                designation="Backend Engineer",
                department="Payments",
                keywords=["payments-api", "service a", "tokens", "transactions"],
            ),
            "emp-carol": Profile(
                user_id="emp-carol",
                designation="Security Engineer",
                department="Security",
                keywords=["authentication", "jwks", "keys", "rotation", "auditing"],
            ),
        }

        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for uid, entry in data.items():
                            if isinstance(entry, dict) and "user_id" in entry:
                                default_profiles[uid] = Profile.from_dict(entry)
            except Exception:
                pass

        self._profiles = default_profiles

    def _persist(self) -> None:
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        serializable = {uid: p.to_dict() for uid, p in self._profiles.items()}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    def get(self, user_id: str) -> Profile | None:
        return self._profiles.get(user_id)

    def save(self, profile: Profile) -> Profile:
        self._profiles[profile.user_id] = profile
        self._persist()
        return profile


class CloudProfileRepository(ProfileRepository):
    """Production storage boundary for Google Cloud Firestore.

    To activate in production:
      1. Ensure Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS are set.
      2. Set APP_ENV=production.
    """

    def __init__(self, collection_name: str | None = None):
        from google.cloud import firestore  # type: ignore
        project = settings.firestore_project_id or settings.firebase_project_id
        self.db = firestore.Client(project=project) if project else firestore.Client()
        self.collection = self.db.collection(collection_name or settings.firestore_profiles_collection)

    def get(self, user_id: str) -> Profile | None:
        doc = self.collection.document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data:
                return Profile.from_dict(data)
        return None

    def save(self, profile: Profile) -> Profile:
        self.collection.document(profile.user_id).set(profile.to_dict())
        return profile


def get_profile_repository() -> ProfileRepository:
    """Factory selecting the storage implementation based on configuration."""
    if settings.profile_store.lower() == "firestore":
        return CloudProfileRepository()
    if settings.app_env.lower() == "production":
        raise RuntimeError("Production requires PROFILE_STORE=firestore")
    return LocalProfileRepository()


profile_repo = get_profile_repository()
