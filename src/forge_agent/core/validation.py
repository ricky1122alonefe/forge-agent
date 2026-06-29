"""Pydantic validation models for forge-agent core data structures (T3.4).

Provides:
    - Pydantic models that mirror core dataclasses with runtime validation
    - ``validate_*()`` functions to validate existing dataclass instances
    - ``schema_*()`` functions to export JSON Schema for each model
    - Range constraints (confidence 0~1, risk 0~1, weight >= 0, etc.)

Usage::

    from forge_agent.core.validation import validate_report, schema_report

    # Validate an existing AgentReport
    report = AgentReport(agent_id="x", confidence=0.8, risk=0.2)
    validated = validate_report(report)  # raises ValidationError if invalid

    # Get JSON Schema
    schema = schema_report()  # returns dict
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# AgentReport validation model
# ---------------------------------------------------------------------------


class AgentReportModel(BaseModel):
    """Pydantic model for validating AgentReport data."""

    agent_id: str = Field(..., min_length=1, description="Globally unique agent identifier")
    name: str = Field(..., min_length=1, description="Human-readable name")
    domain: str = Field("generic", description="Business domain tag")
    verdict: str = Field("neutral", description="Semantic verdict")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence 0.0~1.0")
    risk: float = Field(0.0, ge=0.0, le=1.0, description="Risk 0.0~1.0")
    weight: float = Field(1.0, ge=0.0, description="Vote weight >= 0.0")
    evidence: list[str] = Field(default_factory=list, description="Evidence bullet points")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
    recommended_action: str = Field("watch", description="Suggested next action")
    metrics: dict[str, float] = Field(default_factory=dict, description="Quantitative metrics")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw output data")
    run_id: str = Field("", description="Run identifier")
    timestamp: str = Field("", description="ISO8601 timestamp")
    version: str = Field("0.1.0", description="Agent version")

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        from forge_agent.core.enums import Verdict

        valid = {m.value for m in Verdict}
        if v not in valid:
            raise ValueError(f"Invalid verdict {v!r}. Must be one of: {sorted(valid)}")
        return v

    @field_validator("recommended_action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        from forge_agent.core.enums import Action

        valid = {m.value for m in Action}
        if v not in valid:
            raise ValueError(f"Invalid action {v!r}. Must be one of: {sorted(valid)}")
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# AgentBoard validation model
# ---------------------------------------------------------------------------


class AgentBoardModel(BaseModel):
    """Pydantic model for validating AgentBoard data."""

    ok: bool = Field(..., description="Overall success flag")
    scope_id: str = Field(..., min_length=1, description="Domain-specific scope id")
    scope_name: str = Field("", description="Human-readable scope label")
    generated_at: str = Field("", description="ISO8601 timestamp")
    domain: str = Field("generic", description="Business domain tag")
    agents: list[AgentReportModel] = Field(default_factory=list, description="Agent reports")
    hard_guards: list[str] = Field(default_factory=list, description="Hard rule violations")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary data")
    version: str = Field("0.1.0", description="Board version")

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# AgentContext validation model
# ---------------------------------------------------------------------------


class AgentContextModel(BaseModel):
    """Pydantic model for validating AgentContext data."""

    scope_id: str = Field(..., min_length=1, description="Domain-specific scope id")
    scope_name: str = Field("", description="Human-readable label")
    domain: str = Field("generic", description="Business domain tag")
    payload: dict[str, Any] = Field(default_factory=dict, description="Domain data")
    config: dict[str, Any] = Field(default_factory=dict, description="Per-run config")
    run_id: str = Field("", description="Run identifier")
    parent_run_id: str = Field("", description="Parent run id")
    timestamp: str = Field("", description="ISO8601 timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# ChatMessage validation model
# ---------------------------------------------------------------------------


class ChatMessageModel(BaseModel):
    """Pydantic model for validating LLM chat messages."""

    role: str = Field(..., description="Message role")
    content: str = Field("", description="Message content")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tool calls")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"system", "user", "assistant", "tool"}
        if v not in valid:
            raise ValueError(f"Invalid role {v!r}. Must be one of: {sorted(valid)}")
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# LLMResponse validation model
# ---------------------------------------------------------------------------


class LLMResponseModel(BaseModel):
    """Pydantic model for validating LLM responses."""

    content: str = Field("", description="Response content")
    tokens_in: int = Field(0, ge=0, description="Input tokens")
    tokens_out: int = Field(0, ge=0, description="Output tokens")
    cost_usd: float = Field(0.0, ge=0.0, description="Cost in USD")
    provider: str = Field("", description="Provider name")
    model: str = Field("", description="Model name")

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Validate functions — accept dataclass instances or dicts
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass or dict to a plain dict for Pydantic validation."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    # dataclass asdict fallback
    from dataclasses import asdict

    return asdict(obj)


def validate_report(obj: Any) -> AgentReportModel:
    """Validate an AgentReport instance or dict."""
    return AgentReportModel(**_to_dict(obj))


def validate_board(obj: Any) -> AgentBoardModel:
    """Validate an AgentBoard instance or dict."""
    return AgentBoardModel(**_to_dict(obj))


def validate_context(obj: Any) -> AgentContextModel:
    """Validate an AgentContext instance or dict."""
    return AgentContextModel(**_to_dict(obj))


def validate_chat_message(obj: Any) -> ChatMessageModel:
    """Validate a ChatMessage instance or dict."""
    return ChatMessageModel(**_to_dict(obj))


def validate_llm_response(obj: Any) -> LLMResponseModel:
    """Validate an LLMResponse instance or dict."""
    return LLMResponseModel(**_to_dict(obj))


# ---------------------------------------------------------------------------
# JSON Schema export
# ---------------------------------------------------------------------------


def schema_report() -> dict[str, Any]:
    """Return JSON Schema for AgentReport."""
    return AgentReportModel.model_json_schema()


def schema_board() -> dict[str, Any]:
    """Return JSON Schema for AgentBoard."""
    return AgentBoardModel.model_json_schema()


def schema_context() -> dict[str, Any]:
    """Return JSON Schema for AgentContext."""
    return AgentContextModel.model_json_schema()


def schema_chat_message() -> dict[str, Any]:
    """Return JSON Schema for ChatMessage."""
    return ChatMessageModel.model_json_schema()


def schema_llm_response() -> dict[str, Any]:
    """Return JSON Schema for LLMResponse."""
    return LLMResponseModel.model_json_schema()
