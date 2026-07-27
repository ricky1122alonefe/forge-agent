"""Smoke tests for the MCP gateway (S2 safety net).

Covers the core tool lifecycle: register → call → list, plus permission
enforcement and error paths. No external MCP server required.

Key behavior: empty PermissionPolicy = default DENY. Tools must have an
explicit allow rule to be callable.
"""

from __future__ import annotations

import pytest

from forge_agent.exceptions import ToolDeniedError, ToolNotRegisteredError
from forge_agent.mcp.gateway import MCPGateway
from forge_agent.mcp.permissions import PermissionPolicy, PermissionRule


def _allow(tool: str) -> PermissionPolicy:
    """Convenience: a policy that allows one tool."""
    return PermissionPolicy().allow(tool)


class TestToolLifecycle:
    """register → list → call happy path (with explicit allow)."""

    async def test_register_and_list(self) -> None:
        gw = MCPGateway()

        async def handler(args: dict) -> dict:
            return {"echo": args.get("msg", "")}

        gw.register_tool("tavily.search", handler, policy=_allow("tavily.search"))
        assert "tavily.search" in gw.list_tools()

    async def test_call_returns_handler_result(self) -> None:
        gw = MCPGateway()

        async def handler(args: dict) -> dict:
            return {"result": f"got {args['q']}"}

        gw.register_tool("echo", handler, policy=_allow("echo"))
        result = await gw.call("echo", {"q": "hello"})
        assert result == {"result": "got hello"}

    async def test_call_with_no_args(self) -> None:
        gw = MCPGateway()

        async def handler(args: dict) -> dict:
            return {"ok": True}

        gw.register_tool("ping", handler, policy=_allow("ping"))
        result = await gw.call("ping")
        assert result == {"ok": True}


class TestErrors:
    async def test_call_unregistered_raises(self) -> None:
        gw = MCPGateway()
        with pytest.raises(ToolNotRegisteredError):
            await gw.call("nope")

    async def test_set_policy_on_unknown_raises(self) -> None:
        gw = MCPGateway()
        with pytest.raises(ToolNotRegisteredError):
            gw.set_policy("ghost", PermissionPolicy())


class TestPermissions:
    def test_permission_rule_exact_match(self) -> None:
        rule = PermissionRule(action="allow", tool="tavily.search")
        assert rule.matches("tavily.search")
        assert not rule.matches("tavily.other")

    def test_permission_rule_wildcard(self) -> None:
        rule = PermissionRule(action="allow", tool="db.*")
        assert rule.matches("db.query")
        assert rule.matches("db.write")
        assert not rule.matches("cache.get")

    def test_policy_allow_then_deny(self) -> None:
        # first-match-wins: deny must come before broader allow
        policy = PermissionPolicy().deny("tavily.delete", "deletes are forbidden").allow("tavily.*")
        allowed, _ = policy.check("tavily.search")
        assert allowed is True
        denied, reason = policy.check("tavily.delete")
        assert denied is False
        assert "forbidden" in reason

    def test_empty_policy_denies_by_default(self) -> None:
        """No rules = default deny (fail-closed)."""
        policy = PermissionPolicy()
        allowed, reason = policy.check("any.tool")
        assert allowed is False
        assert reason  # non-empty reason

    async def test_gateway_denies_without_allow_rule(self) -> None:
        """Tools registered without an allow policy are denied by default."""
        gw = MCPGateway()

        async def handler(args: dict) -> dict:
            return {"ok": True}

        gw.register_tool("locked.tool", handler)  # no policy = default deny
        with pytest.raises(ToolDeniedError):
            await gw.call("locked.tool")

    async def test_gateway_allows_with_explicit_policy(self) -> None:
        gw = MCPGateway()

        async def handler(args: dict) -> dict:
            return {"ok": True}

        gw.register_tool("free.tool", handler, policy=_allow("free.tool"))
        result = await gw.call("free.tool")
        assert result == {"ok": True}
