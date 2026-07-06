"""Tests for compose bundle export and edit CI (A12)."""

from __future__ import annotations

import pytest
import yaml

from forge_agent.agent_spec.ci import CIGateError, persist_agent_document_with_ci
from forge_agent.agent_spec.compose import compose_from_requirement
from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.models import MockCase
from forge_agent.agent_spec.writer import apply_spec
from forge_agent.web.bundles import export_compose_bundle, validate_bundle


class TestComposeExport:
    def test_export_compose_bundle_shape(self) -> None:
        plan = compose_from_requirement(
            "抓微博和小红书 labubu 热度，再汇总成一份报告",
            keyword="labubu",
            pipeline_id="labubu_export",
        )
        bundle = export_compose_bundle(plan)
        validate_bundle(bundle)
        assert bundle["composed"] is True
        assert bundle["agent_count"] == 3
        assert bundle["pipeline"]["team"]["mode"] == "sequential"
        assert all(a["_meta"].get("spec_version") for a in bundle["agents"])


class TestPersistAgentCI:
    def test_persist_blocks_bad_edit(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="edit_ci")
        apply_spec(tmp_path, spec, ci_gate=True)
        raw = yaml.safe_load((tmp_path / "agents" / "edit_ci.yaml").read_text(encoding="utf-8"))
        agent = raw["agents"][0]
        agent["mock_cases"] = [
            MockCase(name="bad", input={"query": "x"}, expect_keys=["missing_key"]).to_dict()
        ]
        with pytest.raises(CIGateError):
            persist_agent_document_with_ci(tmp_path, "edit_ci", raw, ci_gate=True)

    def test_persist_bumps_revision(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="edit_ok")
        apply_spec(tmp_path, spec, ci_gate=True)
        raw = yaml.safe_load((tmp_path / "agents" / "edit_ok.yaml").read_text(encoding="utf-8"))
        result = persist_agent_document_with_ci(tmp_path, "edit_ok", raw, ci_gate=True)
        assert result["revision"] == 2
