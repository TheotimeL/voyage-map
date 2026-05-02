"""Itinerary stop CRUD endpoints, scoped to a map slug.

A "stop" spans `date`..`end_date` inclusive. Single-day stops have
`end_date == date`. The table name `itinerary_days` is kept for backward
compatibility but each row represents one stop, not one calendar day.

Domain helpers (overlap detection, coalescing) live in :mod:`services.itinerary`;
this module is the HTTP boundary only.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.db import get_db
from services.itinerary import coalesce_consecutive_stops, stops_overlap, validate_span
from services.lookup import get_itinerary_day_or_404, get_map_or_404
from services.models import ItineraryDay, Point
from services.schemas import ItineraryDayIn, ItineraryDayOut, ItineraryDayPatch
from services.storage import delete_image, extract_upload_urls

router = APIRouter(prefix="/maps/{slug}/itinerary", tags=["itinerary"])


@router.post("", response_model=ItineraryDayOut, status_code=201)
def add_day(slug: str, payload: ItineraryDayIn, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    end = payload.end_date or payload.date
    validate_span(payload.date, end)
    if stops_overlap(db, m.id, payload.date, end):
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
    """Bulk-insert stops. Coalescing of consecutive same-place rows happens in
    :func:`services.itinerary.coalesce_consecutive_stops`."""
    m = get_map_or_404(db, slug)
    if replace:
        db.query(ItineraryDay).filter(ItineraryDay.map_id == m.id).delete()

    coalesced = coalesce_consecutive_stops(payload)

    if not replace:
        for c in coalesced:
            if stops_overlap(db, m.id, c["date"], c["end_date"]):
                raise HTTPException(409, f"A stop already covers {c['date']}..{c['end_date']}")

    rows = [ItineraryDay(map_id=m.id, **c) for c in coalesced]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@router.patch("/{day_id}", response_model=ItineraryDayOut)
def update_day(slug: str, day_id: int, payload: ItineraryDayPatch, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    d = get_itinerary_day_or_404(db, m.id, day_id)
    old_notes = d.notes
    fields = payload.model_dump(exclude_unset=True)
    new_start = fields.get("date", d.date)
    new_end = fields.get("end_date", d.end_date)
    if "date" in fields and "end_date" not in fields and new_end < new_start:
        # User shrank the start past the stored end_date — collapse to single-day.
        new_end = new_start
        fields["end_date"] = new_end
    validate_span(new_start, new_end)
    if stops_overlap(db, m.id, new_start, new_end, exclude_id=d.id):
        raise HTTPException(409, "A stop already covers one of those dates")
    for k, v in fields.items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    # GC: delete any upload images no longer referenced in notes.
    old_urls = extract_upload_urls(old_notes)
    new_urls = extract_upload_urls(d.notes)
    for url in old_urls - new_urls:
        delete_image(url)
    return d


@router.delete("/{day_id}", status_code=204)
def delete_day(slug: str, day_id: int, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    d = get_itinerary_day_or_404(db, m.id, day_id)
    # GC: delete all upload images referenced in notes before removing the row.
    for url in extract_upload_urls(d.notes):
        delete_image(url)
    # SQLite's ON DELETE SET NULL won't fire (foreign_keys pragma is off), so
    # detach attached points manually before removing the row.
    db.query(Point).filter(Point.itinerary_day_id == d.id).update(
        {Point.itinerary_day_id: None}, synchronize_session=False,
    )
    db.delete(d)
    db.commit()


@router.delete("", status_code=204)
def clear_itinerary(slug: str, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    day_ids = [d.id for d in db.query(ItineraryDay.id).filter(ItineraryDay.map_id == m.id).all()]
    if day_ids:
        db.query(Point).filter(Point.itinerary_day_id.in_(day_ids)).update(
            {Point.itinerary_day_id: None}, synchronize_session=False,
        )
    db.query(ItineraryDay).filter(ItineraryDay.map_id == m.id).delete()
    db.commit()
