"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server import app
from services.db import Base, engine


@pytest.fixture(autouse=True)
def _fresh_db():
    """Each test gets a clean schema. Same SQLite file, dropped + recreated."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_point():
    """A map + one point inside it. Yields an object with .id and .slug."""
    client = TestClient(app)
    map_resp = client.post(
        "/api/maps",
        json={"title": "test", "center_lat": 0, "center_lng": 0, "radius_m": 10000},
    )
    assert map_resp.status_code in (200, 201), (
        f"map create failed: {map_resp.status_code} {map_resp.text}"
    )
    map_data = map_resp.json()
    pt_resp = client.post(
        f"/api/maps/{map_data['slug']}/points",
        json={"lat": 0, "lng": 0, "title": "test pin"},
    )
    assert pt_resp.status_code in (200, 201), (
        f"point create failed: {pt_resp.status_code} {pt_resp.text}"
    )
    pt = pt_resp.json()

    class _Pt:
        id = pt["id"]
        slug = map_data["slug"]

    return _Pt
