"""ScraperEngine — orchestrates fetching, parsing, and storing data.

This is the core execution engine that:
1. Fetches data from URLs (HTML/JSON/RSS)
2. Parses using configured fields
3. Stores in ForgeStore (unified storage)
4. Handles retries, rate limiting, and anti-scraping
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timezone
from typing import Any

import httpx

from forge_agent.scraper.config import AuthType, ScraperConfig, SourceType
from forge_agent.scraper.parser import compute_checksum, parse_html, parse_json, parse_rss
from forge_agent.storage import ForgeStore, Record

log = logging.getLogger(__name__)

# Default User-Agent pool for anti-scraping
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


class ScraperEngine:
    """Core scraper execution engine.

    Usage::

        config = ScraperConfig(
            agent_id="weather.beijing",
            name="Beijing Weather",
            source_type=SourceType.HTML,
            urls=["https://wttr.in/Beijing?format=j1"],
            fields=[...],
        )
        store = ForgeStore()
        engine = ScraperEngine(config, store)

        # Run once
        results = await engine.run()

        # Or start scheduled execution
        await engine.start_scheduler()
    """

    def __init__(
        self,
        config: ScraperConfig,
        store: ForgeStore | None = None,
    ) -> None:
        self.config = config
        self.store = store or ForgeStore()
        self._scheduler_task: asyncio.Task | None = None

    async def run(self) -> list[Record]:
        """Execute scraper once for all configured URLs.

        Returns:
            List of Record objects that were stored
        """
        records = []

        for url in self.config.urls:
            try:
                record = await self._scrape_url(url)
                if record:
                    stored = self.store.insert(
                        agent_id=record.agent_id,
                        data=record.data,
                        category="scraped",
                        source=record.source,
                        checksum=record.checksum,
                        timestamp=record.timestamp,
                        dedup=bool(record.checksum),
                    )
                    if stored.id and stored.id > 0:
                        records.append(stored)
                        log.info(
                            "Stored record for %s from %s (id=%d)",
                            self.config.agent_id,
                            url,
                            stored.id,
                        )
                    else:
                        log.debug("Skipped duplicate record for %s", self.config.agent_id)

                # Rate limiting between URLs
                if self.config.rate_limit > 0 and url != self.config.urls[-1]:
                    await asyncio.sleep(self.config.rate_limit)

            except Exception as exc:
                log.error(
                    "Failed to scrape %s from %s: %s",
                    self.config.agent_id,
                    url,
                    exc,
                )

        return records

    async def _scrape_url(self, url: str) -> Record | None:
        """Scrape a single URL with retry logic."""
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                data = await self._fetch(url)
                if data is None:
                    return None

                # Parse based on source type
                parsed = self._parse(data)

                # Create record
                timestamp = datetime.now(timezone.utc).isoformat()
                checksum = compute_checksum(parsed) if self.config.dedup else ""

                return Record(
                    agent_id=self.config.agent_id,
                    data=parsed,
                    category="scraped",
                    source=url,
                    checksum=checksum,
                    timestamp=timestamp,
                )

            except Exception as exc:
                last_error = exc
                log.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                )

                if attempt < self.config.max_retries:
                    # Exponential backoff
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        log.error(
            "All %d attempts failed for %s: %s",
            self.config.max_retries,
            url,
            last_error,
        )
        return None

    async def _fetch(self, url: str) -> str | dict | None:
        """Fetch content from URL with anti-scraping measures."""
        # Build headers
        headers = dict(self.config.custom_headers)
        if not self.config.user_agent:
            headers["User-Agent"] = random.choice(_USER_AGENTS)
        else:
            headers["User-Agent"] = self.config.user_agent

        # Add auth headers
        if self.config.auth_type == AuthType.BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        elif self.config.auth_type == AuthType.API_KEY:
            headers["X-API-Key"] = self.config.auth_token

        # Build client config
        client_kwargs: dict[str, Any] = {
            "timeout": self.config.timeout,
            "follow_redirects": True,
        }
        if self.config.proxy_url:
            client_kwargs["proxies"] = {"all://": self.config.proxy_url}

        # Auth for basic auth
        auth = None
        if self.config.auth_type == AuthType.BASIC:
            auth = (self.config.auth_user, self.config.auth_pass)

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url, headers=headers, auth=auth)
            response.raise_for_status()

            # Return appropriate format based on source type
            if self.config.source_type == SourceType.JSON_API:
                return response.json()
            else:
                return response.text

    def _parse(self, data: str | dict) -> dict[str, Any]:
        """Parse fetched data based on source type."""
        if self.config.source_type == SourceType.HTML:
            if not isinstance(data, str):
                raise ValueError("HTML source requires string data")
            return parse_html(data, self.config.fields)

        elif self.config.source_type == SourceType.JSON_API:
            if not isinstance(data, dict | list):
                raise ValueError("JSON API source requires dict/list data")
            return parse_json(data, self.config.fields)

        elif self.config.source_type == SourceType.RSS:
            if not isinstance(data, str):
                raise ValueError("RSS source requires string data")
            items = parse_rss(data, self.config.fields)
            # Return first item or empty dict
            return items[0] if items else {}

        else:
            raise ValueError(f"Unknown source type: {self.config.source_type}")

    async def start_scheduler(self) -> None:
        """Start scheduled execution based on cron or interval.

        This runs indefinitely until stop_scheduler() is called.
        """
        if self._scheduler_task:
            log.warning("Scheduler already running for %s", self.config.agent_id)
            return

        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        log.info(
            "Started scheduler for %s (schedule=%s, interval=%ds)",
            self.config.agent_id,
            self.config.schedule,
            self.config.interval_seconds,
        )

    async def stop_scheduler(self) -> None:
        """Stop scheduled execution."""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
            self._scheduler_task = None
            log.info("Stopped scheduler for %s", self.config.agent_id)

    async def _scheduler_loop(self) -> None:
        """Internal scheduler loop."""
        try:
            if self.config.interval_seconds > 0:
                # Fixed interval mode
                while True:
                    await self.run()
                    await asyncio.sleep(self.config.interval_seconds)

            elif self.config.schedule:
                # Cron expression mode
                try:
                    from croniter import croniter
                except ImportError:
                    log.error(
                        "croniter is required for cron scheduling. "
                        "Install with: pip install croniter"
                    )
                    return

                cron = croniter(self.config.schedule, datetime.now(timezone.utc))

                while True:
                    next_run = cron.get_next(datetime)
                    now = datetime.now(timezone.utc)
                    delay = (next_run - now).total_seconds()

                    if delay > 0:
                        log.debug(
                            "Next run for %s at %s (in %.1fs)",
                            self.config.agent_id,
                            next_run.isoformat(),
                            delay,
                        )
                        await asyncio.sleep(delay)

                    await self.run()

            else:
                log.error(
                    "No schedule configured for %s (need schedule or interval_seconds)",
                    self.config.agent_id,
                )

        except asyncio.CancelledError:
            log.debug("Scheduler loop cancelled for %s", self.config.agent_id)
            raise
