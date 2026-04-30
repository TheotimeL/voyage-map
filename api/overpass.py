"""Thin Overpass QL proxy. Backend so we sidestep CORS and can cache via SW."""

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/overpass", tags=["overpass"])

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@router.get("")
async def overpass_query(
    south: float = Query(...),
    west: float = Query(...),
    north: float = Query(...),
    east: float = Query(...),
    kind: str = Query("survival"),
):
    if kind != "survival":
        raise HTTPException(400, "unknown kind")
    bbox = f"{south},{west},{north},{east}"
    ql = f"""
    [out:json][timeout:25];
    (
      node["amenity"="drinking_water"]({bbox});
      node["amenity"="waste_disposal"]({bbox});
      node["sanitary_dump_station"="yes"]({bbox});
      node["amenity"="toilets"]({bbox});
    );
    out body;
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            OVERPASS_URL,
            data={"data": ql},
            headers={"User-Agent": "Voyage Map (Claude Code)"}
        )
    if r.status_code >= 500:
        raise HTTPException(502, "Overpass upstream error")
    return r.json()
