"""Web UI authentication (P2.3/P2.4)."""

from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.middleware import WebAuthMiddleware
from forge_agent.web.auth.service import AuthService, AuthUser

__all__ = ["AuthService", "AuthUser", "WebAuthConfig", "WebAuthMiddleware"]
