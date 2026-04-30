<template>
  <main class="home">
    <div class="corner top-left"><CompassRose :size="160" /></div>
    <div class="corner bottom-right ornament">✦</div>

    <section class="hero paper">
      <p class="eyebrow">A field journal for places</p>
      <h1>Voyage Map</h1>
      <p class="subtitle">
        Plant a flag anywhere on earth, draw a circle around it, and share the link.
        Anyone with the URL can mark spots and leave notes.
      </p>

      <div class="form">
        <label class="lbl">Where to?</label>
        <GeocoderSearch
          placeholder="Las Vegas, Mt. Fuji, 11° N 80° W…"
          @pick="onPick"
        />

        <Transition name="reveal">
          <div v-if="picked" class="preview-wrap">
            <div ref="mapEl" class="preview-map"></div>

            <RadiusSlider v-model="radiusM" @change="updateCircle" />

            <div class="row">
              <input
                v-model="title"
                class="field title-field"
                placeholder="Name this voyage (optional)"
                maxlength="120"
              />
              <button class="btn" :disabled="creating" @click="create">
                {{ creating ? 'Charting…' : 'Begin Journey ⛵' }}
              </button>
            </div>
            <p v-if="error" class="error">{{ error }}</p>
          </div>
        </Transition>
      </div>
    </section>

    <footer class="foot mono">
      <span>est. {{ year }}</span>
      <span class="dot">·</span>
      <span>cartography by you</span>
    </footer>
  </main>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import { api } from '@/api.js'
import CompassRose from '@/components/CompassRose.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'
import RadiusSlider from '@/components/RadiusSlider.vue'

const router = useRouter()
const year = new Date().getFullYear()

const picked = ref(null)
const radiusM = ref(50000) // 50 km — a reasonable mid-range default
const title = ref('')
const creating = ref(false)
const error = ref('')

const mapEl = ref(null)
let map = null
let centerMarker = null
let circle = null

watch(radiusM, () => updateCircle())

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
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19,
  }).addTo(map)
  centerMarker = L.marker([0, 0], { icon: makePinIcon('⚑'), draggable: true }).addTo(map)
  centerMarker.on('drag', (e) => {
    const ll = e.target.getLatLng()
    circle.setLatLng(ll)
    picked.value = { ...picked.value, lat: ll.lat, lng: ll.lng }
  })
  circle = L.circle([0, 0], {
    radius: radiusM.value,
    color: '#8b3a3a',
    weight: 2,
    fillColor: '#b88a4a',
    fillOpacity: 0.12,
    dashArray: '4 6',
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

function makePinIcon(glyph) {
  return L.divIcon({
    className: 'pin-wrapper',
    html: `<div class="pin"><span>${glyph}</span></div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
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
  display: grid;
  place-items: center;
  padding: clamp(1.5rem, 4vw, 4rem) 1.2rem;
  position: relative;
  overflow: hidden;
}
.corner {
  position: absolute;
  pointer-events: none;
  color: var(--ink-soft);
  opacity: 0.55;
}
.corner.top-left { top: 1.5rem; left: 1.5rem; }
.corner.bottom-right.ornament {
  bottom: 1.4rem; right: 1.8rem;
  font-family: var(--serif-display);
  font-size: 2rem;
}

.hero {
  width: min(720px, 100%);
  text-align: left;
  position: relative;
  z-index: 1;
}
.subtitle {
  font-size: 1.12rem;
  color: var(--ink-soft);
  margin: 0.2rem 0 1.6rem;
  max-width: 56ch;
}
.form { display: grid; gap: 1rem; }
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}

.preview-wrap { display: grid; gap: 0.9rem; }
.preview-map {
  width: 100%;
  height: 280px;
  border: 1px solid var(--paper-edge);
  border-radius: 2px;
  background: var(--paper-deep);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.5) inset, 0 6px 18px -6px rgba(40, 20, 0, 0.3);
}

.row { display: flex; gap: 0.7rem; align-items: end; flex-wrap: wrap; }
.title-field { flex: 1; min-width: 220px; }
.error { color: var(--oxblood-deep); font-style: italic; }

.foot {
  position: absolute;
  bottom: 1.4rem;
  left: 50%;
  transform: translateX(-50%);
  color: var(--ink-faded);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
.foot .dot { padding: 0 0.5rem; }

.reveal-enter-active { transition: opacity 280ms ease, transform 280ms ease; }
.reveal-enter-from { opacity: 0; transform: translateY(8px); }
</style>
