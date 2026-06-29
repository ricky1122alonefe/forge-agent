"""Tests for T2.1.5: agent_type field in manifest, store, and list command."""

from __future__ import annotations

import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from forge_agent.generator.manifest import AgentManifestEntry, Manifest
from forge_agent.generator.store import FileCodeStore

# ── Manifest agent_type ──────────────────────────────────────────────


class TestManifestAgentType:
    def test_default_empty(self):
        entry = AgentManifestEntry(agent_id="a1", created_at="2026-01-01", active_version="v1")
        assert entry.agent_type == ""

    def test_set_type(self):
        entry = AgentManifestEntry(
            agent_id="a1", created_at="2026-01-01", active_version="v1", agent_type="scraper"
        )
        assert entry.agent_type == "scraper"

    def test_to_dict_includes_type(self):
        entry = AgentManifestEntry(
            agent_id="a1", created_at="2026-01-01", active_version="v1", agent_type="analyzer"
        )
        d = entry.to_dict()
        assert d["agent_type"] == "analyzer"

    def test_from_dict_with_type(self):
        d = {
            "agent_id": "a1",
            "created_at": "2026-01-01",
            "active_version": "v1",
            "agent_type": "monitor",
            "versions": [],
        }
        entry = AgentManifestEntry.from_dict(d)
        assert entry.agent_type == "monitor"

    def test_from_dict_missing_type(self):
        d = {"agent_id": "a1", "created_at": "2026-01-01", "active_version": "v1", "versions": []}
        entry = AgentManifestEntry.from_dict(d)
        assert entry.agent_type == ""

    def test_roundtrip(self):
        entry = AgentManifestEntry(
            agent_id="a1", created_at="2026-01-01", active_version="v1", agent_type="generator"
        )
        restored = AgentManifestEntry.from_dict(entry.to_dict())
        assert restored.agent_type == "generator"


# ── FileCodeStore agent_type ─────────────────────────────────────────


class TestStoreAgentType:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_new_agent_with_type(self):
        store = FileCodeStore(self.tmpdir / "out")
        store.save("agent1", "print('hi')", requirement="test", agent_type="scraper")
        entry = store.manifest.agents["agent1"]
        assert entry.agent_type == "scraper"

    def test_save_new_agent_without_type(self):
        store = FileCodeStore(self.tmpdir / "out")
        store.save("agent1", "print('hi')", requirement="test")
        entry = store.manifest.agents["agent1"]
        assert entry.agent_type == ""

    def test_save_existing_agent_preserves_type(self):
        store = FileCodeStore(self.tmpdir / "out")
        store.save("agent1", "print('v1')", requirement="test", agent_type="analyzer")
        store.save("agent1", "print('v2')", requirement="test2")
        # agent_type stays from first creation
        assert store.manifest.agents["agent1"].agent_type == "analyzer"

    def test_manifest_persisted_with_type(self):
        store = FileCodeStore(self.tmpdir / "out")
        store.save("agent1", "print('hi')", requirement="test", agent_type="monitor")
        # Reload from disk
        manifest2 = Manifest.load(store.manifest_path)
        assert manifest2.agents["agent1"].agent_type == "monitor"


# ── cmd_list TYPE column ─────────────────────────────────────────────


class TestCmdListType:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_store_with_agent(self, agent_type="scraper"):
        store = FileCodeStore(self.tmpdir / "out")
        store.save("my-agent", "print('hi')", requirement="test", agent_type=agent_type)
        return store

    def test_list_shows_type_column(self):
        store = self._make_store_with_agent("scraper")
        import argparse

        from forge_agent.cli.cmd_list import run

        args = argparse.Namespace(project=str(self.tmpdir / "out"))
        with patch("forge_agent.cli._helpers.get_store", return_value=store):
            captured = StringIO()
            with patch("sys.stdout", captured):
                ret = run(args)
        output = captured.getvalue()
        assert "TYPE" in output
        assert "scraper" in output
        assert ret == 0

    def test_list_shows_dash_for_empty_type(self):
        store = self._make_store_with_agent("")
        import argparse

        from forge_agent.cli.cmd_list import run

        args = argparse.Namespace(project=str(self.tmpdir / "out"))
        with patch("forge_agent.cli._helpers.get_store", return_value=store):
            captured = StringIO()
            with patch("sys.stdout", captured):
                ret = run(args)
        output = captured.getvalue()
        assert "TYPE" in output
        # Should show "-" for empty type
        lines = output.strip().split("\n")
        data_line = next(line for line in lines if "my-agent" in line)
        assert "-" in data_line
        assert ret == 0
