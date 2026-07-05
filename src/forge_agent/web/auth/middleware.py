"""Auth middleware: require login and enforce tenant isolation."""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.service import AuthService
from forge_agent.web.auth.session import read_session_id

_TENANT_PATH = re.compile(r"^/t/(?P<tenant_id>[^/]+)")


def _is_public_path(path: str) -> bool:
    if path in ("/api/health", "/health"):
        return True
    if path.startswith("/static/"):
        return True
    return path.startswith("/auth/")


class WebAuthMiddleware(BaseHTTPMiddleware):
    """Require session auth and block cross-tenant access when enabled."""

    def __init__(self, app, auth_config: WebAuthConfig) -> None:
        super().__init__(app)
        self.auth_config = auth_config

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.auth_config.enabled:
            return await call_next(request)

        path = request.url.path
        if _is_public_path(path):
            return await call_next(request)

        data_root = request.app.state.data_root
        service = AuthService(data_root, self.auth_config)
        session_id = read_session_id(request, self.auth_config)
        user = service.get_user_for_session(session_id)
        request.state.user = user

        if user is None:
            if path.startswith("/api/") or "/api/" in path:
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            return RedirectResponse(url="/auth/login", status_code=302)

        match = _TENANT_PATH.match(path)
        if match and match.group("tenant_id") != user.tenant_id:
            return JSONResponse(status_code=403, content={"detail": "Forbidden: tenant mismatch"})

        return await call_next(request)
