"""Unified logging for forge-agent.

Built on top of `structlog`, providing:

1. **One format everywhere** — every log line carries the same key set
   (timestamp / level / logger / event / agent_id / run_id / domain ...).
2. **Context propagation via `contextvars`** — when an Agent runs, it
   automatically `bind`s `agent_id` / `run_id` / `domain`; any nested
   call (including concurrent asyncio tasks) inherits that context
   without manual plumbing.
3. **Dual renderer** — pretty colored console in dev (TTY), structured
   JSON in production (CI / server / 12-factor).
4. **stdlib bridge** — third-party libraries (httpx, openai, ...) using
   `logging` are funneled through the same renderer so the output stays
   uniform.

Quick start::

    from forge_agent.observability.logger import configure_logging, get_logger

    configure_logging(level="INFO", json=False)  # call once at startup
    log = get_logger("forge_agent.demo")
    log.info("hello", extra_field=42)  # auto-includes context

Inside a running Agent, the `BaseAgent.run()` template method
automatically binds contextvars — user code in `observe()` / `decide()` /
`act()` can just call `log.info(...)` and the agent_id / run_id appear.

Env vars honored at `configure_logging()` time:

    FORGE_LOG_LEVEL   DEBUG / INFO / WARNING / ERROR (default INFO)
    FORGE_LOG_JSON    1 / true / yes → force JSON output regardless of TTY
    FORGE_LOG_FILE    1 / true / yes → also tee to a rotating file
                       (path defaults to ./logs/forge-agent.log)
    FORGE_LOG_FILE_PATH   override the file path
"""

from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Literal

# Defer-import structlog so that the import error path is clear if missing
# (pyproject requires it, but defensive code stays).
try:
    import structlog
    from structlog.contextvars import (
        bind_contextvars as _bind_contextvars,
    )
    from structlog.contextvars import (
        clear_contextvars as _clear_contextvars,
    )
    from structlog.contextvars import (
        get_contextvars as _get_contextvars,
    )
    from structlog.contextvars import (
        merge_contextvars,
    )
    from structlog.contextvars import (
        unbind_contextvars as _unbind_contextvars,
    )

    _HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover - pyproject enforces structlog
    _HAS_STRUCTLOG = False
    structlog = None  # type: ignore[assignment]
    _bind_contextvars = None  # type: ignore[assignment]
    _unbind_contextvars = None  # type: ignore[assignment]
    _clear_contextvars = None  # type: ignore[assignment]
    _get_contextvars = None  # type: ignore[assignment]
    merge_contextvars = None  # type: ignore[assignment]


# =====================================================================
# Context — propagated through asyncio tasks automatically
# =====================================================================
#
# We delegate to structlog's own contextvars implementation
# (`structlog.contextvars`) because:
#   1. The default `merge_contextvars` processor in our chain already
#      knows how to pull from it.
#   2. It's battle-tested for asyncio task isolation.
#   3. It implements the exact same API we expose (bind / unbind /
#      clear / get) but is also thread- and task-safe.
#
# If structlog isn't installed at runtime (unlikely; pyproject enforces
# it), we fall back to a stdlib `ContextVar` of our own + a custom
# processor.

import contextvars as _stdlib_contextvars

if _HAS_STRUCTLOG:

    def bind_context(**kv: Any) -> None:
        """Bind key/value pairs to the current async-task log context.

        Values of `None` are skipped. Bindings propagate through `await`
        boundaries; concurrent asyncio tasks have isolated contexts.
        """
        filtered = {k: v for k, v in kv.items() if v is not None}
        if filtered:
            _bind_contextvars(**filtered)

    def unbind_context(*keys: str) -> None:
        """Remove one or more keys from the current log context."""
        if keys:
            _unbind_contextvars(*keys)

    def clear_context() -> None:
        """Wipe the entire current log context (use at the end of a run)."""
        _clear_contextvars()

    def current_context() -> dict[str, Any]:
        """Return a copy of the current context bindings (read-only view)."""
        return dict(_get_contextvars())
else:
    _fallback_context: _stdlib_contextvars.ContextVar[dict[str, Any] | None] = (
        _stdlib_contextvars.ContextVar("forge_log_context_fallback", default=None)
    )

    def bind_context(**kv: Any) -> None:
        current = dict(_fallback_context.get() or {})
        current.update({k: v for k, v in kv.items() if v is not None})
        _fallback_context.set(current)

    def unbind_context(*keys: str) -> None:
        current = dict(_fallback_context.get() or {})
        for k in keys:
            current.pop(k, None)
        _fallback_context.set(current)

    def clear_context() -> None:
        _fallback_context.set(None)

    def current_context() -> dict[str, Any]:
        return dict(_fallback_context.get() or {})

    def _merge_fallback_contextvars(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
        """Custom processor that merges our fallback ContextVar."""
        for k, v in (_fallback_context.get() or {}).items():
            if k not in event_dict:
                event_dict[k] = v
        return event_dict


# =====================================================================
# Configuration
# =====================================================================

LogFormat = Literal["console", "json"]

# Cached configuration so we don't re-configure structlog on every call.
_configured: dict[str, Any] = {
    "configured": False,
    "format": "console",
    "level": "INFO",
    "file_path": None,
}


def _env_truthy(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _detect_format() -> LogFormat:
    """Pick console vs JSON based on env + TTY.

    Default rule: JSON in CI / non-TTY, console when interactive.
    Override with FORGE_LOG_JSON=1.
    """
    if _env_truthy("FORGE_LOG_JSON"):
        return "json"
    # Auto-detect: not a TTY → JSON (server, CI, pipe)
    if sys.stderr is not None and not sys.stderr.isatty():
        return "json"
    return "console"


def _detect_level() -> str:
    lvl = os.getenv("FORGE_LOG_LEVEL", "INFO").upper()
    if lvl not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return "INFO"
    return lvl


def configure_logging(
    *,
    level: str | None = None,
    json: bool | None = None,
    log_file: str | Path | None = None,
    force: bool = False,
) -> None:
    """Configure the global structlog + stdlib logging setup.

    Safe to call multiple times — only the first call has effect unless
    `force=True`. CLI startup calls this once with defaults; tests can
    re-configure with `force=True` to switch renderer / level.

    Args:
        level:    DEBUG / INFO / WARNING / ERROR (default from env).
        json:     True=JSON, False=console, None=auto-detect.
        log_file: optional path to also tee logs to (rotating by size).
                  If None and FORGE_LOG_FILE is truthy, defaults to
                  ./logs/forge-agent.log.
        force:    re-configure even if already set (for tests).
    """
    if not _HAS_STRUCTLOG:
        warnings.warn(
            "structlog is not installed — forge-agent logging will use stdlib fallback",
            stacklevel=2,
        )
        return

    if _configured["configured"] and not force:
        return

    # Resolve effective settings
    eff_level = (level or _detect_level()).upper()
    eff_format: LogFormat = (
        "json" if json is True else ("console" if json is False else _detect_format())
    )

    # Tee-to-file path
    eff_file: Path | None = None
    if log_file is not None:
        eff_file = Path(log_file)
    elif _env_truthy("FORGE_LOG_FILE"):
        eff_file = Path(os.getenv("FORGE_LOG_FILE_PATH", "logs/forge-agent.log"))

    # ----- structlog processor chain -----
    shared_processors: list[Any] = [
        merge_contextvars,  # inject contextvars
        structlog.processors.add_log_level,  # "level": "info"
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,  # exc_info → text
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.LINENO,
            ],
        ),
        # Ensure `logger` is present (fall back to name) so JSON has it.
        _ensure_logger_key,
    ]

    if eff_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty() if sys.stderr else True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, eff_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # ----- stdlib bridge: route `logging` through structlog renderer -----
    _bridge_stdlib(eff_level, shared_processors, renderer, eff_file)

    _configured.update(
        configured=True,
        format=eff_format,
        level=eff_level,
        file_path=eff_file,
    )


def _ensure_logger_key(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Ensure every record has a `logger` key (structlog uses `logger` key)."""
    if "logger" not in event_dict:
        event_dict["logger"] = event_dict.get("_logger", "forge_agent")
    return event_dict


def _bridge_stdlib(
    level: str,
    shared_processors: list[Any],
    renderer: Any,
    log_file: Path | None,
) -> None:
    """Make `logging.getLogger(...)` output go through the same renderer.

    Strategy: build a handler that hands the record to structlog's
    processor chain, then writes to stderr (and optionally to a file).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level))

    # Remove our previous bridge handlers (idempotent re-config)
    for h in list(root.handlers):
        if getattr(h, "_forge_bridge", False):
            root.removeHandler(h)

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler._forge_bridge = True  # type: ignore[attr-defined]
    root.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._forge_bridge = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    # Quiet the noisiest libraries by default; user can override later.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# =====================================================================
# Public API
# =====================================================================


def get_logger(name: str = "forge_agent") -> Any:
    """Return a structlog BoundLogger (lazy-configured).

    The returned logger is bound to `name` (the logger key) and
    automatically picks up `contextvars` set via `bind_context()`.
    """
    if _HAS_STRUCTLOG:
        # Lazy: if user never called configure_logging, do it now
        # with defaults (console + INFO) so first import still works.
        if not _configured["configured"]:
            configure_logging()
        return structlog.get_logger(name)
    # stdlib fallback (shouldn't happen given pyproject)
    return logging.getLogger(name)


def is_configured() -> bool:
    """Whether `configure_logging()` has been called (and not reset)."""
    return bool(_configured.get("configured", False))


def current_config() -> dict[str, Any]:
    """Return a copy of the active configuration (for introspection / tests)."""
    return dict(_configured)


def reset_for_tests() -> None:
    """Reset module state. For tests only."""
    _configured.update(configured=False, format="console", level="INFO", file_path=None)
    clear_context()


# =====================================================================
# Structured logger that satisfies LoggerProtocol
# =====================================================================


class StructLogger:
    """Adapter exposing structlog as `LoggerProtocol`.

    Used by `BaseAgent.logger` so the `self.log(...)` calls route through
    the unified pipeline. If structlog isn't installed, falls back to
    stdlib `logging`.
    """

    def __init__(self, name: str = "forge_agent") -> None:
        self.name = name
        self._log = get_logger(name)

    def log(
        self,
        level: str,
        agent_id: str,
        msg: str,
        **extra: Any,
    ) -> None:
        # Use structlog's bound `_log` so contextvars are inherited.
        method = getattr(self._log, level.lower(), None)
        if method is None:
            method = self._log.info
        # `agent_id` is also included in context (defensive — BaseAgent
        # also binds it via contextvars, but if a logger is constructed
        # outside an agent run we still want it visible).
        method(msg, agent_id=agent_id, **extra)
