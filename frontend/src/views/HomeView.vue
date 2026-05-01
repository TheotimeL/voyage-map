<template>
  <main class="home">
    <header class="topbar">
      <span class="brand">
        <span class="brand-mark">●</span>
        <span class="brand-name">Voyage Map</span>
      </span>
      <span class="brand-meta mono">FIELD GUIDE · EST {{ year }}</span>
    </header>

    <section class="hero">
      <div class="hero-text">
        <p class="eyebrow">Road-trip planner</p>
        <h1>
          Sketch the route.<br />
          <span class="hl">Share the map.</span>
        </h1>
        <p class="lede">
          Drop pins, stitch days together, and send the link. No accounts —
          anyone with the URL can plan along.
        </p>
      </div>
      <div class="hero-mark">
        <CompassRose :size="160" />
      </div>
    </section>

    <section class="form">
      <p class="form-eyebrow mono">Where does the trip begin?</p>
      <GeocoderSearch
        placeholder="Las Vegas · Yosemite · Grand Canyon · Big Sur…"
        :bias="homeBias"
        @pick="onPick"
      />
      <div class="form-row-actions">
        <button class="locate-link" type="button" @click="useMyLocation" :disabled="locating">
          ⌖ {{ locating ? 'Locating…' : 'Start from my location' }}
        </button>
        <span class="qs-divider mono">or jump to</span>
        <span class="quick-starts">
          <button v-for="p in quickStarts" :key="p.label" class="qs-chip" type="button" @click="onPick({ lat: p.lat, lng: p.lng, label: p.label })">{{ p.label }}</button>
        </span>
      </div>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <Transition name="reveal">
        <div v-if="picked" class="preview-wrap">
          <div ref="mapEl" class="preview-map"></div>
          <div class="row">
            <input
              v-model="title"
              class="field title-field"
              placeholder="Name your trip — e.g. Vegas → SF"
              maxlength="120"
              @keydown.enter.prevent="create"
            />
            <button class="btn" :disabled="creating" @click="create">
              {{ creating ? 'Plotting…' : 'Begin trip →' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
        </div>
      </Transition>
    </section>

    <section v-if="recents.length" class="recents">
      <p class="eyebrow lbl">Resume a trip</p>
      <ul class="recents-list">
        <li v-for="r in recents" :key="r.slug" class="recent-card">
          <router-link
            :to="{ name: 'map', params: { slug: r.slug } }"
            class="recent-link"
            :title="`Open /m/${r.slug}`"
          >
            <span class="recent-title">{{ r.title || 'Untitled trip' }}</span>
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

    <footer class="foot mono">
      Tap the map to drop pins · drag day numbers to refine · share the URL
    </footer>
  </main>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import { api } from '@/api.js'
import { getMyLocation } from '@/util.js'
import { recentMaps, rememberMap, forgetMap } from '@/lib/recents.js'
import CompassRose from '@/components/CompassRose.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'

const router = useRouter()
const year = new Date().getFullYear()

const picked = ref(null)
const title = ref('')
const creating = ref(false)
const error = ref('')
const locating = ref(false)
const locateError = ref('')
const recents = ref(recentMaps())

// Pre-baked starting points covering the classic west-USA loops — gives
// new visitors a one-click way to start without typing.
const quickStarts = [
  { label: 'Las Vegas',   lat: 36.1699, lng: -115.1398 },
  { label: 'Los Angeles', lat: 34.0522, lng: -118.2437 },
  { label: 'Denver',      lat: 39.7392, lng: -104.9903 },
  { label: 'Seattle',     lat: 47.6062, lng: -122.3321 },
]

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
async function copyLink(slug) {
  try {
    await navigator.clipboard.writeText(`${window.location.origin}/m/${slug}`)
    copiedSlug.value = slug
    setTimeout(() => { if (copiedSlug.value === slug) copiedSlug.value = null }, 1400)
  } catch { /* no clipboard permission */ }
}

const mapEl = ref(null)
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
  // Seed the title from the picked location's first segment, but only if the
  // user hasn't typed anything yet (don't clobber their work).
  if (!title.value.trim() && r.label) {
    title.value = r.label.split(',')[0].trim().slice(0, 120)
  }
  await nextTick()
  ensureMap()
  map.setView([r.lat, r.lng], 9)
  centerMarker.setLatLng([r.lat, r.lng])
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
    router.push({ name: 'map', params: { slug: m.slug } })
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
  padding: 1.4rem clamp(1.2rem, 4vw, 3rem) 4rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
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
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  color: var(--ink-soft);
}

/* Hero ----------------------------------------------------------- */
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2rem;
  align-items: center;
  padding-top: 0.4rem;
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
  max-width: 42ch;
  margin: 0;
}
.hero-mark { display: grid; place-items: center; }

/* Form ----------------------------------------------------------- */
.form {
  display: grid;
  gap: 0.75rem;
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  background: var(--paper);
  padding: 1.3rem 1.4rem 1.5rem;
  box-shadow: 6px 6px 0 var(--ink);
}
.form-eyebrow {
  margin: 0;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.form-row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.7rem;
  margin-top: -0.1rem;
}

.preview-wrap { display: grid; gap: 0.75rem; margin-top: 0.4rem; }
.preview-map {
  width: 100%;
  height: 260px;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--cream-deep);
}

.row { display: flex; gap: 0.7rem; align-items: stretch; flex-wrap: wrap; }
.title-field { flex: 1; min-width: 220px; }
.error { color: var(--vermillion-deep); font-weight: 500; margin: 0; }
.error.sm { font-size: 0.85rem; }

.locate-link {
  background: transparent;
  border: none;
  padding: 0;
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
}
.locate-link:hover { color: var(--vermillion-deep); }
.locate-link:disabled { color: var(--ink-faded); cursor: wait; }

.qs-divider {
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.quick-starts {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.qs-chip {
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  padding: 0.2rem 0.7rem;
  font-family: var(--mono);
  font-size: 0.74rem;
  color: var(--ink-soft);
  cursor: pointer;
  transition: all 90ms ease;
}
.qs-chip:hover { border-color: var(--vermillion); color: var(--vermillion); background: var(--cream); }

/* Recents -------------------------------------------------------- */
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
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

/* Footer --------------------------------------------------------- */
.foot {
  text-align: center;
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  color: var(--ink-faded);
  padding-top: 1rem;
  border-top: 1px dashed var(--cream-edge);
}

.reveal-enter-active { transition: opacity 280ms ease, transform 280ms ease; }
.reveal-enter-from { opacity: 0; transform: translateY(8px); }

@media (max-width: 720px) {
  .hero { grid-template-columns: 1fr; gap: 1rem; }
  .hero-mark { display: none; }
  .form-row-actions { flex-direction: column; align-items: flex-start; gap: 0.45rem; }
}
</style>
