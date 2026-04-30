"""Map CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.db import get_db
from services.models import Map
from services.schemas import MapIn, MapOut, MapPatch
from services.slug import make_slug

router = APIRouter(prefix="/maps", tags=["maps"])


def _get_or_404(db: Session, slug: str) -> Map:
    m = db.query(Map).filter(Map.slug == slug).first()
    if m is None:
        raise HTTPException(404, "Map not found")
    return m


@router.post("", response_model=MapOut, status_code=201)
def create_map(payload: MapIn, db: Session = Depends(get_db)):
    # Retry slug generation in the (vanishingly unlikely) collision case.
    for _ in range(8):
        slug = make_slug()
        if not db.query(Map).filter(Map.slug == slug).first():
            break
    else:
        raise HTTPException(500, "Could not allocate slug")

    m = Map(
        slug=slug,
        title=payload.title,
        center_lat=payload.center_lat,
        center_lng=payload.center_lng,
        radius_m=payload.radius_m,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.get("/{slug}", response_model=MapOut)
def get_map(slug: str, db: Session = Depends(get_db)):
    return _get_or_404(db, slug)


@router.patch("/{slug}", response_model=MapOut)
def update_map(slug: str, payload: MapPatch, db: Session = Depends(get_db)):
    m = _get_or_404(db, slug)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m
