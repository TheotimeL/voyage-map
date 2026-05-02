# Markdown Notes & Image Uploads — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plain-text `comment` (pins) and `notes` (stops) with a Notion-style markdown editor that supports inline image uploads; the first inline image of a pin's note becomes its map marker thumbnail.

**Architecture:** Backend gets a thin storage abstraction (file-system today, swappable later) and a multipart upload endpoint serving images from `/uploads/`. Schema migrates to `Text` columns (20k char soft cap) and drops the legacy `photos` JSON column. Frontend adds a Tiptap-based WYSIWYG editor (`MarkdownEditor.vue`) and a read-only `markdown-it` viewer (`MarkdownView.vue`); pin markers in `MapView.vue` dispatch to a new `makePhotoPinIcon` when the note's first image is a local upload.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite, Pillow + pillow-heif for image processing, Vue 3 + Tiptap (`@tiptap/vue-3`, `tiptap-markdown`) + markdown-it, Leaflet for markers.

**Spec:** `docs/superpowers/specs/2026-05-02-markdown-notes-and-image-uploads-design.md`

---

## Phase 1 — Backend foundations

### Task 1: Add image-processing dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append Pillow and pillow-heif**

```
Pillow>=10.4
pillow-heif>=0.18
```

Append these two lines to `requirements.txt`.

- [ ] **Step 2: Install locally**

Run: `pip install -r requirements.txt`
Expected: both packages install without error.

- [ ] **Step 3: Smoke import**

Run: `python -c "from PIL import Image; import pillow_heif; pillow_heif.register_heif_opener(); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add Pillow + pillow-heif for image upload pipeline"
```

---

### Task 2: Storage abstraction (TDD)

**Files:**
- Create: `services/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'services.storage'`.

- [ ] **Step 3: Implement `services/storage.py`**

Create `services/storage.py`:

```python
"""File-storage abstraction for uploaded images.

Today: filesystem-backed (Render persistent disk at /data/uploads, ./uploads
locally). Tomorrow: swappable to S3/R2 by re-implementing this module — no
caller code changes needed.
"""

from __future__ import annotations

import io
import logging
import os
import re
import uuid
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

logger = logging.getLogger(__name__)

# HEIC support (iPhone photos) — registers a Pillow opener for image/heic.
register_heif_opener()

UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))

# Marker thumbnails: small enough to render 100+ on a map at ~10-15 KB each.
THUMB_MAX_DIM = 192

# Full-size variant: matches the existing browser-side downscale used in the
# old base64 photo flow, keeping single images comfortably under 500 KB.
FULL_MAX_DIM = 1600

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

# Markdown image syntax — captures only paths under /uploads/, ignores remote
# URLs (we can't generate thumbs for those, see the spec).
_UPLOAD_IMG_RE = re.compile(r"!\[[^\]]*\]\((/uploads/[^)\s]+)\)")


def save_image(data: bytes, content_type: str) -> dict[str, str]:
    """Decode, EXIF-rotate, downscale, write JPEG + thumbnail. Return URLs.

    Raises ValueError on bad input (unknown type, undecodable bytes).
    """
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # force decode now so we catch corrupt bytes here, not later
    except Exception as exc:  # Pillow raises a variety of types
        raise ValueError(f"Could not decode image: {exc}") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex
    full_path = UPLOADS_DIR / f"{name}.jpg"
    thumb_path = UPLOADS_DIR / f"{name}_thumb.jpg"

    full = img.copy()
    full.thumbnail((FULL_MAX_DIM, FULL_MAX_DIM), Image.LANCZOS)
    full.save(full_path, format="JPEG", quality=85, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((THUMB_MAX_DIM, THUMB_MAX_DIM), Image.LANCZOS)
    thumb.save(thumb_path, format="JPEG", quality=82, optimize=True)

    return {
        "url": f"/uploads/{name}.jpg",
        "thumb_url": f"/uploads/{name}_thumb.jpg",
    }


def delete_image(url: str | None) -> None:
    """Best-effort. Silently no-ops on:
      - non-/uploads/ URLs (external or unrecognized)
      - missing files
      - any path that resolves outside UPLOADS_DIR (traversal guard)
    """
    if not url or not url.startswith("/uploads/"):
        return
    rel = url[len("/uploads/"):]
    target = (UPLOADS_DIR / rel).resolve()
    try:
        uploads_resolved = UPLOADS_DIR.resolve()
    except FileNotFoundError:
        return
    # `is_relative_to` was added in Python 3.9; we're on 3.12.
    if not target.is_relative_to(uploads_resolved):
        logger.warning("delete_image refused path outside UPLOADS_DIR: %s", url)
        return
    # Delete the full-size file and its _thumb sibling (filename convention).
    base = target.with_suffix("")  # strip .jpg
    siblings = [target]
    if not base.name.endswith("_thumb"):
        siblings.append(base.parent / f"{base.name}_thumb{target.suffix}")
    for p in siblings:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("delete_image could not unlink %s: %s", p, exc)


def extract_upload_urls(markdown: str | None) -> set[str]:
    """Pull every /uploads/... URL referenced in markdown image syntax."""
    if not markdown:
        return set()
    return set(_UPLOAD_IMG_RE.findall(markdown))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/storage.py tests/test_storage.py
git commit -m "feat(storage): add filesystem-backed image upload abstraction"
```

---

### Task 3: Upload endpoint (TDD)

**Files:**
- Create: `api/uploads.py`
- Create: `tests/test_uploads.py`
- Modify: `server.py` (include router, mount static, ensure UPLOADS_DIR exists)

- [ ] **Step 1: Write failing tests**

Create `tests/test_uploads.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_uploads.py -v`
Expected: tests fail (404 because the endpoint doesn't exist yet).

- [ ] **Step 3: Implement `api/uploads.py`**

Create `api/uploads.py`:

```python
"""POST /api/uploads/image — multipart image upload."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from services import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Soft upper bound on raw upload size. Pillow downscales below FULL_MAX_DIM
# anyway, but we want to reject obvious abuse before reading the whole body.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/image")
async def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    if file.content_type not in storage.ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    try:
        return storage.save_image(data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Wire into `server.py`**

Modify `server.py`. After the existing `from api.points import …` block, add:

```python
from api.uploads import router as uploads_router
```

Inside the `lifespan` async context manager, after `_migrate_inline()`:

```python
storage.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
```

Add the import at the top:

```python
from fastapi.staticfiles import StaticFiles  # already imported above — verify
from services import storage
```

After the existing `app.include_router(...)` lines:

```python
app.include_router(uploads_router, prefix="/api")
app.mount("/uploads", StaticFiles(directory=str(storage.UPLOADS_DIR)), name="uploads")
```

(Mount AFTER `mkdir` runs in `lifespan` is incorrect — `app.mount` runs at import time, before `lifespan`. Solution: call `storage.UPLOADS_DIR.mkdir(...)` at module top-level too, just before the mount, so the directory exists when StaticFiles inspects it.)

Final order in `server.py`:

```python
# ...existing imports + app = FastAPI(...)

storage.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ...existing CORS middleware

app.include_router(maps_router, prefix="/api")
app.include_router(points_router, prefix="/api")
app.include_router(itinerary_router, prefix="/api")
app.include_router(overpass_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.mount("/uploads", StaticFiles(directory=str(storage.UPLOADS_DIR)), name="uploads")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_uploads.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Run the existing test suite to verify no regression**

Run: `pytest tests/ -v`
Expected: all tests PASS (storage + uploads + existing geocoding + routing).

- [ ] **Step 7: Commit**

```bash
git add api/uploads.py tests/test_uploads.py server.py
git commit -m "feat(api): add POST /api/uploads/image with multipart support"
```

---

### Task 4: Schema changes — Text columns + drop photos column

**Files:**
- Modify: `services/models.py`
- Modify: `services/schemas.py`
- Modify: `server.py` (`_migrate_inline`)
- Create: `tests/test_migration.py`

- [ ] **Step 1: Write failing migration test**

Create `tests/test_migration.py`:

```python
"""_migrate_inline — drop legacy itinerary_days.photos column."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text


def _table_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def test_drop_photos_column_runs_idempotently(tmp_path, monkeypatch):
    db_path = tmp_path / "voyage.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # Force-reload the engine + models against the new env var.
    import importlib
    from services import db as db_module
    importlib.reload(db_module)
    from services import models as models_module
    importlib.reload(models_module)

    db_module.Base.metadata.create_all(bind=db_module.engine)
    # Manually re-add the legacy column to simulate a pre-migration DB.
    with db_module.engine.begin() as conn:
        conn.execute(text("ALTER TABLE itinerary_days ADD COLUMN photos TEXT"))
        assert "photos" in _table_columns(conn, "itinerary_days")

    # Reload server module so _migrate_inline sees the correct engine.
    import server as server_module
    importlib.reload(server_module)
    server_module._migrate_inline()

    with db_module.engine.begin() as conn:
        assert "photos" not in _table_columns(conn, "itinerary_days")

    # Second run — idempotent, no error.
    server_module._migrate_inline()
    with db_module.engine.begin() as conn:
        assert "photos" not in _table_columns(conn, "itinerary_days")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration.py -v`
Expected: fails — `_migrate_inline` doesn't drop the column yet.

- [ ] **Step 3: Update `services/models.py`**

Replace the `Point.comment`, `ItineraryDay.notes`, and `ItineraryDay.photos` lines:

In `Point`:
```python
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
```

In `ItineraryDay`:
```python
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `photos` column removed — photos now live inline in `notes` markdown.
```

(Drop the entire `photos: Mapped[str | None] = ...` line and its comment block.)

- [ ] **Step 4: Update `services/schemas.py`**

In `PointIn` and `PointPatch`, change the `comment` field:
```python
    comment: str | None = Field(default=None, max_length=20_000)
```

In `ItineraryDayIn` and `ItineraryDayPatch`:
```python
    notes: str | None = Field(default=None, max_length=20_000)
```

Remove the `photos: str | None = Field(...)` line from `ItineraryDayIn` and `ItineraryDayPatch`.

In `ItineraryDayOut`, remove `photos: str | None = None`.

- [ ] **Step 5: Update `_migrate_inline` in `server.py`**

The block that adds the photos column (lines ~46-48 — `if "photos" not in iti_cols:`) gets **replaced** by a drop block:

```python
        iti_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(itinerary_days)"))}
        if "photos" in iti_cols:
            conn.execute(text("ALTER TABLE itinerary_days DROP COLUMN photos"))
            logger.info("Migrated: dropped itinerary_days.photos (M3 clean-slate)")
```

- [ ] **Step 6: Run migration test to verify it passes**

Run: `pytest tests/test_migration.py -v`
Expected: PASS.

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add services/models.py services/schemas.py server.py tests/test_migration.py
git commit -m "feat(schema): Text columns for notes/comment, drop legacy photos column"
```

---

### Task 5: Garbage-collect images on points PATCH/DELETE (TDD)

**Files:**
- Modify: `api/points.py`
- Create: `tests/test_points_gc.py` (or extend any existing point tests)

- [ ] **Step 1: Read current `api/points.py` to locate PATCH and DELETE handlers**

Run: `grep -n "def \|@router" api/points.py`

Expected: identifies the route handlers (e.g., `update_point`, `delete_point`). The next steps assume their names — adjust to match what you find.

- [ ] **Step 2: Write failing tests for GC behavior**

Create `tests/test_points_gc.py`:

```python
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
    full.write_bytes(b"\xff\xd8\xff fake jpeg")  # content not validated by GC
    thumb.write_bytes(b"\xff\xd8\xff fake thumb")
    return f"/uploads/{name}.jpg", full, thumb


def test_patch_removes_images_no_longer_in_comment(client, uploads_dir, sample_point):
    """When a PATCH replaces comment markdown that previously had an image,
    the orphaned image file should be deleted from disk."""
    url_a, full_a, thumb_a = _seed_uploaded_files(uploads_dir, "aaa")
    # Seed: point.comment references image A.
    client.patch(f"/api/points/{sample_point.id}",
                 json={"comment": f"see this ![pic]({url_a})"})
    # New PATCH drops the image entirely.
    client.patch(f"/api/points/{sample_point.id}", json={"comment": "no more pics"})
    assert not full_a.exists()
    assert not thumb_a.exists()


def test_patch_keeps_images_still_referenced(client, uploads_dir, sample_point):
    url_a, full_a, _ = _seed_uploaded_files(uploads_dir, "bbb")
    client.patch(f"/api/points/{sample_point.id}",
                 json={"comment": f"keep ![]({url_a}) please"})
    client.patch(f"/api/points/{sample_point.id}",
                 json={"comment": f"still keep ![]({url_a})"})
    assert full_a.exists()


def test_delete_point_removes_all_referenced_images(client, uploads_dir, sample_point):
    url_a, full_a, _ = _seed_uploaded_files(uploads_dir, "ccc")
    url_b, full_b, _ = _seed_uploaded_files(uploads_dir, "ddd")
    client.patch(f"/api/points/{sample_point.id}",
                 json={"comment": f"![]({url_a}) and ![]({url_b})"})
    client.delete(f"/api/points/{sample_point.id}")
    assert not full_a.exists()
    assert not full_b.exists()
```

You'll need a `sample_point` fixture. If `tests/conftest.py` doesn't exist, create one with a fixture that creates a Map and a Point via the API and yields the point. Pattern:

Create `tests/conftest.py` (only if it doesn't already exist; otherwise extend it):

```python
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
    """A map + one point inside it, returned as a small object with .id."""
    client = TestClient(app)
    map_resp = client.post(
        "/api/maps",
        json={"title": "test", "center_lat": 0, "center_lng": 0, "radius_m": 10000},
    )
    map_data = map_resp.json()
    pt_resp = client.post(
        f"/api/maps/{map_data['slug']}/points",
        json={"lat": 0, "lng": 0, "title": "test pin"},
    )
    pt = pt_resp.json()

    class _Pt:
        id = pt["id"]
        slug = map_data["slug"]
    return _Pt
```

(Adjust the URLs and JSON shapes to match the actual `api/maps.py` and `api/points.py` routes — verify with `grep -n "@router" api/points.py api/maps.py` first.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_points_gc.py -v`
Expected: tests fail because GC isn't wired in `api/points.py` yet.

- [ ] **Step 4: Implement GC in `api/points.py`**

In the PATCH handler (e.g., `update_point`), before committing the change:

```python
from services.storage import delete_image, extract_upload_urls

# ... inside update_point, after loading the existing row but before applying patch:
old_comment = point.comment

# ... apply patch fields as today (point.title = ..., point.comment = patch.comment, etc.)
db.commit()

# After commit, GC orphans (best-effort).
old_urls = extract_upload_urls(old_comment)
new_urls = extract_upload_urls(point.comment)
for url in old_urls - new_urls:
    delete_image(url)
```

In the DELETE handler:

```python
# Before db.delete(point):
for url in extract_upload_urls(point.comment):
    delete_image(url)
db.delete(point)
db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_points_gc.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6: Run full backend suite**

Run: `pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add api/points.py tests/test_points_gc.py tests/conftest.py
git commit -m "feat(points): GC orphan upload images on comment PATCH and DELETE"
```

---

### Task 6: Garbage-collect images on itinerary PATCH/DELETE + drop photos field

**Files:**
- Modify: `api/itinerary.py`
- Create: `tests/test_itinerary_gc.py`

- [ ] **Step 1: Read `api/itinerary.py` to locate PATCH/DELETE handlers and any `photos` field handling**

Run: `grep -n "def \|@router\|photos" api/itinerary.py`

Take note of:
- The PATCH and DELETE handler function names
- Any line that reads/writes `photos` (we'll remove these)

- [ ] **Step 2: Write failing tests**

Create `tests/test_itinerary_gc.py`:

```python
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
    map_resp = client.post(
        "/api/maps",
        json={"title": "t", "center_lat": 0, "center_lng": 0, "radius_m": 10000},
    )
    slug = map_resp.json()["slug"]
    day_resp = client.post(
        f"/api/maps/{slug}/itinerary",
        json={"date": "2026-05-09", "label": "stop"},
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
    url_a, full_a, _ = _seed(uploads_dir, "ddd")
    client.patch(f"/api/itinerary-days/{sample_stop.id}",
                 json={"notes": f"![]({url_a})"})
    client.patch(f"/api/itinerary-days/{sample_stop.id}",
                 json={"notes": "no images"})
    assert not full_a.exists()


def test_delete_stop_removes_all_referenced_images(client, uploads_dir, sample_stop):
    url_a, full_a, _ = _seed(uploads_dir, "eee")
    client.patch(f"/api/itinerary-days/{sample_stop.id}",
                 json={"notes": f"![]({url_a})"})
    client.delete(f"/api/itinerary-days/{sample_stop.id}")
    assert not full_a.exists()
```

(Adjust URLs to match real itinerary routes — verify with `grep -n "@router" api/itinerary.py`.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_itinerary_gc.py -v`
Expected: fails.

- [ ] **Step 4: Modify `api/itinerary.py`**

For each PATCH handler:

```python
from services.storage import delete_image, extract_upload_urls

# ... inside update_stop, before applying the patch:
old_notes = day.notes

# ... apply patch fields. CRITICALLY: any line that reads/writes `photos`
# from the request body or the model — remove it. The `photos` column no
# longer exists. The Pydantic schema no longer has the field, so attempts
# to set it would 422 anyway.

db.commit()

old_urls = extract_upload_urls(old_notes)
new_urls = extract_upload_urls(day.notes)
for url in old_urls - new_urls:
    delete_image(url)
```

For DELETE:

```python
for url in extract_upload_urls(day.notes):
    delete_image(url)
db.delete(day)
db.commit()
```

Search-and-destroy on any leftover `photos` references inside `api/itinerary.py` (assignments like `day.photos = ...`, response shaping that includes `photos`, etc.). The schema layer already drops the field, so most code that simply spreads a Pydantic model into a SQLAlchemy row will be fine.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_itinerary_gc.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite green**

Run: `pytest tests/ -v`
Expected: all PASS (existing tests + storage + uploads + migration + GC).

- [ ] **Step 7: Commit**

```bash
git add api/itinerary.py tests/test_itinerary_gc.py
git commit -m "feat(itinerary): GC orphan upload images on PATCH/DELETE; drop photos handling"
```

---

### Task 7: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append `uploads/` to `.gitignore`**

Append:

```
# Local uploads dir for image storage (mirrors /data/uploads on Render)
uploads/
```

- [ ] **Step 2: Verify it's ignored**

Run: `mkdir -p uploads && touch uploads/test.jpg && git status`
Expected: `uploads/test.jpg` does NOT appear in `git status` output. Then `rm -rf uploads`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore local uploads/ directory"
```

---

## Phase 2 — Frontend foundations

### Task 8: Add Tiptap + markdown-it dependencies

**Files:**
- Modify: `frontend/package.json` (via npm install — don't hand-edit)

- [ ] **Step 1: Install editor + viewer libs**

Run from `frontend/`:

```bash
cd frontend
npm install @tiptap/vue-3 @tiptap/starter-kit @tiptap/extension-image @tiptap/extension-link @tiptap/extension-placeholder @tiptap/extension-dropcursor tiptap-markdown markdown-it
```

Expected: clean install. `npm audit` warnings are OK; `npm audit fix --force` is NOT to be run.

- [ ] **Step 2: Verify build still works**

Run: `npm run build`
Expected: Vite build succeeds. Bundle gets bigger; that's fine.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/package.json frontend/package-lock.json
git commit -m "deps(frontend): add Tiptap + markdown-it for note editor"
```

---

### Task 9: `extractMarkerThumb` util (TDD)

**Files:**
- Modify: `frontend/src/util.js`
- Create: `frontend/test/util.test.mjs`

- [ ] **Step 1: Write failing test**

Create `frontend/test/util.test.mjs`:

```javascript
// frontend/test/util.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { extractMarkerThumb, markdownExcerpt } from '../src/util.js'

test('extractMarkerThumb returns null for empty / no image', () => {
  assert.equal(extractMarkerThumb(null), null)
  assert.equal(extractMarkerThumb(''), null)
  assert.equal(extractMarkerThumb('just some text'), null)
})

test('extractMarkerThumb returns null for external image (not /uploads/)', () => {
  assert.equal(extractMarkerThumb('![pic](https://example.com/cat.jpg)'), null)
})

test('extractMarkerThumb extracts first /uploads/ image and derives thumb URL', () => {
  const r = extractMarkerThumb('text ![](/uploads/abc123.jpg) and more')
  assert.deepEqual(r, {
    full_url: '/uploads/abc123.jpg',
    thumb_url: '/uploads/abc123_thumb.jpg',
  })
})

test('extractMarkerThumb picks the FIRST upload, even if a remote precedes it', () => {
  const md = '![remote](https://e.com/x.png)\n\n![local](/uploads/xyz.jpg)'
  const r = extractMarkerThumb(md)
  assert.equal(r.full_url, '/uploads/xyz.jpg')
})

test('extractMarkerThumb handles .png extension correctly in thumb derivation', () => {
  const r = extractMarkerThumb('![](/uploads/foo.png)')
  assert.equal(r.thumb_url, '/uploads/foo_thumb.png')
})

test('markdownExcerpt strips formatting and truncates to maxLen', () => {
  const md = '# Title\n\n**bold** and _italic_ with ![pic](/uploads/x.jpg) in it.'
  assert.equal(markdownExcerpt(md, 80), 'Title bold and italic with  in it.')
})

test('markdownExcerpt returns empty string for null/empty input', () => {
  assert.equal(markdownExcerpt(null), '')
  assert.equal(markdownExcerpt(''), '')
})

test('markdownExcerpt truncates and appends ellipsis when over maxLen', () => {
  const long = 'word '.repeat(100)
  const out = markdownExcerpt(long, 30)
  assert(out.length <= 33)  // 30 + '…' (with possible trailing trim)
  assert(out.endsWith('…'))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `frontend/`:

```bash
node --test test/util.test.mjs
```

Expected: failures because `extractMarkerThumb` and `markdownExcerpt` don't exist yet.

- [ ] **Step 3: Add helpers to `frontend/src/util.js`**

Append to `frontend/src/util.js`:

```javascript
// First /uploads/ image inline in a markdown note. The thumb URL follows the
// `<name>_thumb.<ext>` convention created by services/storage.py — derived
// instead of stored so we have one source of truth (the markdown).
export function extractMarkerThumb(markdown) {
  if (!markdown) return null
  const m = markdown.match(/!\[[^\]]*\]\((\/uploads\/[^)\s]+)\)/)
  if (!m) return null
  const fullUrl = m[1]
  const thumbUrl = fullUrl.replace(/(\.[^.]+)$/, '_thumb$1')
  return { full_url: fullUrl, thumb_url: thumbUrl }
}

// One-line plain-text preview for compact UI (the today-banner). Strips
// markdown formatting *crudely* — we don't need a real parser for a banner
// snippet, and pulling markdown-it into util.js would bloat early bundles.
export function markdownExcerpt(markdown, maxLen = 120) {
  if (!markdown) return ''
  const stripped = markdown
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')        // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')     // links → keep label
    .replace(/[*_`#>~]+/g, '')                    // emphasis / headings / code
    .replace(/\n+/g, ' ')                         // collapse newlines
    .replace(/\s+/g, ' ')                         // collapse whitespace
    .trim()
  return stripped.length > maxLen ? stripped.slice(0, maxLen).trimEnd() + '…' : stripped
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test test/util.test.mjs`
Expected: all 8 tests PASS.

- [ ] **Step 5: Run the existing util-using tests for regression**

Run: `node --test test/`
Expected: all existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/util.js frontend/test/util.test.mjs
git commit -m "feat(util): add extractMarkerThumb and markdownExcerpt helpers"
```

---

### Task 10: `MarkdownView.vue` — read-only renderer

**Files:**
- Create: `frontend/src/components/molecules/MarkdownView.vue`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/molecules/MarkdownView.vue`:

```vue
<template>
  <div class="md-view" v-html="rendered" />
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

// Single shared instance — markdown-it is heavy to construct.
const md = new MarkdownIt({
  html: false,        // refuse raw HTML in user notes (XSS guard)
  linkify: true,
  breaks: true,       // newline → <br>, journal-friendly
})

// Add lazy-loading + max-width to images via custom renderer rule.
const defaultImageRenderer = md.renderer.rules.image || ((tokens, idx, opts, env, self) => self.renderToken(tokens, idx, opts))
md.renderer.rules.image = (tokens, idx, opts, env, self) => {
  const token = tokens[idx]
  token.attrSet('loading', 'lazy')
  const existingClass = token.attrGet('class') || ''
  token.attrSet('class', `${existingClass} md-img`.trim())
  return defaultImageRenderer(tokens, idx, opts, env, self)
}

const props = defineProps({
  source: { type: String, default: '' },
})

const rendered = computed(() => (props.source ? md.render(props.source) : ''))
</script>

<style scoped>
.md-view :deep(p) { margin: 0.4em 0; }
.md-view :deep(h1), .md-view :deep(h2), .md-view :deep(h3) { margin: 0.6em 0 0.3em; }
.md-view :deep(ul), .md-view :deep(ol) { margin: 0.4em 0; padding-left: 1.4em; }
.md-view :deep(blockquote) {
  margin: 0.4em 0;
  padding: 0.2em 0.8em;
  border-left: 3px solid var(--ink, #333);
  opacity: 0.85;
}
.md-view :deep(.md-img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 0.4em 0;
}
.md-view :deep(a) { color: var(--accent, #1864ab); }
.md-view :deep(code) {
  background: rgba(0,0,0,0.06);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.9em;
}
</style>
```

- [ ] **Step 2: Smoke-mount the component in the dev server**

Run: `cd frontend && npm run dev`
Then in another shell, briefly add a temporary `<MarkdownView source="# Hi\n\n**bold** and ![](/uploads/foo.jpg)" />` somewhere reachable (e.g., `App.vue`), open the browser, confirm it renders, then revert the temp insertion.

(Skip if you trust the code — the integration tasks below will exercise it for real.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/molecules/MarkdownView.vue
git commit -m "feat(ui): add MarkdownView component (markdown-it, read-only)"
```

---

### Task 11: `MarkdownEditor.vue` — Tiptap WYSIWYG editor with image upload

**Files:**
- Create: `frontend/src/components/molecules/MarkdownEditor.vue`
- Modify: `frontend/src/api.js` (add `uploadImage` helper if `api.js` is the central client; otherwise use `fetch` directly)

- [ ] **Step 1: Add `uploadImage` to the API client**

Read `frontend/src/api.js` to find the existing pattern (`grep -n "export\|fetch" frontend/src/api.js | head -20`). Append a helper that mirrors the existing style. Sketch:

```javascript
export async function uploadImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${API_BASE}/api/uploads/image`, { method: 'POST', body: fd })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Upload failed (${res.status}): ${detail}`)
  }
  return res.json() // { url, thumb_url }
}
```

(Rename `API_BASE` to whatever constant `api.js` already exports.)

- [ ] **Step 2: Create the editor component**

Create `frontend/src/components/molecules/MarkdownEditor.vue`:

```vue
<template>
  <div class="md-editor" :class="{ 'is-empty': !modelValue }">
    <div v-if="editor" class="md-toolbar">
      <button type="button" :class="{ active: editor.isActive('bold') }" @click="editor.chain().focus().toggleBold().run()" title="Bold"><b>B</b></button>
      <button type="button" :class="{ active: editor.isActive('italic') }" @click="editor.chain().focus().toggleItalic().run()" title="Italic"><i>I</i></button>
      <button type="button" :class="{ active: editor.isActive('heading', { level: 2 }) }" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()" title="Heading">H</button>
      <button type="button" :class="{ active: editor.isActive('bulletList') }" @click="editor.chain().focus().toggleBulletList().run()" title="Bullet list">•</button>
      <button type="button" @click="editor.chain().focus().setHorizontalRule().run()" title="Horizontal rule">—</button>
      <button type="button" @click="onLink" title="Link">🔗</button>
      <label class="img-btn" title="Insert image">
        📷
        <input type="file" accept="image/*" class="hidden" @change="onPickImage" />
      </label>
    </div>
    <editor-content :editor="editor" class="md-surface" />
    <p v-if="uploadError" class="md-error">{{ uploadError }}</p>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import Dropcursor from '@tiptap/extension-dropcursor'
import { Markdown } from 'tiptap-markdown'
import { uploadImage } from '@/api.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Notes…' },
})
const emit = defineEmits(['update:modelValue'])

const uploadError = ref('')

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit.configure({
      // Drop default Image — we use the proper extension below for drag.
    }),
    Image.configure({
      // Native node-drag inside ProseMirror — gives us reorder for free.
      inline: false,
      allowBase64: false,
    }),
    Link.configure({ openOnClick: false, autolink: true }),
    Placeholder.configure({ placeholder: () => props.placeholder }),
    Dropcursor.configure({ class: 'md-dropcursor' }),
    Markdown.configure({
      transformPastedText: true,
      transformCopiedText: true,
    }),
  ],
  editorProps: {
    handlePaste: (view, event) => handleImagePaste(event),
    handleDrop: (view, event) => handleImageDrop(event),
  },
  onUpdate: ({ editor }) => {
    // Tiptap-markdown exposes `.storage.markdown.getMarkdown()` for serialize.
    const md = editor.storage.markdown.getMarkdown()
    emit('update:modelValue', md)
  },
})

// Keep external model changes in sync without echoing our own emits.
watch(() => props.modelValue, (next) => {
  if (!editor.value) return
  const current = editor.value.storage.markdown.getMarkdown()
  if (next !== current) editor.value.commands.setContent(next || '', false)
})

onBeforeUnmount(() => editor.value?.destroy())

async function onPickImage(e) {
  const file = (e.target.files || [])[0]
  e.target.value = ''
  if (file) await uploadAndInsert(file)
}

async function uploadAndInsert(file) {
  if (!file || !file.type.startsWith('image/')) return
  uploadError.value = ''
  try {
    const { url } = await uploadImage(file)
    editor.value?.chain().focus().setImage({ src: url, alt: file.name || '' }).run()
  } catch (err) {
    uploadError.value = err.message || 'Upload failed.'
  }
}

function handleImagePaste(event) {
  const items = event.clipboardData?.items || []
  for (const item of items) {
    if (item.type?.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) { uploadAndInsert(file); return true }
    }
  }
  return false
}

function handleImageDrop(event) {
  const file = event.dataTransfer?.files?.[0]
  if (file && file.type?.startsWith('image/')) {
    event.preventDefault()
    uploadAndInsert(file)
    return true
  }
  return false
}

function onLink() {
  const prev = editor.value?.getAttributes('link').href || ''
  const url = window.prompt('Link URL', prev)
  if (url === null) return
  if (url === '') {
    editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
    return
  }
  editor.value?.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
}
</script>

<style scoped>
.md-editor {
  border: 1px solid var(--rule, #d8d2c3);
  border-radius: 8px;
  background: var(--paper, #fdfaf2);
  font-family: inherit;
}
.md-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.4rem;
  border-bottom: 1px solid var(--rule, #d8d2c3);
  position: sticky;
  top: 0;
  background: inherit;
  z-index: 1;
}
.md-toolbar button, .md-toolbar .img-btn {
  border: 1px solid transparent;
  background: transparent;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.95em;
}
.md-toolbar button.active { background: rgba(0,0,0,0.08); }
.md-toolbar button:hover, .md-toolbar .img-btn:hover { background: rgba(0,0,0,0.04); }
.img-btn { display: inline-flex; align-items: center; }
.hidden { display: none; }
.md-surface { padding: 0.6rem 0.8rem; min-height: 6em; }
.md-surface :deep(.ProseMirror) { outline: none; min-height: 5em; }
.md-surface :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  color: var(--muted, #968b76);
  pointer-events: none;
  height: 0;
}
.md-surface :deep(img) { max-width: 100%; border-radius: 6px; cursor: grab; }
.md-error { color: #b53127; font-size: 0.85em; padding: 0 0.8rem 0.4rem; }
</style>
```

- [ ] **Step 3: Smoke-test in the dev server**

Run from `frontend/`: `npm run dev`. Temporarily mount `<MarkdownEditor v-model="x" />` somewhere accessible, type some text, drag-drop an image, verify the upload hits the backend (check browser network panel) and the URL gets inserted as a markdown image. Revert the temp insertion when satisfied.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/molecules/MarkdownEditor.vue frontend/src/api.js
git commit -m "feat(ui): add MarkdownEditor (Tiptap + image upload)"
```

---

## Phase 3 — Frontend integration

### Task 12: Wire `MarkdownEditor` + `MarkdownView` into pin form/detail

**Files:**
- Modify: `frontend/src/components/organisms/PointFormModal.vue`
- Modify: `frontend/src/components/organisms/PointDetailCard.vue`

- [ ] **Step 1: Update `PointFormModal.vue`**

Open `frontend/src/components/organisms/PointFormModal.vue`. At the top of `<script setup>`, add:

```javascript
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'
```

Replace the textarea around line 48 (the one bound to `form.comment`):

```vue
<MarkdownEditor v-model="form.comment" placeholder="Notes, links, photos…" />
```

The existing flag-prefix logic (functions `readFlags`, `writeFlags`, `hasFlag` and the bound chips) reads/writes `form.comment` as a plain string — that still works because `MarkdownEditor` emits markdown text, and a `[FLAG_A] …` prefix is valid markdown (renders as plain text). Verify by reading those functions; no change expected.

- [ ] **Step 2: Update `PointDetailCard.vue`**

In `frontend/src/components/organisms/PointDetailCard.vue`, around lines 28-29, replace:

```vue
<p v-if="point.comment" class="comment">{{ point.comment }}</p>
<p v-else class="comment muted"><em>No notes yet.</em></p>
```

With:

```vue
<MarkdownView v-if="point.comment" :source="point.comment" class="comment" />
<p v-else class="comment muted"><em>No notes yet.</em></p>
```

Add to `<script setup>`:

```javascript
import MarkdownView from '@/components/molecules/MarkdownView.vue'
```

- [ ] **Step 3: Smoke test in the browser**

Run from `frontend/`: `npm run dev`. In the app:
- Create a new pin
- Open the form, type some markdown (`# title\n**bold**\n- list item`), insert an image via the 📷 button, save
- Verify the detail card shows formatted text + the image
- Edit again, drag the image to reorder, save, verify

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/organisms/PointFormModal.vue frontend/src/components/organisms/PointDetailCard.vue
git commit -m "feat(ui): markdown editor on pin form, markdown view on detail card"
```

---

### Task 13: Wire `MarkdownEditor` into stop modal + remove the photo grid

**Files:**
- Modify: `frontend/src/components/organisms/ItineraryDayModal.vue`

- [ ] **Step 1: Replace notes textarea with `MarkdownEditor`**

Open `frontend/src/components/organisms/ItineraryDayModal.vue`. Add to `<script setup>`:

```javascript
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'
```

Replace the existing notes textarea (around line 36-41) with:

```vue
<label class="lbl">Notes</label>
<MarkdownEditor v-model="form.notes" placeholder="Plans, journal, photos…" />
```

- [ ] **Step 2: Remove the entire photo grid block**

Delete:
- The `<label class="lbl">Photos</label>` and its `<div class="photos">…</div>` block (lines ~43-67 in the template)
- The `photoUrls`, `photoError`, `MAX_PHOTOS`, `MAX_DIM`, `hydratePhotos`, `onPhotoPick`, `removePhoto`, `downscaleToDataUrl` definitions in `<script setup>` (the comment-blocked photo section lines ~102-165)
- The `photos: photoUrls.value.length ? JSON.stringify(photoUrls.value) : null,` line in the save handler (around line 217)
- The `.photos { display: grid; gap: 0.4rem; }` rule in `<style>` (around line 280) and any sibling photo-* rules

Verify nothing else in the file references the deleted symbols:

Run: `grep -n "photoUrls\|MAX_PHOTOS\|hydratePhotos\|onPhotoPick\|removePhoto\|downscaleToDataUrl\|\.photos " frontend/src/components/organisms/ItineraryDayModal.vue`
Expected: no matches.

- [ ] **Step 3: Smoke test in the browser**

Run `npm run dev`. Open a stop's edit modal:
- Notes editor renders, photo grid is gone
- Type markdown, insert image, save, reopen — content round-trips

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/organisms/ItineraryDayModal.vue
git commit -m "feat(ui): markdown editor for stop notes; remove legacy photo grid"
```

---

### Task 14: Use `markdownExcerpt` in MapView's today-banner

**Files:**
- Modify: `frontend/src/views/MapView.vue` (line ~90, the `<span class="banner-notes">` block)

- [ ] **Step 1: Add the import**

In the existing imports of `frontend/src/views/MapView.vue` from `@/util.js`, add `markdownExcerpt` to the destructured import. Run `grep -n "from '@/util.js'" frontend/src/views/MapView.vue` to find the line; add the helper there.

- [ ] **Step 2: Pipe banner notes through `markdownExcerpt`**

Find line ~90:

```vue
<span v-if="todayBanner.notes" class="banner-notes">{{ todayBanner.notes }}</span>
```

Replace with:

```vue
<span v-if="todayBanner.notes" class="banner-notes">{{ markdownExcerpt(todayBanner.notes, 140) }}</span>
```

Find the v-if for the entire banner row (around line 69) — the `todayBanner.notes` truthy check works fine since markdown notes are still truthy strings; no change there.

- [ ] **Step 3: Smoke test**

Run dev server. Set a stop's notes to multi-line markdown with an image. Open the map — the banner should show a clean one-liner excerpt of the text only (image syntax stripped), and clicking opens the full editor.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "feat(banner): render stop notes as plain-text excerpt in map banner"
```

---

### Task 15: Photo-marker on the map (`makePhotoPinIcon` + dispatch in `addPointMarker`)

**Files:**
- Modify: `frontend/src/views/MapView.vue` (function `makePinIcon` ~line 1268 and `addPointMarker` ~line 1277, plus CSS at the bottom)

- [ ] **Step 1: Add `extractMarkerThumb` to the import**

In the `import { ... } from '@/util.js'` line (already touched in Task 14), add `extractMarkerThumb`.

- [ ] **Step 2: Add `makePhotoPinIcon` next to `makePinIcon`**

Insert after `makePinIcon` (after line ~1275):

```javascript
function makePhotoPinIcon(thumbUrl, ringColor, extra = '') {
  return L.divIcon({
    className: `pin-wrapper pin-photo ${extra}`,
    html: `<div class="pin pin-photo-wrap" style="--ring:${ringColor}">
             <img src="${thumbUrl}" loading="lazy"
                  onerror="this.replaceWith(Object.assign(document.createElement('span'),{textContent:'📍'}))"
                  alt="" />
           </div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  })
}
```

- [ ] **Step 3: Dispatch in `addPointMarker`**

Around line 1281-1284, replace the marker construction:

```javascript
function addPointMarker(p) {
  const extra = p.priority === 'maybe' ? 'is-maybe' : ''
  const photo = extractMarkerThumb(p.comment)
  const ring = p.color || 'var(--ink, #2a241a)'
  const icon = photo
    ? makePhotoPinIcon(photo.thumb_url, ring, extra)
    : makePinIcon(emojiByCategory[p.category] || '📍', extra)
  const m = L.marker([p.lat, p.lng], {
    icon,
    opacity: p.priority === 'maybe' ? 0.6 : 1,
  })
  // ...rest of the function unchanged (m._priority = ..., m.on('click', ...), etc.)
```

(Keep the rest of `addPointMarker` exactly as it is.)

- [ ] **Step 4: Add CSS at the bottom of MapView.vue's `<style>` block**

```css
.pin-photo-wrap {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3px solid var(--ring);
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  background: #fff;
  overflow: hidden;
  box-sizing: border-box;
}
.pin-photo-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pin-wrapper.pin-photo:hover .pin-photo-wrap {
  transform: scale(1.08);
  transition: transform 0.15s;
}
```

The existing `.pin-wrapper.is-maybe` rule (already in the stylesheet) keeps the dim treatment; photo pins inherit it via the same class chain.

- [ ] **Step 5: Smoke test**

Open the dev server. Create a pin without a photo (emoji renders as before). Edit the pin and add an image as the first thing in the note (drag/drop or 📷 button). Save and reload — the marker should now show a circular thumb of that photo. Move the image lower in the note (or replace with a different image first), save, reload — marker updates accordingly.

Edge cases:
- Pin with only an external image (`![](https://…)` first) → emoji marker (correct fallback)
- Pin with broken `/uploads/` URL (manually corrupt the markdown, e.g., `/uploads/nonexistent.jpg`) → after one render, the `onerror` handler swaps to 📍 (correct fallback)
- "Maybe" priority pin with photo → still renders dimmer (CSS inheritance works)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "feat(map): pin marker shows note's first photo as circular thumbnail"
```

---

## Phase 4 — Verification

### Task 16: Final smoke checklist + production build

**Files:** none

- [ ] **Step 1: Run the entire backend suite once more**

Run: `pytest tests/ -v`
Expected: every test passes (geocoding, routing, storage, uploads, migration, points GC, itinerary GC).

- [ ] **Step 2: Run the entire frontend test suite**

Run: `cd frontend && node --test test/`
Expected: every test passes.

- [ ] **Step 3: Production build**

Run: `cd frontend && npm run build`
Expected: clean Vite build. Bundle size is bigger (Tiptap adds ~150 KB gzipped); confirm Vite reports no errors.

- [ ] **Step 4: End-to-end manual smoke**

Bring up backend (`uvicorn server:app --reload --port 8000`) and frontend (`cd frontend && npm run dev`):

1. Create a map
2. Add a pin → write a note with markdown formatting → upload an image (drag, paste, AND 📷 button — try all three) → save → verify the pin marker shows the thumbnail
3. Edit the pin → drag the image to be the second item → verify save round-trips → verify the marker now shows the *new* first image (or emoji if no images remain)
4. Delete the image entirely from the note, save → verify marker reverts to emoji and the file is removed from `./uploads/` (`ls uploads/` should not list the abandoned file)
5. Add a stop with markdown notes + an image → verify the today-banner shows a plain-text excerpt → open the stop modal → verify the editor shows the WYSIWYG content
6. Delete the pin → confirm both files (full + thumb) gone from `./uploads/`
7. Reload the page → all data persists

- [ ] **Step 5: Final review**

Read the diff for any new file you created (`git log --since="2 hours ago" --stat`) and skim the changes — particularly any place you used inline `<style>` to make sure styles aren't fighting with existing rules. No commit needed if everything looks clean.

---

## Rollout note

There is no separate "PR1: backend / PR2: frontend" split. Tasks 1-7 are pure backend, build green, deploy-safe in isolation; Tasks 8-15 are frontend, depend on the backend endpoints existing. Pushing all of this in one branch (or two adjacent ones) is fine for a single-user app — no migration choreography needed thanks to M3 clean-slate.

The trip starts 2026-05-09; this whole plan should land before then.
