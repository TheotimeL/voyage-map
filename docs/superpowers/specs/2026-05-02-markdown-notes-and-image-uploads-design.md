# Markdown Notes & Image Uploads — Design

**Date:** 2026-05-02
**Status:** Draft, pending implementation
**Goal:** Turn the plain-text `comment` (pins) and `notes` (stops) fields into a Notion-style WYSIWYG markdown experience with inline image uploads, and let the first image of a pin's note replace its emoji marker on the map.

## Motivation

The trip starts 2026-05-09. Today the app supports plain-text notes only: pins have a 2000-char `comment`, stops have a 500-char `notes` plus a separate base64-photo grid. That's enough for planning shorthand but not for a *journal de bord* where the user wants:

- Headings, lists, links, and other markdown formatting on both pins and stops.
- Photos uploaded directly from a phone, embedded inline in the note.
- The pin's marker on the map to show the photo as a thumbnail (instead of the category emoji) when one is present — a more visual, recognizable map.

A single source of truth — the markdown note — covers both planning ("food spots near Moab", "potential trail with 1500 m D+") and journaling ("did this run today, took this photo, met X").

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Photo-on-marker behavior | **A** — first inline image replaces the emoji as a circular thumbnail; emoji fallback when no photo |
| Image storage | **Local disk** on Render's persistent volume (`/data/uploads/`), behind a thin abstraction (`services/storage.py`) so a future swap to R2/S3 is ~30 min |
| Editor UX | **B** — Notion-style WYSIWYG (Tiptap + `tiptap-markdown`) |
| Notes ↔ photos relationship | **Y** — fully inline; no separate photo grid; first image in markdown = marker thumbnail |
| Migration of existing photo data | **M3** — clean slate; drop the `photos` column, no data conversion (no real prod data yet) |
| Notes length cap | 20 000 chars (soft cap, Pydantic-side) |
| In-editor image reordering | In scope — Tiptap drag handles |

## Architecture overview

```
[MarkdownEditor (Tiptap)]  --drop / paste / 📷 button-->  [POST /api/uploads/image]
       |                                                          |
       v                                                          v
  inserts ![](/uploads/<uuid>.jpg)                       [services/storage.py]
       |                                                          |
       v                                                          v
  PATCH /api/points/:id                                  /data/uploads/<uuid>.jpg
  or  /api/itinerary-days/:id                            /data/uploads/<uuid>_thumb.jpg
       |
       v
  comment / notes = raw markdown in DB
       |
       v
  [MarkdownView] (markdown-it)  -->  rendered HTML in PointDetailCard, MapBanner, etc.
  [MapView]                     -->  parses first /uploads/ image -> circular thumbnail marker
```

### Components — new

| File | Purpose |
|---|---|
| `services/storage.py` | File-storage abstraction. `save_image(bytes, content_type) -> {url, thumb_url}`, `delete_image(url)`. File-system backed today; swappable later. |
| `api/uploads.py` | `POST /api/uploads/image` multipart endpoint. Validates type & size, calls storage, returns URLs. |
| `frontend/src/components/molecules/MarkdownEditor.vue` | WYSIWYG editor wrapping Tiptap. Handles image drop/paste/insert + upload. Drag-to-reorder enabled. |
| `frontend/src/components/molecules/MarkdownView.vue` | Read-only markdown renderer using `markdown-it`. Lazy-loaded images, sanitized HTML. |
| `tests/test_uploads.py`, `tests/test_storage.py`, `tests/test_migration.py` | Backend tests (see Testing section). |

### Components — modified

| File | Change |
|---|---|
| `services/models.py` | `Point.comment` → `Text`. `ItineraryDay.notes` → `Text`. Drop `ItineraryDay.photos`. |
| `services/schemas.py` | `comment` and `notes` cap raised to 20 000. Remove `photos` from itinerary schemas. |
| `server.py` (`_migrate_inline`) | Add idempotent block: if `itinerary_days.photos` exists → `ALTER TABLE itinerary_days DROP COLUMN photos`. Add static mount `app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR))`. Include the new uploads router. |
| `api/points.py` | On PATCH: diff old vs new markdown image URLs, GC orphans. On DELETE: GC all images in current markdown. |
| `api/itinerary.py` | Same GC logic on PATCH/DELETE. Drop `photos` field from request/response handling. |
| `frontend/src/components/organisms/PointFormModal.vue` | Replace `<textarea v-model="form.comment">` with `<MarkdownEditor v-model="form.comment">`. |
| `frontend/src/components/organisms/ItineraryDayModal.vue` | Replace notes textarea with `<MarkdownEditor>`. **Remove the entire photo grid block** (lines ~43-67 plus the supporting JS in `<script>`); photos now live inline in the note. |
| `frontend/src/components/organisms/PointDetailCard.vue` | Replace `<p class="comment">{{ point.comment }}</p>` with `<MarkdownView :source="point.comment">` + the empty-state placeholder. |
| Map banner / stop detail (existing component rendering stop notes) | Replace plain text with `<MarkdownView>`. |
| `frontend/src/views/MapView.vue` (`addPointMarker`, line ~1277) | Before calling `makePinIcon`, check `extractMarkerThumb(point.comment)`. If a thumb exists, build a photo divIcon directly; otherwise call the existing `makePinIcon(emojiByCategory[...], extra)` path unchanged. |
| `frontend/src/util.js` | Add `extractMarkerThumb(markdown)` helper. |

## Data model

**Schema diff (SQLAlchemy):**

```python
# services/models.py
class Point(Base):
    # ...
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # was String(2000)

class ItineraryDay(Base):
    # ...
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)    # was String(500)
    # photos column removed entirely
```

**Pydantic diff (`services/schemas.py`):**

- `PointIn.comment`, `PointPatch.comment` → `Field(default=None, max_length=20_000)`
- `ItineraryDayIn.notes`, `ItineraryDayPatch.notes` → `Field(default=None, max_length=20_000)`
- Remove `photos` from `ItineraryDayIn`, `ItineraryDayPatch`, `ItineraryDayOut`.

**Migration (in `_migrate_inline`):**

```python
iti_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(itinerary_days)"))}
if "photos" in iti_cols:
    conn.execute(text("ALTER TABLE itinerary_days DROP COLUMN photos"))
    logger.info("Migrated: dropped itinerary_days.photos (M3 clean-slate)")
```

`ALTER TABLE … DROP COLUMN` is supported in SQLite ≥ 3.35 (March 2021). Render's image is recent enough.

No new column for the marker thumb — derived on the fly from the first `/uploads/` image in the markdown.

## Storage layer

**`services/storage.py`** (~50 lines):

```python
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))
THUMB_MAX_DIM = 192   # ~10–15 KB, marker-friendly
FULL_MAX_DIM = 1600   # mirrors current browser-side downscale

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

def save_image(data: bytes, content_type: str) -> dict[str, str]:
    """Validate, decode (Pillow + pillow-heif for HEIC), apply EXIF transpose,
    downscale to <= FULL_MAX_DIM, write JPEG to /uploads/<uuid>.jpg, generate
    and write _thumb.jpg at <= THUMB_MAX_DIM. Returns {"url", "thumb_url"}.
    Raises ValueError on bad input."""

def delete_image(url: str) -> None:
    """Best-effort. Refuses URLs not under /uploads/. Resolves the final path
    and confirms it stays inside UPLOADS_DIR (path-traversal guard).
    Deletes both file and its _thumb variant; ignores missing."""
```

Pillow handles JPEG/PNG/WebP natively. `pillow-heif` is added to `requirements.txt` so iPhone HEIC uploads decode.

`UPLOADS_DIR.mkdir(parents=True, exist_ok=True)` runs at boot inside `lifespan`. Local dev uses `UPLOADS_DIR=./uploads` via `.env`; the directory is gitignored.

## Upload endpoint

**`api/uploads.py`:**

```
POST /api/uploads/image
  multipart/form-data, field "file"
  Validations:
    - content_type ∈ ALLOWED_TYPES
    - raw size ≤ 10 MB (soft upper bound; Pillow downscales after)
  Response 200:
    {"url": "/uploads/<uuid>.jpg", "thumb_url": "/uploads/<uuid>_thumb.jpg"}
  Errors:
    400 — invalid content type, malformed image (Pillow can't open)
    413 — file too large
```

Static serving in `server.py`:

```python
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
```

## Garbage collection

Stale uploaded images (no longer referenced by any note) are deleted at the time of the note edit, not by a background sweep:

- **PATCH**: extract `/uploads/...` URLs from the prior `comment`/`notes` and the new value via a shared regex helper. Delete the diff (URLs in the prior value but not the new one).
- **DELETE**: extract all `/uploads/...` URLs from the current `comment`/`notes`, delete each.
- Helper `extract_upload_urls(md: str) -> set[str]` lives in `services/storage.py` (or a new `services/markdown.py` if it grows). Regex: `!\[[^\]]*\]\((/uploads/[^)\s]+)\)`.

A crash between `save_image` and the PATCH leaves orphan files on disk. Acceptable: on a 1 GB disk, gigabytes of waste are unrealistic. If it ever becomes a concern, a one-shot `scripts/gc_orphan_uploads.py` (compare disk vs URLs in DB) is straightforward to write — out of scope here.

## Frontend — `MarkdownEditor.vue`

**Library:** Tiptap (`@tiptap/vue-3`) with extensions:
- `StarterKit` (paragraph, heading, bold, italic, lists, blockquote, code…)
- `Image` configured with `draggable: true` for drag-to-reorder
- `Link` with sane defaults (no JS schemes)
- `Placeholder`
- `Dropcursor` (visual feedback when dragging images between blocks)
- `tiptap-markdown` for serialize/parse

Bundle cost: ~150 KB gzipped. Acceptable.

**Toolbar (mobile-friendly, sticky to top of editor):**

```
[B] [I] [H₂] [•≡] [—] [link] [📷]
```

**Image insert flow:**

1. User drops a file, pastes from clipboard, or taps 📷 (file input, `accept="image/*"`).
2. Editor inserts a placeholder image node (pulse/spinner) at the cursor.
3. POST to `/api/uploads/image`. Optionally pre-downscale on the browser side (canvas) when raw size > ~3 MB to save mobile bandwidth.
4. On success, swap placeholder src for the returned URL.
5. On failure, remove placeholder, surface a toast (`"Upload failed — retry?"`).

**Output:** raw markdown via `tiptap-markdown.serialize()`, emitted on debounce (~500 ms) via `update:modelValue`.

**Reordering:** Tiptap's built-in node drag works because images are draggable nodes. Desktop: hover an image → ⠿ handle on the side. Mobile: long-press to drag.

## Frontend — `MarkdownView.vue` (read-only)

`markdown-it` renderer (~40 KB) instead of mounting a full Tiptap instance per detail card.

```
Props: source (string)
Render rules:
  - linkify on
  - html_inline / html_block off  (no raw user HTML)
  - <img loading="lazy" style="max-width:100%; border-radius:8px">
```

Sanitization is "safe by default" because we disable raw HTML at the parser level. Image URLs aren't sanitized further — anyone can paste `![](https://evil.example/track.gif)` and it'll load. Single-user app, accepted risk.

## Map marker logic

**`util.js`:**

```js
export function extractMarkerThumb(markdown) {
  if (!markdown) return null
  const m = markdown.match(/!\[[^\]]*\]\((\/uploads\/[^)\s]+)\)/)
  if (!m) return null
  const fullUrl = m[1]
  const thumbUrl = fullUrl.replace(/(\.[^.]+)$/, '_thumb$1')
  return { thumb_url: thumbUrl, full_url: fullUrl }
}
```

**Marker construction (in `MapView.vue`, modify `addPointMarker` around line 1277):**

The existing `makePinIcon(glyph, extra)` builds the emoji marker. We add a sibling helper `makePhotoPinIcon(thumbUrl, ringColor, extra)` and dispatch in `addPointMarker`:

```js
function makePhotoPinIcon(thumbUrl, ringColor, extra = '') {
  return L.divIcon({
    className: `pin-wrapper pin-photo ${extra}`,
    // onerror → if the thumb 404s, fall back to a default emoji span
    html: `<div class="pin pin-photo-wrap" style="--ring:${ringColor}">
             <img src="${thumbUrl}" loading="lazy"
                  onerror="this.replaceWith(Object.assign(document.createElement('span'),{textContent:'📍'}))"
                  alt="" />
           </div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  })
}

function addPointMarker(p) {
  const extra = p.priority === 'maybe' ? 'is-maybe' : ''
  const photo = extractMarkerThumb(p.comment)
  const ring = p.color || 'var(--ink)' // re-use existing palette token; trails set p.color
  const icon = photo
    ? makePhotoPinIcon(photo.thumb_url, ring, extra)
    : makePinIcon(emojiByCategory[p.category] || '📍', extra)
  const m = L.marker([p.lat, p.lng], { icon, opacity: p.priority === 'maybe' ? 0.6 : 1 })
  // ...rest unchanged
}
```

The current code does not associate a color with each category — pins inherit the cream/ink palette and rely on the emoji for category readability. We keep that for the photo marker too: the default ring uses the existing ink color token, and pins/trails that already set `point.color` keep that color (consistent with how trail color works today).

**CSS:**

```css
.pin-photo-wrap {
  width: 40px; height: 40px;
  border-radius: 50%;
  border: 3px solid var(--ring);
  box-shadow: 0 2px 6px rgba(0,0,0,.3);
  background: #fff;
  overflow: hidden;
}
.pin-photo-wrap img { width: 100%; height: 100%; object-fit: cover; }
.pin-wrapper.pin-photo:hover .pin-photo-wrap { transform: scale(1.08); transition: transform .15s; }
/* `is-maybe` already lowers opacity at the marker level (existing behavior); */
/* no extra rule needed here — photo pins inherit the same dim treatment.    */
```

**Performance:** Each thumb is ~10–15 KB; 100 photo-pins = ~1.5 MB total, with `loading="lazy"` skipping ones outside the viewport. Existing markercluster plugin still aggregates at low zoom — no clustering changes needed.

**External-image fallback:** if the first image is an absolute URL (not `/uploads/`), `extractMarkerThumb` returns `null` and we render the emoji marker — we can't generate a thumb for arbitrary remote images.

**Broken-image fallback:** the `onerror` handler swaps the `<img>` for an inline emoji span, so dead links don't leave a blank circle.

## Error handling & edge cases

| Case | Behavior |
|---|---|
| Upload network failure | Editor placeholder removed, toast shown, user can retry |
| Pillow can't decode | 400 with `"Invalid image"` — editor surfaces toast |
| HEIC from iPhone | Decoded by `pillow-heif`, transcoded to JPEG on save |
| Photo orientation (EXIF) | `ImageOps.exif_transpose` applied before downscale → no sideways photos |
| Concurrent edits (two tabs) | Last PATCH wins (current behavior, mono-user app — accepted) |
| GC race (server crash mid-write) | Orphan file on disk, no DB ref. Acceptable on 1 GB. Optional offline sweep script if it ever matters. |
| Path traversal | `delete_image` resolves the path and refuses anything outside `UPLOADS_DIR` |
| Migration re-run | Bloc checks `PRAGMA table_info` first — idempotent |
| External-URL image first in note | Marker falls back to emoji (can't generate thumb for remote) |
| Note with only text | Marker stays on emoji, as today |

## Testing

Pragmatic — minimal-but-load-bearing, not a full TDD pass.

**Backend (pytest, in `tests/`):**

- `test_uploads.py`
  - happy path: POST a small JPEG → 200, both files exist on disk, both URLs valid
  - rejects `text/plain`
  - rejects > 10 MB body
  - decodes HEIC correctly (pillow-heif active)
- `test_storage.py`
  - `save_image` produces both full and thumb at expected dimensions
  - `delete_image` removes both files
  - `delete_image` refuses path-traversal payloads (`/uploads/../etc/passwd`)
- `test_migration.py`
  - DROP COLUMN block runs once: column gone after first call, second call no-ops without error
- `test_gc.py` (new) — stub or extend existing point/itinerary tests:
  - PATCH that removes an image URL deletes the file
  - DELETE pin removes all images in its note

**Frontend:**

- One vitest unit test for `extractMarkerThumb` (pure function, easy):
  - returns `null` for empty / no image / external image
  - returns correct `{thumb_url, full_url}` for `/uploads/abc.jpg`
  - handles `_thumb` suffix insertion before the extension correctly
- Manual browser smoke test for editor + marker rendering — no E2E framework added.

## Out of scope

- Per-day notes inside multi-day stops (one note per stop, as today)
- Captions on images beyond markdown's `alt` attribute
- Search across notes
- PDF / HTML export of the journal
- Offline-first upload queueing
- Thumbnail-on-cluster-marker (clusters keep current count-circle look)
- Migration of any existing base64 photo data (M3 = clean slate)

## Rollout

1. Backend changes (storage, schema, upload endpoint, GC) ship as one PR. Run migration on Render boot.
2. Frontend changes (editor + view + marker logic) ship as a follow-up PR. Until merged, the existing textareas keep working — `markdown-it` rendering and Tiptap editing degrade gracefully against plain-text content (markdown that's all plain text renders as plain text).
3. User's trip starts 2026-05-09. Both PRs land before then.

## Open questions

None at this stage — all decisions confirmed during brainstorming.
