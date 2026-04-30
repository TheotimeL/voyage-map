<template>
  <main class="home">
    <header class="topbar">
      <span class="brand">
        <span class="brand-mark">●</span>
        <span class="brand-name">Voyage Map</span>
      </span>
      <span class="brand-meta mono">№ 001 · FIELD GUIDE</span>
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

    <section class="form">
      <label class="eyebrow lbl">01 · Where to?</label>
      <GeocoderSearch
        placeholder="Las Vegas · Mt. Fuji · 11° N 80° W…"
        @pick="onPick"
      />
      <button class="locate-link" type="button" @click="useMyLocation" :disabled="locating">
        ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
      </button>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <Transition name="reveal">
        <div v-if="picked" class="preview-wrap">
          <p class="eyebrow lbl">02 · How wide?</p>
          <div ref="mapEl" class="preview-map"></div>
          <RadiusSlider v-model="radiusM" @change="updateCircle" />

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
import { ref, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import { api } from '@/api.js'
import { getMyLocation } from '@/util.js'
import CompassRose from '@/components/CompassRose.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'
import RadiusSlider from '@/components/RadiusSlider.vue'

const router = useRouter()
const year = new Date().getFullYear()

const picked = ref(null)
const radiusM = ref(50000)
const title = ref('')
const creating = ref(false)
const error = ref('')
const locating = ref(false)
const locateError = ref('')

const mapEl = ref(null)
let map = null
let centerMarker = null
let circle = null

watch(radiusM, () => updateCircle())

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
  await nextTick()
  ensureMap()
  map.setView([r.lat, r.lng], zoomForRadius(radiusM.value))
  centerMarker.setLatLng([r.lat, r.lng])
  circle.setLatLng([r.lat, r.lng])
  circle.setRadius(radiusM.value)
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
    circle.setLatLng(ll)
    picked.value = { ...picked.value, lat: ll.lat, lng: ll.lng }
  })
  circle = L.circle([0, 0], {
    radius: radiusM.value,
    color: '#e85d3c',
    weight: 2.5,
    fillColor: '#e85d3c',
    fillOpacity: 0.08,
    dashArray: '6 6',
  }).addTo(map)
}

function updateCircle() {
  if (!circle) return
  circle.setRadius(radiusM.value)
  if (picked.value && map) {
    map.setView([picked.value.lat, picked.value.lng], zoomForRadius(radiusM.value), { animate: true })
  }
}

function zoomForRadius(m) {
  if (m < 1500) return 14
  if (m < 4000) return 13
  if (m < 10000) return 12
  if (m < 25000) return 11
  if (m < 60000) return 10
  if (m < 150000) return 9
  if (m < 400000) return 8
  if (m < 900000) return 7
  return 6
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
      radius_m: radiusM.value,
    })
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
