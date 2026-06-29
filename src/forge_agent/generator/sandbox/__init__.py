"""Sandbox package — isolated execution for generated Agents.

Public API (backward compatible with v0.2):
    - ResourceLimits
    - Sandbox
    - SmokeTestResult
"""

from __future__ import annotations

from forge_agent.generator.sandbox.core import (
    ResourceLimits,
    Sandbox,
    SmokeTestResult,
)

__all__ = ["ResourceLimits", "Sandbox", "SmokeTestResult"]
