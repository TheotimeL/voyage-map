"""Itinerary day CRUD endpoints, scoped to a map slug."""

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


@router.post("", response_model=ItineraryDayOut, status_code=201)
def add_day(slug: str, payload: ItineraryDayIn, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    d = ItineraryDay(map_id=m.id, **payload.model_dump())
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
    m = _get_map_or_404(db, slug)
    if replace:
        db.query(ItineraryDay).filter(ItineraryDay.map_id == m.id).delete()
    rows = [ItineraryDay(map_id=m.id, **p.model_dump()) for p in payload]
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
        raise HTTPException(404, "Day not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
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
