"""Unit tests for agent asset versioning (A8)."""

from __future__ import annotations

import yaml

from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.versioning import (
    AGENT_ASSET_SPEC_VERSION,
    next_revision,
    stamp_agent_meta,
    validate_agent_asset,
)
from forge_agent.agent_spec.writer import apply_spec, spec_to_agent_dict


class TestAgentAssetVersioning:
    def test_apply_spec_stamps_meta(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="versioned")
        result = apply_spec(tmp_path, spec)
        assert result["spec_version"] == AGENT_ASSET_SPEC_VERSION
        assert result["revision"] == 1

        raw = yaml.safe_load((tmp_path / "agents" / "versioned.yaml").read_text(encoding="utf-8"))
        meta = raw["agents"][0]["_meta"]
        assert meta["spec_version"] == AGENT_ASSET_SPEC_VERSION
        assert meta["revision"] == 1
        assert meta.get("generated_at")

    def test_overwrite_bumps_revision_and_resets_verification(self, tmp_path) -> None:
        spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="rev_agent")
        apply_spec(tmp_path, spec, smoke_verified=True)

        apply_spec(tmp_path, spec, overwrite=True)
        raw = yaml.safe_load((tmp_path / "agents" / "rev_agent.yaml").read_text(encoding="utf-8"))
        meta = raw["agents"][0]["_meta"]
        assert meta["revision"] == 2
        assert "smoke_verified" not in meta
        assert meta.get("maturity") == "draft"

    def test_validate_agent_asset_ok(self) -> None:
        spec = generate_spec_rule_based("分析 labubu 微博", agent_id="valid_asset")
        agent = spec_to_agent_dict(spec)
        agent["_meta"] = stamp_agent_meta(agent["_meta"], revision=1)
        assert validate_agent_asset(agent) == []

    def test_validate_agent_asset_missing_version(self) -> None:
        spec = generate_spec_rule_based("分析 labubu 微博", agent_id="no_version")
        agent = spec_to_agent_dict(spec)
        errors = validate_agent_asset(agent)
        assert any("spec_version" in e for e in errors)

    def test_next_revision(self) -> None:
        assert next_revision(None) == 1
        assert next_revision({"_meta": {"revision": 3}}) == 4
