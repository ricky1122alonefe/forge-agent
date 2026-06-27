"""Tests for T3.3 — ForgeError hierarchy and user-friendly error messages."""

from __future__ import annotations

import pytest

from forge_agent.exceptions import (
    AgentNotFoundError,
    DuplicateNodeError,
    DuplicateRegistrationError,
    ForgeError,
    GeneratedDirNotFoundError,
    InvalidAgentTypeError,
    MCPNotConnectedError,
    MCPToolCallError,
    MissingDependencyError,
    PipelineNodeNotFoundError,
    PromptFileNotFoundError,
    PromptNotFoundError,
    PromptVariableError,
    ProviderNotConfiguredError,
    ToolDeniedError,
    ToolNotRegisteredError,
    VersionError,
    VersionNotFoundError,
)


# ---------------------------------------------------------------------------
# ForgeError base
# ---------------------------------------------------------------------------

class TestForgeError:
    def test_message_and_hint(self):
        err = ForgeError("something broke", hint="try again")
        assert str(err) == "something broke"
        assert err.message == "something broke"
        assert err.hint == "try again"

    def test_default_hint(self):
        err = ForgeError("oops")
        assert err.hint == ""

    def test_friendly_output(self):
        err = ForgeError("bad input", hint="check your config")
        text = err.friendly()
        assert "Error: bad input" in text
        assert "Hint:  check your config" in text

    def test_friendly_without_hint(self):
        err = ForgeError("bad input")
        text = err.friendly()
        assert "Error: bad input" in text
        assert "Hint:" not in text

    def test_is_exception(self):
        assert issubclass(ForgeError, Exception)


# ---------------------------------------------------------------------------
# AgentNotFoundError
# ---------------------------------------------------------------------------

class TestAgentNotFoundError:
    def test_basic(self):
        err = AgentNotFoundError("my-agent")
        assert "my-agent" in str(err)
        assert "not found" in str(err).lower()
        assert err.agent_id == "my-agent"

    def test_with_available(self):
        err = AgentNotFoundError("x", available=["a", "b"])
        assert "['a', 'b']" in str(err)

    def test_is_key_error(self):
        assert issubclass(AgentNotFoundError, KeyError)
        assert issubclass(AgentNotFoundError, ForgeError)

    def test_default_hint(self):
        err = AgentNotFoundError("x")
        assert "forge-agent list" in err.hint


# ---------------------------------------------------------------------------
# DuplicateRegistrationError
# ---------------------------------------------------------------------------

class TestDuplicateRegistrationError:
    def test_basic(self):
        err = DuplicateRegistrationError("dup-agent")
        assert "dup-agent" in str(err)
        assert err.agent_id == "dup-agent"

    def test_is_value_error(self):
        assert issubclass(DuplicateRegistrationError, ValueError)

    def test_default_hint(self):
        err = DuplicateRegistrationError("x")
        assert "override" in err.hint.lower()


# ---------------------------------------------------------------------------
# InvalidAgentTypeError
# ---------------------------------------------------------------------------

class TestInvalidAgentTypeError:
    def test_basic(self):
        err = InvalidAgentTypeError("bad", ["scraper", "monitor"])
        assert "bad" in str(err)
        assert "scraper" in str(err)
        assert err.value == "bad"

    def test_is_value_error(self):
        assert issubclass(InvalidAgentTypeError, ValueError)

    def test_hint_lists_types(self):
        err = InvalidAgentTypeError("x", ["a", "b"])
        assert "a" in err.hint and "b" in err.hint


# ---------------------------------------------------------------------------
# Version errors
# ---------------------------------------------------------------------------

class TestVersionErrors:
    def test_version_error(self):
        err = VersionError("no previous version")
        assert issubclass(VersionError, ValueError)
        assert issubclass(VersionError, ForgeError)

    def test_version_not_found_error(self):
        err = VersionNotFoundError("agent1", "v3")
        assert "v3" in str(err)
        assert "agent1" in str(err)
        assert err.agent_id == "agent1"
        assert err.version == "v3"
        assert issubclass(VersionNotFoundError, KeyError)


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------

class TestProviderNotConfiguredError:
    def test_basic(self):
        err = ProviderNotConfiguredError("gpt4")
        assert "gpt4" in str(err)
        assert err.provider_id == "gpt4"

    def test_with_available(self):
        err = ProviderNotConfiguredError("gpt4", available=["deepseek", "ollama"])
        assert "deepseek" in str(err)

    def test_is_key_error(self):
        assert issubclass(ProviderNotConfiguredError, KeyError)


# ---------------------------------------------------------------------------
# Prompt errors
# ---------------------------------------------------------------------------

class TestPromptErrors:
    def test_prompt_not_found(self):
        err = PromptNotFoundError("agent-x")
        assert "agent-x" in str(err)
        assert err.agent_id == "agent-x"
        assert issubclass(PromptNotFoundError, KeyError)

    def test_prompt_variable_error(self):
        err = PromptVariableError("agent-x", "name")
        assert "name" in str(err)
        assert err.variable == "name"
        assert "name" in err.hint

    def test_prompt_file_not_found(self):
        err = PromptFileNotFoundError("/path/to/file.j2")
        assert "/path/to/file.j2" in str(err)
        assert err.path == "/path/to/file.j2"
        assert issubclass(PromptFileNotFoundError, FileNotFoundError)


# ---------------------------------------------------------------------------
# Pipeline errors
# ---------------------------------------------------------------------------

class TestPipelineErrors:
    def test_node_not_found(self):
        err = PipelineNodeNotFoundError("node-99")
        assert "node-99" in str(err)
        assert err.node_id == "node-99"
        assert issubclass(PipelineNodeNotFoundError, KeyError)

    def test_duplicate_node(self):
        err = DuplicateNodeError("dup-node")
        assert "dup-node" in str(err)
        assert err.node_id == "dup-node"
        assert issubclass(DuplicateNodeError, ValueError)


# ---------------------------------------------------------------------------
# MCP errors
# ---------------------------------------------------------------------------

class TestMCPErrors:
    def test_tool_not_registered(self):
        err = ToolNotRegisteredError("search")
        assert "search" in str(err)
        assert err.tool_name == "search"
        assert issubclass(ToolNotRegisteredError, KeyError)

    def test_tool_denied(self):
        err = ToolDeniedError("rm", "write not allowed")
        assert "rm" in str(err)
        assert "write not allowed" in str(err)
        assert err.tool_name == "rm"
        assert issubclass(ToolDeniedError, PermissionError)

    def test_tool_denied_no_reason(self):
        err = ToolDeniedError("rm")
        assert "rm" in str(err)

    def test_tool_call_error(self):
        err = MCPToolCallError("read_file", "timeout")
        assert "read_file" in str(err)
        assert "timeout" in str(err)
        assert err.tool_name == "read_file"
        assert issubclass(MCPToolCallError, RuntimeError)

    def test_not_connected(self):
        err = MCPNotConnectedError()
        assert "not connected" in str(err).lower()
        assert issubclass(MCPNotConnectedError, ConnectionError)

    def test_missing_dependency(self):
        err = MissingDependencyError("mcp", "mcp")
        assert "mcp" in str(err)
        assert "pip install" in err.hint
        assert err.package == "mcp"
        assert err.extra == "mcp"
        assert issubclass(MissingDependencyError, ImportError)


# ---------------------------------------------------------------------------
# File errors
# ---------------------------------------------------------------------------

class TestFileErrors:
    def test_generated_dir_not_found(self):
        err = GeneratedDirNotFoundError("/tmp/foo")
        assert "/tmp/foo" in str(err)
        assert err.path == "/tmp/foo"
        assert "forge-agent generate" in err.hint
        assert issubclass(GeneratedDirNotFoundError, FileNotFoundError)


# ---------------------------------------------------------------------------
# Integration: raise sites use ForgeError subclasses
# ---------------------------------------------------------------------------

class TestRaiseSites:
    """Verify that actual code paths raise ForgeError subclasses."""

    def test_registry_agent_not_found(self):
        from forge_agent.registry.registry import AgentRegistry
        # Reset singleton for clean test
        AgentRegistry._instance = None
        reg = AgentRegistry()
        with pytest.raises(AgentNotFoundError) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(reg.get("nonexistent"))
        assert "nonexistent" in str(exc_info.value)
        # Cleanup
        AgentRegistry._instance = None

    def test_registry_duplicate(self):
        from forge_agent.registry.registry import AgentRegistry
        from forge_agent.core.base import BaseAgent

        AgentRegistry._instance = None
        reg = AgentRegistry()

        class FakeAgent(BaseAgent):
            agent_id = "test-dup-t33"
            async def observe(self, ctx): return {}
            async def decide(self, ctx, obs): return {}
            async def act(self, ctx, decision): return {}

        reg.register(FakeAgent)
        with pytest.raises(DuplicateRegistrationError):
            reg.register(FakeAgent)
        AgentRegistry._instance = None

    def test_agent_type_invalid(self):
        from forge_agent.core.agent_type import AgentType
        with pytest.raises(InvalidAgentTypeError):
            AgentType.from_string("nonexistent_type")

    def test_pipeline_duplicate_node(self):
        from forge_agent.pipeline.pipeline import Pipeline, PipelineNode, NodeType
        p = Pipeline(pipeline_id="test")
        node = PipelineNode(node_id="n1", node_type=NodeType.FUNCTION)
        p.add_node(node)
        with pytest.raises(DuplicateNodeError):
            p.add_node(node)

    def test_pipeline_node_not_found(self):
        from forge_agent.pipeline.pipeline import Pipeline
        p = Pipeline(pipeline_id="test")
        with pytest.raises(PipelineNodeNotFoundError):
            p.add_edge("a", "b")

    def test_gateway_tool_not_registered(self):
        from forge_agent.mcp.gateway import MCPGateway
        gw = MCPGateway()
        with pytest.raises(ToolNotRegisteredError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(gw.call("nonexistent"))

    def test_gateway_tool_denied(self):
        from forge_agent.mcp.gateway import MCPGateway
        from forge_agent.mcp.permissions import PermissionPolicy

        gw = MCPGateway()

        async def dummy(args):
            return {"ok": True}

        policy = PermissionPolicy().deny("blocked_tool", reason="blocked for testing")
        gw.register_tool("blocked_tool", dummy, policy=policy)
        with pytest.raises(ToolDeniedError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(gw.call("blocked_tool"))

    def test_scheduler_duplicate_task(self):
        from forge_agent.scheduler.scheduler import Scheduler
        from forge_agent.scheduler.tasks import ScheduleTask
        from forge_agent.core.context import AgentContext
        s = Scheduler()
        ctx = AgentContext(scope_id="s1", config={})
        task = ScheduleTask(task_id="t1", agent_id="a1", context=ctx)
        s.add_task(task)
        with pytest.raises(DuplicateRegistrationError):
            s.add_task(task)

    def test_store_activate_not_found(self, tmp_path):
        from forge_agent.generator.store import FileCodeStore
        store = FileCodeStore(tmp_path)
        with pytest.raises(AgentNotFoundError):
            store.activate("nonexistent", "v1")

    def test_store_activate_version_not_found(self, tmp_path):
        from forge_agent.generator.store import FileCodeStore
        store = FileCodeStore(tmp_path)
        store.save("agent1", "print('hello')")
        with pytest.raises(VersionNotFoundError):
            store.activate("agent1", "v99")

    def test_store_rollback_no_previous(self, tmp_path):
        from forge_agent.generator.store import FileCodeStore
        store = FileCodeStore(tmp_path)
        store.save("agent1", "print('v1')")
        with pytest.raises(VersionError):
            store.rollback("agent1")

    def test_store_delete_only_version(self, tmp_path):
        from forge_agent.generator.store import FileCodeStore
        store = FileCodeStore(tmp_path)
        store.save("agent1", "print('v1')")
        with pytest.raises(VersionError):
            store.delete_version("agent1", "v1")

    def test_prompt_store_not_found(self, tmp_path):
        from forge_agent.prompt.store import FilePromptStore
        ps = FilePromptStore(tmp_path)
        with pytest.raises(PromptNotFoundError):
            ps.get("nonexistent")

    def test_prompt_store_file_not_found(self, tmp_path):
        from forge_agent.prompt.store import FilePromptStore
        ps = FilePromptStore(tmp_path)
        ps.register("agent1", "v1", "Hello {name}")
        # Delete the file to trigger PromptFileNotFoundError
        import os
        os.unlink(tmp_path / "agent1" / "v1.j2")
        with pytest.raises(PromptFileNotFoundError):
            ps.get("agent1", version="v1")

    def test_prompt_store_missing_variable(self, tmp_path):
        from forge_agent.prompt.store import FilePromptStore
        ps = FilePromptStore(tmp_path)
        ps.register("agent1", "v1", "Hello {name}")
        with pytest.raises(PromptVariableError):
            ps.render("agent1", {})

    def test_capabilities_prompt_not_found(self):
        from forge_agent.core.capabilities import InMemoryPromptManager
        pm = InMemoryPromptManager()
        with pytest.raises(PromptNotFoundError):
            pm.get("nonexistent")

    def test_capabilities_missing_variable(self):
        from forge_agent.core.capabilities import InMemoryPromptManager
        pm = InMemoryPromptManager()
        pm.register("a1", "v1", "Hello {name}")
        with pytest.raises(PromptVariableError):
            pm.render("a1", {})

    def test_helpers_generated_dir_not_found(self, tmp_path):
        from forge_agent.cli._helpers import get_store
        with pytest.raises(GeneratedDirNotFoundError):
            get_store(tmp_path)


# ---------------------------------------------------------------------------
# All ForgeError subclasses are catchable as ForgeError
# ---------------------------------------------------------------------------

class TestCatchAsForgeError:
    """All custom exceptions should be catchable via `except ForgeError`."""

    @pytest.mark.parametrize("exc_class,args", [
        (AgentNotFoundError, ("x",)),
        (DuplicateRegistrationError, ("x",)),
        (InvalidAgentTypeError, ("x", ["a"])),
        (VersionError, ("msg",)),
        (VersionNotFoundError, ("x", "v1")),
        (ProviderNotConfiguredError, ("x",)),
        (PromptNotFoundError, ("x",)),
        (PromptVariableError, ("x", "v")),
        (PromptFileNotFoundError, ("/p",)),
        (PipelineNodeNotFoundError, ("x",)),
        (DuplicateNodeError, ("x",)),
        (ToolNotRegisteredError, ("x",)),
        (ToolDeniedError, ("x",)),
        (MCPToolCallError, ("x", "r")),
        (MCPNotConnectedError, ()),
        (MissingDependencyError, ("pkg", "ext")),
        (GeneratedDirNotFoundError, ("/p",)),
    ])
    def test_catchable_as_forge_error(self, exc_class, args):
        with pytest.raises(ForgeError):
            raise exc_class(*args)

    @pytest.mark.parametrize("exc_class,args", [
        (AgentNotFoundError, ("x",)),
        (DuplicateRegistrationError, ("x",)),
        (InvalidAgentTypeError, ("x", ["a"])),
        (VersionError, ("msg",)),
        (VersionNotFoundError, ("x", "v1")),
        (ProviderNotConfiguredError, ("x",)),
        (PromptNotFoundError, ("x",)),
        (PromptVariableError, ("x", "v")),
        (PromptFileNotFoundError, ("/p",)),
        (PipelineNodeNotFoundError, ("x",)),
        (DuplicateNodeError, ("x",)),
        (ToolNotRegisteredError, ("x",)),
        (ToolDeniedError, ("x",)),
        (MCPToolCallError, ("x", "r")),
        (MCPNotConnectedError, ()),
        (MissingDependencyError, ("pkg", "ext")),
        (GeneratedDirNotFoundError, ("/p",)),
    ])
    def test_all_have_friendly(self, exc_class, args):
        err = exc_class(*args)
        text = err.friendly()
        assert "Error:" in text
