"""`forge-agent llm` — multi-tenant LLM management: list, show, test, set."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("llm", help="LLM management")
    sub_p = p.add_subparsers(dest="llm_cmd", required=True)

    # list
    p_list = sub_p.add_parser("list", help="List configured providers and their status")
    _add_scope_args(p_list)
    p_list.set_defaults(func=_list)

    # show
    p_show = sub_p.add_parser("show", help="Show effective config for tenant/project")
    _add_scope_args(p_show)
    p_show.set_defaults(func=_show)

    # test
    p_test = sub_p.add_parser("test", help="Test a provider with a sample prompt")
    _add_scope_args(p_test)
    p_test.add_argument("provider", help="Provider ID (e.g. deepseek)")
    p_test.add_argument(
        "--message",
        "-m",
        default="Hello, please reply with one short sentence.",
        help="Test message",
    )
    p_test.set_defaults(func=_test)

    # set
    p_set = sub_p.add_parser("set", help="Set provider config for tenant or project")
    _add_scope_args(p_set)
    p_set.add_argument("--provider", "-p", required=True, help="Provider ID")
    p_set.add_argument("--model", default=None, help="Model name")
    p_set.add_argument("--base-url", default=None, help="API base URL")
    p_set.add_argument(
        "--api-key-env", default=None, help="Environment variable holding the API key"
    )
    p_set.add_argument(
        "--enabled",
        type=_str_to_bool,
        default=None,
        help="Enable or disable the provider (true/false)",
    )
    p_set.add_argument(
        "--primary",
        action="store_true",
        help="Set this provider as the primary provider",
    )
    p_set.set_defaults(func=_set)


def _add_scope_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--tenant", default="default", help="Tenant id (default: default)")
    p.add_argument(
        "--project",
        dest="project_id",
        default=None,
        help="Project id (omit for tenant-level scope)",
    )


def _str_to_bool(value: str) -> bool:
    return value.lower() in {"true", "1", "yes", "on"}


def _resolve_project_id(args: argparse.Namespace) -> str | None:
    """Use explicit --project or infer from the current working directory."""
    if args.project_id is not None:
        return args.project_id
    cwd = Path.cwd()
    if cwd.parent.parent.parent.name == "tenants":
        return cwd.name
    return None


def _manager(args: argparse.Namespace) -> Any:
    from forge_agent.platform import LLMConfigManager, LocalTenant

    tenant = LocalTenant(args.tenant)
    return LLMConfigManager(tenant)


def _list(args: argparse.Namespace) -> int:
    manager = _manager(args)
    project_id = _resolve_project_id(args)
    cfg = manager.load(project_id)

    print(f"Tenant:  {args.tenant}")
    print(f"Project: {project_id or '(tenant-level)'}")
    print(f"Primary: {cfg.primary_id}")
    print(f"Mode:    {cfg.predict_mode}")
    print(f"Source:  {cfg.source_path or '(built-in defaults)'}")
    print()
    print(f"{'PROVIDER':<16} {'TYPE':<12} {'MODEL':<32} {'ENABLED':<8} {'KEY STATUS'}")
    print("-" * 80)
    for pid, provider in cfg.providers.items():
        envs = [provider.api_key_env] if provider.api_key_env else []
        envs.extend(provider.alt_envs)
        key_status = "—"
        for env in envs:
            if env and os.environ.get(env):
                key_status = f"{env} ✓"
                break
        else:
            key_status = "(no key needed)" if provider.type == "ollama" else "no key set"
        print(
            f"{pid:<16} {provider.type:<12} {provider.model:<32} "
            f"{provider.enabled!s:<8} {key_status}"
        )
    return 0


def _show(args: argparse.Namespace) -> int:
    manager = _manager(args)
    project_id = _resolve_project_id(args)
    cfg = manager.load(project_id)
    out = {
        "tenant": args.tenant,
        "project": project_id,
        "primary_id": cfg.primary_id,
        "predict_mode": cfg.predict_mode,
        "source_path": str(cfg.source_path) if cfg.source_path else None,
        "providers": {pid: provider.__dict__ for pid, provider in cfg.providers.items()},
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _test(args: argparse.Namespace) -> int:
    return asyncio.run(_test_async(args))


async def _test_async(args: argparse.Namespace) -> int:
    from forge_agent.llm import chat
    from forge_agent.llm.registry import get_registry

    manager = _manager(args)
    project_id = _resolve_project_id(args)
    cfg = manager.load(project_id)
    get_registry().configure(cfg)

    response = await chat(args.message, provider=args.provider)
    print(f"✓ {args.provider} ({response.model})")
    print(f"  latency: {response.latency_ms:.0f}ms")
    print(f"  tokens:  in={response.tokens_in} out={response.tokens_out}")
    print(f"  content: {response.content[:200]}")
    return 0


def _set(args: argparse.Namespace) -> int:
    manager = _manager(args)
    project_id = _resolve_project_id(args)

    if project_id is not None:
        path = manager.project_config_path(project_id)
    else:
        path = manager.tenant_config_path

    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    providers = data.setdefault("providers", {})
    provider = providers.setdefault(args.provider, {})
    provider["type"] = args.provider
    if args.model is not None:
        provider["model"] = args.model
    if args.base_url is not None:
        provider["base_url"] = args.base_url
    if args.api_key_env is not None:
        provider["api_key_env"] = args.api_key_env
    if args.enabled is not None:
        provider["enabled"] = args.enabled
    if args.primary:
        data["primary_id"] = args.provider

    if project_id is not None:
        manager.save_project(project_id, data)
        scope = "project"
    else:
        manager.save_tenant(data)
        scope = "tenant"
    print(f"Updated provider {args.provider!r} in {scope} scope.")
    return 0
