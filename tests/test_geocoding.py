"""Reverse-geocode primary/secondary fallback + Angels-Landing cache fix."""

from __future__ import annotations

import asyncio

import pytest

from api import geocode as geocode_module
from services.geocoding import (
    extract_primary_secondary,
    merge_overrides,
    primary_resolution,
    rerank_search_results,
)
from services.nps_overrides import find_overrides


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


# ---------------------------------------------------------------------------
# Forward-search re-rank + curated NPS overrides — "Bryce Canyon" should
# resolve to the National Park, not a Tropic-village or a Texas street.
# ---------------------------------------------------------------------------


def _bryce_organic_nominatim_payload() -> list[dict]:
    """A sanitised copy of what live Nominatim returns for ``Bryce Canyon``
    *before* re-ranking — the village/street/valley hits that prompted the
    user's bug report. Used to exercise both the re-rank logic and the
    curated-override merge in a single fixture."""
    return [
        {
            "place_id": 1,
            "lat": "37.6184",
            "lon": "-112.1422",
            "class": "natural",
            "type": "valley",
            "place_rank": 22,
            "importance": 0.18,
            "addresstype": "valley",
            "name": "Bryce Canyon",
            "display_name": "Bryce Canyon, Tropic, Garfield County, Utah, United States",
            "address": {"valley": "Bryce Canyon", "village": "Tropic"},
        },
        {
            "place_id": 2,
            "lat": "29.6478",
            "lon": "-98.4619",
            "class": "highway",
            "type": "residential",
            "place_rank": 26,
            "importance": 0.05,
            "addresstype": "road",
            "name": "Bryce Canyon",
            "display_name": "Bryce Canyon, San Antonio, Bexar County, Texas, United States",
            "address": {"road": "Bryce Canyon", "city": "San Antonio"},
        },
        {
            "place_id": 3,
            "lat": "39.0281",
            "lon": "-76.9468",
            "class": "highway",
            "type": "residential",
            "place_rank": 26,
            "importance": 0.05,
            "addresstype": "road",
            "name": "Bryce Canyon",
            "display_name": "Bryce Canyon, Calverton, Maryland, United States",
            "address": {"road": "Bryce Canyon"},
        },
    ]


def test_rerank_promotes_protected_area_over_village_valley():
    """Pure unit test for the re-ranker. A protected_area entry hidden at
    the bottom of Nominatim's response must surface to the top — without
    needing the curated overrides table."""
    organic = _bryce_organic_nominatim_payload() + [
        {
            "place_id": 99,
            "lat": "37.59",
            "lon": "-112.19",
            "class": "boundary",
            "type": "protected_area",
            "addresstype": "nature_reserve",
            "importance": 0.51,
            "name": "Bryce Canyon National Park",
            "display_name": "Bryce Canyon National Park, Garfield County, Utah",
            "extratags": {
                "boundary": "protected_area",
                "operator": "National Park Service",
                "protect_class": "2",
            },
        },
    ]
    reranked = rerank_search_results(organic, "Bryce Canyon")
    assert reranked[0]["name"] == "Bryce Canyon National Park"
    # Same-name natural feature must drop *below* the parks/streets, not vanish.
    valley_index = next(
        i for i, r in enumerate(reranked)
        if r["class"] == "natural" and r["type"] == "valley"
    )
    park_index = next(
        i for i, r in enumerate(reranked) if "National Park" in r["name"]
    )
    assert park_index < valley_index


def test_find_overrides_matches_bryce_grand_canyon_death_valley():
    for query, expected in [
        ("Bryce Canyon", "Bryce Canyon National Park"),
        ("bryce canyon", "Bryce Canyon National Park"),
        ("Grand Canyon", "Grand Canyon National Park"),
        ("Death Valley", "Death Valley National Park"),
        ("zion", "Zion National Park"),
    ]:
        hits = find_overrides(query)
        assert hits, f"expected curated hit for {query!r}"
        assert hits[0]["name"] == expected
        # Must look like a Nominatim /search hit so the existing frontend
        # contract holds.
        for key in ("lat", "lon", "name", "display_name", "address", "boundingbox"):
            assert key in hits[0]


def test_find_overrides_ignores_unrelated_query():
    assert find_overrides("San Antonio") == []
    assert find_overrides("") == []


def test_merge_overrides_prepends_and_dedupes_by_name():
    curated = find_overrides("Bryce Canyon")
    organic = _bryce_organic_nominatim_payload() + [
        {
            "name": "Bryce Canyon National Park",  # duplicate of curated
            "lat": "0",
            "lon": "0",
            "class": "leisure",
            "type": "nature_reserve",
            "importance": 0.5,
        },
    ]
    merged = merge_overrides(curated, organic, limit=8)
    # Curated entry must lead.
    assert merged[0]["name"] == "Bryce Canyon National Park"
    # Dedup: the duplicate organic National Park must be dropped.
    park_count = sum(1 for r in merged if r["name"] == "Bryce Canyon National Park")
    assert park_count == 1


def test_geocode_endpoint_returns_bryce_canyon_national_park_first(monkeypatch):
    """End-to-end behaviour: the bug the user filed. Typing ``Bryce Canyon``
    must put the National Park first, not Tropic / a Texas street / the
    Maryland street. Combines curated override + organic re-rank."""
    async def fake_nominatim_get(path, params, accept_language):
        assert path == "/search"
        return _bryce_organic_nominatim_payload()

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    out = _run(geocode_module.geocode(q="Bryce Canyon"))
    assert isinstance(out, list)
    assert out, "expected at least one result"
    assert out[0]["name"] == "Bryce Canyon National Park"
    # Top-2 must contain the park even if a future override list grows.
    top2_names = {r.get("name") for r in out[:2]}
    assert "Bryce Canyon National Park" in top2_names
    # Original Nominatim hits must still be returned (not silently dropped).
    assert any(
        r.get("display_name", "").startswith("Bryce Canyon, Tropic") for r in out
    )


def test_geocode_endpoint_surfaces_grand_canyon_np_even_if_nominatim_omits_it(monkeypatch):
    """Live Nominatim returns *only* the geographic valley node for
    ``Grand Canyon``; the curated override is what guarantees the park
    still shows up at all."""
    async def fake_nominatim_get(path, params, accept_language):
        return [
            {
                "place_id": 11,
                "lat": "36.0980",
                "lon": "-112.0963",
                "class": "natural",
                "type": "valley",
                "place_rank": 22,
                "importance": 0.58,
                "addresstype": "valley",
                "name": "Grand Canyon",
                "display_name": "Grand Canyon, Coconino County, Arizona, United States",
            },
        ]

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    out = _run(geocode_module.geocode(q="Grand Canyon"))
    assert out[0]["name"] == "Grand Canyon National Park"


def test_geocode_endpoint_surfaces_death_valley_np(monkeypatch):
    async def fake_nominatim_get(path, params, accept_language):
        return [
            {
                "place_id": 21,
                "lat": "36.4229",
                "lon": "-116.9137",
                "class": "natural",
                "type": "desert",
                "place_rank": 22,
                "importance": 0.57,
                "addresstype": "desert",
                "name": "Death Valley",
                "display_name": "Death Valley, California, United States",
            },
        ]

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    out = _run(geocode_module.geocode(q="Death Valley"))
    assert out[0]["name"] == "Death Valley National Park"


def test_geocode_endpoint_unrelated_query_passes_through_unchanged(monkeypatch):
    """Non-NPS queries must not be polluted with curated overrides and
    must preserve Nominatim's order when no protected-area boost applies."""
    payload = [
        {
            "place_id": 30,
            "name": "Page",
            "display_name": "Page, Coconino County, Arizona, United States",
            "class": "place",
            "type": "city",
            "addresstype": "city",
            "importance": 0.5,
            "lat": "36.91",
            "lon": "-111.46",
        },
    ]

    async def fake_nominatim_get(path, params, accept_language):
        return list(payload)

    monkeypatch.setattr(geocode_module, "_nominatim_get", fake_nominatim_get)

    out = _run(geocode_module.geocode(q="Page"))
    assert len(out) == 1
    assert out[0]["name"] == "Page"
