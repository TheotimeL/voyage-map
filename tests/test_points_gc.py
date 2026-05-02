"""Image GC on point PATCH/DELETE — orphaned uploads get cleaned up."""

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


def _seed_uploaded_files(uploads_dir: Path, name: str) -> tuple[str, Path, Path]:
    """Create a fake (full, thumb) pair on disk and return (url, full_path, thumb_path)."""
    full = uploads_dir / f"{name}.jpg"
    thumb = uploads_dir / f"{name}_thumb.jpg"
    full.write_bytes(b"\xff\xd8\xff fake jpeg")
    thumb.write_bytes(b"\xff\xd8\xff fake thumb")
    return f"/uploads/{name}.jpg", full, thumb


def test_patch_removes_images_no_longer_in_comment(client, uploads_dir, sample_point):
    url_a, full_a, thumb_a = _seed_uploaded_files(uploads_dir, "aaa")
    # Points are scoped under /api/maps/{slug}/points/{point_id}
    client.patch(
        f"/api/maps/{sample_point.slug}/points/{sample_point.id}",
        json={"comment": f"see this ![pic]({url_a})"},
    )
    client.patch(
        f"/api/maps/{sample_point.slug}/points/{sample_point.id}",
        json={"comment": "no more pics"},
    )
    assert not full_a.exists()
    assert not thumb_a.exists()


def test_patch_keeps_images_still_referenced(client, uploads_dir, sample_point):
    url_a, full_a, _ = _seed_uploaded_files(uploads_dir, "bbb")
    client.patch(
        f"/api/maps/{sample_point.slug}/points/{sample_point.id}",
        json={"comment": f"keep ![]({url_a}) please"},
    )
    client.patch(
        f"/api/maps/{sample_point.slug}/points/{sample_point.id}",
        json={"comment": f"still keep ![]({url_a})"},
    )
    assert full_a.exists()


def test_delete_point_removes_all_referenced_images(client, uploads_dir, sample_point):
    url_a, full_a, _ = _seed_uploaded_files(uploads_dir, "ccc")
    url_b, full_b, _ = _seed_uploaded_files(uploads_dir, "ddd")
    client.patch(
        f"/api/maps/{sample_point.slug}/points/{sample_point.id}",
        json={"comment": f"![]({url_a}) and ![]({url_b})"},
    )
    client.delete(f"/api/maps/{sample_point.slug}/points/{sample_point.id}")
    assert not full_a.exists()
    assert not full_b.exists()
