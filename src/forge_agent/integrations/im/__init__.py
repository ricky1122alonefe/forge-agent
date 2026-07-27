"""IM integration adapters for forge-agent.

Adapters are plugins over the runtime layer — they trigger Pipelines
and receive callbacks, but never touch core / Pipeline directly.

S1 ships the protocol + data contracts; concrete platform adapters
(Feishu, DingTalk, WeCom, Slack) land in S5.
"""

from forge_agent.integrations.im.base import IMAdapter, IMEvent, IMMessage

__all__ = ["IMAdapter", "IMEvent", "IMMessage"]
