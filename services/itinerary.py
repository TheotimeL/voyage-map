"""Itinerary domain logic. The router stays thin — HTTP-shaped helpers (raise
``HTTPException``) plus pure functions for things that don't need a DB session."""

from datetime import date as date_type, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from services.models import ItineraryDay
from services.schemas import ItineraryDayIn


def validate_span(start: date_type, end: date_type) -> None:
    if end < start:
        raise HTTPException(400, "end_date must be on or after date")


def stops_overlap(
    db: Session,
    map_id: int,
    start: date_type,
    end: date_type,
    exclude_id: int | None = None,
) -> bool:
    """True iff any other stop on this map intersects the [start, end] range."""
    q = db.query(ItineraryDay).filter(
        ItineraryDay.map_id == map_id,
        ItineraryDay.date <= end,
        ItineraryDay.end_date >= start,
    )
    if exclude_id is not None:
        q = q.filter(ItineraryDay.id != exclude_id)
    return db.query(q.exists()).scalar()


def coalesce_consecutive_stops(payload: list[ItineraryDayIn]) -> list[dict]:
    """Merge consecutive rows with matching label+coords+notes into spans.

    The typical paste-import shape is "Day 6 BLM, Day 7 BLM" where the same
    place spans multiple days. Single-day rows pass through untouched.
    Validates each span via :func:`validate_span` and returns plain dicts
    suitable for ``ItineraryDay(**row)`` construction.
    """
    sorted_payload = sorted(payload, key=lambda r: r.date)
    coalesced: list[dict] = []
    for r in sorted_payload:
        end = r.end_date or r.date
        validate_span(r.date, end)
        prev = coalesced[-1] if coalesced else None
        same_place = (
            prev is not None
            and prev["label"] == r.label
            and prev["lat"] == r.lat
            and prev["lng"] == r.lng
            and prev["notes"] == r.notes
            and prev["end_date"] + timedelta(days=1) == r.date
        )
        if same_place:
            prev["end_date"] = end
        else:
            coalesced.append({
                "date": r.date,
                "end_date": end,
                "label": r.label,
                "lat": r.lat,
                "lng": r.lng,
                "notes": r.notes,
            })
    return coalesced
