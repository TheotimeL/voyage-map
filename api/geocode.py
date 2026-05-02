"""Nominatim proxy. Browser-side calls to nominatim.openstreetmap.org get rate-
limited (429) which surfaces as opaque CORS errors. Routing through the backend
lets us set a proper User-Agent, share an in-process cache across users, and
serialize requests so we never breach the 1 req/s policy."""

import httpx
from fastapi import APIRouter, HTTPException, Query

from services.cache import TTLMemoryCache
from services.throttle import AsyncThrottler

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
    # Round to 0.1° (~10 km) for the cache key — same precision the frontend used.
    cache_key = f"r:{lat:.1f},{lng:.1f}|{zoom}|{accept_language or ''}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"format": "json", "zoom": zoom, "lat": lat, "lon": lng}
    data = await _nominatim_get("/reverse", params, accept_language)
    _cache.set(cache_key, data)
    return data
