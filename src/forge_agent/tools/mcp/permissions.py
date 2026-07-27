"""Permission model for MCP tool access.

Two layers:
    1. Agent-level: what tools an agent_class can declare.
    2. Run-level:   what tools a specific run can invoke.

Both are expressed as PermissionRule lists. The MCPGateway enforces them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Scope = Literal["agent", "run"]


@dataclass(frozen=True)
class PermissionRule:
    """Allow or deny a specific tool pattern.

    Examples:
        PermissionRule(action="allow", tool="tavily.search")
        PermissionRule(action="allow", tool="db.*")
        PermissionRule(action="deny",  tool="db.drop_*")
    """

    action: Literal["allow", "deny"]
    tool: str
    reason: str = ""

    def matches(self, tool: str) -> bool:
        if self.tool == tool:
            return True
        if self.tool.endswith(".*"):
            prefix = self.tool[:-2]
            return tool.startswith(prefix + ".") or tool == prefix
        if self.tool.startswith("*"):
            return tool.endswith(self.tool[1:])
        return False


@dataclass
class PermissionPolicy:
    """Ordered set of rules. First-match-wins. Deny rules should be listed last."""

    rules: list[PermissionRule] = field(default_factory=list)

    def allow(self, tool: str, reason: str = "") -> PermissionPolicy:
        self.rules.append(PermissionRule(action="allow", tool=tool, reason=reason))
        return self

    def deny(self, tool: str, reason: str = "") -> PermissionPolicy:
        self.rules.append(PermissionRule(action="deny", tool=tool, reason=reason))
        return self

    def check(self, tool: str) -> tuple[bool, str]:
        """Return (allowed, matched_rule_reason)."""
        for rule in self.rules:
            if rule.matches(tool):
                return (rule.action == "allow"), rule.reason
        return False, "no matching rule (default deny)"
