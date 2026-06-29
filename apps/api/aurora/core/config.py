"""Typed, environment-driven settings (12-factor).

Every variable is documented in the repo-root ``.env.example``. Settings fail fast in
production if insecure placeholder values are left in place.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-change-me-please-set-a-strong-secret-key"
INSECURE_PLACEHOLDERS = {_DEV_SECRET, "dev-insecure-change-me", "change-me", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core
    app_env: str = "local"  # local | staging | production
    log_level: str = "info"
    secret_key: str = _DEV_SECRET
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600
    jwt_algorithm: str = "HS256"

    # API surface
    project_name: str = "AURORA API"
    version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost"]

    # Datastores (declared now; wired in Phase 2). Optional so Phase 1 runs in-memory.
    database_url: Optional[str] = None
    neo4j_uri: Optional[str] = None
    redis_url: Optional[str] = None

    # AI provider abstraction (mock requires no keys).
    ai_provider: str = "mock"  # mock | openai | bedrock

    # Demo seeding
    seed_demo_on_startup: bool = True
    demo_password: str = "aurora-demo-2026"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_runtime(self) -> None:
        """Refuse to run in production with insecure defaults."""
        if self.is_production and self.secret_key in INSECURE_PLACEHOLDERS:
            raise RuntimeError(
                "SECRET_KEY must be set to a strong value when APP_ENV=production."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
