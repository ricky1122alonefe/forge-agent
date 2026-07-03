"""End-to-end test: Web UI golden path (create agents → pipeline → run).

Covers the P0 acceptance flow via HTTP API (same backend as forge-agent up).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from forge_agent.platform import LocalTenant
from forge_agent.project.state_store import StateStore
from forge_agent.web.app import create_app


@pytest.fixture
def web_project(tmp_path: Path) -> tuple[LocalTenant, Path]:
    """Create an isolated tenant project for web UI tests."""
    root = tmp_path / "data"
    tenant = LocalTenant("acme", root_dir=root)
    project_root = tenant.create_project("demo")
    return tenant, project_root


@pytest.fixture
async def client(web_project: tuple[LocalTenant, Path]) -> AsyncIterator[httpx.AsyncClient]:
    tenant, project_root = web_project
    app = create_app(tenant=tenant, project_root=project_root)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


class TestWebGoldenPath:
    """P0: create agents → pipeline → run → history."""

    @pytest.mark.asyncio
    async def test_health(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["tenant_id"] == "acme"

    @pytest.mark.asyncio
    async def test_create_pipeline_page_defaults_chief(self, client: httpx.AsyncClient) -> None:
        """Chief dropdown should offer generic.chief by default."""
        await client.post(
            "/api/agents",
            json={
                "agent_type": "scraper",
                "agent_id": "weibo_scraper",
                "params": {
                    "keyword": "labubu",
                    "platform": "weibo",
                    "tool": "weibo.hot_search",
                },
            },
        )
        response = await client.get("/pipelines/new")
        assert response.status_code == 200
        assert "generic.chief" in response.text
        assert "selected" in response.text

    @pytest.mark.asyncio
    async def test_golden_path(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path]
    ) -> None:
        _, project_root = web_project

        scraper_params = [
            {
                "agent_id": "weibo_scraper",
                "params": {
                    "keyword": "labubu",
                    "platform": "weibo",
                    "tool": "weibo.hot_search",
                },
            },
            {
                "agent_id": "xhs_scraper",
                "params": {
                    "keyword": "labubu",
                    "platform": "xiaohongshu",
                    "tool": "xiaohongshu.search",
                },
            },
        ]

        for item in scraper_params:
            response = await client.post(
                "/api/agents",
                json={
                    "agent_type": "scraper",
                    "agent_id": item["agent_id"],
                    "params": item["params"],
                },
            )
            assert response.status_code == 200, response.text
            assert (project_root / "agents" / f"{item['agent_id']}.yaml").exists()

        response = await client.post(
            "/api/pipelines",
            json={
                "pipeline_id": "trend",
                "name": "Trend Pipeline",
                "agent_ids": ["weibo_scraper", "xhs_scraper"],
                "chief_id": "generic.chief",
                "mode": "parallel",
                "description": "P0 golden path",
            },
        )
        assert response.status_code == 200, response.text
        assert (project_root / "pipelines" / "trend.yaml").exists()

        response = await client.post(
            "/api/pipelines/trend/run",
            json={"payload": {"keyword": "labubu"}},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["run_id"]
        assert len(data["record"]["agent_reports"]) == 2
        assert data["record"]["chief_summary"] is not None
        assert data["record"]["metadata"]["has_chief"] is True

        records = StateStore(project_root).list()
        assert len(records) >= 1
        assert records[0].pipeline_id == "trend"

        response = await client.get("/runs")
        assert response.status_code == 200
        assert data["run_id"] in response.text

        response = await client.get(f"/runs/{data['run_id']}")
        assert response.status_code == 200
        assert "labubu" in response.text
