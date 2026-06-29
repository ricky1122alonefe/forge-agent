"""Async utilities."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, TypeVar

T = TypeVar("T")


def run_sync(coro: Awaitable[T]) -> T:
    """Run an awaitable to completion. Convenience for scripts & tests."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an event loop; create a new one in a thread.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, coro).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


async def gather_dict(tasks: dict[str, Awaitable[Any]]) -> dict[str, Any]:
    """Like asyncio.gather but returns a dict keyed by task name."""
    keys = list(tasks.keys())
    values = await asyncio.gather(*tasks.values(), return_exceptions=False)
    return dict(zip(keys, values, strict=False))
