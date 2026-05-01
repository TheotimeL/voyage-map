"""OSRM driving-route proxy with persistent SQLite cache.

Browser-side calls to the OSRM demo server are rate-limited and unreliable;
worse, the in-memory cache evaporates on every page load, so the user sees
the dashed-fallback "estimate" lines come back even after the routes already
resolved once. Routing through the backend lets us:

  * persist resolved geometries across sessions in a single `route_cache`
    table (key = quantised (a, b) pair so reverse + slightly-moved points
    still hit the same row),
  * serialize requests so we don't hammer the public OSRM,
  * keep the response shape identical to what `frontend/src/lib/routing.js`
    already consumes — drop-in replacement.
"""

import asyncio
import json
import logging
import time

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from services.db import engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/route", tags=["route"])

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
TIMEOUT = 10.0
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
MIN_INTERVAL = 0.6  # be polite to the public OSRM demo

_lock = asyncio.Lock()
_last_call = 0.0
_table_ready = False


def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS route_cache (
                key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """))
    _table_ready = True


def _key(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> str:
    # Quantise to ~10 m so two near-identical pin moves still hit cache, and
    # canonicalise endpoint order (driving distance is direction-sensitive in
    # general, but for road graphs the diff is tiny — the cache hit is worth
    # it for trip-scale legs).
    pts = sorted([
        (round(a_lat, 4), round(a_lng, 4)),
        (round(b_lat, 4), round(b_lng, 4)),
    ])
    (la1, ln1), (la2, ln2) = pts
    return f"{la1},{ln1}|{la2},{ln2}"


def _cache_get(key: str):
    _ensure_table()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT payload, created_at FROM route_cache WHERE key = :k"),
            {"k": key},
        ).first()
    if not row:
        return None
    payload, created = row
    if time.time() - created > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _cache_set(key: str, value) -> None:
    _ensure_table()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO route_cache (key, payload, created_at) "
                "VALUES (:k, :p, :ts) "
                "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, "
                "created_at = excluded.created_at"
            ),
            {"k": key, "p": json.dumps(value), "ts": int(time.time())},
        )


async def _fetch_osrm(a_lat: float, a_lng: float, b_lat: float, b_lng: float):
    """Call the public OSRM demo, throttled and serialized."""
    global _last_call
    url = (
        f"{OSRM_URL}/{a_lng},{a_lat};{b_lng},{b_lat}"
        "?overview=simplified&geometries=geojson&steps=false"
    )
    async with _lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(url, headers={"User-Agent": "Voyage Map"})
        _last_call = time.monotonic()
    if r.status_code >= 400:
        raise HTTPException(502, "OSRM upstream error")
    data = r.json()
    route = (data.get("routes") or [None])[0]
    if not route:
        return None
    distance = route.get("distance")
    duration = route.get("duration")
    if not isinstance(distance, (int, float)) or not isinstance(duration, (int, float)):
        return None
    coords = (route.get("geometry") or {}).get("coordinates") or []
    # Convert OSRM's [lng, lat] tuples to Leaflet's [lat, lng] up-front so
    # the frontend doesn't have to.
    geometry = [[lat, lng] for lng, lat in coords] if coords else None
    return {
        "km": round(distance / 1000),
        "minutes": round(duration / 60),
        "source": "osrm",
        "geometry": geometry,
    }


@router.get("")
async def get_route(
    a_lat: float = Query(...),
    a_lng: float = Query(...),
    b_lat: float = Query(...),
    b_lng: float = Query(...),
):
    key = _key(a_lat, a_lng, b_lat, b_lng)
    cached = _cache_get(key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        result = await _fetch_osrm(a_lat, a_lng, b_lat, b_lng)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("OSRM fetch failed: %s", exc)
        raise HTTPException(502, "OSRM upstream unreachable")

    if result is None:
        raise HTTPException(502, "OSRM returned no route")

    _cache_set(key, result)
    return {**result, "cached": False}
