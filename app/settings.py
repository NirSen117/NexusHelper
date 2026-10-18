from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NexusHelper"
    app_version: str = "0.1.0"
    app_env: str = "development"

    # FalkorDB connection settings
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    falkordb_graph: str = "nexushelper"
    falkordb_use_tls: bool = False

    # Authentication settings
    demo_auth_enabled: bool = True
    demo_principals: dict[str, list[str]] = {
        "emp-alice": ["team-platform"],
        "emp-bob": ["team-payments"],
        "emp-carol": ["team-security"],
        "emp-admin": ["team-platform", "team-payments", "team-security"],
    }
    demo_admin_users: list[str] = ["emp-admin"]

    firebase_auth_enabled: bool = False
    firebase_project_id: str | None = None
    firebase_api_key: str | None = None
    firebase_auth_domain: str | None = None

    # CORS and routing
    frontend_origin: str = "http://localhost:5173"
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Provider keys are server-only. Never expose them via Vite/public env.
    model_provider: str = "mock"
    model_api_key: str | None = None  # backwards-compatible alias for GEMINI_API_KEY
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    model_timeout_seconds: float = 25.0
    model_name: str = "mock-nexus-deterministic"

    # Shared profile and trusted membership data
    profile_store: str = "local"  # local | firestore
    firestore_project_id: str | None = None
    firestore_profiles_collection: str = "nexushelper_profiles"
    firestore_memberships_collection: str = "nexushelper_memberships"

    # Storage paths for local dev abstractions
    data_dir: str = ".local_data"

    @field_validator("demo_principals", mode="before")
    @classmethod
    def parse_demo_principals(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return v


settings = Settings()
