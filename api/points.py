"""Point CRUD endpoints, scoped to a map slug."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.db import get_db
from services.models import Map, Point
from services.schemas import PointIn, PointOut, PointPatch

router = APIRouter(prefix="/maps/{slug}/points", tags=["points"])


def _get_map_or_404(db: Session, slug: str) -> Map:
    m = db.query(Map).filter(Map.slug == slug).first()
    if m is None:
        raise HTTPException(404, "Map not found")
    return m


def _get_point_or_404(db: Session, map_id: int, point_id: int) -> Point:
    p = db.query(Point).filter(Point.id == point_id, Point.map_id == map_id).first()
    if p is None:
        raise HTTPException(404, "Point not found")
    return p


@router.post("", response_model=PointOut, status_code=201)
def add_point(slug: str, payload: PointIn, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    p = Point(
        map_id=m.id,
        lat=payload.lat,
        lng=payload.lng,
        title=payload.title,
        comment=payload.comment,
        category=payload.category,
        gpx_data=payload.gpx_data,
        color=payload.color,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/{point_id}", response_model=PointOut)
def update_point(slug: str, point_id: int, payload: PointPatch, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    p = _get_point_or_404(db, m.id, point_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{point_id}", status_code=204)
def delete_point(slug: str, point_id: int, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    p = _get_point_or_404(db, m.id, point_id)
    db.delete(p)
    db.commit()
