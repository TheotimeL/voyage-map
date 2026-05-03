"""Curated US National Park Service unit overrides for the forward geocoder.

Nominatim's importance ranking systematically buries NPS-protected areas
under same-named villages, valleys, gorges and deserts. For a US road-trip
product that's the wrong default — when a user types "Death Valley" or
"Grand Canyon" they almost always mean the park, not the unincorporated
community or the geographic feature.

Rather than scrape nps.gov, we keep a small hand-maintained table of the
most ambiguous units (Southwest-heavy because that's where the May 2026
trip lives, plus the famous-name parks where a bare query is likely to
collide elsewhere on the planet). Entries are merged into the geocoder
response when the query matches an alias — they get placed at rank 0 with
``addresstype=protected_area`` so the existing frontend renders them like
any other Nominatim hit.

Coords were sourced from the units' Wikipedia infobox / NPS visitor center
addresses. Centimeter accuracy isn't the goal — the user re-confirms the
spot via the map UI before saving, so "good enough to land in the park" is
the bar. ``boundingbox`` is roughly the unit envelope so the frontend's
fly-to logic frames it sensibly.
"""

from __future__ import annotations

import re

# Schema mirrors a Nominatim /search hit closely enough that the existing
# response-shape contract holds. ``aliases`` are lower-cased substrings the
# query must match (after normalisation) for the override to apply.
_OVERRIDES: list[dict] = [
    {
        "aliases": ("bryce canyon", "bryce"),
        "name": "Bryce Canyon National Park",
        "display_name": "Bryce Canyon National Park, Garfield County, Utah, United States",
        "lat": "37.5930",
        "lon": "-112.1871",
        "boundingbox": ["37.4421", "37.6993", "-112.2740", "-112.0833"],
        "address": {
            "nature_reserve": "Bryce Canyon National Park",
            "county": "Garfield County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("grand canyon",),
        "name": "Grand Canyon National Park",
        "display_name": "Grand Canyon National Park, Coconino County, Arizona, United States",
        "lat": "36.0544",
        "lon": "-112.1401",
        "boundingbox": ["35.9700", "36.5000", "-113.4000", "-111.7000"],
        "address": {
            "nature_reserve": "Grand Canyon National Park",
            "county": "Coconino County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("death valley",),
        "name": "Death Valley National Park",
        "display_name": "Death Valley National Park, Inyo County, California, United States",
        "lat": "36.5054",
        "lon": "-117.0794",
        "boundingbox": ["35.7500", "37.4000", "-117.7500", "-116.0500"],
        "address": {
            "nature_reserve": "Death Valley National Park",
            "county": "Inyo County",
            "state": "California",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("zion",),
        "name": "Zion National Park",
        "display_name": "Zion National Park, Washington County, Utah, United States",
        "lat": "37.2982",
        "lon": "-113.0263",
        "boundingbox": ["37.1300", "37.5000", "-113.2700", "-112.8500"],
        "address": {
            "nature_reserve": "Zion National Park",
            "county": "Washington County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("arches",),
        "name": "Arches National Park",
        "display_name": "Arches National Park, Grand County, Utah, United States",
        "lat": "38.7331",
        "lon": "-109.5925",
        "boundingbox": ["38.5800", "38.8300", "-109.7600", "-109.4500"],
        "address": {
            "nature_reserve": "Arches National Park",
            "county": "Grand County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("canyonlands",),
        "name": "Canyonlands National Park",
        "display_name": "Canyonlands National Park, San Juan County, Utah, United States",
        "lat": "38.2000",
        "lon": "-109.9300",
        "boundingbox": ["37.7300", "38.5800", "-110.2300", "-109.5400"],
        "address": {
            "nature_reserve": "Canyonlands National Park",
            "county": "San Juan County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("capitol reef",),
        "name": "Capitol Reef National Park",
        "display_name": "Capitol Reef National Park, Wayne County, Utah, United States",
        "lat": "38.3667",
        "lon": "-111.2615",
        "boundingbox": ["37.7300", "38.6000", "-111.5000", "-110.9000"],
        "address": {
            "nature_reserve": "Capitol Reef National Park",
            "county": "Wayne County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("joshua tree",),
        "name": "Joshua Tree National Park",
        "display_name": "Joshua Tree National Park, Riverside County, California, United States",
        "lat": "33.8734",
        "lon": "-115.9010",
        "boundingbox": ["33.5500", "34.1500", "-116.4000", "-115.4000"],
        "address": {
            "nature_reserve": "Joshua Tree National Park",
            "county": "Riverside County",
            "state": "California",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("yosemite",),
        "name": "Yosemite National Park",
        "display_name": "Yosemite National Park, Mariposa County, California, United States",
        "lat": "37.8651",
        "lon": "-119.5383",
        "boundingbox": ["37.4900", "38.1900", "-119.8900", "-119.2000"],
        "address": {
            "nature_reserve": "Yosemite National Park",
            "county": "Mariposa County",
            "state": "California",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("sequoia",),
        "name": "Sequoia National Park",
        "display_name": "Sequoia National Park, Tulare County, California, United States",
        "lat": "36.4864",
        "lon": "-118.5658",
        "boundingbox": ["36.2400", "36.8200", "-118.8400", "-118.2600"],
        "address": {
            "nature_reserve": "Sequoia National Park",
            "county": "Tulare County",
            "state": "California",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("kings canyon",),
        "name": "Kings Canyon National Park",
        "display_name": "Kings Canyon National Park, Fresno County, California, United States",
        "lat": "36.8879",
        "lon": "-118.5551",
        "boundingbox": ["36.6800", "37.1000", "-118.9600", "-118.3000"],
        "address": {
            "nature_reserve": "Kings Canyon National Park",
            "county": "Fresno County",
            "state": "California",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("yellowstone",),
        "name": "Yellowstone National Park",
        "display_name": "Yellowstone National Park, Wyoming, United States",
        "lat": "44.4280",
        "lon": "-110.5885",
        "boundingbox": ["44.1320", "45.1100", "-111.1550", "-109.8300"],
        "address": {
            "nature_reserve": "Yellowstone National Park",
            "state": "Wyoming",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("grand teton",),
        "name": "Grand Teton National Park",
        "display_name": "Grand Teton National Park, Teton County, Wyoming, United States",
        "lat": "43.7904",
        "lon": "-110.6818",
        "boundingbox": ["43.5600", "44.0000", "-110.9000", "-110.4000"],
        "address": {
            "nature_reserve": "Grand Teton National Park",
            "county": "Teton County",
            "state": "Wyoming",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("glacier national park", "glacier np"),
        "name": "Glacier National Park",
        "display_name": "Glacier National Park, Flathead County, Montana, United States",
        "lat": "48.7596",
        "lon": "-113.7870",
        "boundingbox": ["48.2200", "49.0000", "-114.5000", "-113.2000"],
        "address": {
            "nature_reserve": "Glacier National Park",
            "county": "Flathead County",
            "state": "Montana",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("rocky mountain national park", "rocky mountain np", "rmnp"),
        "name": "Rocky Mountain National Park",
        "display_name": "Rocky Mountain National Park, Larimer County, Colorado, United States",
        "lat": "40.3428",
        "lon": "-105.6836",
        "boundingbox": ["40.1500", "40.5500", "-105.9100", "-105.4900"],
        "address": {
            "nature_reserve": "Rocky Mountain National Park",
            "county": "Larimer County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("mesa verde",),
        "name": "Mesa Verde National Park",
        "display_name": "Mesa Verde National Park, Montezuma County, Colorado, United States",
        "lat": "37.2309",
        "lon": "-108.4618",
        "boundingbox": ["37.1500", "37.4000", "-108.6000", "-108.2900"],
        "address": {
            "nature_reserve": "Mesa Verde National Park",
            "county": "Montezuma County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("great sand dunes",),
        "name": "Great Sand Dunes National Park",
        "display_name": "Great Sand Dunes National Park, Saguache County, Colorado, United States",
        "lat": "37.7916",
        "lon": "-105.5943",
        "boundingbox": ["37.6500", "37.9500", "-105.7800", "-105.4500"],
        "address": {
            "nature_reserve": "Great Sand Dunes National Park",
            "county": "Saguache County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("black canyon of the gunnison", "black canyon"),
        "name": "Black Canyon of the Gunnison National Park",
        "display_name": "Black Canyon of the Gunnison National Park, Montrose County, Colorado, United States",
        "lat": "38.5754",
        "lon": "-107.7416",
        "boundingbox": ["38.4800", "38.6500", "-107.8500", "-107.5800"],
        "address": {
            "nature_reserve": "Black Canyon of the Gunnison National Park",
            "county": "Montrose County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("petrified forest",),
        "name": "Petrified Forest National Park",
        "display_name": "Petrified Forest National Park, Apache County, Arizona, United States",
        "lat": "34.9100",
        "lon": "-109.8068",
        "boundingbox": ["34.7500", "35.0800", "-109.9500", "-109.6500"],
        "address": {
            "nature_reserve": "Petrified Forest National Park",
            "county": "Apache County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("saguaro",),
        "name": "Saguaro National Park",
        "display_name": "Saguaro National Park, Pima County, Arizona, United States",
        "lat": "32.2967",
        "lon": "-111.1666",
        "boundingbox": ["32.1500", "32.4500", "-111.2300", "-110.5800"],
        "address": {
            "nature_reserve": "Saguaro National Park",
            "county": "Pima County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("carlsbad caverns", "carlsbad"),
        "name": "Carlsbad Caverns National Park",
        "display_name": "Carlsbad Caverns National Park, Eddy County, New Mexico, United States",
        "lat": "32.1479",
        "lon": "-104.5567",
        "boundingbox": ["32.0500", "32.2700", "-104.7500", "-104.3500"],
        "address": {
            "nature_reserve": "Carlsbad Caverns National Park",
            "county": "Eddy County",
            "state": "New Mexico",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("white sands",),
        "name": "White Sands National Park",
        "display_name": "White Sands National Park, Otero County, New Mexico, United States",
        "lat": "32.7872",
        "lon": "-106.3257",
        "boundingbox": ["32.6700", "33.0500", "-106.5800", "-106.1100"],
        "address": {
            "nature_reserve": "White Sands National Park",
            "county": "Otero County",
            "state": "New Mexico",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("guadalupe mountains",),
        "name": "Guadalupe Mountains National Park",
        "display_name": "Guadalupe Mountains National Park, Culberson County, Texas, United States",
        "lat": "31.9231",
        "lon": "-104.8694",
        "boundingbox": ["31.7800", "32.0500", "-105.0000", "-104.6500"],
        "address": {
            "nature_reserve": "Guadalupe Mountains National Park",
            "county": "Culberson County",
            "state": "Texas",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("big bend",),
        "name": "Big Bend National Park",
        "display_name": "Big Bend National Park, Brewster County, Texas, United States",
        "lat": "29.1275",
        "lon": "-103.2425",
        "boundingbox": ["28.9700", "29.6800", "-103.6700", "-102.9400"],
        "address": {
            "nature_reserve": "Big Bend National Park",
            "county": "Brewster County",
            "state": "Texas",
            "country": "United States",
            "country_code": "us",
        },
    },
    # Selected national monuments / recreation areas — same naming-collision
    # problem (e.g. "Bears Ears" the buttes vs the monument).
    {
        "aliases": ("bears ears",),
        "name": "Bears Ears National Monument",
        "display_name": "Bears Ears National Monument, San Juan County, Utah, United States",
        "lat": "37.6294",
        "lon": "-109.8632",
        "boundingbox": ["37.2500", "38.0000", "-110.3500", "-109.4000"],
        "address": {
            "nature_reserve": "Bears Ears National Monument",
            "county": "San Juan County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("grand staircase", "grand staircase-escalante", "escalante"),
        "name": "Grand Staircase-Escalante National Monument",
        "display_name": "Grand Staircase-Escalante National Monument, Kane County, Utah, United States",
        "lat": "37.4413",
        "lon": "-111.6730",
        "boundingbox": ["37.0000", "37.9000", "-112.4000", "-110.7000"],
        "address": {
            "nature_reserve": "Grand Staircase-Escalante National Monument",
            "county": "Kane County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("monument valley",),
        "name": "Monument Valley Navajo Tribal Park",
        "display_name": "Monument Valley Navajo Tribal Park, San Juan County, Utah, United States",
        "lat": "36.9980",
        "lon": "-110.0985",
        "boundingbox": ["36.9000", "37.1000", "-110.2000", "-109.9500"],
        "address": {
            "nature_reserve": "Monument Valley Navajo Tribal Park",
            "county": "San Juan County",
            "state": "Utah",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("antelope canyon",),
        "name": "Antelope Canyon",
        "display_name": "Antelope Canyon, Coconino County, Arizona, United States",
        "lat": "36.8619",
        "lon": "-111.3743",
        "boundingbox": ["36.8500", "36.8800", "-111.3900", "-111.3600"],
        "address": {
            "nature_reserve": "Antelope Canyon",
            "county": "Coconino County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("horseshoe bend",),
        "name": "Horseshoe Bend",
        "display_name": "Horseshoe Bend, Coconino County, Arizona, United States",
        "lat": "36.8791",
        "lon": "-111.5104",
        "boundingbox": ["36.8700", "36.8900", "-111.5200", "-111.5000"],
        "address": {
            "nature_reserve": "Horseshoe Bend",
            "county": "Coconino County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
    {
        "aliases": ("lake powell",),
        "name": "Glen Canyon National Recreation Area",
        "display_name": "Glen Canyon National Recreation Area (Lake Powell), Coconino County, Arizona, United States",
        "lat": "37.0680",
        "lon": "-111.2400",
        "boundingbox": ["36.7000", "37.7500", "-111.6500", "-110.5000"],
        "address": {
            "nature_reserve": "Glen Canyon National Recreation Area",
            "county": "Coconino County",
            "state": "Arizona",
            "country": "United States",
            "country_code": "us",
        },
    },
]


_WORD = re.compile(r"[a-z0-9]+")


def _normalise(s: str) -> str:
    """Lowercase + collapse whitespace + strip punctuation for matching."""
    return " ".join(_WORD.findall(s.lower()))


def find_overrides(query: str) -> list[dict]:
    """Return curated NPS hits whose alias matches the (normalised) query.

    Matching is *contains* in either direction — typing "Bryce" or
    "Bryce Canyon" or "Bryce Canyon NP" all surface the Bryce override.
    Returned dicts are shallow copies shaped like Nominatim /search hits
    so they can be merged into the response without further massaging.
    """
    normalised = _normalise(query)
    if not normalised:
        return []

    hits: list[dict] = []
    seen_names: set[str] = set()
    for entry in _OVERRIDES:
        for alias in entry["aliases"]:
            if alias in normalised or normalised in alias:
                if entry["name"] in seen_names:
                    break
                hits.append(_to_search_hit(entry))
                seen_names.add(entry["name"])
                break
    return hits


def _to_search_hit(entry: dict) -> dict:
    """Shape a curated entry like a Nominatim /search response item.

    Uses the same key set the live API returns so the frontend doesn't
    need to special-case overrides. ``place_id`` is namespaced into a
    distinct integer range (9_000_000_000+) to avoid colliding with real
    Nominatim ids if the frontend ever dedupes by id.
    """
    name = entry["name"]
    return {
        "place_id": 9_000_000_000 + (hash(name) & 0x3FFFFFFF),
        "licence": "Curated NPS overrides (Voyage Map)",
        "osm_type": "relation",
        "osm_id": 0,
        "lat": entry["lat"],
        "lon": entry["lon"],
        "class": "boundary",
        "type": "protected_area",
        "place_rank": 24,
        "importance": 0.95,  # Above any organic Nominatim result.
        "addresstype": "nature_reserve",
        "name": name,
        "display_name": entry["display_name"],
        "address": dict(entry["address"]),
        "extratags": {
            "boundary": "protected_area",
            "operator": "National Park Service",
            "protect_class": "2",
            "curated": "voyage-map",
        },
        "boundingbox": list(entry["boundingbox"]),
    }
