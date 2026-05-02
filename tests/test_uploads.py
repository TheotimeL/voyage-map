"""POST /api/uploads/image — the multipart upload endpoint."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server import app
from services import storage


def _png_bytes(size: tuple[int, int] = (400, 300)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color="blue").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def client():
    return TestClient(app)


def test_post_image_returns_urls_and_writes_files(client, uploads_dir):
    files = {"file": ("test.png", _png_bytes(), "image/png")}
    r = client.post("/api/uploads/image", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/uploads/")
    assert body["thumb_url"].endswith("_thumb.jpg")
    assert (uploads_dir / Path(body["url"]).name).exists()
    assert (uploads_dir / Path(body["thumb_url"]).name).exists()


def test_post_rejects_non_image_content_type(client, uploads_dir):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    r = client.post("/api/uploads/image", files=files)
    assert r.status_code == 400


def test_post_rejects_oversize_payload(client, uploads_dir):
    # Soft cap is 10 MB; pad to 11 MB of binary noise.
    big = b"\x00" * (11 * 1024 * 1024)
    files = {"file": ("big.jpg", big, "image/jpeg")}
    r = client.post("/api/uploads/image", files=files)
    assert r.status_code == 413


def test_post_rejects_undecodable_bytes(client, uploads_dir):
    files = {"file": ("fake.jpg", b"not a real jpeg", "image/jpeg")}
    r = client.post("/api/uploads/image", files=files)
    assert r.status_code == 400


def test_post_accepts_heic_upload(client, uploads_dir):
    """HEIC is the iPhone photo format — pillow-heif must decode it."""
    import io as _io

    from pillow_heif import from_pillow

    # Synthesize a small HEIC by wrapping a Pillow image with pillow-heif.
    src = Image.new("RGB", (200, 150), color="green")
    buf = _io.BytesIO()
    from_pillow(src).save(buf, format="HEIF")
    heic_bytes = buf.getvalue()

    files = {"file": ("photo.heic", heic_bytes, "image/heic")}
    r = client.post("/api/uploads/image", files=files)
    assert r.status_code == 200, f"unexpected: {r.status_code} {r.text}"
    body = r.json()
    assert body["url"].startswith("/uploads/")
    # Output is normalized to JPEG (we re-encode in save_image).
    assert body["url"].endswith(".jpg")
