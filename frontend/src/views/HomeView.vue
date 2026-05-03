<template>
  <main class="home">
    <header class="topbar">
      <span class="brand">
        <span class="brand-mark">●</span>
        <span class="brand-name">Voyage Map</span>
      </span>
      <!-- Issue stamp — pure flavour text, deliberately styled flatter than
           the brand mark so it doesn't read as a navigation link. -->
      <span class="brand-meta mono" aria-hidden="true">ISSUE №001 · FIELD GUIDE</span>
    </header>

    <section class="hero">
      <div class="hero-text">
        <p class="eyebrow">Plot your course</p>
        <h1>
          Pin a place.<br />
          <span class="hl">Share a map.</span>
        </h1>
        <p class="lede">
          A bare-bones travel journal: anyone with the URL can drop pins,
          jot notes, and shape the map together. No accounts, no setup.
        </p>
      </div>

      <div class="hero-mark">
        <CompassRose :size="180" />
      </div>
    </section>

    <section v-if="recents.length" class="recents">
      <p class="eyebrow lbl">Resume a voyage</p>
      <ul class="recents-list">
        <li v-for="r in recents" :key="r.slug" class="recent-card">
          <router-link
            :to="{ name: 'map', params: { slug: displaySlug(r) } }"
            class="recent-link"
            :title="`Open /m/${displaySlug(r)}`"
          >
            <span class="recent-title">{{ r.title || 'Untitled voyage' }}</span>
            <span v-if="r.stats" class="recent-stats mono">
              <template v-if="r.stats.days">{{ r.stats.days }} day{{ r.stats.days === 1 ? '' : 's' }} · </template>
              <template v-if="r.stats.trails">{{ r.stats.trails }} trail{{ r.stats.trails === 1 ? '' : 's' }} · </template>
              {{ r.stats.points }} pin{{ r.stats.points === 1 ? '' : 's' }}
            </span>
            <span class="recent-meta mono">{{ relTime(r.visitedAt) }}</span>
          </router-link>
          <button
            class="recent-action"
            type="button"
            :title="`Copy share link for ${r.title || 'voyage'}`"
            @click="copyLink(r.slug)"
          >
            {{ copiedSlug === r.slug ? '✓' : '⧉' }}
          </button>
          <button
            class="recent-forget"
            type="button"
            :title="`Remove ${r.title || 'voyage'} from this list`"
            @click="forget(r.slug)"
          >×</button>
        </li>
      </ul>
    </section>

    <section class="form">
      <!-- 01 · Name. The trip name is free-text and primary — the user said
           things like "Vegas → SF, May 2026"; deriving it from the origin was
           the original bug. -->
      <label class="eyebrow lbl" for="trip-title-field">01 · Name your trip</label>
      <input
        id="trip-title-field"
        v-model="title"
        class="field title-field"
        placeholder="e.g. Vegas → SF road trip"
        maxlength="120"
      />

      <!-- 02 · Origin. Picking does NOT overwrite the title anymore. Instead
           the picked label sticks around in a chip next to the search field
           so the user can see what they selected (the geocoder clears its own
           input after pick). -->
      <label class="eyebrow lbl">02 · Where does the trip start?</label>
      <GeocoderSearch
        placeholder="Las Vegas · Mt. Fuji · 11° N 80° W…"
        :bias="homeBias"
        @pick="onPick"
      />
      <div class="origin-row">
        <button class="locate-link" type="button" @click="useMyLocation" :disabled="locating">
          ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
        </button>
        <span v-if="picked" class="origin-chip" :title="picked.label">
          <span class="origin-chip-lbl mono">Starting from</span>
          <span class="origin-chip-val">{{ pickedShort }}</span>
          <button
            class="origin-chip-clear"
            type="button"
            title="Clear origin"
            @click="clearPicked"
          >×</button>
        </span>
      </div>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <Transition name="reveal">
        <div v-if="picked" ref="readyEl" class="ready-wrap">
          <!-- Action bar lives directly under the picker so "Begin journey"
               is visible without scrolling on a 14" laptop. -->
          <div class="action-row">
            <label class="day1-toggle">
              <input type="checkbox" v-model="addDay1Stop" />
              <span>Add <strong>{{ pickedShort }}</strong> as a Day-1 stop ({{ todayLabel }})</span>
            </label>
            <button class="btn primary" :disabled="creating" @click="create">
              {{ creating ? 'Plotting…' : 'Begin journey →' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>

          <p class="eyebrow lbl">Preview</p>
          <div ref="mapEl" class="preview-map"></div>
        </div>
      </Transition>
    </section>

    <footer class="foot mono">
      EST. {{ year }} · CARTOGRAPHY BY YOU
    </footer>
  </main>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import L from 'leaflet'
import { api } from '@/api.js'
import { getMyLocation } from '@/util.js'
import { recentMaps, rememberMap, forgetMap } from '@/lib/recents.js'
import { buildMapSlug } from '@/lib/slug.js'
import CompassRose from '@/components/atoms/CompassRose.vue'
import GeocoderSearch from '@/components/molecules/GeocoderSearch.vue'

const route = useRoute()
const router = useRouter()

// Personal-app convenience: when there's exactly one recent voyage, jump
// straight into it on '/'. Multi-voyage users still get the picker. The
// dock-back link "← Voyages" navigates here with ?home=1 so it overrides.
onMounted(() => {
  if (route.query.home != null) return
  const rs = recentMaps()
  if (rs.length === 1) {
    router.replace({ name: 'map', params: { slug: buildMapSlug(rs[0]) } })
  }
})
const year = new Date().getFullYear()

const picked = ref(null)
const title = ref('')
const creating = ref(false)
const error = ref('')
const locating = ref(false)
const locateError = ref('')
const recents = ref(recentMaps())
// Default-on: most trips start on the day they're created. The user can
// uncheck this if they're plotting a region map without a fixed Day 1.
const addDay1Stop = ref(true)

// First comma-segment is the human-friendly short name ("Las Vegas, Clark…"
// → "Las Vegas"). Used both in the chip and as the auto Day-1 stop title.
const pickedShort = computed(() => {
  if (!picked.value?.label) return ''
  return picked.value.label.split(',')[0].trim().slice(0, 120)
})

// Today, formatted as YYYY-MM-DD in local time (matches what the itinerary
// schema expects — a `date`, not a `datetime`).
function todayIso() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const todayLabel = computed(() =>
  new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
)

// Bias the home search by the most recent voyage's centre — anchors the user
// in their familiar territory between sessions.
const homeBias = computed(() => {
  const r = recents.value[0]
  if (!r?.lastCenter) return null
  return { lat: r.lastCenter.lat, lng: r.lastCenter.lng, radiusKm: 1000 }
})

function relTime(iso) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const min = Math.floor(ms / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} hr ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d} day${d === 1 ? '' : 's'} ago`
  const w = Math.floor(d / 7)
  if (w < 5) return `${w} wk ago`
  return new Date(iso).toLocaleDateString()
}

function forget(slug) {
  forgetMap(slug)
  recents.value = recentMaps()
}

const copiedSlug = ref(null)
function displaySlug(r) {
  return buildMapSlug(r)
}
async function copyLink(slug) {
  try {
    const r = recents.value.find((x) => x.slug === slug)
    const display = r ? buildMapSlug(r) : slug
    await navigator.clipboard.writeText(`${window.location.origin}/m/${display}`)
    copiedSlug.value = slug
    setTimeout(() => { if (copiedSlug.value === slug) copiedSlug.value = null }, 1400)
  } catch { /* no clipboard permission */ }
}

const mapEl = ref(null)
const readyEl = ref(null)
let map = null
let centerMarker = null

async function useMyLocation() {
  locating.value = true
  locateError.value = ''
  try {
    const loc = await getMyLocation()
    await onPick({ lat: loc.lat, lng: loc.lng, label: 'My current location' })
  } catch (e) {
    locateError.value = e.message
  } finally {
    locating.value = false
  }
}

async function onPick(r) {
  picked.value = r
  // Note: we deliberately no longer seed the title from the picked location —
  // origin and trip name are independent fields now.
  await nextTick()
  ensureMap()
  map.setView([r.lat, r.lng], 9)
  centerMarker.setLatLng([r.lat, r.lng])
  // Scroll the action bar (with "Begin journey") into view so the user sees
  // the next step without hunting below the map preview.
  if (readyEl.value?.scrollIntoView) {
    readyEl.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function clearPicked() {
  picked.value = null
  if (map) {
    // Tear down so the preview block remounts cleanly next time.
    map.remove()
    map = null
    centerMarker = null
  }
}

function ensureMap() {
  if (map) return
  map = L.map(mapEl.value, {
    zoomControl: false,
    attributionControl: true,
    scrollWheelZoom: false,
    dragging: true,
  })
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(map)
  centerMarker = L.marker([0, 0], { icon: makePinIcon('⚑', 'center-pin'), draggable: true }).addTo(map)
  centerMarker.on('drag', (e) => {
    const ll = e.target.getLatLng()
    picked.value = { ...picked.value, lat: ll.lat, lng: ll.lng }
  })
}

function makePinIcon(glyph, extra = '') {
  return L.divIcon({
    className: `pin-wrapper ${extra}`,
    html: `<div class="pin"><span>${glyph}</span></div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  })
}

async function create() {
  if (!picked.value) return
  creating.value = true
  error.value = ''
  try {
    const m = await api.createMap({
      title: title.value.trim() || null,
      center_lat: picked.value.lat,
      center_lng: picked.value.lng,
      radius_m: 50000,
    })
    rememberMap(m.slug, m.title)

    // Auto Day-1 stop: create an itinerary day for today anchored at the
    // origin, and a `camp` pin attached to it. Failures here shouldn't block
    // the user from entering their map — log and continue.
    if (addDay1Stop.value) {
      try {
        const today = todayIso()
        const stopName = pickedShort.value || 'Day 1'
        const day = await api.addItineraryDay(m.slug, {
          date: today,
          label: stopName,
          lat: picked.value.lat,
          lng: picked.value.lng,
        })
        await api.addPoint(m.slug, {
          lat: picked.value.lat,
          lng: picked.value.lng,
          title: stopName,
          category: 'camp',
          itinerary_day_id: day?.id ?? null,
        })
      } catch (seedErr) {
        // Non-fatal: the map exists, user can add the pin manually.
        console.warn('Day-1 auto-stop failed:', seedErr)
      }
    }

    router.push({ name: 'map', params: { slug: buildMapSlug(m) } })
  } catch (e) {
    error.value = e.message || 'Could not chart your map.'
    creating.value = false
  }
}

onBeforeUnmount(() => {
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<style scoped>
.home {
  min-height: 100%;
  max-width: 980px;
  margin: 0 auto;
  padding: 1.4rem clamp(1.2rem, 4vw, 3rem) 5rem;
  display: flex;
  flex-direction: column;
  gap: 2.2rem;
  position: relative;
}

/* Top bar -------------------------------------------------------- */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 0.9rem;
}
.brand { display: inline-flex; align-items: center; gap: 0.55rem; }
.brand-mark { color: var(--vermillion); font-size: 1rem; line-height: 1; }
.brand-name {
  font-family: var(--display);
  font-size: 1.25rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.brand-meta {
  font-size: 0.66rem;
  letter-spacing: 0.22em;
  color: var(--ink-faded);
  /* Decorative label — explicitly non-interactive. The default cursor and
     opacity push it visually behind the brand mark so it doesn't read as
     a link the user has yet to discover. */
  cursor: default;
  user-select: none;
  font-style: italic;
  opacity: 0.85;
}

/* Hero ----------------------------------------------------------- */
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2rem;
  align-items: center;
  padding-top: 0.5rem;
}
.hero-text { min-width: 0; }
h1 { margin: 0.5rem 0 1rem; }
.hl {
  background: var(--vermillion);
  color: var(--paper);
  padding: 0.02em 0.18em;
  display: inline-block;
  line-height: 0.94;
  box-shadow: 4px 4px 0 var(--ink);
}
.lede {
  font-size: 1.05rem;
  color: var(--ink-soft);
  max-width: 38ch;
  margin: 0;
}
.hero-mark { display: grid; place-items: center; padding: 0.5rem; }

/* Recents -------------------------------------------------------- */
.recents { margin-bottom: 1.4rem; }
.recents .lbl { margin-bottom: 0.5rem; display: block; }
.recents-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.6rem;
}
.recent-card {
  display: flex;
  align-items: stretch;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--paper);
  overflow: hidden;
  transition: transform 80ms ease, box-shadow 120ms ease;
}
.recent-card:hover { transform: translate(-2px, -2px); box-shadow: 4px 4px 0 var(--ink); }
.recent-link {
  flex: 1;
  display: grid;
  gap: 0.15rem;
  padding: 0.7rem 0.8rem;
  color: var(--ink);
  text-decoration: none;
  min-width: 0;
}
.recent-title {
  font-family: var(--display);
  font-size: 1.1rem;
  line-height: 1.15;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  /* Two-line clamp so trip names like "USA Southwest 2026 (Test)" wrap
     gracefully inside the card grid instead of being chopped mid-word. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.recent-stats { font-size: 0.72rem; color: var(--ink-soft); letter-spacing: 0.04em; }
.recent-meta { font-size: 0.7rem; color: var(--ink-faded); letter-spacing: 0.08em; }
.recent-action,
.recent-forget {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.55rem;
  border-left: 1px dashed var(--cream-edge);
  display: grid;
  place-items: center;
  min-width: 2rem;
}
.recent-action:hover { color: var(--vermillion); background: var(--cream); }
.recent-forget:hover { color: var(--vermillion); background: var(--cream); }

/* Form ----------------------------------------------------------- */
.form {
  display: grid;
  gap: 0.6rem;
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  background: var(--paper);
  padding: 1.4rem 1.4rem 1.6rem;
  box-shadow: 6px 6px 0 var(--ink);
}
.lbl { color: var(--ink); font-weight: 700; }
.eyebrow.lbl { margin: 0; }
/* Tighter rhythm between section labels and the rest of the form rows. */
.form .eyebrow.lbl { margin-top: 0.3rem; }
.form .eyebrow.lbl:first-of-type { margin-top: 0; }

.title-field { width: 100%; font-size: 1.05rem; }

/* Origin chip ---------------------------------------------------- */
.origin-row {
  display: flex;
  gap: 0.7rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: -0.2rem;
}
.origin-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.45rem 0.25rem 0.6rem;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  background: var(--cream);
  font-size: 0.85rem;
  max-width: 100%;
}
.origin-chip-lbl {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.origin-chip-val {
  font-family: var(--display);
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}
.origin-chip-clear {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.1rem;
}
.origin-chip-clear:hover { color: var(--vermillion); }

/* Ready wrap (action bar + preview) ----------------------------- */
.ready-wrap { display: grid; gap: 0.7rem; margin-top: 0.6rem; }
.action-row {
  display: flex;
  gap: 0.9rem;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0.6rem 0.7rem;
  border: 1.5px dashed var(--ink);
  border-radius: 4px;
  background: var(--cream);
}
.day1-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  color: var(--ink-soft);
  cursor: pointer;
  flex: 1 1 240px;
  min-width: 0;
}
.day1-toggle input { accent-color: var(--vermillion); }
.day1-toggle strong { color: var(--ink); }
.btn.primary {
  /* Slightly emphasised so it reads as the next step. */
  font-weight: 700;
}
/* Smaller preview thumb so the action bar + map fit above the fold on a
   typical 14" laptop without scrolling. */
.preview-map {
  width: 100%;
  height: 160px;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--cream-deep);
}

.error { color: var(--vermillion-deep); font-weight: 500; margin: 0; }
.error.sm { font-size: 0.85rem; }

.locate-link {
  background: transparent;
  border: none;
  padding: 0.1rem 0;
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
}
.locate-link:hover { color: var(--vermillion-deep); }
.locate-link:disabled { color: var(--ink-faded); cursor: wait; }

/* Footer --------------------------------------------------------- */
.foot {
  text-align: center;
  font-size: 0.74rem;
  letter-spacing: 0.22em;
  color: var(--ink-faded);
  padding-top: 1rem;
  border-top: 1.5px solid var(--ink);
}

.reveal-enter-active { transition: opacity 280ms ease, transform 280ms ease; }
.reveal-enter-from { opacity: 0; transform: translateY(8px); }

@media (max-width: 720px) {
  .hero { grid-template-columns: 1fr; }
  .hero-mark { justify-self: start; }
  .action-row { flex-direction: column; align-items: stretch; }
  .action-row .btn { width: 100%; }
}
</style>
