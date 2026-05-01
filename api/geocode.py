"""Nominatim proxy. Browser-side calls to nominatim.openstreetmap.org get rate-
limited (429) which surfaces as opaque CORS errors. Routing through the backend
lets us set a proper User-Agent, share an in-process cache across users, and
serialize requests so we never breach the 1 req/s policy."""

import asyncio
import time
from collections import OrderedDict

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["geocode"])

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "Voyage Map (https://github.com/TheotimeL/voyage-map)"
TIMEOUT = 10.0
MIN_INTERVAL = 1.05  # Nominatim policy: ≤1 req/s

_cache: "OrderedDict[str, tuple[float, object]]" = OrderedDict()
CACHE_MAX = 512
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

_lock = asyncio.Lock()
_last_call = 0.0


def _cache_get(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > CACHE_TTL:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return val


def _cache_set(key: str, val) -> None:
    _cache[key] = (time.time(), val)
    _cache.move_to_end(key)
    while len(_cache) > CACHE_MAX:
        _cache.popitem(last=False)


async def _nominatim_get(path: str, params: dict, accept_language: str | None):
    global _last_call
    async with _lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        headers = {"User-Agent": USER_AGENT}
        if accept_language:
            headers["Accept-Language"] = accept_language
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"{NOMINATIM_BASE}{path}", params=params, headers=headers)
        _last_call = time.monotonic()
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
    cached = _cache_get(cache_key)
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
    _cache_set(cache_key, data)
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
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {"format": "json", "zoom": zoom, "lat": lat, "lon": lng}
    data = await _nominatim_get("/reverse", params, accept_language)
    _cache_set(cache_key, data)
    return data
