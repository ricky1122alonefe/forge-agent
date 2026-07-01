"""Tests for forge_agent.cli.cmd_llm."""

from __future__ import annotations

import argparse
import json

import pytest

from forge_agent.cli import cmd_llm


@pytest.fixture
def temp_root(monkeypatch, tmp_path):
    from forge_agent.platform.local_tenant import LocalTenant

    monkeypatch.setattr(LocalTenant, "DEFAULT_ROOT", tmp_path)
    return tmp_path


def test_set_tenant(temp_root, capsys):
    args = argparse.Namespace(
        tenant="acme",
        project_id=None,
        provider="openai",
        model="gpt-4o",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        enabled=True,
        primary=True,
    )
    assert cmd_llm._set(args) == 0
    captured = capsys.readouterr()
    assert "Updated provider" in captured.out

    path = temp_root / "tenants" / "acme" / "llm_providers.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["primary_id"] == "openai"
    assert data["providers"]["openai"]["model"] == "gpt-4o"


def test_set_project(temp_root, capsys):
    from forge_agent.platform import LocalTenant

    tenant = LocalTenant("acme")
    tenant.create_project("demo")

    args = argparse.Namespace(
        tenant="acme",
        project_id="demo",
        provider="deepseek",
        model="deepseek-reasoner",
        base_url=None,
        api_key_env=None,
        enabled=None,
        primary=True,
    )
    assert cmd_llm._set(args) == 0

    path = temp_root / "tenants" / "acme" / "projects" / "demo" / "llm_providers.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["primary_id"] == "deepseek"


def test_show_tenant(temp_root, capsys):
    tenant_dir = temp_root / "tenants" / "acme"
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "llm_providers.json").write_text(
        json.dumps({"primary_id": "openai"}),
        encoding="utf-8",
    )
    args = argparse.Namespace(tenant="acme", project_id=None)
    assert cmd_llm._show(args) == 0
    captured = capsys.readouterr()
    assert "openai" in captured.out


def test_list_tenant(temp_root, capsys):
    tenant_dir = temp_root / "tenants" / "acme"
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "llm_providers.json").write_text(
        json.dumps({"primary_id": "openai"}),
        encoding="utf-8",
    )
    args = argparse.Namespace(tenant="acme", project_id=None)
    assert cmd_llm._list(args) == 0
    captured = capsys.readouterr()
    assert "openai" in captured.out
    assert "deepseek" in captured.out


def test_resolve_project_id_from_cwd(monkeypatch, tmp_path):
    project_root = tmp_path / "tenants" / "acme" / "projects" / "demo"
    project_root.mkdir(parents=True)
    monkeypatch.chdir(project_root)
    args = argparse.Namespace(project_id=None)
    assert cmd_llm._resolve_project_id(args) == "demo"


def test_resolve_project_id_prefers_explicit():
    args = argparse.Namespace(project_id="explicit")
    assert cmd_llm._resolve_project_id(args) == "explicit"
