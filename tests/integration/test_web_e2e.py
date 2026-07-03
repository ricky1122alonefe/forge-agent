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
def project_base() -> str:
    return "/t/acme/p/demo"


@pytest.fixture
async def client(
    web_project: tuple[LocalTenant, Path], tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    root = tmp_path / "data"
    app = create_app(
        data_root=root,
        default_tenant_id="acme",
        default_project_id="demo",
    )
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
        assert data["default_tenant_id"] == "acme"
        assert "acme" in data["tenants"]

    @pytest.mark.asyncio
    async def test_create_project_api(self, client: httpx.AsyncClient, tmp_path: Path) -> None:
        response = await client.post(
            "/t/acme/api/projects",
            json={"project_id": "lab"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["project_id"] == "lab"
        assert data["url"] == "/t/acme/p/lab/"

    @pytest.mark.asyncio
    async def test_create_pipeline_page_defaults_chief(
        self, client: httpx.AsyncClient, project_base: str
    ) -> None:
        """Chief dropdown should offer generic.chief by default."""
        await client.post(
            f"{project_base}/api/agents",
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
        response = await client.get(f"{project_base}/pipelines/new")
        assert response.status_code == 200
        assert "generic.chief" in response.text
        assert "selected" in response.text

    @pytest.mark.asyncio
    async def test_golden_path(
        self,
        client: httpx.AsyncClient,
        web_project: tuple[LocalTenant, Path],
        project_base: str,
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
                f"{project_base}/api/agents",
                json={
                    "agent_type": "scraper",
                    "agent_id": item["agent_id"],
                    "params": item["params"],
                },
            )
            assert response.status_code == 200, response.text
            assert (project_root / "agents" / f"{item['agent_id']}.yaml").exists()

        response = await client.post(
            f"{project_base}/api/pipelines",
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
            f"{project_base}/api/pipelines/trend/run",
            json={"payload": {"keyword": "labubu"}},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["run_id"]
        assert len(data["record"]["agent_reports"]) == 2
        assert data["record"]["chief_summary"] is not None
        assert data["record"]["metadata"]["has_chief"] is True
        assert data["record"]["metadata"]["mock_mode"] is True

        records = StateStore(project_root).list()
        assert len(records) >= 1
        assert records[0].pipeline_id == "trend"

        response = await client.get(f"{project_base}/runs")
        assert response.status_code == 200
        assert data["run_id"] in response.text

        response = await client.get(f"{project_base}/runs/{data['run_id']}")
        assert response.status_code == 200
        assert "labubu" in response.text

    @pytest.mark.asyncio
    async def test_create_agent_from_preset(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        _, project_root = web_project
        response = await client.post(
            f"{project_base}/api/agents/from-preset", json={"preset_id": "weibo_trend"}
        )
        assert response.status_code == 200, response.text
        assert (project_root / "agents" / "weibo_analyst.yaml").exists()

    @pytest.mark.asyncio
    async def test_update_agent_config(self, client: httpx.AsyncClient, project_base: str) -> None:
        await client.post(
            f"{project_base}/api/agents",
            json={
                "agent_type": "scraper",
                "agent_id": "weibo_scraper",
                "params": {"keyword": "labubu", "platform": "weibo", "tool": "weibo.hot_search"},
            },
        )
        response = await client.put(
            f"{project_base}/api/agents/weibo_scraper/config",
            json={"mock_mode": False, "prompt": "updated prompt", "tools": ["weibo.hot_search"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["config"]["mock_mode"] is False

    @pytest.mark.asyncio
    async def test_pipeline_payload_fields(
        self, client: httpx.AsyncClient, project_base: str
    ) -> None:
        await client.post(
            f"{project_base}/api/agents",
            json={
                "agent_type": "scraper",
                "agent_id": "weibo_scraper",
                "params": {"keyword": "labubu", "platform": "weibo", "tool": "weibo.hot_search"},
            },
        )
        await client.post(
            f"{project_base}/api/pipelines",
            json={
                "pipeline_id": "trend",
                "name": "Trend",
                "agent_ids": ["weibo_scraper"],
                "chief_id": "generic.chief",
            },
        )
        response = await client.get(f"{project_base}/api/pipelines/trend/payload-fields")
        assert response.status_code == 200
        fields = response.json()["fields"]
        names = [f["name"] for f in fields]
        assert names == ["keyword"]
        assert "platform" not in names
        assert "tool" not in names

    @pytest.mark.asyncio
    async def test_tenant_isolation_by_url(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path]
    ) -> None:
        _, project_root = web_project
        await client.post(
            "/t/acme/p/demo/api/agents",
            json={
                "agent_type": "scraper",
                "agent_id": "secret_agent",
                "params": {"keyword": "x", "platform": "weibo", "tool": "weibo.hot_search"},
            },
        )
        assert (project_root / "agents" / "secret_agent.yaml").exists()

        response = await client.get("/t/bob/p/demo/api/agents/secret_agent")
        assert response.status_code == 404
