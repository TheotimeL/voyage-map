"""Pydantic request/response schemas."""

from datetime import datetime
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
