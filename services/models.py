"""SQLAlchemy models."""

from datetime import date as date_type, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    itinerary: Mapped[list["ItineraryDay"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="ItineraryDay.date",
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
    gpx_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # When set, this pin/trail is "attached" to a specific itinerary day.
    # Detaching is handled on day-delete via api/itinerary.py — we don't rely
    # on SQLite's FK ON DELETE SET NULL since foreign_keys pragma isn't on.
    itinerary_day_id: Mapped[int | None] = mapped_column(
        ForeignKey("itinerary_days.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # "must" (must-see) or "maybe"; null for legacy pins with no priority set.
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    map: Mapped[Map] = relationship(back_populates="points")


class ItineraryDay(Base):
    """A *stop* in the trip. Spans `date`..`end_date` (inclusive); a single-day
    stop has `end_date == date`. The table name and class name are kept for
    backward compatibility with prior data — conceptually each row is a stop,
    not a day."""

    __tablename__ = "itinerary_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    date: Mapped[date_type] = mapped_column(Date, index=True)
    end_date: Mapped[date_type] = mapped_column(Date, index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Photo journal: JSON array of base64 data-URLs ("data:image/jpeg;base64,…").
    # Storing inline keeps the snapshot self-contained for offline sync; the
    # tradeoff is row size — the schema cap (5 MB) is a soft fence per stop.
    photos: Mapped[str | None] = mapped_column(Text, nullable=True)

    map: Mapped[Map] = relationship(back_populates="itinerary")
