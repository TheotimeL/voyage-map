"""Pluggable TTL caches for upstream proxy responses.

Two backends, one shape — both expose ``get(key) -> value | None`` and
``set(key, value)``. Routers pick the backend that matches their lifetime
needs:

* :class:`TTLMemoryCache` — fast, process-local, lost on restart.
* :class:`SQLiteTTLCache` — persisted, survives restarts, slightly slower.
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


class TTLMemoryCache:
    """LRU + TTL in-process cache. Eviction order is access-time."""

    def __init__(self, *, max_entries: int = 512, ttl_seconds: int = 60 * 60 * 24):
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_entries
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        hit = self._store.get(key)
        if not hit:
            return None
        ts, val = hit
        if time.time() - ts > self._ttl:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return val

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)


class SQLiteTTLCache:
    """Persistent JSON cache backed by an arbitrary SQLite table.

    The first call to :meth:`get` or :meth:`set` lazily creates the table —
    callers don't need a separate migration step.
    """

    def __init__(self, engine: Engine, *, table: str, ttl_seconds: int):
        self._engine = engine
        self._table = table
        self._ttl = ttl_seconds
        self._ready = False

    def _ensure_table(self) -> None:
        if self._ready:
            return
        with self._engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """))
        self._ready = True

    def get(self, key: str) -> Any | None:
        self._ensure_table()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(f"SELECT payload, created_at FROM {self._table} WHERE key = :k"),
                {"k": key},
            ).first()
        if not row:
            return None
        payload, created = row
        if time.time() - created > self._ttl:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any) -> None:
        self._ensure_table()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {self._table} (key, payload, created_at) "
                    "VALUES (:k, :p, :ts) "
                    "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, "
                    "created_at = excluded.created_at"
                ),
                {"k": key, "p": json.dumps(value), "ts": int(time.time())},
            )
