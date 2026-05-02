"""Nominatim proxy. Browser-side calls to nominatim.openstreetmap.org get rate-
limited (429) which surfaces as opaque CORS errors. Routing through the backend
lets us set a proper User-Agent, share an in-process cache across users, and
serialize requests so we never breach the 1 req/s policy."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from services.cache import TTLMemoryCache
from services.geocoding import primary_resolution
from services.throttle import AsyncThrottler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["geocode"])

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "Voyage Map (https://github.com/TheotimeL/voyage-map)"
TIMEOUT = 10.0

_cache = TTLMemoryCache(max_entries=512, ttl_seconds=60 * 60 * 24 * 7)  # 7 days
_throttle = AsyncThrottler(min_interval_seconds=1.05)  # Nominatim policy: ≤1 req/s


async def _nominatim_get(path: str, params: dict, accept_language: str | None):
    headers = {"User-Agent": USER_AGENT}
    if accept_language:
        headers["Accept-Language"] = accept_language
    async with _throttle:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"{NOMINATIM_BASE}{path}", params=params, headers=headers)
    if r.status_code == 429:
        raise HTTPException(429, "Geocoder rate-limited; try again in a moment")
    if r.status_code >= 400:
        raise HTTPException(502, "Geocoder upstream error")
    return r.json()


@router.get("/geocode")
async def geocode(
    q: str = Query(..., min_length=2),
    viewbox: str | None = Query(None),
    bounded: int = Query(0, ge=0, le=1),
    accept_language: str | None = Query(None, alias="lang"),
):
    """Forward search. `viewbox` is `west,north,east,south` (Nominatim convention)."""
    cache_key = f"s:{q}|{viewbox or ''}|{bounded}|{accept_language or ''}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "format": "json",
        "limit": "8",
        "dedupe": "1",
        "addressdetails": "1",
        "extratags": "1",
        "q": q,
    }
    if viewbox:
        params["viewbox"] = viewbox
        if bounded:
            params["bounded"] = "1"
    data = await _nominatim_get("/search", params, accept_language)
    _cache.set(cache_key, data)
    return data


@router.get("/reverse")
async def reverse(
    lat: float = Query(...),
    lng: float = Query(...),
    zoom: int = Query(10, ge=0, le=18),
    accept_language: str | None = Query(None, alias="lang"),
):
    # Round to ~1 km. The previous 0.1° (~10 km) bucket was wide enough to
    # let a pin at Angels Landing (Washington Co., UT) collide with a cached
    # Kane County result and serve the wrong admin polygon — we'd rather
    # pay extra Nominatim calls than misattribute a stop's county.
    cache_key = f"r:{lat:.2f},{lng:.2f}|{zoom}|{accept_language or ''}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"format": "json", "zoom": zoom, "lat": lat, "lon": lng}
    data = await _nominatim_get("/reverse", params, accept_language)
    data = _enrich_reverse(data, lat, lng)
    _cache.set(cache_key, data)
    return data


def _enrich_reverse(data: dict, lat: float, lng: float) -> dict:
    """Attach primary/secondary labels and log the resolved admin region.

    Logging lets us spot upstream stale-tile / wrong-polygon issues (where
    Nominatim returns the wrong county for a point) without having to
    re-run the trip — the requested point and resolved address show up
    side-by-side in the server log.
    """
    if not isinstance(data, dict):
        return data
    address = data.get("address") or {}
    resolution = primary_resolution(address)
    enriched = {**data, **resolution}
    logger.info(
        "reverse %.5f,%.5f → %s (county=%s state=%s)",
        lat, lng, resolution.get("label"), address.get("county"), address.get("state"),
    )
    return enriched
