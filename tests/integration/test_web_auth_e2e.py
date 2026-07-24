"""E2E tests for web auth (P2.3/P2.4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from forge_agent.web.app import create_app
from forge_agent.web.auth.config import WebAuthConfig


@pytest_asyncio.fixture
async def auth_client(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, Path]]:
    root = tmp_path / "data"
    app = create_app(
        data_root=root,
        auth_config=WebAuthConfig(enabled=True, session_secret="e2e-test-secret"),
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, root


class TestWebAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_redirects_to_login(
        self, auth_client: tuple[httpx.AsyncClient, Path]
    ) -> None:
        client, _ = auth_client
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"

    @pytest.mark.asyncio
    async def test_register_login_and_tenant_isolation(
        self, auth_client: tuple[httpx.AsyncClient, Path]
    ) -> None:
        client, root = auth_client

        response = await client.post(
            "/auth/register",
            json={"username": "alice", "password": "password123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/t/alice/p/default/"
        assert "forge_session" in response.cookies

        response = await client.get("/t/alice/p/default/")
        assert response.status_code == 200

        response = await client.get("/t/bob/p/default/")
        assert response.status_code == 403

        assert (root / "tenants" / "alice" / "projects" / "default").exists()
        assert not (root / "tenants" / "bob").exists()

    @pytest.mark.asyncio
    async def test_second_user_cannot_see_first_user_data(self, tmp_path: Path) -> None:
        root = tmp_path / "data"
        app = create_app(
            data_root=root,
            auth_config=WebAuthConfig(enabled=True, session_secret="e2e-test-secret"),
        )
        transport = ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=False
        ) as client_a:
            await client_a.post(
                "/auth/register",
                json={"username": "usera", "password": "password123"},
            )
            await client_a.post(
                "/t/usera/p/default/api/agents",
                json={
                    "agent_type": "scraper",
                    "agent_id": "secret_agent",
                    "params": {
                        "keyword": "x",
                        "platform": "weibo",
                        "tool": "weibo.hot_search",
                    },
                },
            )

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=False
        ) as client_b:
            await client_b.post(
                "/auth/register",
                json={"username": "userb", "password": "password123"},
            )
            response = await client_b.get("/t/usera/p/default/api/agents/secret_agent")
            assert response.status_code == 403

            response = await client_b.get("/t/userb/p/default/")
            assert response.status_code == 200

        assert (root / "tenants" / "usera" / "projects" / "default" / "agents").exists()

    @pytest.mark.asyncio
    async def test_login_existing_user(self, auth_client: tuple[httpx.AsyncClient, Path]) -> None:
        client, _ = auth_client
        await client.post(
            "/auth/register",
            json={"username": "loginme", "password": "password123"},
            follow_redirects=False,
        )
        client.cookies.clear()

        response = await client.post(
            "/auth/login",
            json={"username": "loginme", "password": "password123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/t/loginme/p/default/"
