"""Phase 5 integration: tenant types + from-type AgentSpec path."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import yaml
from httpx import ASGITransport

from forge_agent.platform import LocalTenant
from forge_agent.web.app import create_app


@pytest.fixture
def web_project(tmp_path: Path) -> tuple[LocalTenant, Path]:
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


@pytest.mark.asyncio
async def test_a53_from_type_apply_includes_mock_cases(
    client: httpx.AsyncClient,
    web_project: tuple[LocalTenant, Path],
    project_base: str,
) -> None:
    _, project_root = web_project

    response = await client.post(
        f"{project_base}/api/agent-spec/from-type",
        json={
            "agent_type": "monitor",
            "agent_id": "inventory_watch",
            "params": {"metric_name": "inventory", "threshold": 50},
            "apply": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["smoke"]["success"] is True
    assert data["spec"]["mock_cases"]

    agent_yaml = yaml.safe_load(
        (project_root / "agents" / "inventory_watch.yaml").read_text(encoding="utf-8")
    )
    assert agent_yaml["agents"][0].get("mock_cases")


@pytest.mark.asyncio
async def test_a52_tenant_type_crud(
    client: httpx.AsyncClient,
    project_base: str,
) -> None:
    payload = {
        "agent_type": {
            "type_id": "tenant_sentiment",
            "name": "Tenant Sentiment",
            "description": "Custom sentiment",
            "domain": "generic",
            "template": "prompt_agent",
            "params": [
                {"name": "topic", "type": "string", "required": True, "description": "Topic"}
            ],
            "prompt_template": "Classify sentiment for {topic}",
            "output_schema": {
                "type": "object",
                "properties": {"verdict": {"type": "string"}},
                "required": ["verdict"],
            },
            "output_mapping": {"verdict": "verdict"},
        }
    }
    response = await client.post(f"{project_base}/api/agent-types", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "tenant"

    response = await client.get(f"{project_base}/api/agent-types")
    types = {t["type_id"]: t for t in response.json()["types"]}
    assert types["tenant_sentiment"]["source"] == "tenant"

    response = await client.delete(f"{project_base}/api/agent-types/tenant_sentiment")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a61_single_agent_run(
    client: httpx.AsyncClient,
    web_project: tuple[LocalTenant, Path],
    project_base: str,
) -> None:
    """AGENT_PLAN A6: run one agent without pipeline."""
    response = await client.post(
        f"{project_base}/api/agent-spec/apply",
        json={"requirement": "搜索 AI 行业动态", "keyword": "AI", "run_smoke": False},
    )
    assert response.status_code == 200, response.text
    agent_id = response.json()["agent_id"]

    response = await client.post(
        f"{project_base}/api/agents/{agent_id}/run",
        json={"payload": {}},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["report"]["agent_id"] == agent_id
