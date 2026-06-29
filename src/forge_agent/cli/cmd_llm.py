"""`forge-agent llm` — LLM management: list, test, config."""

from __future__ import annotations

import argparse
import asyncio


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("llm", help="LLM management")
    sub_p = p.add_subparsers(dest="llm_cmd", required=True)

    # list
    p_list = sub_p.add_parser("list", help="List configured providers and their status")
    p_list.set_defaults(func=_list)

    # test
    p_test = sub_p.add_parser("test", help="Test a provider with a sample prompt")
    p_test.add_argument("provider", help="Provider ID (e.g. deepseek)")
    p_test.add_argument(
        "--message",
        "-m",
        default="Hello, please reply with one short sentence.",
        help="Test message",
    )
    p_test.set_defaults(func=_test)

    # config
    p_config = sub_p.add_parser("config", help="Show effective config")
    p_config.set_defaults(func=_config)


def _list(args: argparse.Namespace) -> int:
    import os

    from forge_agent.llm.config import load_config

    cfg = load_config()
    print(f"Primary:  {cfg.primary_id}")
    print(f"Mode:     {cfg.predict_mode}")
    print(f"Source:   {cfg.source_path or '(built-in defaults)'}")
    print()
    print(f"{'PROVIDER':<16} {'TYPE':<12} {'MODEL':<32} {'ENABLED':<8} {'KEY STATUS'}")
    print("-" * 80)
    for pid, p in cfg.providers.items():
        envs = [p.api_key_env] if p.api_key_env else []
        envs.extend(p.alt_envs)
        key_status = "—"
        for env in envs:
            if env and os.environ.get(env):
                key_status = f"{env} ✓"
                break
        else:
            key_status = "(no key needed)" if p.type == "ollama" else "no key set"
        print(f"{pid:<16} {p.type:<12} {p.model:<32} {p.enabled!s:<8} {key_status}")
    return 0


def _test(args: argparse.Namespace) -> int:
    return asyncio.run(_test_async(args))


async def _test_async(args: argparse.Namespace) -> int:
    from forge_agent.llm import chat

    try:
        r = await chat(args.message, provider=args.provider)
    except Exception as exc:
        print(f"❌ {args.provider}: {exc}")
        return 1
    print(f"✓ {args.provider} ({r.model})")
    print(f"  latency: {r.latency_ms:.0f}ms")
    print(f"  tokens:  in={r.tokens_in} out={r.tokens_out}")
    print(f"  content: {r.content[:200]}")
    return 0


def _config(args: argparse.Namespace) -> int:
    import json as _json

    from forge_agent.llm.config import load_config

    cfg = load_config()
    out = {
        "primary_id": cfg.primary_id,
        "predict_mode": cfg.predict_mode,
        "source_path": str(cfg.source_path) if cfg.source_path else None,
        "providers": {pid: p.__dict__ for pid, p in cfg.providers.items()},
    }
    print(_json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0
