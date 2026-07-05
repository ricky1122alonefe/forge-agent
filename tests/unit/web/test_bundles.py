"""Tests for bundle export/import (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml
from forge_agent.web.bundles import (
    export_agent_bundle,
    export_pipeline_bundle,
    import_bundle,
    save_shared_bundle,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    tenant = LocalTenant("acme", root_dir=tmp_path / "data")
    root = tenant.create_project("demo")
    type_def = {
        "type_id": "scraper",
        "name": "Scraper",
        "domain": "generic",
        "template": "scraper_agent",
        "params": [],
        "tools": ["weibo.hot_search"],
        "prompt_template": "test",
        "output_schema": {},
        "output_mapping": {},
    }
    (root / "agents" / "weibo.yaml").write_text(
        build_agent_yaml(
            type_def,
            "weibo_analyst",
            {"keyword": "x", "platform": "weibo", "tool": "weibo.hot_search"},
        ),
        encoding="utf-8",
    )
    (root / "pipelines" / "trend.yaml").write_text(
        build_pipeline_yaml("trend", "Trend", ["weibo_analyst"], chief_id="generic.chief"),
        encoding="utf-8",
    )
    return root


class TestBundles:
    def test_export_agent_includes_mock_cases_count(self, project_root: Path) -> None:
        from forge_agent.agent_spec.generator import generate_spec_rule_based
        from forge_agent.agent_spec.writer import apply_spec

        spec = generate_spec_rule_based("搜索 AI 行业动态", keyword="AI")
        apply_spec(project_root, spec, overwrite=True)
        bundle = export_agent_bundle(project_root, spec.agent_id)
        assert bundle["mock_cases_count"] >= 1
        assert bundle["agents"][0].get("mock_cases")

    def test_export_and_import_agent(self, project_root: Path, tmp_path: Path) -> None:
        bundle = export_agent_bundle(project_root, "weibo_analyst")
        assert bundle["kind"] == "forge_agent_bundle"
        assert len(bundle["agents"]) == 1

        target = tmp_path / "imported"
        tenant = LocalTenant("bob", root_dir=tmp_path / "data2")
        target = tenant.create_project("lab")

        result = import_bundle(target, bundle)
        assert "weibo_analyst" in result["agents_created"]
        assert (target / "agents" / "weibo_analyst.yaml").exists()

    def test_export_pipeline_includes_agents(self, project_root: Path) -> None:
        bundle = export_pipeline_bundle(project_root, "trend")
        assert bundle["pipeline"]["pipeline_id"] == "trend"
        assert len(bundle["agents"]) == 1

    def test_publish_shared_bundle(self, project_root: Path, tmp_path: Path) -> None:
        bundle = export_pipeline_bundle(project_root, "trend")
        market_dir = tmp_path / "market"
        path = save_shared_bundle(market_dir, bundle)
        assert path.exists()
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert loaded["kind"] == "forge_agent_bundle"

    def test_parse_bundle_yaml_text(self, project_root: Path) -> None:
        from forge_agent.web.bundles import parse_bundle_text

        bundle = export_agent_bundle(project_root, "weibo_analyst")
        yaml_text = yaml.safe_dump(bundle, allow_unicode=True)
        parsed = parse_bundle_text(yaml_text)
        assert parsed["bundle_id"] == bundle["bundle_id"]
