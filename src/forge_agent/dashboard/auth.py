"""Dashboard authentication and authorization.

Provides:
- AuthConfig: authentication configuration
- AuthMiddleware: FastAPI middleware for API key validation
- require_auth: dependency for protected routes
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class AuthConfig:
    """Authentication configuration for the dashboard."""

    enabled: bool = False
    api_key: str | None = None
    header_name: str = "X-API-Key"

    @classmethod
    def from_env(cls) -> AuthConfig:
        """Load config from environment variables."""
        enabled = os.environ.get("FORGE_AGENT_AUTH_ENABLED", "").lower() in ("1", "true", "yes")
        api_key = os.environ.get("FORGE_AGENT_API_KEY")
        header_name = os.environ.get("FORGE_AGENT_AUTH_HEADER", "X-API-Key")
        return cls(enabled=enabled, api_key=api_key, header_name=header_name)

    def validate_key(self, provided_key: str | None) -> bool:
        """Validate the provided API key."""
        if not self.enabled:
            return True
        if not self.api_key:
            return True
        if not provided_key:
            return False
        return secrets.compare_digest(provided_key, self.api_key)


# Global auth config instance
_auth_config: AuthConfig | None = None


def get_auth_config() -> AuthConfig:
    """Get the global auth config."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig.from_env()
    return _auth_config


def set_auth_config(config: AuthConfig) -> None:
    """Set the global auth config (for testing)."""
    global _auth_config
    _auth_config = config


def reset_auth_config() -> None:
    """Reset the global auth config (for testing)."""
    global _auth_config
    _auth_config = None


# API key header security scheme
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_auth(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Dependency that validates the API key.

    Raises HTTPException 401 if authentication fails.
    """
    config = get_auth_config()
    if not config.enabled:
        return
    if not config.validate_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API key for all requests.

    Skips authentication for:
    - Health check endpoints (/api/health)
    - Static files (/static/*)
    - WebSocket connections (handled separately)
    """

    def __init__(self, app, auth_config: AuthConfig | None = None):
        super().__init__(app)
        self.auth_config = auth_config

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        config = self.auth_config or get_auth_config()

        # Skip auth if disabled
        if not config.enabled:
            return await call_next(request)

        # Skip health check and static files
        path = request.url.path
        if path in ("/api/health", "/health") or path.startswith("/static/"):
            return await call_next(request)

        # Skip WebSocket (handled by route-level auth)
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        # Validate API key
        provided_key = request.headers.get(config.header_name)
        if not config.validate_key(provided_key):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API key"},
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)
