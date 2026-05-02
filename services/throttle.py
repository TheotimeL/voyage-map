"""Async throttler shared by upstream proxies.

Public APIs we proxy (Nominatim, OSRM demo) impose request-rate ceilings; a
single ``AsyncThrottler`` per upstream serializes calls in-process and waits
out the gap when callers arrive too soon.
"""

import asyncio
import time


class AsyncThrottler:
    """Serialize async calls and enforce a minimum interval between them."""

    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def __aenter__(self):
        await self._lock.acquire()
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._last_call = time.monotonic()
        self._lock.release()
