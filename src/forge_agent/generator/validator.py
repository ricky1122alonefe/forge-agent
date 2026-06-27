"""Contract validator — checks that a (generated) class conforms to BaseAgent.

This is the gatekeeper for the Code Generator. Without strict validation,
a misbehaving generated Agent could break the Pipeline.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


class ContractValidator:
    """Static checks for BaseAgent conformance.

    Performs AST-level inspection (does NOT exec the code in the sandbox —
    that's the Sandbox's job).
    """

    def __init__(self) -> None:
        self.required_class_methods = {"observe", "decide", "act"}
        self.required_classvars = {"agent_id", "name"}

    def validate_source(self, source: str) -> ValidationResult:
        """Validate Python source code string."""
        result = ValidationResult(ok=True)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            result.ok = False
            result.errors.append(f"SyntaxError: {exc}")
            return result

        # Find candidate BaseAgent subclasses
        subclasses = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        if not subclasses:
            result.ok = False
            result.errors.append("No class found in source")
            return result

        # Use the last class (typical generator output: imports → class)
        target = subclasses[-1]

        # Check base classes include BaseAgent
        base_names = {
            ast.unparse(b) for b in target.bases
        } if hasattr(ast, "unparse") else set()
        if not any("BaseAgent" in n for n in base_names):
            result.warnings.append(
                f"Class {target.name!r} does not appear to subclass BaseAgent: {base_names}"
            )

        # Check required methods exist
        method_names = {
            n.name for n in target.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for m in self.required_class_methods:
            if m not in method_names:
                result.ok = False
                result.errors.append(f"Missing required method: {m}")

        # Check required ClassVars
        for cv in self.required_classvars:
            if not any(
                isinstance(n, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == cv
                    for t in n.targets
                )
                for n in target.body
            ):
                result.warnings.append(f"Missing ClassVar: {cv}")

        result.info["class_name"] = target.name
        result.info["line_count"] = source.count("\n") + 1
        return result

    def validate_class(self, cls: type) -> ValidationResult:
        """Validate an already-imported class object."""
        result = ValidationResult(ok=True)
        for m in self.required_class_methods:
            if not hasattr(cls, m):
                result.ok = False
                result.errors.append(f"Missing method: {m}")
        for cv in self.required_classvars:
            if not hasattr(cls, cv) or not getattr(cls, cv):
                result.warnings.append(f"Missing/empty ClassVar: {cv}")
        return result
