"""Typed runtime configuration (SEC-018 / OBS-003 remediation).

All configuration is loaded once into an immutable :class:`Settings` object via
``pydantic-settings``. Legacy unprefixed env vars (``TRANSPORT`` / ``HOST`` /
``PORT``) keep working; the canonical names use the ``EFV_MCP_`` prefix.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EFV_MCP_", extra="ignore")

    transport: str = Field(
        default="stdio",
        validation_alias=AliasChoices("EFV_MCP_TRANSPORT", "TRANSPORT"),
        description="stdio (local) or sse / streamable-http / http (cloud)",
    )
    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("EFV_MCP_HOST", "HOST"),
        description="Bind host for network transports. Loopback by default.",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("EFV_MCP_PORT", "PORT"),
    )
    log_level: str = Field(default="INFO", description="structlog level (JSON to stderr)")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="SSE only: explicit allowed browser origins (default-deny).",
    )
    cache_ttl: int = Field(default=86400, ge=0, description="Dump cache TTL in seconds")
    http_timeout: float = Field(default=60.0, gt=0, description="Per-request HTTP timeout (s)")
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing (requires the 'otel' extra); OBS-006",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        # NoDecode hands us the raw env string; accept both a JSON list and a
        # comma-separated string.
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json

                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
