"""Forge-Agent custom exception hierarchy.

Every ForgeError carries:
  - message: what went wrong
  - hint:    how the user can fix it (shown in CLI output)

Usage::

    from forge_agent.exceptions import AgentNotFoundError
    raise AgentNotFoundError("my-agent", available=["a", "b"])
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class ForgeError(Exception):
    """Base class for all forge-agent user-facing errors."""

    default_hint: str = ""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint or self.default_hint

    def friendly(self) -> str:
        """Return a user-friendly string with hint."""
        parts = [f"Error: {self.message}"]
        if self.hint:
            parts.append(f"Hint:  {self.hint}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Registration / lookup errors
# ---------------------------------------------------------------------------

class AgentNotFoundError(ForgeError, KeyError):
    """Raised when an agent_id is not found in the registry or store."""

    default_hint = "Run 'forge-agent list' to see registered agents."

    def __init__(self, agent_id: str, *, available: list[str] | None = None, hint: str | None = None) -> None:
        msg = f"Agent {agent_id!r} not found."
        if available:
            msg += f" Available: {sorted(available)}"
        super().__init__(msg, hint=hint)
        self.agent_id = agent_id


class DuplicateRegistrationError(ForgeError, ValueError):
    """Raised when trying to register an agent_id that already exists."""

    default_hint = "Pass override=True to replace, or use a different agent_id."

    def __init__(self, agent_id: str, *, hint: str | None = None) -> None:
        super().__init__(f"Agent {agent_id!r} already registered.", hint=hint)
        self.agent_id = agent_id


class ToolNotRegisteredError(ForgeError, KeyError):
    """Raised when an MCP tool is not found in the gateway."""

    default_hint = "Run 'forge-agent mcp list-tools' to see registered tools."

    def __init__(self, tool_name: str, *, hint: str | None = None) -> None:
        super().__init__(f"Tool {tool_name!r} not registered in gateway.", hint=hint)
        self.tool_name = tool_name


class ToolDeniedError(ForgeError, PermissionError):
    """Raised when an MCP tool call is denied by permission policy."""

    default_hint = "Check your PermissionPolicy rules in the gateway configuration."

    def __init__(self, tool_name: str, reason: str = "", *, hint: str | None = None) -> None:
        msg = f"Tool {tool_name!r} denied"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, hint=hint)
        self.tool_name = tool_name


# ---------------------------------------------------------------------------
# Version / store errors
# ---------------------------------------------------------------------------

class VersionError(ForgeError, ValueError):
    """Raised for version-related problems in CodeStore."""

    default_hint = "Run 'forge-agent list' to check available versions."


class VersionNotFoundError(ForgeError, KeyError):
    """Raised when a specific version is not found."""

    default_hint = "Run 'forge-agent list' to see available versions."

    def __init__(self, agent_id: str, version: str, *, hint: str | None = None) -> None:
        super().__init__(f"Version {version!r} of {agent_id!r} not found.", hint=hint)
        self.agent_id = agent_id
        self.version = version


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class InvalidAgentTypeError(ForgeError, ValueError):
    """Raised when an invalid agent type string is provided."""

    def __init__(self, value: str, valid_types: list[str], *, hint: str | None = None) -> None:
        msg = f"Invalid agent type: {value!r}. Valid types: {valid_types}"
        default_hint = f"Use one of: {', '.join(valid_types)}"
        super().__init__(msg, hint=hint or default_hint)
        self.value = value


class ProviderNotConfiguredError(ForgeError, KeyError):
    """Raised when an LLM provider is not configured."""

    default_hint = "Add the provider to your forge-agent config or set the API key env var."

    def __init__(self, provider_id: str, *, available: list[str] | None = None, hint: str | None = None) -> None:
        msg = f"Provider {provider_id!r} not configured."
        if available:
            msg += f" Available: {available}"
        super().__init__(msg, hint=hint)
        self.provider_id = provider_id


# ---------------------------------------------------------------------------
# Prompt errors
# ---------------------------------------------------------------------------

class PromptNotFoundError(ForgeError, KeyError):
    """Raised when no prompt is found for an agent."""

    default_hint = "Register a prompt with PromptStore or CapabilitiesRegistry."

    def __init__(self, agent_id: str, *, hint: str | None = None) -> None:
        super().__init__(f"No prompt found for agent {agent_id!r}.", hint=hint)
        self.agent_id = agent_id


class PromptVariableError(ForgeError, KeyError):
    """Raised when a required prompt template variable is missing."""

    def __init__(self, agent_id: str, variable: str, *, hint: str | None = None) -> None:
        msg = f"Missing variable {variable!r} for prompt {agent_id!r}."
        default_hint = f"Pass {variable!r} when rendering the prompt template."
        super().__init__(msg, hint=hint or default_hint)
        self.agent_id = agent_id
        self.variable = variable


class PromptFileNotFoundError(ForgeError, FileNotFoundError):
    """Raised when a prompt .j2 template file is missing."""

    default_hint = "Check that the .j2 file exists at the expected path."

    def __init__(self, path: str, *, hint: str | None = None) -> None:
        super().__init__(f"Prompt file not found: {path}", hint=hint)
        self.path = path


# ---------------------------------------------------------------------------
# Pipeline errors
# ---------------------------------------------------------------------------

class PipelineNodeNotFoundError(ForgeError, KeyError):
    """Raised when a pipeline node is not found."""

    def __init__(self, node_id: str, *, hint: str | None = None) -> None:
        super().__init__(f"Pipeline node {node_id!r} not found.", hint=hint or "Check node IDs in your pipeline definition.")
        self.node_id = node_id


class DuplicateNodeError(ForgeError, ValueError):
    """Raised when a duplicate node_id is added to a pipeline."""

    def __init__(self, node_id: str, *, hint: str | None = None) -> None:
        super().__init__(f"Duplicate pipeline node: {node_id!r}", hint=hint or "Each node must have a unique node_id.")
        self.node_id = node_id


# ---------------------------------------------------------------------------
# MCP errors
# ---------------------------------------------------------------------------

class MCPToolCallError(ForgeError, RuntimeError):
    """Raised when an MCP tool call fails."""

    default_hint = "Check the MCP server logs for details."

    def __init__(self, tool_name: str, reason: str, *, hint: str | None = None) -> None:
        super().__init__(f"MCP tool {tool_name!r} call failed: {reason}", hint=hint)
        self.tool_name = tool_name


class MCPNotConnectedError(ForgeError, ConnectionError):
    """Raised when trying to call a tool on a disconnected MCP client."""

    default_hint = "Call connect() before calling tools."

    def __init__(self, *, hint: str | None = None) -> None:
        super().__init__("MCPClient is not connected.", hint=hint)


class MissingDependencyError(ForgeError, ImportError):
    """Raised when an optional dependency is not installed."""

    def __init__(self, package: str, extra: str, *, hint: str | None = None) -> None:
        msg = f"The '{package}' package is required."
        default_hint = f"Install it with: pip install 'forge-agent[{extra}]'"
        super().__init__(msg, hint=hint or default_hint)
        self.package = package
        self.extra = extra


# ---------------------------------------------------------------------------
# File / path errors
# ---------------------------------------------------------------------------

class GeneratedDirNotFoundError(ForgeError, FileNotFoundError):
    """Raised when the generated_agents/ directory is missing."""

    default_hint = "Run 'forge-agent generate' first, or create the directory."

    def __init__(self, path: str, *, hint: str | None = None) -> None:
        super().__init__(f"No generated_agents/ directory at {path}.", hint=hint)
        self.path = path
