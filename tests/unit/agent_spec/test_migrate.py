"""Tests for legacy agent migration (A11.1)."""

from __future__ import annotations

import yaml

from forge_agent.agent_spec.versioning import (
    AGENT_ASSET_SPEC_VERSION,
    migrate_agent_dict,
    validate_agent_asset,
)


class TestMigrateAgentDict:
    def test_migrate_adds_spec_version(self) -> None:
        legacy = {
            "agent_id": "legacy_one",
            "name": "Legacy",
            "template": "search_agent",
            "config": {"output_schema": {"type": "object"}, "variables": {"query": "query"}},
            "mock_cases": [
                {"name": "default", "input": {"query": "x"}, "expect_keys": ["verdict"]}
            ],
        }
        migrated = migrate_agent_dict(legacy)
        assert migrated["_meta"]["spec_version"] == AGENT_ASSET_SPEC_VERSION
        assert migrated["_meta"]["primitive"] == "searcher"
        assert validate_agent_asset(migrated) == []

    def test_migrate_api_writes_yaml(self, tmp_path) -> None:
        from forge_agent.web.data import get_agent

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "old.yaml").write_text(
            yaml.safe_dump(
                {
                    "agents": [
                        {
                            "agent_id": "old",
                            "name": "Old",
                            "template": "prompt_agent",
                            "config": {
                                "output_schema": {"type": "object"},
                                "variables": {"reports": "reports"},
                            },
                            "mock_cases": [
                                {
                                    "name": "default",
                                    "input": {"reports": []},
                                    "expect_keys": ["verdict"],
                                }
                            ],
                        }
                    ]
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        agent = get_agent(tmp_path, "old")
        assert agent is not None
        migrated = migrate_agent_dict(agent)
        (agents_dir / "old.yaml").write_text(
            yaml.safe_dump({"agents": [migrated]}, allow_unicode=True),
            encoding="utf-8",
        )
        updated = get_agent(tmp_path, "old")
        assert updated["_meta"]["primitive"] == "synthesizer"
