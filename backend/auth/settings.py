from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Configuration for authentication, JWT, and cookie defaults."""

    model_config = SettingsConfigDict(env_prefix="TFM_", case_sensitive=False, extra="ignore")

    access_token_minutes: int = Field(30, alias="ACCESS_TOKEN_MINUTES")
    refresh_token_minutes: int = Field(60 * 24 * 7, alias="REFRESH_TOKEN_MINUTES")

    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_secret: SecretStr = Field(SecretStr("dev-secret-change-me"), alias="JWT_SECRET")
    refresh_token_secret: SecretStr | None = Field(default=None, alias="REFRESH_SECRET")
    jwt_issuer: str | None = Field(default=None, alias="JWT_ISSUER")
    jwt_audience: str | None = Field(default=None, alias="JWT_AUDIENCE")

    api_token: str | None = Field(default=None, alias="API_TOKEN")
    legacy_api_token: str | None = Field(default=None, alias="LEGACY_API_TOKEN")

    refresh_cookie_name: str = Field("tm_refresh_token", alias="AUTH_REFRESH_COOKIE")
    cookie_secure: bool = Field(False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    cookie_samesite: str = Field("lax", alias="COOKIE_SAMESITE")

    default_scopes: List[str] = Field(default_factory=lambda: ["console:read", "console:write"])

    def expected_api_token(self) -> Optional[str]:
        """Return the configured API token value (TFM_API_TOKEN preferred, fallback to API_TOKEN)."""
        if self.api_token:
            return self.api_token
        # Support legacy `API_TOKEN` without prefix
        raw = os.getenv("API_TOKEN")
        if raw:
            return raw
        return self.legacy_api_token

    def resolved_refresh_secret(self) -> SecretStr:
        """Return the refresh secret, falling back to the access secret when unset."""
        return self.refresh_token_secret or self.access_token_secret


@lru_cache()
def _get_settings() -> AuthSettings:
    return AuthSettings()


auth_settings = _get_settings()
