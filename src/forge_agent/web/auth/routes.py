"""Login and registration routes (P2.3/P2.4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from forge_agent.web.auth.config import WebAuthConfig
from forge_agent.web.auth.service import AuthService
from forge_agent.web.auth.session import clear_session_cookie, read_session_id, set_session_cookie
from forge_agent.web.context import project_url

router = APIRouter(prefix="/auth", tags=["auth"])


class _AuthPayload(BaseModel):
    username: str
    password: str


def _templates():
    from fastapi.templating import Jinja2Templates

    return Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _auth_config(request: Request) -> WebAuthConfig:
    return request.app.state.auth_config


def _service(request: Request) -> AuthService:
    return AuthService(request.app.state.data_root, _auth_config(request))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if not _auth_config(request).enabled:
        return RedirectResponse(url="/", status_code=302)
    templates = _templates()
    return templates.TemplateResponse(
        request=request,
        name="auth_login.html",
        context={"request": request, "register_url": "/auth/register"},
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    if not _auth_config(request).enabled:
        return RedirectResponse(url="/", status_code=302)
    templates = _templates()
    return templates.TemplateResponse(
        request=request,
        name="auth_register.html",
        context={"request": request, "login_url": "/auth/login"},
    )


@router.post("/register")
async def register(
    request: Request,
    payload: _AuthPayload,
) -> RedirectResponse:
    if not _auth_config(request).enabled:
        raise HTTPException(status_code=404, detail="Auth disabled")
    service = _service(request)
    try:
        user, session_id = service.register(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = RedirectResponse(
        url=project_url(user.tenant_id, "default", "/"),
        status_code=303,
    )
    set_session_cookie(response, _auth_config(request), session_id)
    return response


@router.post("/login")
async def login(
    request: Request,
    payload: _AuthPayload,
) -> RedirectResponse:
    if not _auth_config(request).enabled:
        raise HTTPException(status_code=404, detail="Auth disabled")
    service = _service(request)
    try:
        user, session_id = service.login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    response = RedirectResponse(
        url=project_url(user.tenant_id, "default", "/"),
        status_code=303,
    )
    set_session_cookie(response, _auth_config(request), session_id)
    return response


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    config = _auth_config(request)
    service = _service(request)
    session_id = read_session_id(request, config)
    service.logout(session_id)
    response = RedirectResponse(url="/auth/login", status_code=303)
    clear_session_cookie(response, config)
    return response
