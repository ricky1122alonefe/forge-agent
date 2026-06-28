"""Scraper module — comprehensive data scraping system.

Provides:
- ScraperConfig: Structured configuration for scraper tasks
- ScraperEngine: Core execution engine with retry, rate limiting, scheduling
- SQLiteDataStore: Time-series storage for scraped data
- Parsers: HTML (BeautifulSoup), JSON API, RSS feed parsing

Usage::

    from forge_agent.scraper import ScraperConfig, ScraperEngine, SQLiteDataStore

    config = ScraperConfig(
        agent_id="weather.beijing",
        name="Beijing Weather",
        source_type="json_api",
        urls=["https://wttr.in/Beijing?format=j1"],
        fields=[
            {"name": "temp_c", "selector": "current_condition[0].temp_C", "type": "float"},
        ],
        interval_seconds=1800,  # every 30 minutes
    )

    store = SQLiteDataStore()
    engine = ScraperEngine(config, store)

    # Run once
    records = await engine.run()

    # Or start scheduled execution
    await engine.start_scheduler()
"""

from forge_agent.scraper.config import (
    AuthType,
    FieldDef,
    ScraperConfig,
    SourceType,
)
from forge_agent.scraper.engine import ScraperEngine
from forge_agent.scraper.parser import (
    compute_checksum,
    parse_html,
    parse_json,
    parse_rss,
)
from forge_agent.scraper.store import ScrapedRecord, SQLiteDataStore

__all__ = [
    "AuthType",
    "FieldDef",
    "SQLiteDataStore",
    "ScrapedRecord",
    "ScraperConfig",
    "ScraperEngine",
    "SourceType",
    "compute_checksum",
    "parse_html",
    "parse_json",
    "parse_rss",
]
