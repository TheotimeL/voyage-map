"""Itinerary stop CRUD endpoints, scoped to a map slug.

A "stop" spans `date`..`end_date` inclusive. Single-day stops have
`end_date == date`. The table name `itinerary_days` is kept for backward
compatibility but each row represents one stop, not one calendar day.
"""

from datetime import date as date_type, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.db import get_db
from services.models import ItineraryDay, Map, Point
from services.schemas import ItineraryDayIn, ItineraryDayOut, ItineraryDayPatch

router = APIRouter(prefix="/maps/{slug}/itinerary", tags=["itinerary"])


def _get_map_or_404(db: Session, slug: str) -> Map:
    m = db.query(Map).filter(Map.slug == slug).first()
    if m is None:
        raise HTTPException(404, "Map not found")
    return m


def _validate_span(start: date_type, end: date_type) -> None:
    if end < start:
        raise HTTPException(400, "end_date must be on or after date")


def _stops_overlap(db: Session, map_id: int, start: date_type, end: date_type, exclude_id: int | None = None) -> bool:
    """True iff any other stop on this map intersects the [start, end] range."""
    q = db.query(ItineraryDay).filter(
        ItineraryDay.map_id == map_id,
        ItineraryDay.date <= end,
        ItineraryDay.end_date >= start,
    )
    if exclude_id is not None:
        q = q.filter(ItineraryDay.id != exclude_id)
    return db.query(q.exists()).scalar()


@router.post("", response_model=ItineraryDayOut, status_code=201)
def add_day(slug: str, payload: ItineraryDayIn, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    end = payload.end_date or payload.date
    _validate_span(payload.date, end)
    if _stops_overlap(db, m.id, payload.date, end):
        raise HTTPException(409, "A stop already covers one of those dates")
    fields = payload.model_dump()
    fields["end_date"] = end
    d = ItineraryDay(map_id=m.id, **fields)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.post("/bulk", response_model=list[ItineraryDayOut], status_code=201)
def add_days_bulk(
    slug: str,
    payload: list[ItineraryDayIn],
    replace: bool = False,
    db: Session = Depends(get_db),
):
    """Bulk-insert stops. Coalesces consecutive rows with matching label+coords
    (the typical paste-import shape: "Day 6 BLM, Day 7 BLM" → one stop spanning
    both dates). Single-day rows pass through untouched."""
    m = _get_map_or_404(db, slug)
    if replace:
        db.query(ItineraryDay).filter(ItineraryDay.map_id == m.id).delete()

    sorted_payload = sorted(payload, key=lambda r: r.date)
    coalesced: list[dict] = []
    for r in sorted_payload:
        end = r.end_date or r.date
        _validate_span(r.date, end)
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

    if not replace:
        for c in coalesced:
            if _stops_overlap(db, m.id, c["date"], c["end_date"]):
                raise HTTPException(409, f"A stop already covers {c['date']}..{c['end_date']}")

    rows = [ItineraryDay(map_id=m.id, **c) for c in coalesced]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@router.patch("/{day_id}", response_model=ItineraryDayOut)
def update_day(slug: str, day_id: int, payload: ItineraryDayPatch, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    d = db.query(ItineraryDay).filter(ItineraryDay.id == day_id, ItineraryDay.map_id == m.id).first()
    if d is None:
        raise HTTPException(404, "Stop not found")
    fields = payload.model_dump(exclude_unset=True)
    new_start = fields.get("date", d.date)
    new_end = fields.get("end_date", d.end_date)
    if "date" in fields and "end_date" not in fields and new_end < new_start:
        # User shrank the start past the stored end_date — collapse to single-day.
        new_end = new_start
        fields["end_date"] = new_end
    _validate_span(new_start, new_end)
    if _stops_overlap(db, m.id, new_start, new_end, exclude_id=d.id):
        raise HTTPException(409, "A stop already covers one of those dates")
    for k, v in fields.items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return d


@router.delete("/{day_id}", status_code=204)
def delete_day(slug: str, day_id: int, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    d = db.query(ItineraryDay).filter(ItineraryDay.id == day_id, ItineraryDay.map_id == m.id).first()
    if d is None:
        raise HTTPException(404, "Day not found")
    # SQLite's ON DELETE SET NULL won't fire (foreign_keys pragma is off), so
    # detach attached points manually before removing the row.
    db.query(Point).filter(Point.itinerary_day_id == d.id).update(
        {Point.itinerary_day_id: None}, synchronize_session=False,
    )
    db.delete(d)
    db.commit()


@router.delete("", status_code=204)
def clear_itinerary(slug: str, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    day_ids = [d.id for d in db.query(ItineraryDay.id).filter(ItineraryDay.map_id == m.id).all()]
    if day_ids:
        db.query(Point).filter(Point.itinerary_day_id.in_(day_ids)).update(
            {Point.itinerary_day_id: None}, synchronize_session=False,
        )
    db.query(ItineraryDay).filter(ItineraryDay.map_id == m.id).delete()
    db.commit()
