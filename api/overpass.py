"""Thin Overpass QL proxy. Backend so we sidestep CORS and can cache via SW."""

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/overpass", tags=["overpass"])

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Per-kind QL fragments — each `{bbox}` placeholder is filled with the bounding
# box. Add new kinds here as the UI grows.
SURVIVAL_FRAGMENTS = {
    "water": ['node["amenity"="drinking_water"]({bbox});'],
    "trash": [
        'node["amenity"="waste_disposal"]({bbox});',
        'node["amenity"="recycling"]({bbox});',
    ],
    "dump": [
        'node["sanitary_dump_station"="yes"]({bbox});',
        'node["amenity"="sanitary_dump_station"]({bbox});',
    ],
    "toilet": ['node["amenity"="toilets"]({bbox});'],
    "shower": [
        'node["amenity"="shower"]({bbox});',
        'node["shower"="yes"]({bbox});',
    ],
}

DEFAULT_KINDS = "water,trash,dump,toilet"


@router.get("")
async def overpass_query(
    south: float = Query(...),
    west: float = Query(...),
    north: float = Query(...),
    east: float = Query(...),
    kind: str = Query("survival"),
    kinds: str = Query(DEFAULT_KINDS),
):
    if kind == "trails":
        return await _trails_query(south, west, north, east)
    if kind != "survival":
        raise HTTPException(400, "unknown kind")
    bbox = f"{south},{west},{north},{east}"
    requested = [k.strip() for k in (kinds or "").split(",") if k.strip()]
    requested = [k for k in requested if k in SURVIVAL_FRAGMENTS] or list(SURVIVAL_FRAGMENTS)
    body_lines = []
    for k in requested:
        for frag in SURVIVAL_FRAGMENTS[k]:
            body_lines.append(frag.format(bbox=bbox))
    ql = f"""
    [out:json][timeout:25];
    (
      {chr(10).join(body_lines)}
    );
    out body;
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            OVERPASS_URL,
            data={"data": ql},
            headers={"User-Agent": "Voyage Map (Claude Code)"},
        )
    if r.status_code >= 500:
        raise HTTPException(502, "Overpass upstream error")
    return r.json()


async def _trails_query(south: float, west: float, north: float, east: float):
    bbox = f"{south},{west},{north},{east}"
    # Hiking and foot routes (relations) plus named hiking ways. We ask
    # Overpass for both the relation tags and the geometry centre via
    # `out center`, so each result has a single representative coordinate.
    ql = f"""
    [out:json][timeout:30];
    (
      relation["route"~"^(hiking|foot)$"]({bbox});
      way["highway"="path"]["sac_scale"]({bbox});
      way["highway"="path"]["name"]({bbox});
    );
    out tags center;
    """
    async with httpx.AsyncClient(timeout=35) as c:
        r = await c.post(
            OVERPASS_URL,
            data={"data": ql},
            headers={"User-Agent": "Voyage Map (Claude Code)"},
        )
    if r.status_code >= 500:
        raise HTTPException(502, "Overpass upstream error")
    return r.json()
