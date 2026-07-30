"""IM integration adapters for forge-agent.

Adapters are plugins over the runtime layer — they trigger Pipelines
and receive callbacks, but never touch core / Pipeline directly.

S5 implementations: Feishu + DingTalk adapters, DefaultIMRouter,
TextReportFormatter, FeishuCardFormatter, IMCallback.
"""

from forge_agent.integrations.im.base import IMAdapter, IMEvent, IMMessage
from forge_agent.integrations.im.callback import IMCallback
from forge_agent.integrations.im.default_router import DefaultIMRouter
from forge_agent.integrations.im.dingtalk import DingTalkAdapter
from forge_agent.integrations.im.feishu import FeishuAdapter
from forge_agent.integrations.im.formatter import ReportFormatter
from forge_agent.integrations.im.text_formatter import (
    FeishuCardFormatter,
    TextReportFormatter,
)

__all__ = [
    "DefaultIMRouter",
    "DingTalkAdapter",
    "FeishuAdapter",
    "FeishuCardFormatter",
    "IMAdapter",
    "IMCallback",
    "IMEvent",
    "IMMessage",
    "ReportFormatter",
    "TextReportFormatter",
]
