"""Storage module — unified data persistence for all agent types.

Provides:
- SQLiteConnection: Shared connection management (WAL, busy_timeout, lazy init)
- ForgeStore: Generic time-series record store for any agent data

All agent types (Scraper, Monitor, Analyzer, Generator) can use ForgeStore
to persist their data with a consistent API.

Usage::

    from forge_agent.storage import ForgeStore

    store = ForgeStore()  # or ForgeStore("my_data")

    # Insert
    store.insert("weather.beijing", {"temperature": 25.3, "humidity": 60})

    # Query
    records = store.query(agent_id="weather.beijing", limit=100)

    # Time-series
    series = store.get_time_series("weather.beijing", "temperature")

    # Summary
    stats = store.summary()
"""

from forge_agent.storage.base import SQLiteConnection
from forge_agent.storage.store import ForgeStore, Record

__all__ = [
    "ForgeStore",
    "Record",
    "SQLiteConnection",
]
