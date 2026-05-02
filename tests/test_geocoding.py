"""Reverse-geocode primary/secondary fallback + Angels-Landing cache fix."""

from __future__ import annotations

import asyncio

import pytest

from api import geocode as geocode_module
from services.geocoding import extract_primary_secondary, primary_resolution


# ---------------------------------------------------------------------------
# extract_primary_secondary — the "Page / Page" bug and its neighbours.
# ---------------------------------------------------------------------------


def test_page_az_falls_back_to_county_when_city_collides():
    """Page, AZ has both `city` and a township-shaped admin polygon named
    Page, so the naïve secondary (`county`-via-first-non-empty) used to be
    "Page" again. The fallback should keep walking to "Coconino County"."""
    address = {
        "city": "Page",
        "town": "Page",            # OSM duplicates the name across tiers
        "county": "Coconino County",
        "state": "Arizona",
        "country": "United States",
    }
    primary, secondary = extract_primary_secondary(address)
    assert primary == "Page"
    assert secondary == "Coconino County"


def test_clark_county_unincorporated_still_works():
    """Existing-correct case: a pin out in unincorporated desert returns
    just the county. Don't regress this."""
    address = {
        "county": "Clark County",
        "state": "Nevada",
        "country": "United States",
    }
    primary, secondary = extract_primary_secondary(address)
    assert primary == "Clark County"
    assert secondary == "Nevada"


def test_mariposa_county_with_village_renders_distinct_levels():
    address = {
        "village": "El Portal",
        "county": "Mariposa County",
        "state": "California",
        "country": "United States",
    }
    primary, secondary = extract_primary_secondary(address)
    assert primary == "El Portal"
    assert secondary == "Mariposa County"


def test_collision_walks_past_state_district_to_state():
    """Defence in depth: if every admin level up through the county shares
    the city's name, we still keep walking until something distinct (state)
    appears."""
    address = {
        "town": "Same",
        "county": "Same",
        "state_district": "Same",
        "state": "Different",
        "country": "Elsewhere",
    }
    primary, secondary = extract_primary_secondary(address)
    assert primary == "Same"
    assert secondary == "Different"


def test_empty_address_returns_none():
    assert extract_primary_secondary({}) == (None, None)
    assert extract_primary_secondary(None) == (None, None)


def test_primary_resolution_label_is_slash_joined():
    res = primary_resolution({
        "city": "Page",
        "county": "Coconino County",
    })
    assert res == {
        "primary": "Page",
        "secondary": "Coconino County",
        "label": "Page / Coconino County",
    }


def test_primary_resolution_label_drops_empty_subline():
    res = primary_resolution({"city": "Solo"})
    assert res["label"] == "Solo"
    assert res["secondary"] is None


# ---------------------------------------------------------------------------
# Reverse-geocode endpoint — Angels-Landing-style cache collision regression.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_reverse_cache(monkeypatch):
    """Each test gets a fresh in-memory cache so prior runs don't bleed in."""
    from services.cache import TTLMemoryCache

    fresh = TTLMemoryCache(max_entries=64, ttl_seconds=60)
    monkeypatch.setattr(geocode_module, "_cache", fresh)
    yield


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_angels_landing_does_not_serve_kane_county_from_cache(monkeypatch):
    """Two pins ~10 km apart used to share a 0.1°-rounded cache key, so a
    cached "Kane County" reply got served back for an Angels-Landing pin
    that is in Washington County. Tightening the cache key to 0.01° must
    fix the collision."""
    calls = []

    async def fake_nominatim_get(path, params, accept_language):
        calls.append((float(params["lat"]), float(params["lon"])))
        # Return whichever county matches the actual pin — never a stale tile.
        if abs(float(params["lat"]) - 37.27) < 0.05:
            return {
                "address": {
                    "village": "Springdale",
                    "county": "Washington County",
                    "state": "Utah",
                    "country": "United States",
                },
            }
        return {
            "address": {
                "county": "Kane County",
                "state": "Utah",
                "country": "United States",
            },
        }

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    # First request: a Kane County pin (~10 km east of Angels Landing).
    kane = _run(geocode_module.reverse(lat=37.34, lng=-112.86))
    # Second request: Angels Landing itself (Washington County, UT).
    zion = _run(geocode_module.reverse(lat=37.27, lng=-112.95))

    assert kane["address"]["county"] == "Kane County"
    assert zion["address"]["county"] == "Washington County"
    assert zion["primary"] == "Springdale"
    assert zion["secondary"] == "Washington County"
    # Both lookups must hit Nominatim — old 0.1° rounding would have collapsed
    # them into a single cache entry and only made one call.
    assert len(calls) == 2


def test_reverse_attaches_primary_secondary_label(monkeypatch):
    async def fake_nominatim_get(path, params, accept_language):
        return {
            "address": {
                "city": "Page",
                "town": "Page",
                "county": "Coconino County",
                "state": "Arizona",
                "country": "United States",
            },
        }

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    out = _run(geocode_module.reverse(lat=36.91, lng=-111.46))
    assert out["primary"] == "Page"
    assert out["secondary"] == "Coconino County"
    assert out["label"] == "Page / Coconino County"
    # Raw Nominatim fields must still pass through for the existing frontend.
    assert out["address"]["city"] == "Page"


def test_reverse_logs_resolved_admin_region(monkeypatch, caplog):
    """Issue 3 also asks us to log requested point + resolved admin region
    so we can spot upstream stale-tile / wrong-polygon issues without
    re-running the trip."""
    async def fake_nominatim_get(path, params, accept_language):
        return {
            "address": {
                "village": "Springdale",
                "county": "Washington County",
                "state": "Utah",
            },
        }

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    with caplog.at_level("INFO", logger=geocode_module.logger.name):
        _run(geocode_module.reverse(lat=37.27, lng=-112.95))

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "37.27" in joined and "-112.95" in joined
    assert "Washington County" in joined
