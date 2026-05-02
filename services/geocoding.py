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
