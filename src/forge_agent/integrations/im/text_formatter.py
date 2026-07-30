"""Report formatters — render run results into IM messages (S5.3).

TextReportFormatter: plain-text fallback for any platform.
FeishuCardFormatter: Feishu interactive card with rich formatting.
"""

from __future__ import annotations

from typing import Any

from forge_agent.integrations.im.base import IMMessage


class TextReportFormatter:
    """Plain-text formatter — works with any platform."""

    def format_success(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        result: dict[str, Any],
    ) -> IMMessage:
        lines = [
            f"✅ Pipeline `{pipeline_id}` completed",
            f"Run: {run_id}",
        ]
        summary = result.get("chief_summary", {}) if isinstance(result, dict) else {}
        verdict = summary.get("verdict", "")
        if verdict:
            lines.append(f"Verdict: {verdict}")
        confidence = summary.get("confidence", "")
        if confidence is not None:
            lines.append(f"Confidence: {confidence}")
        agents = result.get("agent_reports", [])
        if agents:
            lines.append(f"Agents: {len(agents)}")
        return IMMessage(platform=platform, chat_id=chat_id, text="\n".join(lines))

    def format_failure(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        error: str,
    ) -> IMMessage:
        return IMMessage(
            platform=platform,
            chat_id=chat_id,
            text=(f"❌ Pipeline `{pipeline_id}` failed\nRun: {run_id}\nError: {error[:500]}"),
        )


class FeishuCardFormatter:
    """Feishu interactive card formatter with rich layout."""

    def format_success(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        result: dict[str, Any],
    ) -> IMMessage:
        elements: list[dict[str, Any]] = [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**✅ {pipeline_id}** completed"},
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"Run ID: `{run_id}`"},
            },
        ]

        summary = result.get("chief_summary", {}) if isinstance(result, dict) else {}
        verdict = summary.get("verdict", "")
        if verdict:
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**Verdict:** {verdict}"},
                }
            )
        confidence = summary.get("confidence")
        if confidence is not None:
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**Confidence:** {confidence}"},
                }
            )

        agents = result.get("agent_reports", [])
        if agents:
            agent_lines = []
            for a in agents[:5]:
                name = a.get("name", a.get("agent_id", "?"))
                v = a.get("verdict", "")
                agent_lines.append(f"  • {name}: {v}")
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**Agents:**\n" + "\n".join(agent_lines),
                    },
                }
            )

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"✅ {pipeline_id}"},
                "template": "green",
            },
            "elements": elements,
        }
        return IMMessage(platform=platform, chat_id=chat_id, card=card)

    def format_failure(
        self,
        *,
        platform: str,
        chat_id: str,
        run_id: str,
        pipeline_id: str,
        error: str,
    ) -> IMMessage:
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"❌ {pipeline_id} failed"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"Run ID: `{run_id}`"},
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**Error:** {error[:500]}"},
                },
            ],
        }
        return IMMessage(platform=platform, chat_id=chat_id, card=card)
