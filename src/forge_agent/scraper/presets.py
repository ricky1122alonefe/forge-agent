"""Domain presets — pre-configured scraper templates for common scenarios.

When a user says "grab weather data" or "monitor stock prices",
the system can auto-fill URLs, selectors, and field definitions
based on the domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge_agent.scraper.config import FieldDef, SourceType


@dataclass
class DomainPreset:
    """A pre-configured scraper template for a specific domain."""

    domain: str
    label: str
    description: str
    icon: str
    source_type: SourceType
    sources: list[dict[str, str]]  # [{"name": "...", "url": "...", "description": "..."}]
    fields: list[FieldDef]
    default_schedule: str = "0 */1 * * *"  # default cron
    default_interval: int = 3600  # default interval in seconds
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "source_type": self.source_type.value,
            "sources": self.sources,
            "fields": [f.to_dict() for f in self.fields],
            "default_schedule": self.default_schedule,
            "default_interval": self.default_interval,
            "examples": self.examples,
        }


# ──────────────────────────────────────────────────────────────
# Preset Registry
# ──────────────────────────────────────────────────────────────

PRESETS: dict[str, DomainPreset] = {}


def _register(preset: DomainPreset) -> None:
    PRESETS[preset.domain] = preset


# ── Weather ──────────────────────────────────────────────────

_register(
    DomainPreset(
        domain="weather",
        label="天气数据",
        description="抓取天气预报、实时温度、湿度、风速等气象数据",
        icon="🌤️",
        source_type=SourceType.JSON_API,
        sources=[
            {
                "name": "wttr.in",
                "url": "https://wttr.in/{city}?format=j1",
                "description": "免费天气 API，支持全球城市",
            },
            {
                "name": "Open-Meteo",
                "url": "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true",
                "description": "开源天气 API，无需 API Key",
            },
        ],
        fields=[
            FieldDef(
                name="temperature",
                selector="current_condition[0].temp_C",
                type="float",
                transform="float",
            ),
            FieldDef(
                name="feels_like",
                selector="current_condition[0].FeelsLikeC",
                type="float",
                transform="float",
            ),
            FieldDef(
                name="humidity",
                selector="current_condition[0].humidity",
                type="int",
                transform="int",
            ),
            FieldDef(
                name="description", selector="current_condition[0].weatherDesc[0].value", type="str"
            ),
            FieldDef(
                name="wind_speed",
                selector="current_condition[0].windspeedKmph",
                type="float",
                transform="float",
            ),
            FieldDef(name="wind_dir", selector="current_condition[0].winddir16Point", type="str"),
            FieldDef(
                name="visibility",
                selector="current_condition[0].visibility",
                type="float",
                transform="float",
            ),
            FieldDef(
                name="pressure",
                selector="current_condition[0].pressure",
                type="int",
                transform="int",
            ),
        ],
        default_schedule="*/30 * * * *",
        default_interval=1800,
        examples=["北京天气", "上海实时气温", "东京未来天气"],
    )
)


# ── News ─────────────────────────────────────────────────────

_register(
    DomainPreset(
        domain="news",
        label="新闻资讯",
        description="抓取新闻标题、摘要、发布时间、来源等信息",
        icon="📰",
        source_type=SourceType.RSS,
        sources=[
            {
                "name": "Hacker News",
                "url": "https://hnrss.org/frontpage",
                "description": "Hacker News 首页 RSS",
            },
            {
                "name": "TechCrunch",
                "url": "https://techcrunch.com/feed/",
                "description": "科技新闻",
            },
            {
                "name": "Reuters Top",
                "url": "https://www.reutersagency.com/feed/",
                "description": "路透社头条",
            },
            {
                "name": "BBC News",
                "url": "https://feeds.bbci.co.uk/news/rss.xml",
                "description": "BBC 新闻",
            },
            {"name": "36Kr", "url": "https://36kr.com/feed", "description": "36氪科技资讯"},
        ],
        fields=[
            FieldDef(name="title", selector="title", type="str", transform="strip"),
            FieldDef(name="link", selector="link", type="str"),
            FieldDef(name="description", selector="description", type="str", transform="strip"),
            FieldDef(name="pub_date", selector="pubDate", type="str"),
        ],
        default_schedule="0 */1 * * *",
        default_interval=3600,
        examples=["科技新闻", "财经头条", "Hacker News 热帖"],
    )
)


# ── Stock / Finance ──────────────────────────────────────────

_register(
    DomainPreset(
        domain="stock",
        label="股票行情",
        description="抓取股票价格、涨跌幅、成交量等金融数据",
        icon="📈",
        source_type=SourceType.JSON_API,
        sources=[
            {
                "name": "Yahoo Finance",
                "url": "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d",
                "description": "Yahoo 股票数据 API",
            },
            {
                "name": "CoinGecko",
                "url": "https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true",
                "description": "加密货币价格",
            },
        ],
        fields=[
            FieldDef(
                name="price",
                selector="chart.result[0].meta.regularMarketPrice",
                type="float",
                transform="float",
            ),
            FieldDef(
                name="previous_close",
                selector="chart.result[0].meta.previousClose",
                type="float",
                transform="float",
            ),
            FieldDef(name="currency", selector="chart.result[0].meta.currency", type="str"),
            FieldDef(name="exchange", selector="chart.result[0].meta.exchangeName", type="str"),
        ],
        default_schedule="*/5 * * * *",
        default_interval=300,
        examples=["苹果股价", "比特币价格", "纳斯达克指数"],
    )
)


# ── E-commerce / Price ───────────────────────────────────────

_register(
    DomainPreset(
        domain="ecommerce",
        label="电商价格",
        description="抓取商品价格、库存状态、促销信息",
        icon="🛒",
        source_type=SourceType.HTML,
        sources=[
            {"name": "自定义网站", "url": "", "description": "输入任意电商商品页面 URL"},
        ],
        fields=[
            FieldDef(name="title", selector="h1", type="str", transform="strip"),
            FieldDef(name="price", selector=".price", type="float", transform="float"),
            FieldDef(name="availability", selector=".availability", type="str", transform="strip"),
            FieldDef(name="rating", selector=".rating", type="float", transform="float"),
        ],
        default_schedule="0 */6 * * *",
        default_interval=21600,
        examples=["Amazon 商品价格追踪", "淘宝商品监控"],
    )
)


# ── Sports / Odds ────────────────────────────────────────────

_register(
    DomainPreset(
        domain="sports",
        label="体育数据",
        description="抓取比赛结果、赔率、积分榜等体育数据",
        icon="⚽",
        source_type=SourceType.JSON_API,
        sources=[
            {
                "name": "Football-Data.org",
                "url": "https://api.football-data.org/v4/matches",
                "description": "足球比赛数据（需 API Key）",
            },
            {"name": "自定义 API", "url": "", "description": "输入任意体育数据 API"},
        ],
        fields=[
            FieldDef(name="home_team", selector="matches[0].homeTeam.name", type="str"),
            FieldDef(name="away_team", selector="matches[0].awayTeam.name", type="str"),
            FieldDef(
                name="home_score",
                selector="matches[0].score.fullTime.home",
                type="int",
                transform="int",
            ),
            FieldDef(
                name="away_score",
                selector="matches[0].score.fullTime.away",
                type="int",
                transform="int",
            ),
            FieldDef(name="status", selector="matches[0].status", type="str"),
        ],
        default_schedule="*/15 * * * *",
        default_interval=900,
        examples=["英超比赛结果", "NBA 比分", "世界杯赔率"],
    )
)


# ── Social Media ─────────────────────────────────────────────

_register(
    DomainPreset(
        domain="social",
        label="社交媒体",
        description="抓取帖子内容、互动数据、热门话题",
        icon="💬",
        source_type=SourceType.JSON_API,
        sources=[
            {
                "name": "Reddit",
                "url": "https://www.reddit.com/r/{subreddit}/hot.json?limit=10",
                "description": "Reddit 热帖",
            },
            {
                "name": "Hacker News API",
                "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
                "description": "HN 热门帖子",
            },
        ],
        fields=[
            FieldDef(name="title", selector="data.children[0].data.title", type="str"),
            FieldDef(
                name="score", selector="data.children[0].data.score", type="int", transform="int"
            ),
            FieldDef(
                name="comments",
                selector="data.children[0].data.num_comments",
                type="int",
                transform="int",
            ),
            FieldDef(name="url", selector="data.children[0].data.url", type="str"),
        ],
        default_schedule="0 */2 * * *",
        default_interval=7200,
        examples=["Reddit 热帖", "HN 热门", "微博热搜"],
    )
)


# ── Custom ───────────────────────────────────────────────────

_register(
    DomainPreset(
        domain="custom",
        label="自定义",
        description="完全自定义抓取配置，适合特殊网站和 API",
        icon="⚙️",
        source_type=SourceType.HTML,
        sources=[
            {"name": "自定义", "url": "", "description": "输入任意 URL"},
        ],
        fields=[],
        default_schedule="0 */1 * * *",
        default_interval=3600,
        examples=["任意网站数据抓取"],
    )
)


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────


def list_presets() -> list[dict[str, Any]]:
    """List all available domain presets."""
    return [p.to_dict() for p in PRESETS.values()]


def get_preset(domain: str) -> DomainPreset | None:
    """Get a preset by domain name."""
    return PRESETS.get(domain)


def get_preset_domains() -> list[str]:
    """Get all available domain names."""
    return list(PRESETS.keys())
