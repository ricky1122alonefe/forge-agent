"""Constraint engine.

The engine loads policies and evaluates them against agent inputs, outputs,
decisions, and tool calls. Policies are matched by simple substring / regex
patterns for v0.1; future versions may add semantic classification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from forge_agent.constraints.policy import ConstraintPolicy, TriggerType
from forge_agent.constraints.result import ConstraintResult, ConstraintViolation


class ConstraintEngine:
    """Generic constraint engine.

    Loads policies from YAML files and provides async check methods. The engine
    is intentionally framework-agnostic: it only receives a trigger type and a
    text/blob to inspect, plus optional metadata.

    Example::

        engine = ConstraintEngine()
        engine.load_yaml("builtin/constraints/compliance.yaml")

        result = await engine.check_output(
            text="我保证这场稳赢，包你发财",
            metadata={"agent_id": "football.chief", "tenant_id": "acme"},
        )
        print(result.allowed, result.violations)
    """

    def __init__(self) -> None:
        self._policies: list[ConstraintPolicy] = []

    # ------------------------------------------------------------------ Load

    def add_policy(self, policy: ConstraintPolicy) -> None:
        """Add a single policy."""
        self._policies.append(policy)

    def load_policies(self, policies: list[dict[str, Any]]) -> None:
        """Load policies from a list of dicts."""
        for raw in policies:
            self.add_policy(ConstraintPolicy.from_dict(raw))

    def load_yaml(self, path: str | Path) -> None:
        """Load policies from a YAML file."""
        file_path = Path(path)
        if not file_path.exists():
            return
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if not raw:
            return
        policies = raw.get("policies", raw if isinstance(raw, list) else [])
        self.load_policies(policies)

    def list_policies(self) -> list[ConstraintPolicy]:
        """Return all loaded policies."""
        return [p for p in self._policies if p.enabled]

    # ------------------------------------------------------------------ Check

    async def check_input(
        self,
        payload: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ConstraintResult:
        """Evaluate INPUT policies against a payload."""
        text = self._flatten(payload)
        return await self._check(TriggerType.INPUT, text, metadata)

    async def check_output(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ConstraintResult:
        """Evaluate OUTPUT policies against a text string."""
        return await self._check(TriggerType.OUTPUT, text, metadata)

    async def check_decision(
        self,
        decision: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ConstraintResult:
        """Evaluate DECISION policies against an agent decision."""
        text = self._flatten(decision)
        return await self._check(TriggerType.DECISION, text, metadata)

    async def check_tool_call(
        self,
        tool_name: str,
        *,
        args: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConstraintResult:
        """Evaluate TOOL_CALL policies against a tool name and its arguments."""
        text = f"{tool_name} {self._flatten(args or {})}"
        return await self._check(TriggerType.TOOL_CALL, text, metadata)

    # ------------------------------------------------------------------ Internals

    async def _check(
        self,
        trigger: TriggerType,
        text: str,
        metadata: dict[str, Any] | None,
    ) -> ConstraintResult:
        result = ConstraintResult(
            allowed=True,
            metadata={**(metadata or {}), "trigger": trigger.value},
        )
        for policy in self._policies:
            if not policy.enabled or policy.trigger != trigger:
                continue
            matched_text = self._match(policy.patterns, text)
            if matched_text:
                result.add_violation(
                    ConstraintViolation(
                        policy_id=policy.id,
                        policy_name=policy.name,
                        trigger=policy.trigger.value,
                        severity=policy.severity,
                        matched_text=matched_text,
                        action=policy.action.value,
                    )
                )
        return result

    def _match(self, patterns: list[str], text: str) -> str:
        """Return the first matched substring, or empty string if no match."""
        for pattern in patterns:
            try:
                regex = re.compile(pattern)
                m = regex.search(text)
                if m:
                    return m.group(0)
            except re.error:
                # Fallback to simple substring.
                if pattern in text:
                    return pattern
        return ""

    def _flatten(self, obj: Any) -> str:
        """Convert a dict/list/primitive into a searchable string."""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            parts: list[str] = []
            for k, v in obj.items():
                parts.append(f"{k}={self._flatten(v)}")
            return " ".join(parts)
        if isinstance(obj, list):
            return " ".join(self._flatten(i) for i in obj)
        return str(obj)
