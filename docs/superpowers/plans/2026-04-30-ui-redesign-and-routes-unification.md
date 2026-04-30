# UI Redesign + Routes-as-Points Unification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the GPX-track concept into the existing `Point` model, then replace the 6-section sidebar with a map-first adaptive InfoPanel (desktop dock + mobile bottom sheet) hosting two primary tabs (Places, Itinerary) and a "More" menu.

**Architecture:** Two phases. **Phase A (data unification, tasks 1–5):** add `gpx_data`/`color` to `Point`, migrate existing `tracks` rows into trail-points, delete the `Track` table, update the frontend to render trail-points uniformly. **Phase B (UI redesign, tasks 6–14):** scaffold `InfoPanel` + `TabBar` + `DesktopDock`, migrate sections one at a time behind a feature flag, build `MoreMenu`, then `MobileSheet` with drag-snap, then polish. Each task leaves the app working.

**Tech Stack:** FastAPI, SQLAlchemy 2 (SQLite), Pydantic 2, Vue 3 (Composition API), Vite, Leaflet 1.9, plain CSS (vintage-poster system in `frontend/src/styles/vintage.css`), `node --test`-style assertion scripts in `frontend/test/`. No pytest is configured in the backend; smoke verification is via a one-shot Python script and `curl`. The user prefers pragmatic over ceremonial — formal TDD applies to data-model work, browser verification suffices for UI work.

**Pre-flight (do once before Task 1):**

- [ ] Create a worktree for this plan (the executing skill handles this if you run via subagent-driven-development).
- [ ] Run the backend in one terminal: `uvicorn server:app --reload --port 8000`
- [ ] Run the frontend in another: `cd frontend && npm run dev`
- [ ] Visit `http://localhost:5173/` and create a fresh map with one regular pin and one GPX-uploaded track to use as a baseline for visual checks.
- [ ] Note: existing `voyage_map.db` SQLite file is at the repo root and is NOT gitignored — back it up before Task 3 (`cp voyage_map.db voyage_map.db.pre-migration`).

---

## Phase A — Routes-as-points unification

### Task 1: Add `gpx_data` and `color` to the Point model + schemas

**Files:**
- Modify: `services/models.py:43-55`
- Modify: `services/schemas.py:14-39`

- [ ] **Step 1: Extend the Point ORM model**

In `services/models.py`, replace the `Point` class with:

```python
class Point(Base):
    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str] = mapped_column(String(20), default="note")
    gpx_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    map: Mapped[Map] = relationship(back_populates="points")
```

The `Text` import is already present (used by `Track`). No new imports needed.

- [ ] **Step 2: Extend Pydantic schemas**

In `services/schemas.py`, replace the three Point schemas:

```python
class PointIn(BaseModel):
    lat: float
    lng: float
    title: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)
    category: CATEGORIES = "note"
    gpx_data: str | None = Field(default=None, max_length=10_000_000)
    color: str | None = Field(default=None, max_length=20)


class PointPatch(BaseModel):
    lat: float | None = None
    lng: float | None = None
    title: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=2000)
    category: CATEGORIES | None = None
    gpx_data: str | None = Field(default=None, max_length=10_000_000)
    color: str | None = Field(default=None, max_length=20)


class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lat: float
    lng: float
    title: str | None
    comment: str | None
    category: str
    gpx_data: str | None
    color: str | None
    created_at: datetime
```

- [ ] **Step 3: Apply the column additions to the existing SQLite file**

SQLAlchemy `create_all()` only creates missing tables — it does not add columns to existing ones. Add them manually:

```bash
sqlite3 voyage_map.db "ALTER TABLE points ADD COLUMN gpx_data TEXT; ALTER TABLE points ADD COLUMN color VARCHAR(20);"
sqlite3 voyage_map.db "PRAGMA table_info(points);"
```

Expected: the second command prints all `points` columns, with `gpx_data` (TEXT) and `color` (VARCHAR(20)) at the bottom.

- [ ] **Step 4: Restart the dev server and verify the schema is accepted**

Restart `uvicorn server:app --reload --port 8000` (Ctrl-C and re-run). Then:

```bash
curl -s http://localhost:8000/api/health
# {"status":"ok"}
curl -s http://localhost:8000/api/maps/<your-slug> | python -m json.tool | head -40
```

Expected: existing points return with `"gpx_data": null` and `"color": null` fields. No 500s.

- [ ] **Step 5: Commit**

```bash
git add services/models.py services/schemas.py
git commit -m "feat(model): add gpx_data + color to Point"
```

---

### Task 2: Update the points API to accept gpx_data/color

**Files:**
- Modify: `api/points.py:27-53`

- [ ] **Step 1: Replace `add_point` and `update_point`**

Replace lines 27–53 of `api/points.py` with:

```python
@router.post("", response_model=PointOut, status_code=201)
def add_point(slug: str, payload: PointIn, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    p = Point(
        map_id=m.id,
        lat=payload.lat,
        lng=payload.lng,
        title=payload.title,
        comment=payload.comment,
        category=payload.category,
        gpx_data=payload.gpx_data,
        color=payload.color,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/{point_id}", response_model=PointOut)
def update_point(slug: str, point_id: int, payload: PointPatch, db: Session = Depends(get_db)):
    m = _get_map_or_404(db, slug)
    p = _get_point_or_404(db, m.id, point_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p
```

- [ ] **Step 2: Smoke-test the new fields**

In a terminal:

```bash
SLUG=<your-slug>
curl -s -X POST "http://localhost:8000/api/maps/$SLUG/points" \
  -H 'Content-Type: application/json' \
  -d '{"lat":36.17,"lng":-115.14,"title":"smoke-trail","category":"trail","gpx_data":"<gpx><trk><trkseg><trkpt lat=\"36.17\" lon=\"-115.14\"><ele>610</ele></trkpt><trkpt lat=\"36.18\" lon=\"-115.13\"><ele>650</ele></trkpt></trkseg></trk></gpx>","color":"#0a4d5b"}' | python -m json.tool
```

Expected: response shows `"gpx_data": "<gpx>..."`, `"color": "#0a4d5b"`, `"category": "trail"`. Note the returned `id` for cleanup.

```bash
POINT_ID=<id-from-response>
curl -s -X DELETE "http://localhost:8000/api/maps/$SLUG/points/$POINT_ID" -w "%{http_code}\n"
# 204
```

- [ ] **Step 3: Commit**

```bash
git add api/points.py
git commit -m "feat(api): accept gpx_data + color on point create/update"
```

---

### Task 3: Migrate existing tracks rows into trail-points

**Files:**
- Create: `scripts/migrate_tracks_to_points.py`

- [ ] **Step 1: Back up the database**

```bash
cp voyage_map.db voyage_map.db.pre-migration
ls -la voyage_map.db*
```

Expected: both files present, similar size.

- [ ] **Step 2: Stop the dev server before running the migration**

`Ctrl-C` the `uvicorn` process. The migration writes directly to the SQLite file; running it while uvicorn holds a connection can corrupt state.

- [ ] **Step 3: Create the migration script**

Create `scripts/` directory if it does not exist (`mkdir -p scripts`). Then create `scripts/migrate_tracks_to_points.py`:

```python
"""One-shot: convert each row in `tracks` into a Point with category='trail'.

Idempotent: safe to re-run. Tracks that have already been migrated (i.e., a
trail-point with the same gpx_data already exists for the same map) are
skipped. After a successful run, the `tracks` table is left in place — it is
dropped in a later task once the frontend no longer reads from it.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from sqlalchemy import select

from services.db import SessionLocal
from services.models import Map, Point, Track


def first_coord(gpx_data: str) -> tuple[float, float] | None:
    """Return (lat, lng) of the first trkpt/rtept/wpt, or None if empty."""
    try:
        root = ET.fromstring(gpx_data)
    except ET.ParseError:
        return None
    # GPX namespace is variable; match local-name only.
    for tag in ("trkpt", "rtept", "wpt"):
        for el in root.iter():
            if el.tag.split("}", 1)[-1] == tag:
                lat = el.attrib.get("lat")
                lng = el.attrib.get("lon")
                if lat is not None and lng is not None:
                    try:
                        return float(lat), float(lng)
                    except ValueError:
                        pass
    return None


def migrate() -> int:
    db = SessionLocal()
    migrated = 0
    skipped = 0
    failed: list[int] = []
    try:
        tracks = db.scalars(select(Track)).all()
        for t in tracks:
            coord = first_coord(t.gpx_data)
            if coord is None:
                failed.append(t.id)
                continue
            lat, lng = coord
            existing = db.scalars(
                select(Point).where(
                    Point.map_id == t.map_id,
                    Point.gpx_data == t.gpx_data,
                )
            ).first()
            if existing is not None:
                skipped += 1
                continue
            p = Point(
                map_id=t.map_id,
                lat=lat,
                lng=lng,
                title=t.name,
                comment=None,
                category="trail",
                gpx_data=t.gpx_data,
                color=t.color,
            )
            db.add(p)
            migrated += 1
        db.commit()
    finally:
        db.close()

    print(f"migrated={migrated} skipped={skipped} failed={failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(migrate())
```

- [ ] **Step 4: Run the migration**

```bash
python -m scripts.migrate_tracks_to_points
```

Expected output: `migrated=N skipped=0 failed=[]` where N is the number of rows in your `tracks` table. If `failed` is non-empty, inspect those tracks manually before continuing.

Verify in SQLite:

```bash
sqlite3 voyage_map.db "SELECT count(*) FROM tracks;"
sqlite3 voyage_map.db "SELECT count(*) FROM points WHERE category='trail' AND gpx_data IS NOT NULL;"
```

Expected: the two counts match.

- [ ] **Step 5: Run a second time to confirm idempotency**

```bash
python -m scripts.migrate_tracks_to_points
```

Expected: `migrated=0 skipped=N failed=[]`.

- [ ] **Step 6: Restart the dev server and check the API**

```bash
uvicorn server:app --reload --port 8000 &
sleep 2
curl -s http://localhost:8000/api/maps/<your-slug> | python -m json.tool | head -60
```

Expected: each migrated track now appears as both a `tracks[]` entry AND a `points[]` entry with `category: "trail"`, `gpx_data: "..."`, `color: "..."`. Frontend will continue to render the track from the legacy path until Task 5.

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_tracks_to_points.py
git commit -m "feat(migrate): copy tracks into trail-points (idempotent)"
```

---

### Task 4: Frontend renders trail-points alongside tracks

**Files:**
- Modify: `frontend/src/api.js:22-27`
- Modify: `frontend/src/views/MapView.vue` — track-rendering and GPX-import logic

The frontend will, in this task, switch GPX import to create a `Point` (with `category='trail'` and `gpx_data`) instead of a `Track`. The polyline and elevation-profile rendering reads from `points` filtered by `gpx_data != null`. The existing `tracks` array on `mapData` is no longer read by the UI.

- [ ] **Step 1: Add a points-with-gpx helper to `api.js`**

In `frontend/src/api.js`, leave the existing `addPoint`/`patchPoint`/`deletePoint` functions intact — they already accept the new fields (the backend was extended in Task 2). Remove the now-defunct `addTrack`/`deleteTrack` lines:

```javascript
// REMOVE these two lines from the api object:
//   addTrack: (slug, payload) => request('POST', `/maps/${slug}/tracks`, payload),
//   deleteTrack: (slug, id) => request('DELETE', `/maps/${slug}/tracks/${id}`),
```

The full `api` object after this change has 12 methods (createMap, getMap, patchMap, addPoint, patchPoint, deletePoint, addItineraryDay, addItineraryBulk, patchItineraryDay, deleteItineraryDay, clearItinerary). Verify by saving the file and running `cd frontend && npm run build` — it must succeed (Task 5 deletes the backend endpoint, but it can still be called until then; we just choose not to from the UI).

- [ ] **Step 2: Add a `trailPoints` computed and switch rendering to it**

In `frontend/src/views/MapView.vue`, locate the track-rendering block (around line 265–276 and 347, 447, 572–595). Make the following changes:

Replace `const activeTrackId = ref(null)` (line 265) with:

```javascript
const activeTrailPointId = ref(null)
```

Replace the `activeSeries` computed (lines 266–272) with:

```javascript
const trailPoints = computed(() => {
  if (!mapData.value) return []
  return (mapData.value.points || []).filter((p) => p.gpx_data)
})
const activeSeries = computed(() => {
  if (!activeTrailPointId.value || !mapData.value) return []
  const t = trailPoints.value.find((x) => x.id === activeTrailPointId.value)
  if (!t) return []
  const { coords, elevations } = parseGPX(t.gpx_data)
  return buildElevationSeries(coords, elevations)
})
const activeTrackName = computed(() => {
  const t = trailPoints.value.find((x) => x.id === activeTrailPointId.value)
  return t?.title || ''
})
```

Note: trail-points use `title` (not `name` like Track did). The migration copied `track.name` into `point.title`.

- [ ] **Step 3: Switch the polyline rendering loop to read from points**

Find the line `;(mapData.value.tracks || []).forEach((t, i) => renderTrack(t, i))` (around line 447) and replace with:

```javascript
trailPoints.value.forEach((p, i) => renderTrack(p, i))
```

The `renderTrack` function itself (line 572) keeps its body — it reads `track.gpx_data`, `track.color`, `track.id`, all of which trail-points carry.

- [ ] **Step 4: Switch GPX drop-import to `addPoint`**

Replace the body of `importGpxFile` (around lines 617–635) with:

```javascript
async function importGpxFile(file) {
  gpxError.value = ''
  try {
    const text = await file.text()
    const { coords, name } = parseGPX(text) // validate before POST
    const idx = trailPoints.value.length
    const [lat, lng] = coords[0]
    const created = await api.addPoint(props.slug, {
      lat,
      lng,
      title: name || file.name.replace(/\.gpx$/i, ''),
      category: 'trail',
      gpx_data: text,
      color: trackColor(idx),
    })
    if (!mapData.value.points) mapData.value.points = []
    mapData.value.points.push(created)
    const line = renderTrack(created, idx)
    if (line && leaflet) leaflet.fitBounds(line.getBounds(), { padding: [40, 40] })
  } catch (e) {
    gpxError.value = e.message || 'Could not import GPX.'
  }
}
```

- [ ] **Step 5: Switch track deletion to point deletion**

Replace `deleteTrack` (around line 637) with:

```javascript
async function deleteTrailPoint(id) {
  try {
    await api.deletePoint(props.slug, id)
    mapData.value.points = (mapData.value.points || []).filter((p) => p.id !== id)
    removeTrackLine(id)
  } catch (e) {
    error.value = e.message
  }
}
```

- [ ] **Step 6: Update the legacy Routes section template to read trail-points**

In the `<template>` section, replace the existing Routes `<section class="sec">` block (lines 81–103 of MapView.vue) with one that iterates `trailPoints` and uses `activeTrailPointId` / `deleteTrailPoint`:

```vue
<section class="sec">
  <div class="sec-head">
    <span class="sec-num mono">№ 03</span>
    <h3 class="sec-title">Routes</h3>
    <span v-if="trailPoints.length" class="sec-count mono">{{ trailPoints.length }}</span>
    <label class="btn btn-tiny gpx-pick sec-action">
      + GPX
      <input type="file" accept=".gpx,application/gpx+xml" multiple class="hidden" @change="onGpxFilePick" />
    </label>
  </div>
  <p v-if="gpxError" class="error sm">{{ gpxError }}</p>
  <ul v-if="trailPoints.length" class="track-list">
    <li v-for="(t, i) in trailPoints" :key="t.id"
        class="track-row"
        :class="{ active: activeTrailPointId === t.id }"
        @click="activeTrailPointId = activeTrailPointId === t.id ? null : t.id">
      <span class="track-swatch" :style="{ background: t.color || trackColor(i) }"></span>
      <span class="track-name">{{ t.title || `Track ${i + 1}` }}</span>
      <button class="track-del" type="button" :title="`Delete ${t.title || 'track'}`" @click.stop="deleteTrailPoint(t.id)">×</button>
    </li>
  </ul>
  <p v-else class="hint mono">Drop a .gpx anywhere on the map.</p>
</section>
```

Also update the `ElevationProfile` close handler (line 192) from `@close="activeTrackId = null"` to `@close="activeTrailPointId = null"`.

- [ ] **Step 7: Browser verify**

Refresh the dev page (`http://localhost:5173/map/<slug>`). Verify:
- Existing migrated trails still appear in the Routes section with their swatches.
- Clicking a trail row opens the elevation profile (same as before).
- Drop a fresh `.gpx` file on the map — it imports as a trail-point. Refreshing the page, the new trail persists.
- Regular pins still drop normally and have nothing to do with trails.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api.js frontend/src/views/MapView.vue
git commit -m "refactor(frontend): render trails from points, not tracks"
```

---

### Task 5: Remove the Track table and tracks API

**Files:**
- Delete: `api/tracks.py`
- Modify: `services/models.py:31-35` (remove `tracks` relationship), remove `Track` class
- Modify: `services/schemas.py:56-69, 110` (remove `TrackIn`, `TrackOut`, drop `tracks` from `MapOut`)
- Modify: `server.py:9, 23, 56` (drop the tracks router import + include)

- [ ] **Step 1: Drop the route registration and import**

In `server.py`:
- Remove the line `from api.tracks import router as tracks_router`
- Remove the line `app.include_router(tracks_router, prefix="/api")`

- [ ] **Step 2: Delete `api/tracks.py`**

```bash
git rm api/tracks.py
```

- [ ] **Step 3: Remove the Track model + relationship**

In `services/models.py`:
- Delete the entire `Track` class (lines 58–68 in the original file).
- Inside `Map`, remove the `tracks` relationship block (lines 31–35).

- [ ] **Step 4: Remove the Track schemas + nested `tracks` field**

In `services/schemas.py`:
- Delete `TrackIn` and `TrackOut` classes.
- In `MapOut`, remove the `tracks: list[TrackOut] = []` line.

- [ ] **Step 5: Drop the tracks table from SQLite**

```bash
sqlite3 voyage_map.db "DROP TABLE tracks;"
sqlite3 voyage_map.db ".tables"
```

Expected: `.tables` output includes `points`, `maps`, `itinerary_days` but NOT `tracks`.

- [ ] **Step 6: Restart the server and verify**

```bash
# Restart uvicorn (Ctrl-C, then re-run)
uvicorn server:app --reload --port 8000 &
sleep 2
curl -s http://localhost:8000/api/maps/<your-slug> | python -m json.tool | head -30
```

Expected: response no longer contains a `"tracks"` key. `points[]` still includes trail-points.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8000/api/maps/<your-slug>/tracks" -H 'Content-Type: application/json' -d '{"gpx_data":"<gpx></gpx>"}'
```

Expected: `404` or `405`. (The route is gone.)

- [ ] **Step 7: Browser verify trails still load**

Refresh `http://localhost:5173/map/<slug>`. Trails still render. GPX drop-import still creates a trail-point. Delete a trail; refresh; it stays gone.

- [ ] **Step 8: Commit**

```bash
git add server.py services/models.py services/schemas.py api/tracks.py
git commit -m "refactor(api): drop the Track table, points carries trails"
```

---

## Phase B — Map-first UI redesign

> **Approach:** Phase B is a UI refactor that ships behind a `?ui=v2` query-string flag for the duration of the migration. The flag is removed in Task 13. Tasks 6–8 add the new InfoPanel without removing the old sidebar; Task 9 adds the More menu; Task 10 deletes the old sidebar; Tasks 11–14 add mobile, FAB, and polish. Each task should `npm run dev` and refresh the browser to verify visually.

### Task 6: Scaffold TabBar + DesktopDock + InfoPanel (empty tabs, behind a flag)

**Files:**
- Create: `frontend/src/components/InfoPanel.vue`
- Create: `frontend/src/components/DesktopDock.vue`
- Create: `frontend/src/components/TabBar.vue`
- Modify: `frontend/src/views/MapView.vue` (mount InfoPanel alongside the sidebar when `?ui=v2`)

- [ ] **Step 1: Create `TabBar.vue`**

```vue
<template>
  <nav class="tab-bar" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.key"
      type="button"
      role="tab"
      class="tab"
      :class="{ active: t.key === active }"
      :aria-selected="t.key === active"
      @click="$emit('update:active', t.key)"
    >
      <span class="tab-icon" aria-hidden="true">{{ t.icon }}</span>
      <span class="tab-label">{{ t.label }}</span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  tabs: { type: Array, required: true }, // [{key, label, icon}]
  active: { type: String, required: true },
})
defineEmits(['update:active'])
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--cream-edge);
  background: var(--paper);
}
.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.7rem 0.4rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font: inherit;
  font-size: 0.92rem;
  color: var(--ink-faded);
  cursor: pointer;
  transition: color 90ms ease, border-color 90ms ease;
}
.tab:hover { color: var(--ink); }
.tab.active { color: var(--vermillion); border-bottom-color: var(--vermillion); }
.tab-icon { font-size: 1.05rem; }
.tab-label { font-family: var(--mono); font-size: 0.78rem; letter-spacing: 0.05em; text-transform: uppercase; }
</style>
```

- [ ] **Step 2: Create `DesktopDock.vue`**

```vue
<template>
  <aside class="desktop-dock paper" :class="{ collapsed }">
    <button
      class="dock-collapse btn-icon"
      type="button"
      :aria-label="collapsed ? 'Expand' : 'Collapse'"
      @click="$emit('update:collapsed', !collapsed)"
    >{{ collapsed ? '⟩' : '⟨' }}</button>
    <div v-if="!collapsed" class="dock-body">
      <slot />
    </div>
    <div v-else class="dock-rail">
      <slot name="rail" />
    </div>
  </aside>
</template>

<script setup>
defineProps({
  collapsed: { type: Boolean, default: false },
})
defineEmits(['update:collapsed'])
</script>

<style scoped>
.desktop-dock {
  position: absolute;
  top: 16px;
  left: 16px;
  bottom: 16px;
  width: 360px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--vermillion);
  border-radius: 4px;
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.06);
  z-index: 400;
  overflow: hidden;
}
.desktop-dock.collapsed { width: 56px; }
.dock-collapse {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}
.dock-body { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.dock-rail { flex: 1; padding: 2.5rem 0.5rem 0.5rem; display: flex; flex-direction: column; gap: 0.4rem; }
</style>
```

- [ ] **Step 3: Create `InfoPanel.vue`**

```vue
<template>
  <DesktopDock v-model:collapsed="collapsed">
    <header class="dock-head">
      <slot name="header" />
    </header>
    <TabBar :tabs="tabs" :active="active" @update:active="(k) => emit('update:active', k)" />
    <div class="tab-content">
      <slot :name="active" />
    </div>
    <template #rail>
      <button
        v-for="t in tabs"
        :key="t.key"
        type="button"
        class="rail-icon"
        :class="{ active: t.key === active }"
        :title="t.label"
        @click="rail(t.key)"
      >{{ t.icon }}</button>
    </template>
  </DesktopDock>
</template>

<script setup>
import { ref } from 'vue'
import DesktopDock from './DesktopDock.vue'
import TabBar from './TabBar.vue'

const props = defineProps({
  tabs: { type: Array, required: true },
  active: { type: String, required: true },
})
const emit = defineEmits(['update:active'])

const collapsed = ref(false)
function rail(key) {
  emit('update:active', key)
  collapsed.value = false
}
</script>

<style scoped>
.dock-head {
  padding: 0.9rem 1rem 0.7rem;
  border-bottom: 1px solid var(--cream-edge);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.tab-content { flex: 1; overflow-y: auto; padding: 0.9rem 1rem 1rem; }
.rail-icon {
  background: transparent;
  border: 1px solid transparent;
  font-size: 1.2rem;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 3px;
}
.rail-icon:hover { background: var(--cream); border-color: var(--cream-edge); }
.rail-icon.active { background: var(--cream); border-color: var(--vermillion); }
</style>
```

- [ ] **Step 4: Mount InfoPanel in MapView under a `?ui=v2` flag**

In `frontend/src/views/MapView.vue`:

Add to the imports near the top of `<script setup>`:

```javascript
import InfoPanel from '@/components/InfoPanel.vue'
```

Add a feature-flag computed at the same level as `theme`, `mapData`, etc.:

```javascript
const useV2 = ref(new URLSearchParams(window.location.search).get('ui') === 'v2')
const v2Active = ref('places')
const v2Tabs = [
  { key: 'places', label: 'Places', icon: '📍' },
  { key: 'itinerary', label: 'Itinerary', icon: '🗓' },
  { key: 'more', label: 'More', icon: '⋯' },
]
```

In the `<template>`, immediately after the closing `</aside>` of the existing `.sidebar` block (line 143), add:

```vue
<InfoPanel
  v-if="useV2 && mapData"
  :tabs="v2Tabs"
  :active="v2Active"
  @update:active="(k) => v2Active = k"
>
  <template #header><p class="mono">v2 dock — {{ mapData.title || 'Untitled voyage' }}</p></template>
  <template #places><p>Places tab — empty for now</p></template>
  <template #itinerary><p>Itinerary tab — empty for now</p></template>
  <template #more><p>More menu — empty for now</p></template>
</InfoPanel>
```

- [ ] **Step 5: Browser verify**

Visit `http://localhost:5173/map/<slug>?ui=v2`. Expected:
- Old sidebar still on the left.
- New `InfoPanel` floats at top-left ABOVE/OVER the sidebar (because absolute, z-index 400). Three tabs visible. Tab clicks switch the placeholder content.
- Collapse button toggles between dock and icon rail.

If they overlap badly, that's expected — this is a transient state.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/InfoPanel.vue frontend/src/components/DesktopDock.vue frontend/src/components/TabBar.vue frontend/src/views/MapView.vue
git commit -m "feat(ui): scaffold InfoPanel + TabBar + DesktopDock behind ?ui=v2"
```

---

### Task 7: Migrate Places tab content into InfoPanel

**Files:**
- Modify: `frontend/src/components/PointList.vue` (trail-row swatch on left edge)
- Modify: `frontend/src/views/MapView.vue` (Places tab slot)

- [ ] **Step 1: Add a left-edge swatch to PointList rows for trail-points**

In `frontend/src/components/PointList.vue`, modify the `<li>` content. Replace the template body (lines 1–23) with:

```vue
<template>
  <ul class="point-list">
    <li v-if="points.length === 0" class="empty">
      <em>No marks yet. Click the map to drop one.</em>
    </li>
    <li
      v-for="p in points"
      :key="p.id"
      class="point"
      :class="{ active: p.id === activeId, 'is-trail': !!p.gpx_data }"
      :style="p.gpx_data && p.color ? { '--swatch': p.color } : null"
      @click="$emit('select', p)"
    >
      <span class="pin-mini">{{ emojiFor(p.category) }}</span>
      <div class="text">
        <div class="title">{{ p.title || untitled(p) }}</div>
        <div v-if="p.comment" class="comment">{{ p.comment }}</div>
        <div class="coord">
          {{ formatLat(p.lat) }} · {{ formatLng(p.lng) }}
        </div>
      </div>
    </li>
  </ul>
</template>
```

Add to the `<style scoped>` block at the bottom:

```css
.point.is-trail { border-left: 4px solid var(--swatch, var(--ink-faded)); padding-left: 0.6rem; }
```

- [ ] **Step 2: Build the Places tab slot in MapView**

Replace the placeholder Places template in the `<InfoPanel>` block from Task 6 with the real Places content. Update the InfoPanel mount to:

```vue
<InfoPanel
  v-if="useV2 && mapData"
  :tabs="v2Tabs"
  :active="v2Active"
  @update:active="(k) => v2Active = k"
>
  <template #header>
    <h2 class="title">
      <input
        v-model="titleDraft"
        class="title-input"
        placeholder="Untitled voyage"
        maxlength="120"
        @blur="commitTitle"
        @keydown.enter="$event.target.blur()"
      />
    </h2>
    <p class="coord meta">
      <span class="meta-icon">⌖</span>
      <span>{{ formatLat(mapData.center_lat) }} · {{ formatLng(mapData.center_lng) }}</span>
    </p>
    <div class="radius-row">
      <span class="radius-label mono">Radius · {{ formatRadius(mapData.radius_m) }}</span>
      <RadiusSlider v-model="radiusDraft" @update:modelValue="liveRadius" @change="commitRadius" />
    </div>
  </template>

  <template #places>
    <GeocoderSearch placeholder="Search a spot to mark…" @pick="onSearchPick" />
    <button class="locate-link" type="button" @click="markMyLocation" :disabled="locating">
      ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
    </button>
    <p v-if="locateError" class="error sm">{{ locateError }}</p>
    <CategoryFilters :points="mapData.points" :hidden="hiddenCats" @toggle="toggleCat" @reset="resetCats" />
    <PointList :points="visiblePoints" :active-id="activeId" @select="onSelectPoint" />
    <p v-if="gpxError" class="error sm">{{ gpxError }}</p>
    <p class="hint mono">Drop a .gpx anywhere on the map.</p>
    <label class="btn btn-tiny gpx-pick v2-gpx">
      + GPX
      <input type="file" accept=".gpx,application/gpx+xml" multiple class="hidden" @change="onGpxFilePick" />
    </label>
  </template>

  <template #itinerary><p>Itinerary tab — coming in Task 8</p></template>
  <template #more><p>More menu — coming in Task 9</p></template>
</InfoPanel>
```

Also keep the existing `+ Drop` button in the Places content for now — it moves to a FAB in Task 13. Add it just after the GeocoderSearch:

```vue
<button class="btn btn-tiny" @click="startNewPin">+ Drop</button>
```

- [ ] **Step 3: Browser verify**

Visit `http://localhost:5173/map/<slug>?ui=v2`. Expected:
- Dock header shows the voyage title (editable), coords, radius slider — same as old sidebar header.
- Places tab shows search, "use my location", category filters, full point list (including trail-points with a vermillion-toned left edge swatch).
- Click a trail row in the points list — the elevation profile opens (because the existing `onSelectPoint` flow is the pin-detail flow, which still works). Clicking the trail row in the *legacy* sidebar's Routes section still toggles the polyline as before. Both code paths exist in parallel.
- Itinerary and More tabs still show placeholders.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PointList.vue frontend/src/views/MapView.vue
git commit -m "feat(ui): Places tab in v2 InfoPanel (with trail swatch in list)"
```

---

### Task 8: Migrate Itinerary tab into InfoPanel

**Files:**
- Modify: `frontend/src/views/MapView.vue` (Itinerary slot)

- [ ] **Step 1: Replace the Itinerary placeholder slot**

In the `<InfoPanel>` block, replace the `#itinerary` slot with:

```vue
<template #itinerary>
  <Itinerary
    :days="mapData.itinerary || []"
    @add="onAddDay"
    @add-bulk="onAddBulk"
    @delete="onDeleteDay"
    @go="onGoDay"
  />
</template>
```

- [ ] **Step 2: Browser verify**

Refresh with `?ui=v2`. Click the Itinerary tab. Expected:
- The full Itinerary component renders (paste-import field, day list, add-day form).
- "Center map on today's stop" still works.
- Adding a new day in the v2 dock updates immediately, and is reflected in the legacy sidebar after re-rendering.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "feat(ui): Itinerary tab in v2 InfoPanel"
```

---

### Task 9: Build the More menu (Daylight, Survival, Offline, Share, Theme)

**Files:**
- Create: `frontend/src/components/MoreMenu.vue`
- Modify: `frontend/src/views/MapView.vue` (More tab slot)

- [ ] **Step 1: Create `MoreMenu.vue`**

```vue
<template>
  <div class="more-menu">
    <section class="more-block">
      <h4 class="more-title">Daylight</h4>
      <SunPanel :fallback-lat="fallbackLat" :fallback-lng="fallbackLng" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Survival POIs</h4>
      <SurvivalLayer :get-bounds="getBounds" @render="(v) => emit('render-survival', v)" @clear="emit('clear-survival')" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Offline</h4>
      <PrecacheButton :theme="theme" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Share</h4>
      <button class="btn btn-ghost btn-share" @click="emit('copy-url')">
        {{ copied ? 'Copied ✓' : 'Copy link' }}
      </button>
    </section>

    <section class="more-block">
      <h4 class="more-title">Theme</h4>
      <ThemeToggle />
    </section>
  </div>
</template>

<script setup>
import SunPanel from './SunPanel.vue'
import SurvivalLayer from './SurvivalLayer.vue'
import PrecacheButton from './PrecacheButton.vue'
import ThemeToggle from './ThemeToggle.vue'

defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
  getBounds: { type: Function, required: true },
  theme: { type: String, required: true },
  copied: { type: Boolean, default: false },
})
const emit = defineEmits(['render-survival', 'clear-survival', 'copy-url'])
</script>

<style scoped>
.more-menu { display: flex; flex-direction: column; gap: 1.2rem; }
.more-block { padding-bottom: 0.4rem; border-bottom: 1px dashed var(--cream-edge); }
.more-block:last-child { border-bottom: none; }
.more-title {
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0 0 0.5rem;
}
</style>
```

- [ ] **Step 2: Wire `MoreMenu` into the MapView**

Add to the imports in `<script setup>` of `MapView.vue`:

```javascript
import MoreMenu from '@/components/MoreMenu.vue'
```

Replace the More slot in `<InfoPanel>`:

```vue
<template #more>
  <MoreMenu
    :fallback-lat="mapData.center_lat"
    :fallback-lng="mapData.center_lng"
    :get-bounds="getMapBounds"
    :theme="theme"
    :copied="copied"
    @render-survival="renderSurvival"
    @clear-survival="clearSurvival"
    @copy-url="copyUrl"
  />
</template>
```

- [ ] **Step 3: Browser verify**

Refresh with `?ui=v2`. Click the More tab. Expected:
- Daylight panel renders with sunrise/sunset.
- Survival "render water/trash/dump/toilets" buttons render the Overpass POIs on the map.
- Precache button works.
- Share copies the URL.
- Theme toggle flips light/dark and the map tiles update.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/MoreMenu.vue frontend/src/views/MapView.vue
git commit -m "feat(ui): More menu hosting Daylight + Survival + Offline + Share + Theme"
```

---

### Task 10: Delete the legacy sidebar

**Files:**
- Modify: `frontend/src/views/MapView.vue` (remove the `<aside class="sidebar">` block, remove the v2 flag, remove ~600 lines of sidebar CSS)

The InfoPanel becomes the only UI. The `useV2` flag goes away — v2 is the new default.

- [ ] **Step 1: Delete the legacy sidebar template**

In `frontend/src/views/MapView.vue`, remove the entire `<aside class="sidebar" ...>` block — from line 3 (`<aside class="sidebar paper" :class="{ open: sidebarOpen }">`) through its closing `</aside>` (line 143). The InfoPanel block stays.

- [ ] **Step 2: Remove the feature flag**

Replace the v2 mount condition `v-if="useV2 && mapData"` with `v-if="mapData"`. Delete the `useV2` ref. Keep `v2Active` and `v2Tabs` (rename later if you like — for now they are the only tab state).

- [ ] **Step 3: Remove sidebar-only refs and handlers**

Delete `sidebarOpen` (refs and any other usage) and `activeTrackId` if it survived from the original code (it should already be `activeTrailPointId` after Task 4).

- [ ] **Step 4: Delete sidebar CSS**

In the `<style>` block at the bottom of `MapView.vue`, delete every selector targeting `.sidebar`, `.side-head`, `.voyage-head`, `.sec`, `.sec-head`, `.sec-num`, `.sec-title`, `.sec-count`, `.sec-action`, `.major-rule`, `.side-foot`, `.foot-lbl`, `.btn-share`, `.track-list`, `.track-row`, `.track-swatch`, `.track-name`, `.track-del`, and the `@media (max-width: 720px)` block at the very end (lines 1291–1295). Keep map-overlay CSS (`.today-banner`, `.locate-me`, `.dropzone`, `.elevation-profile`-related, etc.).

This deletion is best done by repeatedly using grep to find each selector, deleting its block, and re-running `npm run dev` to confirm no syntax errors. Aim for a net reduction of ~500–650 lines in MapView.vue.

- [ ] **Step 5: Browser verify**

Visit `http://localhost:5173/map/<slug>` (no flag). Expected:
- Only the floating dock visible.
- Map fills the rest of the screen.
- All tabs work; the today banner still appears at top.
- No console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "refactor(ui): drop legacy sidebar, InfoPanel is now the default"
```

---

### Task 11: Build MobileSheet with drag-snap (peek/half/full)

**Files:**
- Create: `frontend/src/components/MobileSheet.vue`

- [ ] **Step 1: Create `MobileSheet.vue`**

```vue
<template>
  <div
    ref="sheetEl"
    class="mobile-sheet paper"
    :class="['state-' + state]"
    :style="{ '--sheet-h': heightPct + '%' }"
  >
    <div
      class="sheet-handle"
      @pointerdown="onDragStart"
      @pointermove="onDragMove"
      @pointerup="onDragEnd"
      @pointercancel="onDragEnd"
    >
      <span class="handle-bar" />
    </div>
    <slot name="tabs" />
    <div class="sheet-content"><slot /></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const STATES = { peek: 8, half: 50, full: 92 } // % of viewport height
const order = ['peek', 'half', 'full']

const state = ref('peek')
const sheetEl = ref(null)
const heightPct = computed(() => STATES[state.value])

let dragStartY = null
let dragStartPct = null
let dragLivePct = null

function onDragStart(e) {
  dragStartY = e.clientY
  dragStartPct = STATES[state.value]
  dragLivePct = dragStartPct
  e.target.setPointerCapture(e.pointerId)
}
function onDragMove(e) {
  if (dragStartY == null) return
  const dy = dragStartY - e.clientY  // up = positive
  const pct = dragStartPct + (dy / window.innerHeight) * 100
  dragLivePct = Math.max(STATES.peek, Math.min(STATES.full, pct))
  if (sheetEl.value) sheetEl.value.style.setProperty('--sheet-h', `${dragLivePct}%`)
}
function onDragEnd(e) {
  if (dragStartY == null) return
  const target = order
    .map((k) => ({ k, d: Math.abs(STATES[k] - dragLivePct) }))
    .sort((a, b) => a.d - b.d)[0].k
  state.value = target
  dragStartY = null
  if (sheetEl.value) sheetEl.value.style.removeProperty('--sheet-h')
  e.target.releasePointerCapture?.(e.pointerId)
}

defineExpose({ setState: (s) => { if (STATES[s]) state.value = s } })
</script>

<style scoped>
.mobile-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: var(--sheet-h, 8%);
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--vermillion);
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
  z-index: 500;
  transition: height 220ms ease;
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.mobile-sheet.state-peek { transition-duration: 180ms; }
.sheet-handle {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
}
.sheet-handle:active { cursor: grabbing; }
.handle-bar {
  width: 44px;
  height: 4px;
  border-radius: 2px;
  background: var(--ink-faded);
}
.sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem 1rem 1rem;
}
</style>
```

- [ ] **Step 2: Standalone smoke check**

Temporarily mount it in `MapView.vue` instead of `InfoPanel` (just for this step) by adding `<MobileSheet><template #tabs><p>tabs go here</p></template><p>content</p></MobileSheet>` and visit on a phone-width viewport (Chrome DevTools, 375×667). Verify:
- Sheet appears at the bottom in peek state, ~8% tall.
- Drag the handle up — sheet grows to half, then full as you cross the snap thresholds.
- Drag down to peek.
- Content scrolls inside the sheet.

Then revert the smoke check (this is a one-off probe — Task 12 wires it for real).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MobileSheet.vue
git commit -m "feat(ui): MobileSheet with drag-snap (peek/half/full)"
```

---

### Task 12: InfoPanel switches between DesktopDock and MobileSheet

**Files:**
- Modify: `frontend/src/components/InfoPanel.vue`

- [ ] **Step 1: Make InfoPanel responsive**

Replace `frontend/src/components/InfoPanel.vue` with:

```vue
<template>
  <DesktopDock v-if="!isMobile" v-model:collapsed="collapsed">
    <header class="dock-head"><slot name="header" /></header>
    <TabBar :tabs="tabs" :active="active" @update:active="(k) => emit('update:active', k)" />
    <div class="tab-content"><slot :name="active" /></div>
    <template #rail>
      <button v-for="t in tabs" :key="t.key" type="button" class="rail-icon"
              :class="{ active: t.key === active }" :title="t.label" @click="rail(t.key)">{{ t.icon }}</button>
    </template>
  </DesktopDock>

  <MobileSheet v-else>
    <template #tabs>
      <TabBar :tabs="tabs" :active="active" @update:active="(k) => emit('update:active', k)" />
    </template>
    <header class="sheet-head"><slot name="header" /></header>
    <div><slot :name="active" /></div>
  </MobileSheet>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import DesktopDock from './DesktopDock.vue'
import MobileSheet from './MobileSheet.vue'
import TabBar from './TabBar.vue'

const props = defineProps({
  tabs: { type: Array, required: true },
  active: { type: String, required: true },
})
const emit = defineEmits(['update:active'])

const mq = window.matchMedia('(max-width: 720px)')
const isMobile = ref(mq.matches)
const collapsed = ref(false)
function onMQ(e) { isMobile.value = e.matches }
onMounted(() => mq.addEventListener('change', onMQ))
onUnmounted(() => mq.removeEventListener('change', onMQ))

function rail(key) {
  emit('update:active', key)
  collapsed.value = false
}
</script>

<style scoped>
.dock-head, .sheet-head {
  padding: 0.9rem 1rem 0.7rem;
  border-bottom: 1px solid var(--cream-edge);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.tab-content { flex: 1; overflow-y: auto; padding: 0.9rem 1rem 1rem; }
.rail-icon {
  background: transparent; border: 1px solid transparent;
  font-size: 1.2rem; padding: 0.5rem; cursor: pointer; border-radius: 3px;
}
.rail-icon:hover { background: var(--cream); border-color: var(--cream-edge); }
.rail-icon.active { background: var(--cream); border-color: var(--vermillion); }
</style>
```

- [ ] **Step 2: Browser verify on both viewports**

In Chrome DevTools, toggle the device toolbar:
- Desktop (1440×900): floating dock as before.
- iPhone 14 Pro (393×852): bottom sheet at the bottom, peek by default.
- Toggle once at runtime (drag the responsive divider) — InfoPanel switches without reload.

Drag the sheet up — content fills. Tap a different tab — switches to that tab's slot. The map remains responsive to taps.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/InfoPanel.vue
git commit -m "feat(ui): InfoPanel switches between DesktopDock and MobileSheet by viewport"
```

---

### Task 13: Move "Drop pin" to a floating action button on the map

**Files:**
- Create: `frontend/src/components/MapFab.vue`
- Modify: `frontend/src/views/MapView.vue` (remove `+ Drop` from Places tab; add MapFab to map overlays)

- [ ] **Step 1: Create `MapFab.vue`**

```vue
<template>
  <button class="map-fab" type="button" :title="title" @click="$emit('click')">
    <span class="fab-glyph">{{ glyph }}</span>
  </button>
</template>

<script setup>
defineProps({
  glyph: { type: String, default: '+' },
  title: { type: String, default: 'Drop a pin' },
})
defineEmits(['click'])
</script>

<style scoped>
.map-fab {
  position: absolute;
  right: 16px;
  bottom: 16px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--vermillion);
  color: var(--paper);
  border: none;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  z-index: 450;
  transition: transform 90ms ease;
}
.map-fab:hover { transform: scale(1.05); }
.fab-glyph { font-size: 1.6rem; line-height: 1; font-weight: 600; }
</style>
```

- [ ] **Step 2: Mount `MapFab` and remove the `+ Drop` button from Places**

In `MapView.vue`:

Add to imports:

```javascript
import MapFab from '@/components/MapFab.vue'
```

In the `.map-wrap` block of the template, after the `<button class="locate-me">`, add:

```vue
<MapFab glyph="+" title="Drop a pin" @click="startNewPin" />
```

In the Places slot of `<InfoPanel>`, remove the line `<button class="btn btn-tiny" @click="startNewPin">+ Drop</button>` you added in Task 7.

- [ ] **Step 3: Avoid overlap with the locate-me button**

Both buttons want bottom-right. Adjust `.locate-me` (find its CSS in MapView.vue's `<style>` block) to sit at `bottom: 80px` (above the FAB). If `.locate-me` already uses `bottom: 16px`, change the value to `80px`.

- [ ] **Step 4: Browser verify**

- Desktop: FAB at bottom-right of the map. Click → enters drop-pin mode (the existing `startNewPin` flow opens the form modal).
- Mobile: FAB still bottom-right, comfortably above the bottom sheet's peek state. Drag the sheet up to half-state — the FAB is now occluded by the sheet, which is acceptable (user can drop it back to peek to access the FAB).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MapFab.vue frontend/src/views/MapView.vue
git commit -m "feat(ui): drop-pin promoted to a floating action button on the map"
```

---

### Task 14: Polish — banner extension, safe-area, and small fit-and-finish

**Files:**
- Modify: `frontend/src/views/MapView.vue` (today banner: add sunrise/sunset on desktop)
- Modify: `frontend/src/components/MobileSheet.vue` (already has safe-area-inset; double-check)

- [ ] **Step 1: Extend the today banner with sun glance on desktop**

In MapView.vue, `useSun` is already imported via `SunPanel` indirectly. Locate the banner template (line 151–155) and update to show sunrise/sunset on screens > 720px.

Replace the banner block with:

```vue
<div v-if="todayBanner" class="today-banner" @click="onGoDay(todayBanner.day)">
  <span class="banner-tag mono">{{ todayBanner.tag }}</span>
  <span class="banner-text">{{ todayBanner.text }}</span>
  <span v-if="todayBanner.sun" class="banner-sun mono">☀ {{ todayBanner.sun.rise }} → {{ todayBanner.sun.set }}</span>
  <span v-if="todayBanner.notes" class="banner-notes">{{ todayBanner.notes }}</span>
</div>
```

In `<script setup>`, extend the `todayBanner` computed to attach a `sun` property when on desktop AND when a coord is available. Use `suncalc` (already a dependency):

```javascript
import SunCalc from 'suncalc'

// inside todayBanner computed, after the existing logic that returns the banner object:
function fmtHM(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function attachSun(banner) {
  if (!banner) return banner
  if (window.matchMedia('(max-width: 720px)').matches) return banner
  const lat = banner.day.lat ?? mapData.value?.center_lat
  const lng = banner.day.lng ?? mapData.value?.center_lng
  if (lat == null || lng == null) return banner
  const t = SunCalc.getTimes(new Date(banner.day.date), lat, lng)
  if (!t.sunrise || !t.sunset || isNaN(t.sunrise) || isNaN(t.sunset)) return banner
  return { ...banner, sun: { rise: fmtHM(t.sunrise), set: fmtHM(t.sunset) } }
}
```

Then wrap the existing returns of the `todayBanner` computed: instead of `return { tag, text, notes, day }`, do `return attachSun({ tag, text, notes, day })`.

Add corresponding CSS in the same file's `<style>` block (near `.banner-text`):

```css
.banner-sun { font-size: 0.78rem; color: var(--ink-soft); }
```

- [ ] **Step 2: Double-check safe-area-inset on iOS**

In Chrome DevTools, simulate iPhone 14 Pro (393×852, with notch). Resize the bottom sheet to peek state. The handle should not be obscured by the home-indicator area — `padding-bottom: env(safe-area-inset-bottom, 0)` from Task 11 handles this.

- [ ] **Step 3: Browser verify all viewports + interactions**

Spend ~5 minutes exercising the full app on both desktop and mobile widths. Check:
- Drop a pin via FAB → form opens → save → pin appears in Places list and on map.
- Drop a GPX → trail-point appears in Places list with swatch → click → polyline + elevation profile open.
- Itinerary tab: paste-import a small itinerary → days appear → click "Center on today" → map centers, banner updates, banner shows sunrise/sunset on desktop only.
- More tab: Survival → render water → markers appear → clear → markers disappear.
- More tab: Theme toggle → light/dark switches → tiles update.
- More tab: Copy link → clipboard contains the URL.
- Mobile: drag sheet to full → all controls reachable → drop back to peek → map free.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/MapView.vue frontend/src/components/MobileSheet.vue
git commit -m "polish(ui): banner sun glance + safe-area-inset confirmed on mobile"
```

---

## Self-review (already applied)

**Spec coverage:** Each spec section has a task — domain unification (1–5), InfoPanel scaffolding (6), Places (7), Itinerary (8), MoreMenu (9), legacy delete (10), MobileSheet (11), responsive switch (12), MapFab (13), polish (14).

**Placeholder check:** No "TBD"s; every step shows full code. The Task 10 sidebar-CSS deletion lists each selector to remove rather than saying "delete sidebar styles".

**Type/name consistency:** `activeTrailPointId` is consistent across Tasks 4, 7, and 10. `gpx_data` and `color` are consistent across model, schemas, and frontend. `v2Tabs` / `v2Active` introduced in Task 6 persist into Task 10 (renamed away from the v2 prefix is left to a follow-up — keeping the names is harmless).

**Scope:** Backend changes are minimal (one column add, one table drop, one route delete). Frontend changes are layered to keep the app working at every commit. The plan is one feature (the redesign + the data unification it depends on); not split because the UI redesign is meaningless without the data unification.
