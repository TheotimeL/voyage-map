"""SQLAlchemy models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Map(Base):
    __tablename__ = "maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    points: Mapped[list["Point"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="Point.created_at",
    )
    tracks: Mapped[list["Track"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="Track.created_at",
    )


class Point(Base):
    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str] = mapped_column(String(20), default="note")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    map: Mapped[Map] = relationship(back_populates="points")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#0a4d5b")
    gpx_data: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    map: Mapped[Map] = relationship(back_populates="tracks")
