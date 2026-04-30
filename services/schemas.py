"""Pydantic request/response schemas."""

from datetime import date as date_type, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CATEGORIES = Literal[
    "food", "sight", "stay", "drink", "view", "transit", "shop", "note",
    "camp", "trail",
]


class PointIn(BaseModel):
    lat: float
    lng: float
    title: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)
    category: CATEGORIES = "note"


class PointPatch(BaseModel):
    lat: float | None = None
    lng: float | None = None
    title: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)
    category: CATEGORIES | None = None


class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lat: float
    lng: float
    title: str | None
    comment: str | None
    category: str
    created_at: datetime


class MapIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    center_lat: float
    center_lng: float
    radius_m: float = Field(gt=0, le=2_000_000)


class MapPatch(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    center_lat: float | None = None
    center_lng: float | None = None
    radius_m: float | None = Field(default=None, gt=0, le=2_000_000)


class TrackIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    color: str = Field(default="#0a4d5b", max_length=20)
    gpx_data: str = Field(min_length=20, max_length=10_000_000)  # up to ~10 MB


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    color: str
    gpx_data: str
    created_at: datetime


class ItineraryDayIn(BaseModel):
    date: date_type
    label: str | None = Field(default=None, max_length=200)
    lat: float | None = None
    lng: float | None = None
    notes: str | None = Field(default=None, max_length=500)


class ItineraryDayPatch(BaseModel):
    date: date_type | None = None
    label: str | None = Field(default=None, max_length=200)
    lat: float | None = None
    lng: float | None = None
    notes: str | None = Field(default=None, max_length=500)


class ItineraryDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date_type
    label: str | None
    lat: float | None
    lng: float | None
    notes: str | None


class MapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str | None
    center_lat: float
    center_lng: float
    radius_m: float
    created_at: datetime
    points: list[PointOut] = []
    tracks: list[TrackOut] = []
    itinerary: list[ItineraryDayOut] = []
