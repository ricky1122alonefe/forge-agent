"""ScraperConfig — structured configuration for a scraper task.

Abstracts away the differences between HTML scraping, JSON API calls,
and RSS feeds behind a single configuration object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    """Type of data source."""

    HTML = "html"
    JSON_API = "json_api"
    RSS = "rss"


class AuthType(str, Enum):
    """Authentication method."""

    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    API_KEY = "api_key"
    BASIC = "basic"
    COOKIE = "cookie"


@dataclass
class FieldDef:
    """Definition of a single data field to extract."""

    name: str
    selector: str = ""  # CSS selector (HTML) or JSONPath (JSON)
    type: str = "str"  # str / int / float / bool / datetime
    required: bool = False
    default: Any = None
    transform: str = ""  # optional: "strip", "lower", "float", "int"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "selector": self.selector,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "transform": self.transform,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FieldDef:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ScraperConfig:
    """Complete configuration for a scraper task.

    Example::

        config = ScraperConfig(
            agent_id="weather.beijing",
            name="Beijing Weather",
            source_type=SourceType.HTML,
            urls=["https://wttr.in/Beijing?format=j1"],
            fields=[
                FieldDef(name="temp_c", selector=".temp", type="float"),
                FieldDef(name="humidity", selector=".humidity", type="str"),
            ],
            schedule="*/30 * * * *",  # every 30 minutes
        )
    """

    agent_id: str
    name: str
    source_type: SourceType = SourceType.HTML
    urls: list[str] = field(default_factory=list)
    fields: list[FieldDef] = field(default_factory=list)

    # Schedule
    schedule: str = ""  # cron expression, e.g. "*/30 * * * *"
    interval_seconds: int = 0  # alternative: fixed interval

    # HTTP settings
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0
    rate_limit: float = 1.0  # seconds between requests
    user_agent: str = ""
    custom_headers: dict[str, str] = field(default_factory=dict)

    # Auth
    auth_type: AuthType = AuthType.NONE
    auth_token: str = ""
    auth_user: str = ""
    auth_pass: str = ""

    # Proxy
    proxy_url: str = ""

    # Output
    output_format: str = "json"  # json / csv / markdown
    dedup: bool = True  # skip duplicate records

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "urls": self.urls,
            "fields": [f.to_dict() for f in self.fields],
            "schedule": self.schedule,
            "interval_seconds": self.interval_seconds,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "rate_limit": self.rate_limit,
            "user_agent": self.user_agent,
            "custom_headers": self.custom_headers,
            "auth_type": self.auth_type.value,
            "auth_token": self.auth_token,
            "proxy_url": self.proxy_url,
            "output_format": self.output_format,
            "dedup": self.dedup,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScraperConfig:
        fields_raw = d.pop("fields", [])
        source_type = d.pop("source_type", "html")
        auth_type = d.pop("auth_type", "none")
        fields = [FieldDef.from_dict(f) for f in fields_raw]
        return cls(
            fields=fields,
            source_type=SourceType(source_type),
            auth_type=AuthType(auth_type),
            **{k: v for k, v in d.items() if k in cls.__dataclass_fields__},
        )
