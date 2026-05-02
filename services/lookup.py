"""Shared resource-or-404 lookups. Routers reuse these to keep handlers terse
and the 404 messages consistent across the API surface."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from services.models import ItineraryDay, Map, Point


def get_map_or_404(db: Session, slug: str) -> Map:
    m = db.query(Map).filter(Map.slug == slug).first()
    if m is None:
        raise HTTPException(404, "Map not found")
    return m


def get_point_or_404(db: Session, map_id: int, point_id: int) -> Point:
    p = db.query(Point).filter(Point.id == point_id, Point.map_id == map_id).first()
    if p is None:
        raise HTTPException(404, "Point not found")
    return p


def get_itinerary_day_or_404(db: Session, map_id: int, day_id: int) -> ItineraryDay:
    d = db.query(ItineraryDay).filter(
        ItineraryDay.id == day_id, ItineraryDay.map_id == map_id
    ).first()
    if d is None:
        raise HTTPException(404, "Stop not found")
    return d
