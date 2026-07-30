"""BaseAgent — the soul of forge-agent.

**v0.2 design (scaffolding-friendly):**

A newcomer only needs to implement **3 methods** (observe / decide / act) to
get a fully working Agent. The other 5 capabilities (logging / searching /
learning / iteration / custom prompts) are **opt-in** — they have sensible
defaults and are activated either by:

    1.  Subclass overrides (e.g. `searcher = TavilySearcher()`)
    2.  `@has_capability("search")` class decorator
    3.  Configuration at instantiation (`MyAgent(config={"search": {...}})`)

**Capability matrix:**

    ┌──────────────┬─────────┬──────────────────────────────────┐
    │ Capability   │ Default │ To enable                        │
    ├──────────────┼─────────┼──────────────────────────────────┤
    │ observe      │  MUST   │ abstract method                  │
    │ decide       │  MUST   │ abstract method                  │
    │ act          │  MUST   │ abstract method                  │
    │ log          │  auto   │ override `logger` attribute      │
    │ search       │  noop   │ assign `searcher = ...`          │
    │ memory       │  noop   │ assign `memory = ...`            │
    │ reflect      │  noop   │ assign `reflector = ...`         │
    │ prompt_mgr   │  basic  │ assign `prompt_manager = ...`    │
    │ evolve       │  stub   │ override `evolve()` method       │
    └──────────────┴─────────┴──────────────────────────────────┘

**Run cycle (Template Method — never override `run`):**

    observe() → decide() → act() → reflect() → learn()

The cycle is **safe by default**: exceptions in reflect/learn never break the
run; the AgentReport is always returned.
"""

from __future__ import annotations

import abc
from typing import Any, ClassVar

from forge_agent.core.capabilities import (
    InMemoryPromptManager,
    LoggerProtocol,
    MemoryProtocol,
    NoopReflector,
    NoopSearcher,
    PromptManagerProtocol,
    ReflectionProtocol,
    SearcherProtocol,
    StdLogger,
)
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, AgentStatus, Verdict


def has_capability(name: str) -> Any:
    """Class decorator: declare a capability is used.

    Currently informational; reserved for future validators / dashboards.

    Example::

        @register_agent(domain="stock")
        @has_capability("search")
        @has_capability("prompt_manager")
        class StockAgent(BaseAgent): ...
    """

    def decorator(cls: type) -> type:
        caps: list[str] = list(getattr(cls, "__forge_capabilities__", []))
        if name not in caps:
            caps.append(name)
        cls.__forge_capabilities__ = caps  # type: ignore[attr-defined]
        return cls

    return decorator


class BaseAgent(abc.ABC):
    """Abstract base for ALL agents in the forge-agent ecosystem.

    **Minimal example (only 3 methods needed):**::

        @register_agent(domain="hello")
        class HelloAgent(BaseAgent):
            agent_id = "hello.basic"
            name = "Hello Agent"

            async def observe(self, ctx):
                return {"greeting": f"hi, {ctx.scope_name}"}

            async def decide(self, ctx, obs):
                return {"say": obs["greeting"]}

            async def act(self, ctx, dec):
                return AgentReport(agent_id=self.agent_id, name=self.name, evidence=[dec["say"]])

    **Full example (all 5 capabilities enabled):**::

        @register_agent(domain="stock")
        @has_capability("search")
        @has_capability("memory")
        @has_capability("prompt_manager")
        class StockAgent(BaseAgent):
            agent_id = "stock.monitor"
            name = "Stock Monitor"
            searcher = TavilySearcher()
            memory = RedisMemory()
            prompt_manager = FilePromptStore("./prompts/")

            async def observe(self, ctx):
                return await self.search(ctx.payload["ticker"])

            ...
    """

    # ---------------- Class-level metadata (subclass MUST set) ----------------
    agent_id: ClassVar[str] = ""  # globally unique, e.g. "stock.monitor"
    name: ClassVar[str] = ""  # human-readable label
    version: ClassVar[str] = "0.1.0"
    domain: ClassVar[str] = "generic"

    # ---------------- Capability slots (Strategy pattern) ----------------
    # Subclasses override these to enable / customize each capability.
    logger: LoggerProtocol
    searcher: SearcherProtocol
    memory: MemoryProtocol
    reflector: ReflectionProtocol
    prompt_manager: PromptManagerProtocol
    constraint_engine: Any | None = None

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = dict(config or {})
        self._status: AgentStatus = AgentStatus.UNINITIALIZED

        # ---------- Default capability wiring (override in subclasses) ----------
        self.logger = StdLogger(name=f"forge_agent.{self.agent_id or 'agent'}")
        self.searcher = NoopSearcher()
        self.memory = self._create_memory_backend()
        self.reflector = NoopReflector()
        self.prompt_manager = InMemoryPromptManager()
        self.constraint_engine = self._create_constraint_engine()

    def _create_memory_backend(self) -> Any:
        """Create the memory backend from ``self.config``.

        Subclasses can override this to wire a custom backend. By default,
        ``config["memory"]`` is passed to ``create_memory_backend``.
        """
        from forge_agent.memory import create_memory_backend

        return create_memory_backend(self.config.get("memory"))

    def _create_constraint_engine(self) -> Any | None:
        """Create the constraint engine from ``self.config``.

        Subclasses can override this to wire a custom engine. By default,
        ``config["constraints"]`` is passed to ``create_constraint_engine``.
        """
        from forge_agent.constraints.utils import create_constraint_engine

        return create_constraint_engine(self.config.get("constraints"))

    # ====================================================================
    # Lifecycle
    # ====================================================================

    async def initialize(self) -> None:
        self._status = AgentStatus.INITIALIZING
        self._bind_log_context()
        self.log("info", f"Agent {self.agent_id} initializing...")
        try:
            await self._on_init()
            self._status = AgentStatus.READY
            self.log("info", f"Agent {self.agent_id} ready.")
        except Exception as exc:
            self._status = AgentStatus.ERROR
            self.log("error", f"Agent {self.agent_id} init failed: {exc}")
            raise
        finally:
            self._unbind_log_context()

    async def _on_init(self) -> None:
        return None

    async def shutdown(self) -> None:
        self._status = AgentStatus.SHUTTING_DOWN
        self._bind_log_context()
        try:
            await self._on_shutdown()
        finally:
            self._status = AgentStatus.SHUTDOWN
            self.log("info", f"Agent {self.agent_id} shut down.")
            self._unbind_log_context()

    async def _on_shutdown(self) -> None:
        return None

    def _bind_log_context(self) -> None:
        """Bind this agent's identifying fields to the log contextvars."""
        from forge_agent.core.trace_runtime import bind_agent_context

        bind_agent_context(self.agent_id, self.domain, self.version)

    def _unbind_log_context(self) -> None:
        from forge_agent.core.trace_runtime import unbind_agent_context

        unbind_agent_context()

    # ====================================================================
    # Run cycle (Template Method — override hooks, not the cycle)
    # ====================================================================

    async def run(self, ctx: AgentContext) -> AgentReport:
        self._status = AgentStatus.RUNNING
        # Bind run_id in addition to the agent fields so every nested
        # log line carries both "which agent" and "which run".
        from forge_agent.core.trace_runtime import (
            bind_run_context,
            end_span,
            run_step_traced,
            start_agent_span,
            unbind_run_context,
        )

        bind_run_context(self.agent_id, self.domain, self.version, ctx.run_id)
        agent_span, trace = start_agent_span(self.agent_id, ctx.run_id)
        try:
            observation = await run_step_traced(self, "observe", ctx, trace)
            decision = await run_step_traced(self, "decide", ctx, trace, observation=observation)
            result = await run_step_traced(self, "act", ctx, trace, decision=decision)
            result = await self._apply_constraints(ctx, result)
            # Post-execution hooks (best-effort — never break the run)
            try:
                await run_step_traced(
                    self,
                    "reflect",
                    ctx,
                    trace,
                    observation=observation,
                    decision=decision,
                    result=result,
                )
            except Exception as exc:
                self.log("warning", f"reflect() failed: {exc}")
            try:
                await run_step_traced(
                    self,
                    "learn",
                    ctx,
                    trace,
                    observation=observation,
                    decision=decision,
                    result=result,
                )
            except Exception as exc:
                self.log("warning", f"learn() failed: {exc}")
            end_span(agent_span)
            return result
        except Exception as exc:
            end_span(agent_span, status="error", error=str(exc))
            self.log("error", f"Agent {self.agent_id} run failed: {exc}")
            return self._error_report(ctx, exc)
        finally:
            self._status = AgentStatus.READY
            unbind_run_context()

    async def _run_step(
        self,
        step_name: str,
        ctx: AgentContext,
        trace: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a single lifecycle step with trace span (S6.1: delegates to trace_runtime)."""
        from forge_agent.core.trace_runtime import run_step_traced

        return await run_step_traced(self, step_name, ctx, trace, **kwargs)

    async def _apply_constraints(
        self,
        ctx: AgentContext,
        result: AgentReport,
    ) -> AgentReport:
        """Check the agent output against the configured constraint engine.

        Delegates to ``constraints.runtime.apply_constraints`` (S6.2).
        """
        from forge_agent.constraints.runtime import apply_constraints

        return await apply_constraints(
            agent_id=self.agent_id,
            domain=self.domain,
            ctx=ctx,
            result=result,
            engine=self.constraint_engine,
            log_fn=self.log,
        )

    @abc.abstractmethod
    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        """Step 1: gather information. May call `await self.search(...)`."""
        raise NotImplementedError

    @abc.abstractmethod
    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        """Step 2: decide what to do, typically using LLM + `self.prompt_manager`."""
        raise NotImplementedError

    @abc.abstractmethod
    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Step 3: produce a standardized `AgentReport`."""
        raise NotImplementedError

    # ====================================================================
    # The 2 self-* methods (default no-op-ish — override to enable)
    # ====================================================================

    async def reflect(
        self,
        ctx: AgentContext,
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: AgentReport,
    ) -> dict[str, Any]:
        """Step 4: delegate to `self.reflector`. Override to customize."""
        return await self.reflector.reflect(
            agent_id=self.agent_id,
            context=ctx.to_dict(),
            observation=observation,
            decision=decision,
            result=result.to_dict(),
        )

    async def learn(
        self,
        ctx: AgentContext,
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: AgentReport,
    ) -> None:
        """Step 5: persist the run to `self.memory`. Override to customize."""
        await self.memory.store(
            key=f"{self.agent_id}:{ctx.run_id}",
            value={
                "scope_id": ctx.scope_id,
                "observation": observation,
                "decision": decision,
                "result": result.to_dict(),
                "timestamp": ctx.timestamp,
            },
        )

    # ====================================================================
    # Capability #4: self-iteration (v0.4+ — real implementation)
    # ====================================================================

    async def evolve(self, ctx: AgentContext) -> dict[str, Any]:
        """Self-iteration hook — delegates to ``learning.evolve`` (S6.3).

        Performs a full evolution cycle: reflection → optimiser → evolve.
        Override in subclasses for custom evolution strategies.
        """
        from forge_agent.learning.evolve import run_evolution

        return await run_evolution(self, ctx)

    # ====================================================================
    # Convenience methods
    # ====================================================================

    def log(self, level: str, msg: str, **extra: Any) -> None:
        """Unified log entry point — use this everywhere inside Agents."""
        self.logger.log(level=level, agent_id=self.agent_id, msg=msg, **extra)

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Delegate to the configured `self.searcher`."""
        return await self.searcher.search(query, **kwargs)

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def enabled_capabilities(self) -> list[str]:
        """Return the list of capabilities the subclass declared via @has_capability."""
        return list(getattr(self, "__forge_capabilities__", []))

    def _error_report(self, ctx: AgentContext, exc: Exception) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id or "unknown",
            name=self.name or "unknown",
            domain=self.domain,
            verdict=Verdict.RISK,
            confidence=0.0,
            risk=1.0,
            evidence=[],
            warnings=[f"Agent execution failed: {exc}"],
            recommended_action=Action.WATCH,
            raw={"error": str(exc), "run_id": ctx.run_id},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )
