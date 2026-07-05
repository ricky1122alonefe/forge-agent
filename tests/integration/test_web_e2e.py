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
        assert data["record"]["trace_id"]
        assert data["record"]["metadata"]["duration_ms"] is not None
        trace_path = project_root / "logs" / f"{data['record']['trace_id']}.json"
        assert trace_path.exists(), f"missing trace log: {trace_path}"
        assert (project_root / "state" / "forge_data.db").exists()

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
    async def test_llm_settings_api(self, client: httpx.AsyncClient, project_base: str) -> None:
        response = await client.get(f"{project_base}/api/llm/config")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "demo"
        assert any(p["provider_id"] == "deepseek" for p in data["providers"])

        response = await client.put(
            f"{project_base}/api/llm/config",
            json={"primary_id": "deepseek", "providers": {"deepseek": {"enabled": True}}},
        )
        assert response.status_code == 200
        assert response.json()["primary_id"] == "deepseek"

        response = await client.put(
            f"{project_base}/api/llm/secrets",
            json={"provider_id": "deepseek", "api_key": "sk-test-demo"},
        )
        assert response.status_code == 200
        assert response.json()["env_name"] == "DEEPSEEK_API_KEY"

        response = await client.get(f"{project_base}/settings/llm")
        assert response.status_code == 200
        assert "LLM 设置" in response.text

    @pytest.mark.asyncio
    async def test_create_all_platform_pipeline_preset(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        _, project_root = web_project
        response = await client.post(
            f"{project_base}/api/pipelines/from-preset",
            json={"preset_id": "all_platform_trend"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["pipeline_id"] == "all_trend"
        assert len(data["agent_ids"]) == 3
        assert (project_root / "pipelines" / "all_trend.yaml").exists()

    @pytest.mark.asyncio
    async def test_create_pipeline_from_preset(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        _, project_root = web_project
        response = await client.post(
            f"{project_base}/api/pipelines/from-preset",
            json={"preset_id": "multi_platform_trend"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["pipeline_id"] == "trend"
        assert set(data["agent_ids"]) == {"weibo_analyst", "xhs_analyst"}
        assert (project_root / "agents" / "weibo_analyst.yaml").exists()
        assert (project_root / "agents" / "xhs_analyst.yaml").exists()
        assert (project_root / "pipelines" / "trend.yaml").exists()
        assert data["run_url"].endswith("/pipelines/trend/run")

        # Idempotent: second call reuses existing resources
        response2 = await client.post(
            f"{project_base}/api/pipelines/from-preset",
            json={"preset_id": "multi_platform_trend"},
        )
        assert response2.status_code == 200
        assert response2.json()["pipeline_created"] is False
        assert response2.json()["agents_created"] == []

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

    @pytest.mark.asyncio
    async def test_p35_local_journey(
        self,
        client: httpx.AsyncClient,
        web_project: tuple[LocalTenant, Path],
    ) -> None:
        """P3.5: project → preset agents/pipeline → run → history (no auth, local-first)."""
        _, acme_demo_root = web_project

        response = await client.post("/t/acme/api/projects", json={"project_id": "lab"})
        assert response.status_code == 200, response.text
        lab_base = "/t/acme/p/lab"

        response = await client.get(f"{lab_base}/")
        assert response.status_code == 200

        response = await client.post(
            f"{lab_base}/api/pipelines/from-preset",
            json={"preset_id": "multi_platform_trend"},
        )
        assert response.status_code == 200, response.text
        preset = response.json()
        assert preset["success"] is True
        pipeline_id = preset["pipeline_id"]
        lab_root = acme_demo_root.parent / "lab"
        assert (lab_root / "pipelines" / f"{pipeline_id}.yaml").exists()

        response = await client.post(
            f"{lab_base}/api/pipelines/{pipeline_id}/run",
            json={"payload": {"keyword": "labubu"}},
        )
        assert response.status_code == 200, response.text
        run = response.json()
        assert run["success"] is True, run.get("error")
        assert run["record"]["metadata"]["mock_mode"] is True
        assert len(run["record"]["agent_reports"]) == 2
        run_id = run["run_id"]

        response = await client.get(f"{lab_base}/runs")
        assert response.status_code == 200
        assert run_id in response.text

        response = await client.get(f"{lab_base}/runs/{run_id}")
        assert response.status_code == 200
        assert "labubu" in response.text
        assert "trace" in response.text.lower() or "耗时" in response.text

        response = await client.get(f"{lab_base}/settings/llm")
        assert response.status_code == 200
        assert "LLM 设置" in response.text

        assert (lab_root / "state" / "forge_data.db").exists()
        assert (lab_root / "logs" / f"{run['record']['trace_id']}.json").exists()

    @pytest.mark.asyncio
    async def test_p34_scraper_uses_tool_agent_template(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """P3.4: scraper agents are created with scraper_agent template."""
        _, project_root = web_project
        response = await client.post(
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
        assert response.status_code == 200, response.text
        yaml_text = (project_root / "agents" / "weibo_scraper.yaml").read_text(encoding="utf-8")
        assert "template: scraper_agent" in yaml_text

    @pytest.mark.asyncio
    async def test_create_four_platform_pipeline_preset(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        _, project_root = web_project
        response = await client.post(
            f"{project_base}/api/pipelines/from-preset",
            json={"preset_id": "four_platform_trend"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["pipeline_id"] == "four_trend"
        assert len(data["agent_ids"]) == 4
        assert (project_root / "pipelines" / "four_trend.yaml").exists()

    @pytest.mark.asyncio
    async def test_p4_market_export_import(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """Phase 4: export pipeline bundle and import into same project with new ids."""
        _, project_root = web_project
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

        response = await client.get(f"{project_base}/api/pipelines/trend/export")
        assert response.status_code == 200
        bundle = response.json()
        assert bundle["pipeline"]["pipeline_id"] == "trend"

        bundle["pipeline"]["pipeline_id"] = "trend_copy"
        bundle["agents"][0]["agent_id"] = "weibo_copy"
        response = await client.post(
            f"{project_base}/api/bundles/import",
            json={"bundle": bundle, "overwrite": False},
        )
        assert response.status_code == 200
        assert "weibo_copy" in response.json()["agents_created"]
        assert (project_root / "pipelines" / "trend_copy.yaml").exists()

        response = await client.get(f"{project_base}/market")
        assert response.status_code == 200
        assert "模板市场" in response.text

    @pytest.mark.asyncio
    async def test_p06_golden_path_script(
        self,
        client: httpx.AsyncClient,
        web_project: tuple[LocalTenant, Path],
        project_base: str,
    ) -> None:
        """P0.6: mirrors PLAN manual script (weibo + xhs analysts → pipeline → run → history)."""
        _, project_root = web_project

        for preset_id, agent_id in (("weibo_trend", "weibo_analyst"), ("xhs_trend", "xhs_analyst")):
            response = await client.post(
                f"{project_base}/api/agents/from-preset",
                json={"preset_id": preset_id, "agent_id": agent_id},
            )
            assert response.status_code == 200, response.text
            assert (project_root / "agents" / f"{agent_id}.yaml").exists()

        response = await client.post(
            f"{project_base}/api/pipelines",
            json={
                "pipeline_id": "trend",
                "name": "Trend Pipeline",
                "agent_ids": ["weibo_analyst", "xhs_analyst"],
                "chief_id": "generic.chief",
                "mode": "parallel",
                "description": "P0.6 golden path",
            },
        )
        assert response.status_code == 200, response.text

        response = await client.post(
            f"{project_base}/api/pipelines/trend/run",
            json={"payload": {"keyword": "labubu"}},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert len(data["record"]["agent_reports"]) == 2
        assert data["record"]["chief_summary"] is not None

        response = await client.get(f"{project_base}/runs")
        assert response.status_code == 200
        assert data["run_id"] in response.text

        response = await client.get(f"{project_base}/runs/{data['run_id']}")
        assert response.status_code == 200
        assert "labubu" in response.text

    @pytest.mark.asyncio
    async def test_p44_architect_nl_pipeline(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """P4.4: natural language → plan → apply → run."""
        _, project_root = web_project

        response = await client.post(
            f"{project_base}/api/architect/plan",
            json={"requirement": "分析 labubu 在微博和小红书的热度", "use_llm": False},
        )
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["keyword"] == "labubu"
        assert len(plan["agents"]) >= 2

        response = await client.post(
            f"{project_base}/api/architect/apply",
            json={"requirement": "分析 labubu 在微博和小红书的热度", "plan": plan},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        pid = data["pipeline_id"]
        assert (project_root / "pipelines" / f"{pid}.yaml").exists()

        response = await client.post(
            f"{project_base}/api/pipelines/{pid}/run",
            json={"payload": {"keyword": "labubu"}},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        response = await client.get(f"{project_base}/architect")
        assert response.status_code == 200
        assert "智能创建" in response.text

    @pytest.mark.asyncio
    async def test_a15_agent_spec_generate_and_apply(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """AGENT_PLAN A1.5: agent-spec plan → apply → smoke."""
        _, project_root = web_project

        response = await client.post(
            f"{project_base}/api/agent-spec/plan",
            json={"requirement": "搜索 AI 行业动态并分析", "keyword": "AI"},
        )
        assert response.status_code == 200, response.text
        spec = response.json()
        assert spec["primitive"] == "searcher"

        response = await client.post(
            f"{project_base}/api/agent-spec/apply",
            json={"requirement": "搜索 AI 行业动态并分析", "spec": spec},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["smoke"]["success"] is True
        assert (project_root / "agents" / f"{spec['agent_id']}.yaml").exists()

    @pytest.mark.asyncio
    async def test_a31_generate_agent_page(
        self, client: httpx.AsyncClient, project_base: str
    ) -> None:
        """AGENT_PLAN A3.1: Web generate Agent page."""
        response = await client.get(f"{project_base}/agents/generate")
        assert response.status_code == 200
        assert "生成 Agent" in response.text
        assert "agent-spec/plan" in response.text or "/api/agent-spec/plan" in response.text

    @pytest.mark.asyncio
    async def test_a32_agent_smoke_endpoint(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """AGENT_PLAN A3.2: POST /agents/{id}/smoke updates maturity."""
        _, project_root = web_project

        response = await client.post(
            f"{project_base}/api/agent-spec/apply",
            json={
                "requirement": "搜索 AI 行业动态并分析",
                "keyword": "AI",
                "run_smoke": False,
            },
        )
        assert response.status_code == 200, response.text
        agent_id = response.json()["agent_id"]

        response = await client.post(f"{project_base}/api/agents/{agent_id}/smoke")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["smoke"]["success"] is True
        assert data["maturity"]["stage"] == "verified"

        agent_yaml = (project_root / "agents" / f"{agent_id}.yaml").read_text(encoding="utf-8")
        assert "smoke_verified" in agent_yaml

    @pytest.mark.asyncio
    async def test_a33_bundle_includes_mock_cases(
        self, client: httpx.AsyncClient, web_project: tuple[LocalTenant, Path], project_base: str
    ) -> None:
        """AGENT_PLAN A3.3: bundle export preserves mock_cases metadata."""
        response = await client.post(
            f"{project_base}/api/agent-spec/apply",
            json={"requirement": "搜索 AI 行业动态并分析", "keyword": "AI"},
        )
        assert response.status_code == 200, response.text
        agent_id = response.json()["agent_id"]

        response = await client.get(f"{project_base}/api/agents/{agent_id}/export")
        assert response.status_code == 200, response.text
        bundle = response.json()
        assert bundle["mock_cases_count"] >= 1
        assert bundle["agents"][0].get("mock_cases")

    @pytest.mark.asyncio
    async def test_a43_agent_spec_coverage_api(
        self, client: httpx.AsyncClient, project_base: str
    ) -> None:
        """AGENT_PLAN A4.3: coverage API reports matrix stats."""
        response = await client.get(f"{project_base}/api/agent-spec/coverage")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 20
        assert data["routing_pass"] >= 18
        assert data["target_met"] is True
