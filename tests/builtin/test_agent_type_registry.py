"""Tests for AgentTypeRegistry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.exceptions import ForgeError


class TestAgentTypeRegistry:
    def test_loads_builtin_types(self) -> None:
        registry = AgentTypeRegistry()
        type_ids = registry.list_type_ids()

        assert "scraper" in type_ids
        assert "analyzer" in type_ids
        assert "chief" in type_ids

    def test_get_existing_type(self) -> None:
        registry = AgentTypeRegistry()
        scraper = registry.get("scraper")

        assert scraper["type_id"] == "scraper"
        assert "params" in scraper
        assert "prompt_template" in scraper
        assert "output_schema" in scraper

    def test_get_missing_type_raises(self) -> None:
        registry = AgentTypeRegistry()

        with pytest.raises(ForgeError):
            registry.get("missing")

    def test_tenant_types_override_builtin(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "agent_types"
        shared_dir.mkdir(parents=True)
        custom_scraper = {
            "agent_type": {
                "type_id": "scraper",
                "name": "Custom Scraper",
                "description": "Custom",
                "domain": "custom",
                "template": "prompt_agent",
                "params": [],
                "prompt_template": "custom",
                "output_schema": {"type": "object"},
                "output_mapping": {},
            }
        }
        (shared_dir / "scraper.yaml").write_text(yaml.safe_dump(custom_scraper), encoding="utf-8")

        registry = AgentTypeRegistry(tenant_shared_dir=shared_dir)

        assert registry.get("scraper")["name"] == "Custom Scraper"

    def test_list_with_source(self, tmp_path: Path) -> None:
        shared_dir = tmp_path / "agent_types"
        shared_dir.mkdir(parents=True)
        (shared_dir / "custom.yaml").write_text(
            yaml.safe_dump(
                {
                    "agent_type": {
                        "type_id": "custom",
                        "name": "C",
                        "description": "d",
                        "domain": "g",
                        "template": "prompt_agent",
                        "params": [],
                        "prompt_template": "x",
                        "output_schema": {},
                        "output_mapping": {},
                    }
                }
            ),
            encoding="utf-8",
        )
        registry = AgentTypeRegistry(tenant_shared_dir=shared_dir)
        by_id = {t["type_id"]: t for t in registry.list_with_source()}
        assert by_id["custom"]["source"] == "tenant"
        assert by_id["scraper"]["source"] == "builtin"

    def test_schema_file_is_ignored(self) -> None:
        registry = AgentTypeRegistry()

        assert "_schema" not in registry.list_type_ids()
