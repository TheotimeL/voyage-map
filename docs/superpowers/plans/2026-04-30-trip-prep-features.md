# Trip-Prep Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 5 trip-critical features for the May 9–30 US Southwest van trip — offline area pre-cache, sun-tracker, dark mode, elevation profile, Overpass "survival" POIs — and polish the already-built Itinerary feature.

**Architecture:** All five new features integrate into the existing Vue 3 / Leaflet `MapView.vue`. Backend stays mostly untouched (only Overpass needs a thin proxy). PWA scaffolding is already in place via `vite-plugin-pwa`; we extend its runtime caching with a one-shot proactive **pre-cache** that walks tile URLs for the trip area at install time. Pure-client features (suncalc, dark-mode, elevation chart) ship as small Vue components that compose with the existing map state.

**Tech Stack:**
- Existing: Vue 3, Vite, Leaflet, FastAPI, SQLite, `vite-plugin-pwa` + `workbox-window`
- New deps: `suncalc` (sun calc), no new chart library — render elevation profile in a small inline SVG component to keep the bundle tight

**Status snapshot (2026-04-30):**
- ✅ PWA scaffold + Carto tile runtime caching done (`frontend/vite.config.js:9-67`)
- ✅ Itinerary feature complete (backend `api/itinerary.py`, frontend `Itinerary.vue`, `today-banner` in `MapView.vue:108-112`)
- ❌ Offline proactive pre-cache, sun-tracker, dark mode, elevation, Overpass: not started

**Trip context (used for defaults & geofencing):**
Las Vegas → Sedona → Grand Canyon → Page → Bryce → Zion → Death Valley → Tahoe → Yosemite → SF, May 9–30. Bounding box used for area pre-cache: roughly **lat 33.0–39.5, lng −121.0 to −111.5**.

**Conventions:**
- Existing files use no comments unless the *why* is non-obvious — match that.
- All new module imports must work via the `@` alias (`@/util.js`).
- New endpoints under `/api`; routers registered in `server.py`.

**Self-test discipline:** This codebase has no test infrastructure. We add light unit tests **only** for pure logic (parsers, ephemeris formatting, tile-URL math) — created as plain ESM scripts runnable via `node`, since adding Vitest is out-of-scope. UI changes are verified manually via the dev server.

---

## File Structure

**New files:**
- `frontend/src/lib/precache.js` — proactive tile + map data pre-caching
- `frontend/src/lib/sun.js` — wrapper around suncalc with formatting helpers
- `frontend/src/lib/elevation.js` — GPX elevation extraction + smoothing
- `frontend/src/lib/overpass.js` — Overpass QL builder + fetch + result mapping
- `frontend/src/lib/theme.js` — dark-mode store (localStorage-backed)
- `frontend/src/components/PrecacheButton.vue` — sidebar control + progress bar
- `frontend/src/components/SunPanel.vue` — live ephemeris card
- `frontend/src/components/ElevationProfile.vue` — bottom-sheet SVG chart
- `frontend/src/components/SurvivalLayer.vue` — Overpass POI toggle + Leaflet markers
- `frontend/src/components/ThemeToggle.vue` — sun/moon switch in side-head
- `frontend/test/precache.test.mjs` — tile-URL math
- `frontend/test/sun.test.mjs` — sun formatting
- `frontend/test/elevation.test.mjs` — GPX → elevation series
- `frontend/test/overpass.test.mjs` — query builder

**Modified files:**
- `frontend/vite.config.js` — add Overpass + Nominatim runtime caching, expose `__VOYAGE_BBOX__` build-time constant
- `frontend/src/main.js` — load `theme.js` early so the first paint already has the right CSS class
- `frontend/src/views/MapView.vue` — wire new components, switch tile URL based on theme
- `frontend/src/styles/vintage.css` — add `[data-theme="dark"]` overrides for all CSS vars
- `server.py` — register `overpass_router`
- `api/overpass.py` (new) — thin proxy with response caching to dodge CORS + rate limits

**Skipped:** No backend persistence for survival POIs (purely client-side, cached by service worker), no DB migration needed.

---

## Phase 0 — Setup

### Task 0.1: Add npm deps and verify dev server

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Add suncalc**

```bash
cd frontend && npm install suncalc@^1.9.0
```

- [ ] **Step 2: Boot dev servers in two terminals (or background)**

```bash
# Terminal A
source .venv/bin/activate && uvicorn server:app --reload --port 8000

# Terminal B
cd frontend && npm run dev
```

- [ ] **Step 3: Verify the existing app loads**

Open `http://localhost:5173`, create a map, confirm the today-banner and itinerary section render.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "deps: add suncalc for sun-tracker feature"
```

### Task 0.2: Stash current uncommitted itinerary work as its own commit

**Goal:** The 6-file diff currently in the working tree is the finished itinerary feature. Bank it before we start adding more.

- [ ] **Step 1: Review the diff**

```bash
git -C /Users/tlavisse/Documents/code/voyage-map diff --stat
git -C /Users/tlavisse/Documents/code/voyage-map status
```

- [ ] **Step 2: Stage the itinerary work**

```bash
git add api/itinerary.py frontend/src/components/Itinerary.vue \
        frontend/src/api.js frontend/src/util.js \
        frontend/src/views/MapView.vue \
        server.py services/models.py services/schemas.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(itinerary): trip days, paste import, today banner

- ItineraryDay model + CRUD + bulk import
- Parse FR/EN dates from spreadsheet paste
- Today banner above the map with countdown to next stop
- Geocode-on-click for unlocated days"
```

---

## Phase 1 — Offline area pre-cache (Feature #1)

**Why first:** The whole trip happens off-grid. Without proactive caching, the existing PWA only saves tiles you've already viewed at the right zoom — useless for the BLM at midnight in Death Valley.

**Approach:** Add a sidebar button "Pre-cache trip area" that walks tile URLs across a bbox at zooms 6–13 and forces the service worker to download them via `fetch()` (workbox `CacheFirst` strategy will store them automatically). Shows progress, persists "done" state in localStorage so we don't redownload on every visit.

### Task 1.1: Tile-URL math (with tests)

**Files:**
- Create: `frontend/src/lib/precache.js`
- Create: `frontend/test/precache.test.mjs`

- [ ] **Step 1: Write the failing test**

```js
// frontend/test/precache.test.mjs
import assert from 'node:assert/strict'
import { tilesForBbox, lonLatToTile } from '../src/lib/precache.js'

// Vegas at zoom 10
const t = lonLatToTile(36.17, -115.14, 10)
assert.equal(t.x, 178)
assert.equal(t.y, 408)

// Trip bbox at z6 should yield a small finite list
const list = tilesForBbox({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }, [6, 6])
assert.ok(list.length > 0 && list.length < 50, `z6 list size ${list.length}`)

// Bigger zoom = more tiles
const big = tilesForBbox({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }, [10, 10])
assert.ok(big.length > list.length)

console.log('precache: OK')
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd frontend && node test/precache.test.mjs
```

Expected: `Error: Cannot find module '../src/lib/precache.js'` or similar.

- [ ] **Step 3: Implement `precache.js` (math only, no fetching yet)**

```js
// frontend/src/lib/precache.js — slippy-tile math + walker

const SUBDOMAINS = ['a', 'b', 'c', 'd']

export function lonLatToTile(lat, lng, z) {
  const n = 2 ** z
  const x = Math.floor(((lng + 180) / 360) * n)
  const latRad = (lat * Math.PI) / 180
  const y = Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n,
  )
  return { x, y }
}

export function tilesForBbox(bbox, [zMin, zMax]) {
  const out = []
  for (let z = zMin; z <= zMax; z++) {
    const tl = lonLatToTile(bbox.maxLat, bbox.minLng, z)
    const br = lonLatToTile(bbox.minLat, bbox.maxLng, z)
    for (let x = tl.x; x <= br.x; x++) {
      for (let y = tl.y; y <= br.y; y++) out.push({ z, x, y })
    }
  }
  return out
}

export function tileUrl({ z, x, y }, theme = 'light') {
  const sd = SUBDOMAINS[(x + y) % SUBDOMAINS.length]
  const style = theme === 'dark' ? 'dark_all' : 'light_all'
  return `https://${sd}.basemaps.cartocdn.com/${style}/${z}/${x}/${y}.png`
}
```

- [ ] **Step 4: Test passes**

```bash
cd frontend && node test/precache.test.mjs
# expect: precache: OK
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/precache.js frontend/test/precache.test.mjs
git commit -m "feat(offline): tile-URL math for proactive area cache"
```

### Task 1.2: Cache-walker with progress callbacks

**Files:**
- Modify: `frontend/src/lib/precache.js`

- [ ] **Step 1: Append the walker to `precache.js`**

```js
// Append to frontend/src/lib/precache.js

export async function preloadTiles(tiles, theme, { onProgress, signal, concurrency = 6 } = {}) {
  let done = 0, failed = 0
  const total = tiles.length
  const queue = tiles.slice()

  async function worker() {
    while (queue.length) {
      if (signal?.aborted) return
      const t = queue.shift()
      try {
        const res = await fetch(tileUrl(t, theme), { mode: 'cors', cache: 'force-cache' })
        if (!res.ok) failed++
      } catch { failed++ }
      done++
      onProgress?.({ done, failed, total })
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker))
  return { done, failed, total }
}
```

- [ ] **Step 2: Add a quick smoke test**

Append to `frontend/test/precache.test.mjs`:

```js
import { preloadTiles } from '../src/lib/precache.js'
// stub fetch
let calls = 0
globalThis.fetch = async () => { calls++; return { ok: true } }
const r = await preloadTiles(
  [{ z: 6, x: 1, y: 1 }, { z: 6, x: 2, y: 1 }],
  'light',
  { concurrency: 2 },
)
assert.equal(r.done, 2)
assert.equal(r.failed, 0)
assert.equal(calls, 2)
console.log('preloadTiles: OK')
```

- [ ] **Step 3: Run**

```bash
cd frontend && node test/precache.test.mjs
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/precache.js frontend/test/precache.test.mjs
git commit -m "feat(offline): bounded-concurrency tile fetcher"
```

### Task 1.3: `PrecacheButton.vue` UI

**Files:**
- Create: `frontend/src/components/PrecacheButton.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <div class="precache">
    <button
      class="btn btn-tiny"
      :disabled="running"
      type="button"
      @click="run"
    >
      {{ buttonLabel }}
    </button>
    <div v-if="running || lastDone" class="precache-bar">
      <div class="bar-fill" :style="{ width: pct + '%' }"></div>
      <span class="bar-text mono">{{ pct }}% · {{ done }} / {{ total }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { tilesForBbox, preloadTiles } from '@/lib/precache.js'

const props = defineProps({
  bbox: {
    type: Object,
    default: () => ({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }),
  },
  theme: { type: String, default: 'light' },
})

const running = ref(false)
const done = ref(0)
const total = ref(0)
const failed = ref(0)
const lastDone = ref(localStorage.getItem('voyage:precache:done') || '')

const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))
const buttonLabel = computed(() => {
  if (running.value) return 'Caching…'
  if (lastDone.value) return 'Re-cache trip area'
  return 'Pre-cache trip area'
})

async function run() {
  running.value = true
  done.value = 0; failed.value = 0
  const tiles = tilesForBbox(props.bbox, [6, 12])
  total.value = tiles.length
  await preloadTiles(tiles, props.theme, {
    onProgress: ({ done: d, failed: f }) => { done.value = d; failed.value = f },
  })
  lastDone.value = new Date().toISOString()
  localStorage.setItem('voyage:precache:done', lastDone.value)
  running.value = false
}
</script>

<style scoped>
.precache { display: grid; gap: 0.3rem; }
.precache-bar {
  position: relative;
  height: 4px;
  background: var(--cream-edge);
  border-radius: 2px;
  overflow: hidden;
}
.bar-fill { height: 100%; background: var(--vermillion); transition: width 120ms linear; }
.bar-text {
  position: absolute;
  inset: 0;
  font-size: 0.65rem;
  display: grid;
  place-items: center;
  color: var(--ink-soft);
}
</style>
```

- [ ] **Step 2: Mount in `MapView.vue` sidebar**

In `frontend/src/views/MapView.vue`, after the `<Itinerary>` block (around line 73), add:

```vue
        <hr class="rule" />
        <p class="eyebrow">Offline cache</p>
        <PrecacheButton :theme="theme" />
```

And add the import at the top of the script block:

```js
import PrecacheButton from '@/components/PrecacheButton.vue'
```

(Use the placeholder `:theme="'light'"` for now if the theme ref does not yet exist — Phase 3 will replace it.)

- [ ] **Step 3: Verify in the browser**

Run the dev server, click "Pre-cache trip area", watch progress bar fill, verify in DevTools → Application → Cache Storage → `carto-tiles` that ~2k tiles landed.

- [ ] **Step 4: Toggle airplane mode (or block network in DevTools), reload the map, pan around the trip bbox**

Confirm tiles render from cache.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PrecacheButton.vue frontend/src/views/MapView.vue
git commit -m "feat(offline): one-click pre-cache for the trip area"
```

### Task 1.4: Cache GPX, points, and the Nominatim search history

**Files:**
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Extend `runtimeCaching` with new patterns**

In the `workbox.runtimeCaching` array (frontend/vite.config.js:30), add **before** the closing `]`:

```js
{
  // Nominatim geocoding — cache successful queries so locating works offline if user already searched once.
  urlPattern: /^https:\/\/nominatim\.openstreetmap\.org\/.*$/,
  handler: 'StaleWhileRevalidate',
  options: {
    cacheName: 'nominatim',
    expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
    cacheableResponse: { statuses: [0, 200] },
  },
},
{
  // Overpass survival queries
  urlPattern: /\/api\/overpass\b/,
  handler: 'StaleWhileRevalidate',
  options: {
    cacheName: 'overpass',
    expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 7 },
    cacheableResponse: { statuses: [200] },
  },
},
```

- [ ] **Step 2: Rebuild + run the dev server, verify caches show up**

```bash
cd frontend && npm run dev
```

Open the app, run a search → DevTools → Cache Storage → `nominatim` should populate.

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.js
git commit -m "feat(offline): cache Nominatim and Overpass responses"
```

---

## Phase 2 — Sun-tracker (Feature #3)

**Why early:** ~1h of work, huge value the first night in BLM.

### Task 2.1: `lib/sun.js` with formatting + tests

**Files:**
- Create: `frontend/src/lib/sun.js`
- Create: `frontend/test/sun.test.mjs`

- [ ] **Step 1: Failing test**

```js
// frontend/test/sun.test.mjs
import assert from 'node:assert/strict'
import { sunInfo, formatCountdown } from '../src/lib/sun.js'

// Vegas, 1 May 2026 18:00 UTC ≈ 11:00 local (PDT)
const info = sunInfo(36.17, -115.14, new Date('2026-05-01T18:00:00Z'))
assert.ok(info.sunset instanceof Date, 'sunset is a Date')
assert.ok(info.civilEnd instanceof Date)
assert.ok(info.civilEnd > info.sunset, 'civil dusk after sunset')

assert.equal(formatCountdown(0), 'now')
assert.equal(formatCountdown(45 * 60_000), '45 min')
assert.equal(formatCountdown(75 * 60_000), '1h 15m')
assert.equal(formatCountdown(-30 * 60_000), '−30 min')

console.log('sun: OK')
```

- [ ] **Step 2: Run, expect failure**

```bash
cd frontend && node test/sun.test.mjs
```

- [ ] **Step 3: Implement `sun.js`**

```js
// frontend/src/lib/sun.js
import SunCalc from 'suncalc'

export function sunInfo(lat, lng, when = new Date()) {
  const t = SunCalc.getTimes(when, lat, lng)
  return {
    sunrise: t.sunrise,
    sunset: t.sunset,
    civilStart: t.dawn,
    civilEnd: t.dusk,
    night: t.night,
    nightEnd: t.nightEnd,
    now: when,
  }
}

export function formatTime(d) {
  if (!(d instanceof Date) || Number.isNaN(d.valueOf())) return '—'
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatCountdown(ms) {
  const sign = ms < 0 ? '−' : ''
  const abs = Math.abs(ms)
  const minutes = Math.round(abs / 60_000)
  if (minutes === 0) return 'now'
  if (minutes < 60) return `${sign}${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${sign}${h}h ${m}m`
}
```

- [ ] **Step 4: Test passes**

```bash
cd frontend && node test/sun.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/sun.js frontend/test/sun.test.mjs
git commit -m "feat(sun): suncalc wrapper with countdown formatting"
```

### Task 2.2: `SunPanel.vue` component

**Files:**
- Create: `frontend/src/components/SunPanel.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <section v-if="info" class="sun-panel">
    <p class="eyebrow">Daylight</p>
    <ul class="sun-rows">
      <li>
        <span class="lbl">Sunset</span>
        <span class="val">{{ formatTime(info.sunset) }}</span>
        <span class="cd mono" :class="{ urgent: cd.sunset < 60*60_000 && cd.sunset > 0 }">
          {{ formatCountdown(cd.sunset) }}
        </span>
      </li>
      <li>
        <span class="lbl">Civil dusk</span>
        <span class="val">{{ formatTime(info.civilEnd) }}</span>
        <span class="cd mono" :class="{ urgent: cd.civilEnd < 60*60_000 && cd.civilEnd > 0 }">
          {{ formatCountdown(cd.civilEnd) }}
        </span>
      </li>
      <li>
        <span class="lbl">Sunrise (next)</span>
        <span class="val">{{ formatTime(info.sunrise) }}</span>
      </li>
    </ul>
    <p v-if="locating" class="hint mono">Using map center — share location for your real position.</p>
    <button v-else-if="!gotPosition" class="locate-link" @click="locateMe">⌖ Use my location</button>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { sunInfo, formatTime, formatCountdown } from '@/lib/sun.js'
import { getMyLocation } from '@/util.js'

const props = defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
})

const lat = ref(props.fallbackLat)
const lng = ref(props.fallbackLng)
const gotPosition = ref(false)
const locating = ref(false)
const tickHandle = ref(null)
const now = ref(new Date())

const info = computed(() => sunInfo(lat.value, lng.value, now.value))
const cd = computed(() => ({
  sunset: info.value.sunset.valueOf() - now.value.valueOf(),
  civilEnd: info.value.civilEnd.valueOf() - now.value.valueOf(),
}))

async function locateMe() {
  locating.value = true
  try {
    const loc = await getMyLocation()
    lat.value = loc.lat; lng.value = loc.lng
    gotPosition.value = true
  } catch { /* keep fallback */ }
  finally { locating.value = false }
}

onMounted(() => {
  tickHandle.value = setInterval(() => { now.value = new Date() }, 30_000)
})
onBeforeUnmount(() => { clearInterval(tickHandle.value) })
</script>

<style scoped>
.sun-panel { display: grid; gap: 0.35rem; }
.sun-rows { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.2rem; }
.sun-rows li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: baseline;
  gap: 0.6rem;
  font-size: 0.85rem;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.val { font-family: var(--display); font-size: 0.95rem; }
.cd { color: var(--ink-soft); }
.cd.urgent { color: var(--vermillion); font-weight: 700; }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0; }
.locate-link {
  background: transparent;
  border: none;
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: var(--vermillion);
  cursor: pointer;
  justify-self: start;
  padding: 0;
}
</style>
```

- [ ] **Step 2: Mount it in `MapView.vue`**

Below the `PrecacheButton` block:

```vue
        <hr class="rule" />
        <SunPanel
          :fallback-lat="mapData.center_lat"
          :fallback-lng="mapData.center_lng"
        />
```

Import at the top of the script:

```js
import SunPanel from '@/components/SunPanel.vue'
```

- [ ] **Step 3: Manual verify**

Open the map, see sunrise/sunset times and countdown for the map center. Click "Use my location" — values shift to your real coords. Wait one tick (30s) and confirm the countdown updates.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SunPanel.vue frontend/src/views/MapView.vue
git commit -m "feat(sun): live sunset/civil-dusk countdown in sidebar"
```

---

## Phase 3 — Dark mode (Feature #6)

**Why now:** Tile selection in `precache.js` already accepts a `theme` param. Wiring the toggle now means future precaches get the right URLs first time.

### Task 3.1: Add CSS variable overrides

**Files:**
- Modify: `frontend/src/styles/vintage.css`

- [ ] **Step 1: Inspect the existing `:root` block**

```bash
grep -n "^:root\|^--\|^body\b" /Users/tlavisse/Documents/code/voyage-map/frontend/src/styles/vintage.css | head -40
```

- [ ] **Step 2: Append a `[data-theme="dark"]` block at the end of the file**

```css
[data-theme="dark"] {
  --paper: #14171a;
  --cream: #1c2024;
  --cream-deep: #0f1114;
  --cream-edge: #2a2f35;
  --ink: #ebe5d8;
  --ink-soft: #b8b2a4;
  --ink-faded: #6e6a62;
  --vermillion: #ff7a55;
  --vermillion-deep: #e85d3c;
}

[data-theme="dark"] body { background: var(--paper); color: var(--ink); }
[data-theme="dark"] .map { background: var(--cream-deep); }

[data-theme="dark"] .pin { filter: drop-shadow(0 0 1px rgba(255,255,255,0.4)); }
[data-theme="dark"] .leaflet-container { background: #0c0e10; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles/vintage.css
git commit -m "feat(theme): dark-mode CSS-variable overrides"
```

### Task 3.2: Theme store

**Files:**
- Create: `frontend/src/lib/theme.js`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Create `theme.js`**

```js
// frontend/src/lib/theme.js
import { ref, watch } from 'vue'

const KEY = 'voyage:theme'
const initial = localStorage.getItem(KEY)
  || (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

export const theme = ref(initial)

function apply(t) {
  document.documentElement.dataset.theme = t
}

apply(theme.value)
watch(theme, (t) => {
  localStorage.setItem(KEY, t)
  apply(t)
})

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}
```

- [ ] **Step 2: Import early in `main.js`**

Edit `frontend/src/main.js`, add import after `App` import:

```js
import './lib/theme.js'  // applies html[data-theme] before first paint
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/theme.js frontend/src/main.js
git commit -m "feat(theme): persistent theme store with system default"
```

### Task 3.3: Toggle UI + tile-layer swap

**Files:**
- Create: `frontend/src/components/ThemeToggle.vue`
- Modify: `frontend/src/views/MapView.vue`

- [ ] **Step 1: Create the toggle**

```vue
<template>
  <button
    class="theme-toggle"
    type="button"
    :title="theme === 'dark' ? 'Switch to light' : 'Switch to dark'"
    @click="toggleTheme"
  >
    {{ theme === 'dark' ? '☀' : '☾' }}
  </button>
</template>

<script setup>
import { theme, toggleTheme } from '@/lib/theme.js'
</script>

<style scoped>
.theme-toggle {
  background: transparent;
  border: 1px solid var(--ink-faded);
  border-radius: 2px;
  width: 2rem; height: 2rem;
  display: grid; place-items: center;
  color: var(--ink-soft);
  cursor: pointer;
  font-size: 1rem;
}
.theme-toggle:hover { color: var(--vermillion); border-color: var(--vermillion); }
</style>
```

- [ ] **Step 2: Wire it in `MapView.vue`'s `.side-head`**

Find the existing `<div class="side-head">` (around line 4) and add the toggle next to the collapse button:

```vue
      <div class="side-head">
        <router-link to="/" class="back">← Home</router-link>
        <div class="head-actions">
          <ThemeToggle />
          <button class="btn-icon" @click="sidebarOpen = !sidebarOpen" :aria-label="…">
            {{ sidebarOpen ? '⟨' : '⟩' }}
          </button>
        </div>
      </div>
```

Add the import:

```js
import ThemeToggle from '@/components/ThemeToggle.vue'
import { theme } from '@/lib/theme.js'
```

Add an inline scoped style for `.head-actions { display: inline-flex; gap: 0.4rem; align-items: center; }` in the `<style scoped>` block.

- [ ] **Step 3: Swap the tile URL based on theme**

Replace the existing `L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/...')` call (MapView.vue:247-251) with a reactive layer:

```js
let tileLayer = null
function tileUrl() {
  const style = theme.value === 'dark' ? 'dark_all' : 'light_all'
  return `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}.png`
}
function attachTiles() {
  if (tileLayer) leaflet.removeLayer(tileLayer)
  tileLayer = L.tileLayer(tileUrl(), {
    attribution: '© OpenStreetMap © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(leaflet)
}
```

Then in `initLeaflet`, replace the `L.tileLayer(...).addTo(leaflet)` line with `attachTiles()`. After `initLeaflet` is wired, add a watcher (top-level in `<script setup>`):

```js
watch(theme, () => { if (leaflet) attachTiles() })
```

- [ ] **Step 4: Update the `PrecacheButton` mount to pass the live theme**

```vue
<PrecacheButton :theme="theme" />
```

with `import { theme } from '@/lib/theme.js'` already in scope.

- [ ] **Step 5: Manual verify**

Click the toggle. Map flips to dark tiles. Sidebar background flips. Refresh — theme persists. Open dev tools → Application → Local Storage → `voyage:theme` is set.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ThemeToggle.vue frontend/src/views/MapView.vue
git commit -m "feat(theme): toggle dark mode + dark Carto tiles"
```

---

## Phase 4 — Elevation profile (Feature #2)

**Why mid-priority:** Useful for trail running but does not block the trip starting. Heavier UI work.

**Approach:** Many GPX files include `<ele>` tags inside `<trkpt>`. Extract them, downsample to ~200 points, draw a small inline SVG below the map (collapsible, only shows when a track is selected). Hovering the chart syncs a marker on the polyline.

### Task 4.1: Extend `parseGPX` to return elevations

**Files:**
- Modify: `frontend/src/util.js`
- Create: `frontend/test/elevation.test.mjs`

- [ ] **Step 1: Failing test**

```js
// frontend/test/elevation.test.mjs
import assert from 'node:assert/strict'
import { parseGPX } from '../src/util.js'
import { buildElevationSeries } from '../src/lib/elevation.js'

const sample = `<?xml version="1.0"?>
<gpx><trk><name>X</name><trkseg>
  <trkpt lat="36.17" lon="-115.14"><ele>610</ele></trkpt>
  <trkpt lat="36.18" lon="-115.13"><ele>650</ele></trkpt>
  <trkpt lat="36.19" lon="-115.12"><ele>700</ele></trkpt>
</trkseg></trk></gpx>`

// Ensure DOMParser is available (use jsdom-free approach)
import { JSDOM } from 'jsdom'  // already a transitive dep? if not, fall back below
const dom = new JSDOM('')
globalThis.DOMParser = dom.window.DOMParser

const parsed = parseGPX(sample)
assert.equal(parsed.coords.length, 3)
assert.deepEqual(parsed.elevations, [610, 650, 700])

const series = buildElevationSeries(parsed.coords, parsed.elevations)
assert.equal(series.length, 3)
assert.ok(series[0].dist === 0)
assert.ok(series[2].dist > series[1].dist)
assert.equal(series[2].ele, 700)

console.log('elevation: OK')
```

If `jsdom` is not already available, the test instead skips with a clear message. Run:

```bash
cd frontend && npm ls jsdom 2>&1 || npm install --save-dev jsdom
```

- [ ] **Step 2: Run, expect failure**

```bash
cd frontend && node test/elevation.test.mjs
```

- [ ] **Step 3: Update `parseGPX` in `frontend/src/util.js`**

Replace lines 16–37 (the existing `parseGPX`) with:

```js
export function parseGPX(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, 'application/xml')
  if (doc.querySelector('parsererror')) throw new Error('Could not parse GPX file.')

  const collect = (sel) => {
    const out = { coords: [], elevations: [] }
    for (const pt of doc.querySelectorAll(sel)) {
      const lat = parseFloat(pt.getAttribute('lat'))
      const lng = parseFloat(pt.getAttribute('lon'))
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue
      out.coords.push([lat, lng])
      const ele = parseFloat(pt.querySelector('ele')?.textContent ?? '')
      out.elevations.push(Number.isFinite(ele) ? ele : null)
    }
    return out
  }

  let parsed = collect('trkpt')
  if (!parsed.coords.length) parsed = collect('rtept')
  if (!parsed.coords.length) parsed = collect('wpt')
  if (!parsed.coords.length) throw new Error('No track or route points found in GPX.')

  const name =
    doc.querySelector('trk > name')?.textContent?.trim() ||
    doc.querySelector('rte > name')?.textContent?.trim() ||
    doc.querySelector('metadata > name')?.textContent?.trim() ||
    null

  return { coords: parsed.coords, elevations: parsed.elevations, name }
}
```

- [ ] **Step 4: Implement `lib/elevation.js`**

```js
// frontend/src/lib/elevation.js
const R = 6371000 // earth radius m

function haversine([lat1, lng1], [lat2, lng2]) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

export function buildElevationSeries(coords, elevations, targetPoints = 200) {
  if (!coords.length) return []
  const series = []
  let dist = 0
  for (let i = 0; i < coords.length; i++) {
    if (i > 0) dist += haversine(coords[i - 1], coords[i])
    series.push({
      dist,
      ele: elevations?.[i] ?? null,
      coord: coords[i],
    })
  }
  if (series.length <= targetPoints) return series
  const step = series.length / targetPoints
  const out = []
  for (let i = 0; i < targetPoints; i++) out.push(series[Math.floor(i * step)])
  out.push(series[series.length - 1])
  return out
}

export function elevationStats(series) {
  let gain = 0, loss = 0, min = Infinity, max = -Infinity
  for (let i = 0; i < series.length; i++) {
    const e = series[i].ele
    if (e == null) continue
    if (e < min) min = e
    if (e > max) max = e
    if (i > 0 && series[i - 1].ele != null) {
      const d = e - series[i - 1].ele
      if (d > 0) gain += d
      else loss += -d
    }
  }
  return {
    gain: Math.round(gain),
    loss: Math.round(loss),
    min: Number.isFinite(min) ? Math.round(min) : null,
    max: Number.isFinite(max) ? Math.round(max) : null,
    distanceKm: series.at(-1) ? series.at(-1).dist / 1000 : 0,
  }
}
```

- [ ] **Step 5: Test passes**

```bash
cd frontend && node test/elevation.test.mjs
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/util.js frontend/src/lib/elevation.js frontend/test/elevation.test.mjs frontend/package.json frontend/package-lock.json
git commit -m "feat(elevation): extract elevations from GPX, build series + stats"
```

### Task 4.2: `ElevationProfile.vue` SVG chart

**Files:**
- Create: `frontend/src/components/ElevationProfile.vue`

- [ ] **Step 1: Create the component**

```vue
<template>
  <section v-if="series.length" class="elev">
    <div class="elev-head">
      <p class="eyebrow">{{ name || 'Elevation' }}</p>
      <p class="elev-stats mono">
        ↑ {{ stats.gain }} m · ↓ {{ stats.loss }} m · {{ stats.distanceKm.toFixed(1) }} km
      </p>
      <button class="btn-icon-tiny" @click="$emit('close')" aria-label="Close">×</button>
    </div>
    <svg
      class="elev-svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      @mousemove="onMove"
      @mouseleave="onLeave"
    >
      <path :d="areaPath" class="area" />
      <path :d="linePath" class="line" />
      <line v-if="hover" :x1="hover.x" :x2="hover.x" :y1="0" :y2="H" class="cursor" />
      <circle v-if="hover" :cx="hover.x" :cy="hover.y" r="3" class="dot" />
    </svg>
    <p v-if="hover" class="elev-readout mono">
      {{ (hover.point.dist / 1000).toFixed(2) }} km · {{ Math.round(hover.point.ele) }} m
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { elevationStats } from '@/lib/elevation.js'

const props = defineProps({
  series: { type: Array, required: true },
  name: { type: String, default: '' },
})
const emit = defineEmits(['hover', 'close'])

const W = 800, H = 140, PAD = 6
const stats = computed(() => elevationStats(props.series))

const yMin = computed(() => stats.value.min ?? 0)
const yMax = computed(() => Math.max(stats.value.max ?? 0, yMin.value + 50))
const xMax = computed(() => props.series.at(-1)?.dist ?? 1)

function xFor(d) { return PAD + (d / xMax.value) * (W - 2 * PAD) }
function yFor(e) { return H - PAD - ((e - yMin.value) / (yMax.value - yMin.value)) * (H - 2 * PAD) }

const linePath = computed(() => {
  let d = ''
  for (let i = 0; i < props.series.length; i++) {
    const p = props.series[i]
    if (p.ele == null) continue
    d += (d ? 'L' : 'M') + xFor(p.dist) + ',' + yFor(p.ele)
  }
  return d
})

const areaPath = computed(() => {
  if (!linePath.value) return ''
  return linePath.value + ` L ${xFor(xMax.value)},${H - PAD} L ${xFor(0)},${H - PAD} Z`
})

const hover = ref(null)
function onMove(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const px = ((e.clientX - rect.left) / rect.width) * W
  const target = ((px - PAD) / (W - 2 * PAD)) * xMax.value
  let best = props.series[0], bestDelta = Infinity
  for (const p of props.series) {
    const d = Math.abs(p.dist - target)
    if (d < bestDelta) { bestDelta = d; best = p }
  }
  if (best?.ele == null) return
  hover.value = { x: xFor(best.dist), y: yFor(best.ele), point: best }
  emit('hover', best.coord)
}
function onLeave() {
  hover.value = null
  emit('hover', null)
}
</script>

<style scoped>
.elev {
  position: absolute;
  left: 1rem; right: 1rem; bottom: 1rem;
  z-index: 700;
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  box-shadow: 0 6px 20px rgba(0,0,0,0.18);
  display: grid;
  gap: 0.3rem;
}
.elev-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: baseline;
  gap: 0.6rem;
}
.elev-stats { color: var(--ink-soft); font-size: 0.78rem; }
.btn-icon-tiny {
  background: transparent; border: none; cursor: pointer;
  font-size: 1.1rem; line-height: 1; color: var(--ink-faded);
}
.btn-icon-tiny:hover { color: var(--vermillion); }
.elev-svg { width: 100%; height: 110px; display: block; }
.area { fill: rgba(232, 93, 60, 0.15); }
.line { fill: none; stroke: var(--vermillion); stroke-width: 1.6; }
.cursor { stroke: var(--ink-faded); stroke-width: 1; stroke-dasharray: 3 3; }
.dot { fill: var(--vermillion); stroke: var(--paper); stroke-width: 1.5; }
.elev-readout { font-size: 0.8rem; color: var(--ink-soft); margin: 0; }
</style>
```

- [ ] **Step 2: Wire it into `MapView.vue`**

Add to the script:

```js
import ElevationProfile from '@/components/ElevationProfile.vue'
import { buildElevationSeries } from '@/lib/elevation.js'

const activeTrackId = ref(null)
const activeSeries = computed(() => {
  if (!activeTrackId.value || !mapData.value) return []
  const t = mapData.value.tracks.find((x) => x.id === activeTrackId.value)
  if (!t) return []
  const { coords, elevations } = parseGPX(t.gpx_data)
  return buildElevationSeries(coords, elevations)
})
const activeTrackName = computed(() => {
  const t = mapData.value?.tracks?.find((x) => x.id === activeTrackId.value)
  return t?.name || ''
})

let hoverMarker = null
function onElevHover(coord) {
  if (!leaflet) return
  if (!coord) {
    if (hoverMarker) { leaflet.removeLayer(hoverMarker); hoverMarker = null }
    return
  }
  if (!hoverMarker) {
    hoverMarker = L.circleMarker(coord, {
      radius: 6, color: '#e85d3c', weight: 2, fillColor: '#fff', fillOpacity: 1,
    }).addTo(leaflet)
  } else {
    hoverMarker.setLatLng(coord)
  }
}
```

In the template, **inside `<div class="map-wrap">`** below the locate button:

```vue
        <ElevationProfile
          v-if="activeSeries.length"
          :series="activeSeries"
          :name="activeTrackName"
          @hover="onElevHover"
          @close="activeTrackId = null"
        />
```

In the existing track list, make each `track-row` clickable:

```vue
          <li v-for="(t, i) in mapData.tracks" :key="t.id"
              class="track-row"
              :class="{ active: activeTrackId === t.id }"
              @click="activeTrackId = activeTrackId === t.id ? null : t.id">
```

(Make sure the `<button class="track-del">` still calls `@click.stop="deleteTrack(t.id)"` so clicking delete doesn't toggle the row.)

- [ ] **Step 3: Manual verify**

Drag a `.gpx` file with elevation data onto the map. Click the track in the sidebar. The elevation profile slides up from the bottom; hovering the chart moves a dot along the polyline.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ElevationProfile.vue frontend/src/views/MapView.vue
git commit -m "feat(elevation): inline SVG profile with hover-sync to map"
```

---

## Phase 5 — Overpass survival POIs (Feature #4)

**Why later:** Requires network at first call. With Phase 1 caching in place, repeat calls work offline.

**Approach:** A tiny FastAPI proxy passes Overpass QL to the public Overpass instance (avoids CORS quirks + lets us cache responses with our SW). Frontend has a "Survival" toggle that fetches points within the current map bounds for three amenities.

### Task 5.1: Backend proxy

**Files:**
- Create: `api/overpass.py`
- Modify: `server.py`

- [ ] **Step 1: Create the proxy**

```python
# api/overpass.py
"""Thin Overpass QL proxy. Backend so we sidestep CORS and can cache via SW."""

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/overpass", tags=["overpass"])

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

@router.get("")
async def overpass_query(
    south: float = Query(...),
    west: float = Query(...),
    north: float = Query(...),
    east: float = Query(...),
    kind: str = Query("survival"),
):
    if kind != "survival":
        raise HTTPException(400, "unknown kind")
    bbox = f"{south},{west},{north},{east}"
    ql = f"""
    [out:json][timeout:25];
    (
      node["amenity"="drinking_water"]({bbox});
      node["amenity"="waste_disposal"]({bbox});
      node["sanitary_dump_station"="yes"]({bbox});
      node["amenity"="toilets"]({bbox});
    );
    out body;
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(OVERPASS_URL, data={"data": ql})
    if r.status_code >= 500:
        raise HTTPException(502, "Overpass upstream error")
    return r.json()
```

- [ ] **Step 2: Register the router in `server.py`**

After the existing `from api.itinerary import router as itinerary_router`:

```python
from api.overpass import router as overpass_router
```

After `app.include_router(itinerary_router, prefix="/api")`:

```python
app.include_router(overpass_router, prefix="/api")
```

- [ ] **Step 3: Add httpx dep**

```bash
echo "httpx>=0.27" >> requirements.txt
```

Update `pyproject.toml`'s `dependencies` list to include `"httpx>=0.27"`.

```bash
pip install httpx
```

- [ ] **Step 4: Smoke test**

```bash
curl 'http://localhost:8000/api/overpass?south=36.0&west=-115.5&north=36.5&east=-115.0&kind=survival'
```

Expect a JSON body with `elements` array.

- [ ] **Step 5: Commit**

```bash
git add api/overpass.py server.py requirements.txt pyproject.toml
git commit -m "feat(overpass): backend proxy for survival POI queries"
```

### Task 5.2: Frontend `lib/overpass.js` + builder test

**Files:**
- Create: `frontend/src/lib/overpass.js`
- Create: `frontend/test/overpass.test.mjs`

- [ ] **Step 1: Failing test**

```js
// frontend/test/overpass.test.mjs
import assert from 'node:assert/strict'
import { mapElement, classifyKind } from '../src/lib/overpass.js'

const e = {
  type: 'node', id: 1, lat: 36.1, lon: -115.0,
  tags: { amenity: 'drinking_water', name: 'Public fountain' },
}
const m = mapElement(e)
assert.equal(m.kind, 'water')
assert.equal(m.lat, 36.1)
assert.equal(m.label, 'Public fountain')

assert.equal(classifyKind({ amenity: 'waste_disposal' }), 'trash')
assert.equal(classifyKind({ sanitary_dump_station: 'yes' }), 'dump')
assert.equal(classifyKind({ amenity: 'toilets' }), 'toilet')
assert.equal(classifyKind({ amenity: 'unknown' }), null)

console.log('overpass: OK')
```

- [ ] **Step 2: Implement**

```js
// frontend/src/lib/overpass.js

export function classifyKind(tags = {}) {
  if (tags.amenity === 'drinking_water') return 'water'
  if (tags.amenity === 'waste_disposal') return 'trash'
  if (tags.sanitary_dump_station === 'yes') return 'dump'
  if (tags.amenity === 'toilets') return 'toilet'
  return null
}

const ICONS = {
  water: '💧',
  trash: '🗑',
  dump: '🚐',
  toilet: '🚻',
}

export function mapElement(e) {
  const kind = classifyKind(e.tags)
  if (!kind || e.lat == null) return null
  return {
    id: `${e.type}/${e.id}`,
    lat: e.lat,
    lng: e.lon,
    kind,
    icon: ICONS[kind],
    label: e.tags?.name || `${kind}`,
  }
}

export async function fetchSurvival(bounds) {
  const { _southWest: sw, _northEast: ne } = bounds
  const params = new URLSearchParams({
    south: sw.lat, west: sw.lng, north: ne.lat, east: ne.lng, kind: 'survival',
  })
  const res = await fetch(`/api/overpass?${params}`)
  if (!res.ok) throw new Error('Overpass query failed.')
  const data = await res.json()
  return (data.elements || []).map(mapElement).filter(Boolean)
}
```

- [ ] **Step 3: Run test**

```bash
cd frontend && node test/overpass.test.mjs
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/overpass.js frontend/test/overpass.test.mjs
git commit -m "feat(overpass): frontend client + element classification"
```

### Task 5.3: `SurvivalLayer.vue` + map wiring

**Files:**
- Create: `frontend/src/components/SurvivalLayer.vue`
- Modify: `frontend/src/views/MapView.vue`

- [ ] **Step 1: Create the layer component (no template — it manages markers via emits)**

```vue
<template>
  <div class="survival">
    <button
      class="btn btn-tiny"
      :class="{ on: enabled }"
      type="button"
      :disabled="loading"
      @click="toggle"
    >
      {{ loading ? 'Searching…' : enabled ? '✓ Survival' : 'Survival' }}
    </button>
    <p v-if="error" class="error sm">{{ error }}</p>
    <p v-else-if="enabled && !loading" class="hint mono">
      {{ count }} spot{{ count === 1 ? '' : 's' }} in view
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { fetchSurvival } from '@/lib/overpass.js'

const emit = defineEmits(['render', 'clear'])
const props = defineProps({ getBounds: { type: Function, required: true } })

const enabled = ref(false)
const loading = ref(false)
const error = ref('')
const count = ref(0)

async function toggle() {
  if (enabled.value) {
    enabled.value = false
    emit('clear')
    return
  }
  enabled.value = true
  loading.value = true
  error.value = ''
  try {
    const items = await fetchSurvival(props.getBounds())
    count.value = items.length
    emit('render', items)
  } catch (e) {
    error.value = e.message
    enabled.value = false
  } finally { loading.value = false }
}
</script>

<style scoped>
.survival { display: grid; gap: 0.3rem; }
.btn.on { background: var(--vermillion); color: var(--paper); }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0; }
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
```

- [ ] **Step 2: Wire it in `MapView.vue`**

Add to the script:

```js
import SurvivalLayer from '@/components/SurvivalLayer.vue'

const survivalGroup = ref(null) // L.layerGroup
function getMapBounds() { return leaflet?.getBounds() }
function renderSurvival(items) {
  if (!leaflet) return
  if (survivalGroup.value) leaflet.removeLayer(survivalGroup.value)
  survivalGroup.value = L.layerGroup()
  for (const it of items) {
    const m = L.marker([it.lat, it.lng], {
      icon: L.divIcon({
        className: 'survival-pin',
        html: `<div class="sp"><span>${it.icon}</span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      }),
    })
    m.bindTooltip(it.label, { direction: 'top', offset: [0, -10] })
    survivalGroup.value.addLayer(m)
  }
  survivalGroup.value.addTo(leaflet)
}
function clearSurvival() {
  if (survivalGroup.value && leaflet) leaflet.removeLayer(survivalGroup.value)
  survivalGroup.value = null
}
```

In the template, near the existing "Add a place" section:

```vue
        <hr class="rule" />
        <p class="eyebrow">Survival</p>
        <SurvivalLayer
          :get-bounds="getMapBounds"
          @render="renderSurvival"
          @clear="clearSurvival"
        />
```

Add the survival pin styles (in the unscoped global stylesheet `vintage.css`):

```css
.survival-pin .sp {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 50%;
  font-size: 0.95rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.18);
}
```

- [ ] **Step 3: Manual verify**

Click "Survival" with the map zoomed to a city. Wait ~5s. See water/trash/dump icons appear. Click again to clear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SurvivalLayer.vue frontend/src/views/MapView.vue frontend/src/styles/vintage.css
git commit -m "feat(overpass): one-click survival POIs (water, trash, dump, toilets)"
```

---

## Phase 6 — Itinerary polish

The feature is complete. Two small touch-ups identified:

### Task 6.1: Show countdown in days for `T-N` in the banner with hour resolution if < 1 day

**Files:**
- Modify: `frontend/src/views/MapView.vue:466`

- [ ] **Step 1: Replace the inline `Math.round(...)` with a tighter calc**

Find the existing block (around line 463–474):

```js
  const future = sorted.find((d) => d.date > t)
  if (future) {
    const days = Math.round((new Date(future.date) - new Date(t)) / 86400000)
    return {
      tag: `T-${days}`,
      ...
    }
  }
```

Replace with:

```js
  const future = sorted.find((d) => d.date > t)
  if (future) {
    const ms = new Date(future.date) - new Date(t)
    const days = Math.floor(ms / 86400000)
    const tag = days >= 1 ? `T-${days}d` : `T-<1d`
    return {
      tag,
      text: `Next: ${(future.label || 'Untitled').toUpperCase()}`,
      notes: future.notes || null,
      day: future,
    }
  }
```

- [ ] **Step 2: Manual verify the banner reads `T-9d` today (2026-04-30) for the 9 May start.**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "polish(itinerary): banner countdown with explicit day suffix"
```

### Task 6.2: Auto-center the map on today's day on load (when there is one)

**Files:**
- Modify: `frontend/src/views/MapView.vue`

- [ ] **Step 1: Extend `onMounted` after `initLeaflet()` runs**

```js
onMounted(async () => {
  // ... existing code ...
  initLeaflet()

  const today = todayISO()
  const day = (mapData.value.itinerary || []).find((d) => d.date === today)
  if (day && day.lat != null && day.lng != null && leaflet) {
    leaflet.setView([day.lat, day.lng], 11)
  }
})
```

- [ ] **Step 2: Manual verify**

Add a day with today's date and a known location, reload — map opens centered on that location.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "polish(itinerary): center on today's stop on map load"
```

---

## Final verification

- [ ] **Build the production bundle**

```bash
cd frontend && npm run build
```

Expect no errors. Bundle size should stay under ~600 KB gzipped.

- [ ] **Smoke-test the production build behind FastAPI**

```bash
source .venv/bin/activate && uvicorn server:app --port 8080
```

Open `http://localhost:8080`. Verify:
1. Map loads
2. Theme toggle flips light/dark including the tile layer
3. Pre-cache button runs to completion (~2k tiles)
4. After pre-cache: turn off network in DevTools → reload → map still renders
5. Sun panel updates every 30s
6. GPX upload shows elevation profile, hover syncs map dot
7. Survival button populates POIs
8. Today banner shows for the trip date

- [ ] **Tag the trip-ready release**

```bash
git tag -a trip-ready -m "Voyage Map ready for May 9 departure"
```

---

## Self-review checklist

**Spec coverage:**
- ✅ #1 Offline → Phase 1 (PrecacheButton + extended runtime caching)
- ✅ #2 Elevation → Phase 4
- ✅ #3 Sun-tracker → Phase 2
- ✅ #4 Overpass → Phase 5
- ✅ #5 Itinerary → already shipped + Phase 6 polish
- ✅ #6 Dark mode → Phase 3

**Type/name consistency:**
- `theme` ref exported from `@/lib/theme.js`, consumed in `MapView.vue`, `PrecacheButton.vue`. ✓
- `parseGPX` returns `{ coords, elevations, name }` everywhere after Task 4.1. Old callers (`renderTrack`, `importGpxFile`) destructure only `coords` + `name` — still valid. ✓
- `tilesForBbox` and `preloadTiles` signatures match test usage. ✓

**No placeholders:** every step shows complete code or exact commands.
