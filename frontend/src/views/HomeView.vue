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
      <label class="eyebrow lbl">01 · Where to?</label>
      <GeocoderSearch
        placeholder="Las Vegas · Mt. Fuji · 11° N 80° W…"
        :bias="homeBias"
        @pick="onPick"
      />
      <button class="locate-link" type="button" @click="useMyLocation" :disabled="locating">
        ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
      </button>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <Transition name="reveal">
        <div v-if="picked" class="preview-wrap">
          <p class="eyebrow lbl">02 · Preview</p>
          <div ref="mapEl" class="preview-map"></div>

          <p class="eyebrow lbl">03 · Name it (optional) and go</p>
          <div class="row">
            <input
              v-model="title"
              class="field title-field"
              placeholder="e.g. Vegas → SF road trip"
              maxlength="120"
            />
            <button class="btn" :disabled="creating" @click="create">
              {{ creating ? 'Plotting…' : 'Begin journey →' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
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
  gap: 0.9rem;
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  background: var(--paper);
  padding: 1.4rem 1.4rem 1.6rem;
  box-shadow: 6px 6px 0 var(--ink);
}
.lbl { color: var(--ink); font-weight: 700; }
.eyebrow.lbl { margin: 0; }

.preview-wrap { display: grid; gap: 0.9rem; margin-top: 0.4rem; }
.preview-map {
  width: 100%;
  height: 280px;
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
  padding: 0.1rem 0;
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
  justify-self: start;
  margin-top: -0.4rem;
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
}
</style>
