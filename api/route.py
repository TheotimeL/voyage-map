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

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from services.cache import SQLiteTTLCache
from services.db import engine
from services.routing import DEFAULT_VEHICLE, calibrate_duration, known_vehicles
from services.throttle import AsyncThrottler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/route", tags=["route"])

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
TIMEOUT = 10.0

_cache = SQLiteTTLCache(engine, table="route_cache", ttl_seconds=60 * 60 * 24 * 30)  # 30 days
_throttle = AsyncThrottler(min_interval_seconds=0.6)  # be polite to the public OSRM demo


def _key(a_lat: float, a_lng: float, b_lat: float, b_lng: float, vehicle: str) -> str:
    # Quantise to ~10 m so two near-identical pin moves still hit cache, and
    # canonicalise endpoint order (driving distance is direction-sensitive in
    # general, but for road graphs the diff is tiny — the cache hit is worth
    # it for trip-scale legs).
    pts = sorted([
        (round(a_lat, 4), round(a_lng, 4)),
        (round(b_lat, 4), round(b_lng, 4)),
    ])
    (la1, ln1), (la2, ln2) = pts
    return f"{la1},{ln1}|{la2},{ln2}|v={vehicle}"


async def _fetch_osrm(a_lat: float, a_lng: float, b_lat: float, b_lng: float, vehicle: str):
    """Call the public OSRM demo, throttled and serialized."""
    url = (
        f"{OSRM_URL}/{a_lng},{a_lat};{b_lng},{b_lat}"
        "?overview=simplified&geometries=geojson&steps=false"
    )
    async with _throttle:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(url, headers={"User-Agent": "Voyage Map"})
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
    distance_km = distance / 1000.0
    raw_minutes = duration / 60.0
    cal = calibrate_duration(distance_km, raw_minutes, vehicle)
    if cal.applied:
        logger.info(
            "calibrated leg %.1fkm: raw=%.0fmin (%.0fkm/h) → %.0fmin (vehicle=%s)",
            distance_km, cal.raw_minutes, cal.raw_avg_kmh, cal.minutes, vehicle,
        )
    return {
        "km": round(distance_km),
        "minutes": round(cal.minutes),
        "raw_minutes": round(cal.raw_minutes),
        "calibrated": cal.applied,
        "vehicle": cal.vehicle,
        "source": "osrm",
        "geometry": geometry,
    }


@router.get("")
async def get_route(
    a_lat: float = Query(...),
    a_lng: float = Query(...),
    b_lat: float = Query(...),
    b_lng: float = Query(...),
    vehicle: str = Query(DEFAULT_VEHICLE),
):
    if vehicle not in known_vehicles():
        vehicle = DEFAULT_VEHICLE
    key = _key(a_lat, a_lng, b_lat, b_lng, vehicle)
    cached = _cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        result = await _fetch_osrm(a_lat, a_lng, b_lat, b_lng, vehicle)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("OSRM fetch failed: %s", exc)
        raise HTTPException(502, "OSRM upstream unreachable")

    if result is None:
        raise HTTPException(502, "OSRM returned no route")

    _cache.set(key, result)
    return {**result, "cached": False}
