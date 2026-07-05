"""Output schema profiles for AgentSpec generation."""

from __future__ import annotations

from typing import Any

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["lean_positive", "lean_neutral", "lean_negative", "risk"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "risk": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {
            "type": "string",
            "enum": ["execute", "watch", "hold", "alert"],
        },
        "metrics": {"type": "object"},
    },
    "required": [
        "verdict",
        "confidence",
        "risk",
        "evidence",
        "recommended_action",
        "metrics",
    ],
}

ANALYSIS_MAPPING: dict[str, str] = {
    "verdict": "verdict",
    "confidence": "confidence",
    "risk": "risk",
    "evidence": "evidence",
    "recommended_action": "recommended_action",
    "metrics": "metrics",
}

MONITOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alert": {"type": "boolean"},
        "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
        "threshold": {"type": "number"},
        "current_value": {"type": "number"},
        "message": {"type": "string"},
        "recommended_action": {
            "type": "string",
            "enum": ["execute", "watch", "hold", "alert"],
        },
    },
    "required": ["alert", "severity", "message", "recommended_action"],
}

MONITOR_MAPPING: dict[str, str] = {
    "verdict": "severity",
    "confidence": "current_value",
    "risk": "threshold",
    "evidence": "message",
    "recommended_action": "recommended_action",
    "metrics": "metrics",
}

GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "format": {"type": "string"},
        "summary": {"type": "string"},
        "recommended_action": {
            "type": "string",
            "enum": ["execute", "watch", "hold", "alert"],
        },
    },
    "required": ["content", "summary", "recommended_action"],
}

GENERATE_MAPPING: dict[str, str] = {
    "verdict": "format",
    "confidence": "confidence",
    "evidence": "summary",
    "recommended_action": "recommended_action",
    "metrics": "metrics",
}


def analysis_mock_response(label: str = "平台") -> str:
    return (
        '{"verdict": "lean_positive", "confidence": 0.78, "risk": 0.18, '
        f'"evidence": ["{label}: Mock 演示数据"], '
        '"recommended_action": "watch", "metrics": {}}'
    )


def monitor_mock_response() -> str:
    return (
        '{"alert": false, "severity": "info", "threshold": 100, '
        '"current_value": 42, "message": "指标正常（Mock）", '
        '"recommended_action": "watch"}'
    )


def synthesizer_mock_response() -> str:
    return analysis_mock_response("汇总")


def search_mock_response() -> str:
    return analysis_mock_response("搜索")
