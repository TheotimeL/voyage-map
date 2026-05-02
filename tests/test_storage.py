"""services/storage.py — image upload + delete + URL extraction."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from services import storage


def _make_jpeg_bytes(size: tuple[int, int] = (2400, 1800)) -> bytes:
    """A minimum-viable JPEG of `size` pixels — used to test downscaling."""
    buf = io.BytesIO()
    Image.new("RGB", size, color="red").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    """Point storage at a tmp dir for the duration of one test."""
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path)
    return tmp_path


def test_save_image_writes_full_and_thumb(uploads_dir):
    data = _make_jpeg_bytes()
    out = storage.save_image(data, "image/jpeg")
    assert out["url"].startswith("/uploads/")
    assert out["thumb_url"].endswith("_thumb.jpg")
    full = uploads_dir / Path(out["url"]).name
    thumb = uploads_dir / Path(out["thumb_url"]).name
    assert full.exists()
    assert thumb.exists()
    with Image.open(full) as im:
        assert max(im.size) <= storage.FULL_MAX_DIM
    with Image.open(thumb) as im:
        assert max(im.size) <= storage.THUMB_MAX_DIM


def test_save_image_rejects_non_image_type(uploads_dir):
    with pytest.raises(ValueError):
        storage.save_image(b"not an image", "text/plain")


def test_save_image_rejects_corrupt_bytes(uploads_dir):
    with pytest.raises(ValueError):
        storage.save_image(b"\x00\x01\x02\x03", "image/jpeg")


def test_delete_image_removes_full_and_thumb(uploads_dir):
    data = _make_jpeg_bytes((600, 400))
    out = storage.save_image(data, "image/jpeg")
    full = uploads_dir / Path(out["url"]).name
    thumb = uploads_dir / Path(out["thumb_url"]).name
    assert full.exists() and thumb.exists()
    storage.delete_image(out["url"])
    assert not full.exists()
    assert not thumb.exists()


def test_delete_image_ignores_missing(uploads_dir):
    # Should not raise when files don't exist.
    storage.delete_image("/uploads/not-here.jpg")


def test_delete_image_refuses_path_traversal(uploads_dir, tmp_path):
    sentinel = tmp_path.parent / "sentinel.txt"
    sentinel.write_text("keep me")
    # Try to delete a file outside UPLOADS_DIR via a traversal payload.
    storage.delete_image("/uploads/../sentinel.txt")
    assert sentinel.exists(), "delete_image must refuse paths outside UPLOADS_DIR"


def test_delete_image_refuses_non_uploads_url(uploads_dir):
    # Should silently ignore (no raise) URLs that don't start with /uploads/.
    storage.delete_image("/static/foo.jpg")
    storage.delete_image("https://example.com/foo.jpg")


def test_extract_upload_urls_returns_only_local_images():
    md = """
Some text ![local](/uploads/abc.jpg) and ![remote](https://example.com/x.png)
and ![second local](/uploads/def123.jpg) plus a non-image link [click](/uploads/foo.jpg)
"""
    urls = storage.extract_upload_urls(md)
    assert urls == {"/uploads/abc.jpg", "/uploads/def123.jpg"}


def test_extract_upload_urls_handles_empty_or_none():
    assert storage.extract_upload_urls("") == set()
    assert storage.extract_upload_urls(None) == set()
