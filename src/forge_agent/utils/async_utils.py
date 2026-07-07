"""Async utilities."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, TypeVar

T = TypeVar("T")


def run_sync(coro: Awaitable[T]) -> T:
    """Run an awaitable to completion from sync or async callers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


async def gather_dict(tasks: dict[str, Awaitable[Any]]) -> dict[str, Any]:
    """Like asyncio.gather but returns a dict keyed by task name."""
    keys = list(tasks.keys())
    values = await asyncio.gather(*tasks.values(), return_exceptions=False)
    return dict(zip(keys, values, strict=False))
