"""Point CRUD endpoints, scoped to a map slug."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.db import get_db
from services.lookup import get_map_or_404, get_point_or_404
from services.models import Point
from services.schemas import PointIn, PointOut, PointPatch

router = APIRouter(prefix="/maps/{slug}/points", tags=["points"])


@router.post("", response_model=PointOut, status_code=201)
def add_point(slug: str, payload: PointIn, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    p = Point(
        map_id=m.id,
        lat=payload.lat,
        lng=payload.lng,
        title=payload.title,
        comment=payload.comment,
        category=payload.category,
        gpx_data=payload.gpx_data,
        color=payload.color,
        itinerary_day_id=payload.itinerary_day_id,
        priority=payload.priority,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/{point_id}", response_model=PointOut)
def update_point(slug: str, point_id: int, payload: PointPatch, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    p = get_point_or_404(db, m.id, point_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{point_id}", status_code=204)
def delete_point(slug: str, point_id: int, db: Session = Depends(get_db)):
    m = get_map_or_404(db, slug)
    p = get_point_or_404(db, m.id, point_id)
    db.delete(p)
    db.commit()
