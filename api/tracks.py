"""GPX track CRUD endpoints, scoped to a map slug."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.db import get_db
from services.models import Map, Track
from services.schemas import TrackIn, TrackOut

router = APIRouter(prefix="/maps/{slug}/tracks", tags=["tracks"])


def _get_map_or_404(db: Session, slug: str) -> Map:
    m = db.query(Map).filter(Map.slug == slug).first()
    if m is None:
        raise HTTPException(404, "Map not found")
    return m


@router.post("", response_model=TrackOut, status_code=201)
def add_track(slug: str, payload: TrackIn, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    t = Track(
        map_id=m.id,
        name=payload.name,
        color=payload.color,
        gpx_data=payload.gpx_data,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{track_id}", status_code=204)
def delete_track(slug: str, track_id: int, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    t = db.query(Track).filter(Track.id == track_id, Track.map_id == m.id).first()
    if t is None:
        raise HTTPException(404, "Track not found")
    db.delete(t)
    db.commit()
