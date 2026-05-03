"""Helpers for shaping Nominatim reverse-geocode payloads.

Nominatim returns a flat ``address`` block whose populated keys depend on
the OSM tagging at that point. For the UI we want a stable two-line label —
a *primary* place name (usually a city/town) and a *secondary* admin region
(usually a county or state). Naïvely picking the first non-empty key in
each tier breaks for places like Page, AZ where the city, township and
county can all share the same name and you end up showing "Page / Page".

:func:`extract_primary_secondary` walks both tiers and guarantees the two
labels differ — when the obvious fallback collides with the primary it
keeps walking the admin chain until something distinct is found.
"""

from __future__ import annotations


PRIMARY_KEYS = (
    "city",
    "town",
    "village",
    "hamlet",
    "municipality",
    "locality",
    "suburb",
    "neighbourhood",
)

SECONDARY_KEYS = (
    "county",
    "state_district",
    "region",
    "province",
    "state",
    "country",
)


def _first(address: dict, keys: tuple[str, ...], skip: set[str]) -> str | None:
    for k in keys:
        v = address.get(k)
        if v and v not in skip:
            return v
    return None


def extract_primary_secondary(address: dict | None) -> tuple[str | None, str | None]:
    """Return (primary, secondary) labels with a guaranteed-distinct subline.

    When the most-specific populated-place name matches the next admin-level
    label (Page → Page county/township), keep descending the admin chain
    until a different name appears. Falls back gracefully when only admin
    levels are populated (e.g. unincorporated wilderness pins).
    """
    address = address or {}
    primary = _first(address, PRIMARY_KEYS, skip=set())

    if primary is None:
        # No populated-place tag — promote the first admin level to primary
        # so the UI still shows *something* identifiable.
        primary = _first(address, SECONDARY_KEYS, skip=set())
        if primary is None:
            return None, None
        secondary = _first(address, SECONDARY_KEYS, skip={primary})
        return primary, secondary

    secondary = _first(address, SECONDARY_KEYS, skip={primary})
    return primary, secondary


def primary_resolution(address: dict | None) -> dict[str, str | None]:
    """Build a structured response slice attached to the reverse-geocode payload.

    Kept separate from the raw Nominatim fields so existing consumers that
    read ``address.city`` keep working unchanged.
    """
    primary, secondary = extract_primary_secondary(address)
    return {
        "primary": primary,
        "secondary": secondary,
        "label": " / ".join(p for p in (primary, secondary) if p) or None,
    }


# ---------------------------------------------------------------------------
# Forward-search re-ranking — push NPS-protected areas above same-named
# villages, valleys, gorges and (somehow) football stadiums. Nominatim's
# importance metric is global and trained on edit volume, which means a
# tiny Utah hamlet outranks the National Park polygon next door. For a US
# road-trip product the right default is the park.
# ---------------------------------------------------------------------------


# Tags / strings that mark a result as a protected area worth boosting.
_PROTECTED_TYPES = {
    ("boundary", "protected_area"),
    ("boundary", "national_park"),
    ("leisure", "nature_reserve"),
}

_PROTECTED_NAME_HINTS = (
    "national park",
    "national monument",
    "national forest",
    "national recreation area",
    "national seashore",
    "national lakeshore",
    "national preserve",
    "national historic",
    "state park",
    "wilderness",
)

# addresstype values that indicate a populated place — these get pushed
# *down* relative to a same-named protected area.
_VILLAGE_LIKE_ADDRESSTYPES = {
    "village",
    "hamlet",
    "town",
    "city",
    "suburb",
    "neighbourhood",
    "locality",
    "quarter",
    "residential",
    "road",
    "house",
    "place",
}


def _result_text(result: dict) -> str:
    """Concatenate name + display_name for keyword scanning."""
    parts = []
    for key in ("name", "display_name"):
        v = result.get(key)
        if isinstance(v, str):
            parts.append(v.lower())
    return " | ".join(parts)


def _is_protected_area(result: dict) -> bool:
    """Detect NPS-style results across the several ways OSM tags them.

    OSM is gloriously inconsistent: some parks come back as
    ``class=boundary, type=protected_area``, some as
    ``leisure/nature_reserve``, some as plain ``natural/...`` features
    with ``extratags.boundary=protected_area`` or a name suffix. We accept
    any of those signals.
    """
    if not isinstance(result, dict):
        return False

    cls = result.get("class")
    typ = result.get("type")
    if (cls, typ) in _PROTECTED_TYPES:
        return True

    extratags = result.get("extratags") or {}
    if isinstance(extratags, dict):
        if extratags.get("boundary") in {"protected_area", "national_park"}:
            return True
        if extratags.get("protect_class"):
            return True
        if extratags.get("protected_area"):
            return True
        operator = (extratags.get("operator") or "").lower()
        if "national park service" in operator or operator == "nps":
            return True
        website = (extratags.get("website") or "").lower()
        if "nps.gov" in website:
            return True

    name = (result.get("name") or "").lower()
    display = (result.get("display_name") or "").lower()
    for hint in _PROTECTED_NAME_HINTS:
        if hint in name or hint in display:
            return True

    return False


def _is_village_like(result: dict) -> bool:
    addresstype = (result.get("addresstype") or "").lower()
    return addresstype in _VILLAGE_LIKE_ADDRESSTYPES


def _is_natural_feature(result: dict) -> bool:
    """Valleys / gorges / deserts that share a name with the park.

    These are the entries Nominatim ranks above the protected-area polygon
    (Death Valley → ``natural/desert`` outranks the park). We don't *hide*
    them — we just don't want them on top.
    """
    cls = (result.get("class") or "").lower()
    return cls in {"natural"}


def _rank_score(result: dict, query: str) -> tuple[int, float]:
    """Sort key — higher is better.

    Tiers (first element):
      3 = protected area whose name contains the query (best)
      2 = any protected area
      1 = anything else that isn't a village/road/natural feature
      0 = village/road
     -1 = natural feature with same-name collision (valley/desert/gorge)

    Within a tier we fall back to Nominatim's own ``importance`` so the
    organic ranking still breaks ties sensibly.
    """
    importance = result.get("importance")
    try:
        importance = float(importance) if importance is not None else 0.0
    except (TypeError, ValueError):
        importance = 0.0

    name_lc = (result.get("name") or "").lower()
    q_lc = (query or "").lower().strip()

    if _is_protected_area(result):
        if q_lc and q_lc in name_lc:
            return (3, importance)
        return (2, importance)

    if _is_village_like(result):
        return (0, importance)

    if _is_natural_feature(result):
        # Same-name natural feature is the classic "Death Valley desert
        # outranks the park" trap — push it below everything that could
        # plausibly be the park.
        return (-1, importance)

    return (1, importance)


def rerank_search_results(results: list[dict], query: str) -> list[dict]:
    """Stable re-rank of a Nominatim /search response.

    Pure function: takes the list straight off the wire and returns a new
    list. ``stable=True`` (Python's default sort is stable) so within a
    tier we preserve the upstream order — which means we don't have to
    re-implement Nominatim's tie-breaking.
    """
    if not isinstance(results, list):
        return results
    indexed = list(enumerate(results))
    indexed.sort(key=lambda pair: (_rank_score(pair[1], query), -pair[0]), reverse=True)
    return [r for _, r in indexed]


def merge_overrides(curated: list[dict], organic: list[dict], limit: int = 8) -> list[dict]:
    """Prepend curated NPS overrides, dedupe by name, cap at ``limit``.

    Dedupe uses the lower-cased ``name`` field — when Nominatim *does*
    return the same park polygon we want the curated entry to win (its
    ``importance`` is hand-set to 0.95) but we don't want both to appear.
    """
    if not curated:
        return organic[:limit]

    seen_names = {(c.get("name") or "").lower() for c in curated}
    deduped_organic = [
        r for r in organic
        if (r.get("name") or "").lower() not in seen_names
    ]
    merged = curated + deduped_organic
    return merged[:limit]
