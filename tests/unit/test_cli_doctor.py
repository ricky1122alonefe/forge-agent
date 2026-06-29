"""Tests for T3.6 — forge-agent doctor command."""

from __future__ import annotations

import argparse
import json
import os
import sys
from unittest.mock import patch

from forge_agent.cli.cmd_doctor import (
    CheckResult,
    _check_forge_agent,
    _check_generated_dir,
    _check_llm_config,
    _check_optional_dep,
    _check_python_version,
    _check_sqlite,
    run,
)

# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_ok(self):
        r = CheckResult("test", True, "all good")
        assert "✓" in str(r)
        assert "all good" in str(r)

    def test_fail_with_hint(self):
        r = CheckResult("test", False, "broken", hint="fix it")
        text = str(r)
        assert "✗" in text
        assert "broken" in text
        assert "fix it" in text

    def test_fail_no_hint(self):
        r = CheckResult("test", False, "broken")
        text = str(r)
        assert "✗" in text
        assert "→" not in text


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


class TestCheckPythonVersion:
    def test_current_version(self):
        r = _check_python_version()
        # Just check it returns a valid result with version info
        assert isinstance(r.ok, bool)
        assert "." in r.message

    def test_old_version(self):
        import collections

        FakeVersion = collections.namedtuple("FakeVersion", ["major", "minor", "micro"])
        with patch.object(sys, "version_info", FakeVersion(3, 9, 0)):
            r = _check_python_version()
            assert r.ok is False
            assert "3.10" in r.hint

    def test_new_version(self):
        import collections

        FakeVersion = collections.namedtuple("FakeVersion", ["major", "minor", "micro"])
        with patch.object(sys, "version_info", FakeVersion(3, 12, 0)):
            r = _check_python_version()
            assert r.ok is True


class TestCheckForgeAgent:
    def test_installed(self):
        r = _check_forge_agent()
        assert r.ok is True
        assert "v" in r.message


class TestCheckOptionalDep:
    def test_installed(self):
        # json is always available
        r = _check_optional_dep("json", "test")
        assert r.ok is True

    def test_not_installed(self):
        r = _check_optional_dep("nonexistent_package_xyz", "test")
        assert r.ok is False
        assert "pip install" in r.hint


class TestCheckSqlite:
    def test_available(self):
        r = _check_sqlite()
        assert r.ok is True


class TestCheckGeneratedDir:
    def test_missing(self, tmp_path):
        r = _check_generated_dir(tmp_path)
        assert r.ok is False
        assert "forge-agent generate" in r.hint

    def test_exists_no_manifest(self, tmp_path):
        (tmp_path / "generated_agents").mkdir()
        r = _check_generated_dir(tmp_path)
        assert r.ok is True
        assert "no manifest" in r.message

    def test_exists_with_manifest(self, tmp_path):
        d = tmp_path / "generated_agents"
        d.mkdir()
        manifest = {"agents": {"a1": {}, "a2": {}}}
        (d / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        r = _check_generated_dir(tmp_path)
        assert r.ok is True
        assert "2 agent(s)" in r.message


class TestCheckLLMConfig:
    def test_no_config(self, tmp_path):
        results = _check_llm_config(tmp_path)
        assert len(results) == 1
        assert results[0].ok is False
        assert "not found" in results[0].message

    def test_invalid_json(self, tmp_path):
        (tmp_path / "llm_providers.json").write_text("{invalid", encoding="utf-8")
        results = _check_llm_config(tmp_path)
        assert any("invalid" in r.message for r in results if not r.ok)

    def test_valid_config_with_key(self, tmp_path):
        config = {
            "providers": {
                "deepseek": {
                    "type": "deepseek",
                    "enabled": True,
                    "api_key_env": "TEST_DOCTOR_KEY",
                }
            }
        }
        (tmp_path / "llm_providers.json").write_text(json.dumps(config), encoding="utf-8")
        with patch.dict(os.environ, {"TEST_DOCTOR_KEY": "sk-1234567890abcdef"}):
            results = _check_llm_config(tmp_path)
        # Should have: config file OK, JSON OK, API key OK
        assert all(r.ok for r in results)

    def test_valid_config_missing_key(self, tmp_path):
        config = {
            "providers": {
                "deepseek": {
                    "type": "deepseek",
                    "enabled": True,
                    "api_key_env": "TEST_DOCTOR_MISSING_KEY",
                }
            }
        }
        (tmp_path / "llm_providers.json").write_text(json.dumps(config), encoding="utf-8")
        # Ensure the key is NOT set
        env = os.environ.copy()
        env.pop("TEST_DOCTOR_MISSING_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            results = _check_llm_config(tmp_path)
        key_results = [r for r in results if "API key" in r.name]
        assert len(key_results) == 1
        assert key_results[0].ok is False

    def test_disabled_provider_skipped(self, tmp_path):
        config = {
            "providers": {
                "ollama": {
                    "type": "ollama",
                    "enabled": False,
                    "api_key_env": "SHOULD_NOT_CHECK",
                }
            }
        }
        (tmp_path / "llm_providers.json").write_text(json.dumps(config), encoding="utf-8")
        results = _check_llm_config(tmp_path)
        key_results = [r for r in results if "API key" in r.name]
        assert len(key_results) == 0

    def test_env_var_config_path(self, tmp_path):
        config_file = tmp_path / "custom_config.json"
        config = {"providers": {}}
        config_file.write_text(json.dumps(config), encoding="utf-8")
        with patch.dict(os.environ, {"FORGE_LLM_CONFIG": str(config_file)}):
            results = _check_llm_config(tmp_path)
        assert results[0].ok is True
        assert str(config_file) in results[0].message


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------


class TestDoctorRun:
    def test_run_returns_int(self, tmp_path, capsys):
        args = argparse.Namespace(project=tmp_path, fix=False)
        result = run(args)
        assert isinstance(result, int)
        captured = capsys.readouterr()
        assert "forge-agent doctor" in captured.out
        assert "Results:" in captured.out

    def test_run_with_generated_dir(self, tmp_path, capsys):
        (tmp_path / "generated_agents").mkdir()
        args = argparse.Namespace(project=tmp_path, fix=False)
        run(args)
        captured = capsys.readouterr()
        assert "generated_agents/" in captured.out

    def test_run_output_format(self, tmp_path, capsys):
        args = argparse.Namespace(project=tmp_path, fix=False)
        run(args)
        captured = capsys.readouterr()
        # Should have the header
        assert "=" * 50 in captured.out
        # Should have check marks
        assert "✓" in captured.out or "✗" in captured.out
        # Should have summary
        assert "passed" in captured.out
        assert "total" in captured.out
