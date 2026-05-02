"""Image GC on itinerary stop PATCH/DELETE."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services import storage


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_stop(client):
    """A map + one itinerary stop. Returns object with .id and .s (slug)."""
    map_resp = client.post(
        "/api/maps",
        json={"title": "t", "center_lat": 0, "center_lng": 0, "radius_m": 10000},
    )
    assert map_resp.status_code in (200, 201), (
        f"map create: {map_resp.status_code} {map_resp.text}"
    )
    slug = map_resp.json()["slug"]
    day_resp = client.post(
        f"/api/maps/{slug}/itinerary",
        json={"date": "2026-05-09", "label": "stop"},
    )
    assert day_resp.status_code in (200, 201), (
        f"stop create: {day_resp.status_code} {day_resp.text}"
    )
    day = day_resp.json()

    class _S:
        id = day["id"]
        s = slug

    return _S


def _seed(uploads_dir: Path, name: str):
    full = uploads_dir / f"{name}.jpg"
    thumb = uploads_dir / f"{name}_thumb.jpg"
    full.write_bytes(b"x")
    thumb.write_bytes(b"x")
    return f"/uploads/{name}.jpg", full, thumb


def test_patch_removes_orphan_images_in_notes(client, uploads_dir, sample_stop):
    url_a, full_a, thumb_a = _seed(uploads_dir, "ddd")
    client.patch(
        f"/api/maps/{sample_stop.s}/itinerary/{sample_stop.id}",
        json={"notes": f"![]({url_a})"},
    )
    client.patch(
        f"/api/maps/{sample_stop.s}/itinerary/{sample_stop.id}",
        json={"notes": "no images"},
    )
    assert not full_a.exists()
    assert not thumb_a.exists()


def test_delete_stop_removes_all_referenced_images(client, uploads_dir, sample_stop):
    url_a, full_a, thumb_a = _seed(uploads_dir, "eee")
    client.patch(
        f"/api/maps/{sample_stop.s}/itinerary/{sample_stop.id}",
        json={"notes": f"![]({url_a})"},
    )
    client.delete(f"/api/maps/{sample_stop.s}/itinerary/{sample_stop.id}")
    assert not full_a.exists()
    assert not thumb_a.exists()
