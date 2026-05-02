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
