"""Session cookie helpers."""

from __future__ import annotations

from fastapi import Request, Response

from forge_agent.web.auth.config import WebAuthConfig


def read_session_id(request: Request, config: WebAuthConfig) -> str | None:
    value = request.cookies.get(config.cookie_name)
    return value.strip() if value else None


def set_session_cookie(response: Response, config: WebAuthConfig, session_id: str) -> None:
    max_age = config.session_ttl_hours * 3600
    response.set_cookie(
        config.cookie_name,
        session_id,
        httponly=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_session_cookie(response: Response, config: WebAuthConfig) -> None:
    response.delete_cookie(config.cookie_name, path="/")
