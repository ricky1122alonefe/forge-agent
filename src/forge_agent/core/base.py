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
    InMemoryStore,
    LoggerProtocol,
    MemoryProtocol,
    NoopReflector,
    NoopSearcher,
    PromptManagerProtocol,
    ReflectionProtocol,
    SearcherProtocol,
    StdLogger,
)
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Action, AgentStatus, Verdict


def has_capability(name: str) -> Any:
    """Class decorator: declare a capability is used.

    Currently informational; reserved for future validators / dashboards.

    Example::

        @register_agent(domain="stock")
        @has_capability("search")
        @has_capability("prompt_manager")
        class StockAgent(BaseAgent):
            ...
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

            async def observe(self, ctx): return {"greeting": f"hi, {ctx.scope_name}"}
            async def decide(self, ctx, obs): return {"say": obs["greeting"]}
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
    agent_id: ClassVar[str] = ""        # globally unique, e.g. "stock.monitor"
    name: ClassVar[str] = ""            # human-readable label
    version: ClassVar[str] = "0.1.0"
    domain: ClassVar[str] = "generic"

    # ---------------- Capability slots (Strategy pattern) ----------------
    # Subclasses override these to enable / customize each capability.
    logger: LoggerProtocol
    searcher: SearcherProtocol
    memory: MemoryProtocol
    reflector: ReflectionProtocol
    prompt_manager: PromptManagerProtocol

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = dict(config or {})
        self._status: AgentStatus = AgentStatus.UNINITIALIZED

        # ---------- Default capability wiring (override in subclasses) ----------
        self.logger = StdLogger(name=f"forge_agent.{self.agent_id or 'agent'}")
        self.searcher = NoopSearcher()
        self.memory = InMemoryStore()
        self.reflector = NoopReflector()
        self.prompt_manager = InMemoryPromptManager()

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
        """Bind this agent's identifying fields to the log contextvars.

        Anything logged inside an Agent's lifecycle/run automatically
        carries these fields — no manual plumbing needed in observe /
        decide / act / reflect / learn.
        """
        from forge_agent.observability.logger import bind_context

        bind_context(
            agent_id=self.agent_id,
            domain=self.domain,
            agent_version=self.version,
        )

    def _unbind_log_context(self) -> None:
        from forge_agent.observability.logger import unbind_context

        unbind_context("agent_id", "domain", "agent_version", "run_id")

    # ====================================================================
    # Run cycle (Template Method — override hooks, not the cycle)
    # ====================================================================

    async def run(self, ctx: AgentContext) -> AgentReport:
        self._status = AgentStatus.RUNNING
        # Bind run_id in addition to the agent fields so every nested
        # log line carries both "which agent" and "which run".
        from forge_agent.observability.logger import bind_context, unbind_context
        from forge_agent.observability.trace import get_trace_manager, SpanType

        bind_context(agent_id=self.agent_id, domain=self.domain,
                     agent_version=self.version, run_id=ctx.run_id)

        tm = get_trace_manager()
        trace = tm.current_trace
        agent_span = tm.start_span(
            name=f"{self.agent_id}.run",
            span_type=SpanType.AGENT,
            trace=trace,
            attributes={"agent_id": self.agent_id, "run_id": ctx.run_id},
        )
        try:
            observation = await self._run_step("observe", ctx, SpanType.OBSERVE, trace)
            decision = await self._run_step("decide", ctx, SpanType.DECIDE, trace, observation=observation)
            result = await self._run_step("act", ctx, SpanType.ACT, trace, decision=decision)
            # Post-execution hooks (best-effort — never break the run)
            try:
                await self._run_step(
                    "reflect", ctx, SpanType.REFLECT, trace,
                    observation=observation, decision=decision, result=result,
                )
            except Exception as exc:  # noqa: BLE001
                self.log("warning", f"reflect() failed: {exc}")
            try:
                await self._run_step(
                    "learn", ctx, SpanType.LEARN, trace,
                    observation=observation, decision=decision, result=result,
                )
            except Exception as exc:  # noqa: BLE001
                self.log("warning", f"learn() failed: {exc}")
            tm.end_span(agent_span, status="ok")
            return result
        except Exception as exc:
            tm.end_span(agent_span, status="error", error_message=str(exc))
            self.log("error", f"Agent {self.agent_id} run failed: {exc}")
            return self._error_report(ctx, exc)
        finally:
            self._status = AgentStatus.READY
            # Clear only the per-run key; keep agent_id / domain in case
            # the agent is reused within the same task.
            unbind_context("run_id")

    async def _run_step(
        self,
        step_name: str,
        ctx: AgentContext,
        span_type: Any,
        trace: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a single agent step with trace span recording."""
        from forge_agent.observability.trace import get_trace_manager
        tm = get_trace_manager()
        span = tm.start_span(
            name=f"{self.agent_id}.{step_name}",
            span_type=span_type,
            trace=trace,
            attributes={"step": step_name},
        )
        try:
            if step_name == "observe":
                result = await self.observe(ctx)
            elif step_name == "decide":
                result = await self.decide(ctx, kwargs["observation"])
            elif step_name == "act":
                result = await self.act(ctx, kwargs["decision"])
            elif step_name == "reflect":
                result = await self.reflect(ctx, kwargs["observation"], kwargs["decision"], kwargs["result"])
            elif step_name == "learn":
                result = await self.learn(ctx, kwargs["observation"], kwargs["decision"], kwargs["result"])
            else:
                result = None
            tm.end_span(span, status="ok")
            return result
        except Exception as exc:
            tm.end_span(span, status="error", error_message=str(exc))
            raise

    # ====================================================================
    # The 3 contract methods — MUST be implemented
    # ====================================================================

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
    # Capability #4: self-iteration (v0.4+ — default stub)
    # ====================================================================

    async def evolve(self, ctx: AgentContext) -> dict[str, Any]:
        """Self-iteration hook. Default: no-op. Override (or let the Code
        Generator inject) to bump prompt versions or swap capabilities.
        """
        return {"evolved": False, "reason": "evolve() not implemented"}

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
