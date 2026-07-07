"""Smoke runner must work inside FastAPI's running event loop."""

from __future__ import annotations

import asyncio

from forge_agent.agent_spec.generator import generate_spec_rule_based
from forge_agent.agent_spec.smoke import smoke_run_spec_sync
from forge_agent.agent_spec.writer import apply_spec
from forge_agent.platform import LocalTenant


async def _in_async_context() -> None:
    spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="async_smoke")
    result = smoke_run_spec_sync(spec)
    assert result["success"] is True


class TestSmokeInAsyncContext:
    def test_smoke_run_spec_sync_inside_running_loop(self) -> None:
        asyncio.run(_in_async_context())

    def test_apply_spec_ci_inside_running_loop(self, tmp_path) -> None:
        async def _apply() -> None:
            tenant = LocalTenant("t", root_dir=tmp_path / "data")
            root = tenant.create_project("demo")
            spec = generate_spec_rule_based("搜索 popmart 舆情", agent_id="async_apply")
            result = apply_spec(root, spec, ci_gate=True, auto_repair=True, judge_gate=True)
            assert result["success"] is True

        asyncio.run(_apply())
