"""Tests for T3.4 — Pydantic validation and JSON Schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.validation import (
    AgentBoardModel,
    AgentContextModel,
    AgentReportModel,
    ChatMessageModel,
    LLMResponseModel,
    schema_board,
    schema_chat_message,
    schema_context,
    schema_llm_response,
    schema_report,
    validate_board,
    validate_chat_message,
    validate_context,
    validate_llm_response,
    validate_report,
)


# ---------------------------------------------------------------------------
# AgentReport validation
# ---------------------------------------------------------------------------

class TestAgentReportValidation:
    def test_valid_report(self):
        report = AgentReport(
            agent_id="test.agent",
            name="Test Agent",
            confidence=0.8,
            risk=0.2,
            weight=1.5,
            verdict=Verdict.LEAN_POSITIVE,
        )
        validated = validate_report(report)
        assert validated.agent_id == "test.agent"
        assert validated.confidence == 0.8

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentReportModel(agent_id="x", name="X", confidence=1.5)
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_negative(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="x", name="X", confidence=-0.1)

    def test_risk_out_of_range(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="x", name="X", risk=2.0)

    def test_weight_negative(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="x", name="X", weight=-1.0)

    def test_empty_agent_id(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="", name="X")

    def test_invalid_verdict(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="x", name="X", verdict="invalid_verdict")

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            AgentReportModel(agent_id="x", name="X", recommended_action="invalid_action")

    def test_valid_from_dict(self):
        data = {
            "agent_id": "test",
            "name": "Test",
            "confidence": 0.5,
            "risk": 0.3,
            "verdict": "lean_positive",
            "recommended_action": "watch",
        }
        validated = validate_report(data)
        assert validated.agent_id == "test"

    def test_boundary_values(self):
        # All boundary values should be valid
        report = AgentReportModel(
            agent_id="x",
            name="X",
            confidence=0.0,
            risk=0.0,
            weight=0.0,
        )
        assert report.confidence == 0.0

        report2 = AgentReportModel(
            agent_id="x",
            name="X",
            confidence=1.0,
            risk=1.0,
            weight=100.0,
        )
        assert report2.confidence == 1.0


# ---------------------------------------------------------------------------
# AgentBoard validation
# ---------------------------------------------------------------------------

class TestAgentBoardValidation:
    def test_valid_board(self):
        board = AgentBoard(
            ok=True,
            scope_id="test_scope",
            scope_name="Test",
            generated_at="2026-06-27T14:00:00Z",
            agents=[
                AgentReport(agent_id="a1", name="A1", confidence=0.8),
                AgentReport(agent_id="a2", name="A2", confidence=0.6),
            ],
        )
        validated = validate_board(board)
        assert validated.ok is True
        assert len(validated.agents) == 2

    def test_empty_scope_id(self):
        with pytest.raises(ValidationError):
            AgentBoardModel(ok=True, scope_id="", scope_name="X", generated_at="")

    def test_invalid_nested_report(self):
        with pytest.raises(ValidationError):
            AgentBoardModel(
                ok=True,
                scope_id="x",
                scope_name="X",
                generated_at="",
                agents=[
                    {"agent_id": "a1", "name": "A1", "confidence": 5.0},  # invalid
                ],
            )


# ---------------------------------------------------------------------------
# AgentContext validation
# ---------------------------------------------------------------------------

class TestAgentContextValidation:
    def test_valid_context(self):
        ctx = AgentContext(scope_id="test_scope", domain="finance")
        validated = validate_context(ctx)
        assert validated.scope_id == "test_scope"
        assert validated.domain == "finance"

    def test_empty_scope_id(self):
        with pytest.raises(ValidationError):
            AgentContextModel(scope_id="")

    def test_valid_from_dict(self):
        data = {"scope_id": "test", "domain": "sports", "payload": {"key": "value"}}
        validated = validate_context(data)
        assert validated.scope_id == "test"


# ---------------------------------------------------------------------------
# ChatMessage validation
# ---------------------------------------------------------------------------

class TestChatMessageValidation:
    def test_valid_message(self):
        msg = ChatMessageModel(role="user", content="Hello")
        assert msg.role == "user"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            ChatMessageModel(role="invalid_role", content="Hello")

    def test_all_valid_roles(self):
        for role in ["system", "user", "assistant", "tool"]:
            msg = ChatMessageModel(role=role, content="test")
            assert msg.role == role


# ---------------------------------------------------------------------------
# LLMResponse validation
# ---------------------------------------------------------------------------

class TestLLMResponseValidation:
    def test_valid_response(self):
        resp = LLMResponseModel(
            content="Hello",
            tokens_in=10,
            tokens_out=20,
            cost_usd=0.001,
        )
        assert resp.tokens_in == 10

    def test_negative_tokens(self):
        with pytest.raises(ValidationError):
            LLMResponseModel(content="X", tokens_in=-1)

    def test_negative_cost(self):
        with pytest.raises(ValidationError):
            LLMResponseModel(content="X", cost_usd=-0.01)


# ---------------------------------------------------------------------------
# JSON Schema export
# ---------------------------------------------------------------------------

class TestJSONSchema:
    def test_schema_report(self):
        schema = schema_report()
        assert "properties" in schema
        assert "agent_id" in schema["properties"]
        assert "confidence" in schema["properties"]
        # Check range constraints
        conf = schema["properties"]["confidence"]
        assert conf.get("minimum") == 0.0
        assert conf.get("maximum") == 1.0

    def test_schema_board(self):
        schema = schema_board()
        assert "properties" in schema
        assert "agents" in schema["properties"]

    def test_schema_context(self):
        schema = schema_context()
        assert "properties" in schema
        assert "scope_id" in schema["properties"]

    def test_schema_chat_message(self):
        schema = schema_chat_message()
        assert "properties" in schema
        assert "role" in schema["properties"]

    def test_schema_llm_response(self):
        schema = schema_llm_response()
        assert "properties" in schema
        assert "tokens_in" in schema["properties"]
        # Check non-negative constraint
        tokens = schema["properties"]["tokens_in"]
        assert tokens.get("minimum") == 0


# ---------------------------------------------------------------------------
# Integration: validate real dataclass instances
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_validate_real_report(self):
        report = AgentReport(
            agent_id="finance.stock_analyzer",
            name="Stock Analyzer",
            domain="finance",
            verdict=Verdict.LEAN_POSITIVE,
            confidence=0.85,
            risk=0.15,
            weight=1.0,
            evidence=["Price above MA", "Volume increasing"],
            recommended_action=Action.EXECUTE,
            run_id="run_abc123",
        )
        validated = validate_report(report)
        assert validated.confidence == 0.85
        assert validated.verdict == "lean_positive"

    def test_validate_real_board(self):
        board = AgentBoard(
            ok=True,
            scope_id="ticker_AAPL",
            scope_name="Apple Inc.",
            generated_at="2026-06-27T14:00:00Z",
            domain="finance",
            agents=[
                AgentReport(agent_id="a1", name="A1", confidence=0.8, verdict=Verdict.LEAN_POSITIVE),
                AgentReport(agent_id="a2", name="A2", confidence=0.6, verdict=Verdict.LEAN_NEUTRAL),
            ],
            hard_guards=[],
        )
        validated = validate_board(board)
        assert len(validated.agents) == 2

    def test_validate_real_context(self):
        ctx = AgentContext(
            scope_id="fixture_123",
            scope_name="Man Utd vs Liverpool",
            domain="football",
            payload={"home": "Man Utd", "away": "Liverpool"},
            config={"api_key": "test"},
        )
        validated = validate_context(ctx)
        assert validated.scope_id == "fixture_123"
        assert validated.payload["home"] == "Man Utd"
