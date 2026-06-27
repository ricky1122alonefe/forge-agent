"""Contract validator — checks that a (generated) class conforms to BaseAgent.

This is the gatekeeper for the Code Generator. Without strict validation,
a misbehaving generated Agent could break the Pipeline — or worse,
do something dangerous.

**T1.2 hardening (5 layers):**

1. **AST structural check** — class exists, subclasses BaseAgent, 3 methods
2. **Import blacklist** — reject `os.system`, `subprocess`, `shutil.rmtree`, etc.
3. **Dangerous pattern detection** — `open(..., "w")` to non-`./data/` paths
4. **Cyclomatic complexity** — per-function, cap at 10 (configurable)
5. **Type annotation** — all 3 contract methods must have return type

Validation is **AST-only** (no exec). The Sandbox handles runtime checks.
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ Limits

@dataclass
class ValidatorLimits:
    """Configurable caps for the validator."""

    max_complexity: int = 10
    max_line_length: int = 200
    max_function_lines: int = 100


# ------------------------------------------------------------------ Blacklists

# Full names that the generated code MUST NOT import.
DANGEROUS_MODULES: set[str] = {
    "subprocess",
    "ctypes",
    "multiprocessing",
    "asyncio.subprocess",
    "signal",
    "socket",
    "pickle",
    "marshal",
    "pty",
    "fcntl",
}

# Specific names that MUST NOT appear (full dotted path or bare name).
DANGEROUS_NAMES: set[str] = {
    "os.system", "os.exec", "os.execl", "os.execle", "os.execlp",
    "os.execv", "os.execve", "os.execvp", "os.execvpe",
    "shutil.rmtree", "shutil.move",
    "eval", "exec", "__import__", "compile",
}

# Regex for dangerous runtime patterns (matched against source text).
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"open\([^)]*['\"]w['\"]", "file write detected — must be in ./data/"),
    (r"\.rmtree\(", "shutil.rmtree() — recursive delete"),
    (r"\.system\(", "os.system() — shell command"),
    (r"\.exec[lv]?p?e?\(", "os.exec*() — process replacement"),
    (r"__import__\(", "__import__() — dynamic import bypass"),
    (r"\beval\s*\(", "eval() — arbitrary code execution"),
    (r"\bexec\s*\(", "exec() — arbitrary code execution"),
]


# ------------------------------------------------------------------ Result

@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ Validator

class ContractValidator:
    """Static checks for BaseAgent conformance + safety."""

    def __init__(self, limits: ValidatorLimits | None = None) -> None:
        self.limits = limits or ValidatorLimits()
        self.required_class_methods = {"observe", "decide", "act"}
        self.required_classvars = {"agent_id", "name"}

    def validate_source(self, source: str) -> ValidationResult:
        """Validate Python source code string (5-layer check)."""
        result = ValidationResult(ok=True)

        # ----- Layer 0: syntax -----
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            result.ok = False
            result.errors.append(f"SyntaxError: {exc}")
            return result

        # ----- Layer 1: structural (class / methods / classvars) -----
        subclasses = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        if not subclasses:
            result.ok = False
            result.errors.append("No class found in source")
            return result

        target = subclasses[-1]

        base_names = {
            ast.unparse(b) for b in target.bases
        } if hasattr(ast, "unparse") else set()
        if not any("BaseAgent" in n for n in base_names):
            result.warnings.append(
                f"Class {target.name!r} does not appear to subclass BaseAgent: {base_names}"
            )

        method_names = {
            n.name for n in target.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for m in self.required_class_methods:
            if m not in method_names:
                result.ok = False
                result.errors.append(f"Missing required method: {m}")

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

        # ----- Layer 2: import blacklist -----
        import_errors = self._check_imports(tree)
        if import_errors:
            result.ok = False
            result.errors.extend(import_errors)

        # ----- Layer 3: dangerous pattern (regex over source) -----
        pattern_errors = self._check_dangerous_patterns(source)
        if pattern_errors:
            result.ok = False
            result.errors.extend(pattern_errors)

        # ----- Layer 4: complexity per function -----
        complexity_errors = self._check_complexity(target)
        if complexity_errors:
            result.ok = False
            result.errors.extend(complexity_errors)

        # ----- Layer 5: type annotations on required methods -----
        type_errors = self._check_type_hints(target)
        if type_errors:
            result.ok = False
            result.errors.extend(type_errors)

        result.info["class_name"] = target.name
        result.info["line_count"] = source.count("\n") + 1
        result.info["checks_run"] = 5
        return result

    def validate_class(self, cls: type) -> ValidationResult:
        """Validate an already-imported class object (subset of checks)."""
        result = ValidationResult(ok=True)
        for m in self.required_class_methods:
            if not hasattr(cls, m):
                result.ok = False
                result.errors.append(f"Missing method: {m}")
        for cv in self.required_classvars:
            if not hasattr(cls, cv) or not getattr(cls, cv):
                result.warnings.append(f"Missing/empty ClassVar: {cv}")
        return result

    # ====================================================================
    # Internal checks
    # ====================================================================

    def _check_imports(self, tree: ast.AST) -> list[str]:
        """Layer 2: scan AST for forbidden imports."""
        errors: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in DANGEROUS_MODULES or alias.name in DANGEROUS_NAMES:
                        errors.append(f"forbidden import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                full = node.module
                top = full.split(".")[0]
                if top in DANGEROUS_MODULES or full in DANGEROUS_NAMES:
                    errors.append(f"forbidden import: {full}")
                # Also check imported names (e.g. from os import system)
                bare_dangerous = {
                    "system", "exec", "execl", "Popen", "rmtree",
                    "move", "eval", "exec", "__import__", "compile",
                }
                names = node.names  # local ref for Python 3.14 compat
                for alias in names:
                    if alias.name in bare_dangerous:
                        errors.append(f"forbidden import: {full}.{alias.name}")
        return errors

    def _check_dangerous_patterns(self, source: str) -> list[str]:
        """Layer 3: scan source text for dangerous patterns."""
        errors: list[str] = []
        for pattern, msg in DANGEROUS_PATTERNS:
            matches = re.findall(pattern, source)
            if matches:
                errors.append(f"{msg} ({len(matches)} match(es))")
        return errors

    def _check_complexity(self, cls_node: ast.ClassDef) -> list[str]:
        """Layer 4: cyclomatic complexity per function (cap = max_complexity)."""
        errors: list[str] = []
        for node in cls_node.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            complexity = self._cyclomatic_complexity(node)
            if complexity > self.limits.max_complexity:
                errors.append(
                    f"function {node.name!r} too complex: "
                    f"{complexity} > {self.limits.max_complexity}"
                )
            # Also check function length
            n_lines = (node.end_lineno or 0) - (node.lineno or 0) + 1
            if n_lines > self.limits.max_function_lines:
                errors.append(
                    f"function {node.name!r} too long: "
                    f"{n_lines} > {self.limits.max_function_lines} lines"
                )
        return errors

    def _cyclomatic_complexity(self, func_node: ast.AST) -> int:
        """Calculate cyclomatic complexity (base 1 + decision points)."""
        complexity = 1
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.IfExp)):
                complexity += 1
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.With):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # 'and' / 'or' add 1 per additional operand
                complexity += max(0, len(node.values) - 1)
        return complexity

    def _check_type_hints(self, cls_node: ast.ClassDef) -> list[str]:
        """Layer 5: all 3 contract methods must have return type annotation."""
        errors: list[str] = []
        methods = {
            n.name: n for n in cls_node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for m in self.required_class_methods:
            node = methods.get(m)
            if node is None:
                continue  # already reported in Layer 1
            if node.returns is None:
                errors.append(
                    f"method {m!r} missing return type annotation"
                )
        return errors
