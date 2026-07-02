"""Typed, environment-driven settings (12-factor).

Every variable is documented in the repo-root ``.env.example``. Settings fail fast in
production if insecure placeholder values are left in place.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated

from .oidc import OidcConfig, parse_oidc_config

_DEV_SECRET = "dev-insecure-change-me-please-set-a-strong-secret-key"
INSECURE_PLACEHOLDERS = {_DEV_SECRET, "dev-insecure-change-me", "change-me", ""}
_VALID_ANALYTICS_BACKENDS = {"postgres", "clickhouse"}


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
    # NoDecode: pydantic-settings would otherwise require strict JSON for list
    # fields read from the environment and crash on the comma form.
    cors_origins: Annotated[List[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost",
    ]

    # Datastores. When ``database_url`` is set the API uses ``aurora_db`` (Phase 2).
    database_url: Optional[str] = None
    database_auto_create: bool = True  # SQLite local dev: create tables from metadata
    neo4j_uri: Optional[str] = None
    redis_url: Optional[str] = None

    # Analytics (Phase 9)
    analytics_backend: str = "postgres"  # postgres | clickhouse
    clickhouse_url: Optional[str] = None

    # Object storage
    s3_endpoint: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"

    # OIDC / SSO (Phase 9)
    oidc_enabled: bool = False
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_redirect_uri: Optional[str] = None
    oidc_scopes: str = "openid profile email"

    # Security hardening
    auth_rate_limit_per_minute: int = 20
    security_headers_enabled: bool = True

    # AI provider abstraction (mock requires no keys).
    ai_provider: str = "mock"  # mock | anthropic | openai | bedrock
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 30.0

    # Demo seeding
    seed_demo_on_startup: bool = True
    demo_password: str = "aurora-demo-2026"
    demo_seed: int = 42
    demo_seed_scale: float = 0.1  # 1.0 = full Nimbus spec; lower is faster for laptop dev

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Accept a JSON array (Terraform/ECS) or a comma-separated string (.env)."""
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value

    @field_validator("analytics_backend")
    @classmethod
    def validate_analytics_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _VALID_ANALYTICS_BACKENDS:
            raise ValueError(
                f"ANALYTICS_BACKEND must be one of {sorted(_VALID_ANALYTICS_BACKENDS)}"
            )
        return normalized

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_staging_or_production(self) -> bool:
        return self.app_env.lower() in {"staging", "production"}

    def oidc_config(self) -> Optional[OidcConfig]:
        return parse_oidc_config(
            enabled=self.oidc_enabled,
            issuer=self.oidc_issuer,
            client_id=self.oidc_client_id,
            client_secret=self.oidc_client_secret,
            redirect_uri=self.oidc_redirect_uri,
            scopes_raw=self.oidc_scopes,
        )

    def validate_runtime(self) -> None:
        """Refuse to run in production with insecure defaults."""
        if self.is_production and self.secret_key in INSECURE_PLACEHOLDERS:
            raise RuntimeError(
                "SECRET_KEY must be set to a strong value when APP_ENV=production."
            )
        if self.is_production and len(self.secret_key) < 32:
            raise RuntimeError(
                "SECRET_KEY must be at least 32 characters when APP_ENV=production."
            )
        if self.is_production and self.access_token_ttl_seconds > 900:
            raise RuntimeError(
                "ACCESS_TOKEN_TTL_SECONDS must be <= 900 in production."
            )
        if (
            self.is_production
            and self.seed_demo_on_startup
            and self.demo_password == "aurora-demo-2026"
        ):
            raise RuntimeError(
                "Change DEMO_PASSWORD from the default when APP_ENV=production."
            )
        if self.analytics_backend == "clickhouse" and not self.clickhouse_url:
            raise RuntimeError(
                "CLICKHOUSE_URL is required when ANALYTICS_BACKEND=clickhouse."
            )
        if self.ai_provider not in ("mock", "anthropic", "openai", "bedrock"):
            raise RuntimeError(
                "AI_PROVIDER must be one of: mock, anthropic, openai, bedrock."
            )
        if self.ai_provider == "anthropic" and not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic.")
        if self.ai_provider == "openai" and not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
        if self.ai_provider == "bedrock":
            raise RuntimeError(
                "AI_PROVIDER=bedrock is not implemented yet — use anthropic, openai, or mock."
            )
        if self.oidc_enabled:
            self.oidc_config()


@lru_cache
def get_settings() -> Settings:
    return Settings()
