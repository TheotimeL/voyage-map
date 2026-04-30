<template>
  <main class="mapview">
    <aside class="sidebar paper" :class="{ open: sidebarOpen }">
      <div class="side-head">
        <router-link to="/" class="back">← Home</router-link>
        <div class="head-actions">
          <ThemeToggle />
          <button class="btn-icon" @click="sidebarOpen = !sidebarOpen" :aria-label="sidebarOpen ? 'Collapse' : 'Expand'">
            {{ sidebarOpen ? '⟨' : '⟩' }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">Charting…</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <template v-else-if="mapData">
        <header class="voyage-head">
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
        </header>

        <hr class="major-rule" />

        <section class="sec">
          <div class="sec-head">
            <span class="sec-num mono">№ 01</span>
            <h3 class="sec-title">Places</h3>
            <span class="sec-count mono">
              {{ visiblePoints.length }}<template v-if="hiddenCats.size > 0">/{{ mapData.points.length }}</template>
            </span>
            <button class="btn btn-tiny sec-action" @click="startNewPin">+ Drop</button>
          </div>
          <GeocoderSearch placeholder="Search a spot to mark…" @pick="onSearchPick" />
          <button class="locate-link" type="button" @click="markMyLocation" :disabled="locating">
            ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
          </button>
          <p v-if="locateError" class="error sm">{{ locateError }}</p>
          <CategoryFilters
            :points="mapData.points"
            :hidden="hiddenCats"
            @toggle="toggleCat"
            @reset="resetCats"
          />
          <PointList
            :points="visiblePoints"
            :active-id="activeId"
            @select="onSelectPoint"
          />
        </section>

        <section class="sec">
          <div class="sec-head">
            <span class="sec-num mono">№ 02</span>
            <h3 class="sec-title">Itinerary</h3>
          </div>
          <Itinerary
            :days="mapData.itinerary || []"
            @add="onAddDay"
            @add-bulk="onAddBulk"
            @delete="onDeleteDay"
            @go="onGoDay"
          />
        </section>

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

        <section class="sec">
          <div class="sec-head">
            <span class="sec-num mono">№ 04</span>
            <h3 class="sec-title">Daylight</h3>
          </div>
          <SunPanel
            :fallback-lat="mapData.center_lat"
            :fallback-lng="mapData.center_lng"
          />
        </section>

        <section class="sec">
          <div class="sec-head">
            <span class="sec-num mono">№ 05</span>
            <h3 class="sec-title">Survival</h3>
          </div>
          <SurvivalLayer
            :get-bounds="getMapBounds"
            @render="renderSurvival"
            @clear="clearSurvival"
          />
        </section>

        <section class="sec">
          <div class="sec-head">
            <span class="sec-num mono">№ 06</span>
            <h3 class="sec-title">Offline</h3>
          </div>
          <PrecacheButton :theme="theme" />
        </section>

        <footer class="side-foot">
          <p class="foot-lbl mono">Share this map</p>
          <button class="btn btn-ghost btn-share" @click="copyUrl">
            {{ copied ? 'Copied ✓' : 'Copy link' }}
          </button>
        </footer>
      </template>
    </aside>

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

    <div
      class="map-wrap"
      @dragover.prevent="onGpxDragOver"
      @dragleave="onGpxDragLeave"
      @drop.prevent="onGpxDrop"
    >
      <div v-if="todayBanner" class="today-banner" @click="onGoDay(todayBanner.day)">
        <span class="banner-tag mono">{{ todayBanner.tag }}</span>
        <span class="banner-text">{{ todayBanner.text }}</span>
        <span v-if="todayBanner.notes" class="banner-notes">{{ todayBanner.notes }}</span>
      </div>

      <div ref="mapEl" class="map"></div>

      <button
        class="locate-me"
        type="button"
        :class="{ on: myDot }"
        :disabled="locating"
        :title="myDot ? 'Re-centre on me' : 'Show me on the map'"
        @click="showMeOnMap"
      >
        <span class="locate-glyph">⌖</span>
      </button>

      <Transition name="fade">
        <div v-if="gpxDragging" class="dropzone">
          <div class="dropzone-inner">
            <p class="eyebrow">Drop to import</p>
            <h3>Add a .gpx track</h3>
          </div>
        </div>
      </Transition>

      <PointDetailCard
        v-if="detail && !modal"
        :point="detail"
        @edit="onEdit"
        @delete="onDeleteDetail"
        @close="closeDetail"
      />

      <ElevationProfile
        v-if="activeSeries.length"
        :series="activeSeries"
        :name="activeTrackName"
        @hover="onElevHover"
        @close="activeTrailPointId = null"
      />
    </div>

    <PointFormModal
      v-if="modal"
      :model-value="modal"
      :is-new="modal.id == null"
      @save="onSave"
      @close="modal = null"
    />

    <Teleport to="body">
      <div v-if="candidatesFor" class="scrim" @click.self="candidatesFor = null">
        <div class="paper candidate-modal">
          <p class="eyebrow">Multiple matches — pick one</p>
          <h3 class="candidate-title">{{ candidatesFor.day.label }}</h3>
          <ul class="candidate-list">
            <li v-for="(r, i) in candidatesFor.results" :key="i">
              <button class="candidate-btn" type="button" @click="pickCandidate(candidatesFor.day, r)">
                <span class="cand-label">{{ r.label }}</span>
                <span class="cand-coord mono">{{ r.lat.toFixed(3) }}, {{ r.lng.toFixed(3) }}</span>
              </button>
            </li>
          </ul>
          <div class="row">
            <button type="button" class="btn btn-ghost" @click="candidatesFor = null">Cancel</button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import L from 'leaflet'
import { api } from '@/api.js'
// Itinerary + geocode helpers imported below.
import { CATEGORIES, formatLat, formatLng, getMyLocation, parseGPX, trackColor, todayISO } from '@/util.js'
import { geocode } from '@/api.js'
import Itinerary from '@/components/Itinerary.vue'
import PointList from '@/components/PointList.vue'
import PointFormModal from '@/components/PointFormModal.vue'
import PointDetailCard from '@/components/PointDetailCard.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'
import RadiusSlider from '@/components/RadiusSlider.vue'
import CategoryFilters from '@/components/CategoryFilters.vue'
import PrecacheButton from '@/components/PrecacheButton.vue'
import SunPanel from '@/components/SunPanel.vue'
import SurvivalLayer from '@/components/SurvivalLayer.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import ElevationProfile from '@/components/ElevationProfile.vue'
import InfoPanel from '@/components/InfoPanel.vue'
import { theme } from '@/lib/theme.js'
import { buildElevationSeries } from '@/lib/elevation.js'

const props = defineProps({
  slug: { type: String, required: true },
})

const mapData = ref(null)
const loading = ref(true)
const error = ref('')
const titleDraft = ref('')
const radiusDraft = ref(5000)
const sidebarOpen = ref(true)
const useV2 = ref(new URLSearchParams(window.location.search).get('ui') === 'v2')
const v2Active = ref('places')
const v2Tabs = [
  { key: 'places', label: 'Places', icon: '📍' },
  { key: 'itinerary', label: 'Itinerary', icon: '🗓' },
  { key: 'more', label: 'More', icon: '⋯' },
]
const activeId = ref(null)
const modal = ref(null)
const detail = ref(null)
const copied = ref(false)
const locating = ref(false)
const locateError = ref('')
const hiddenCats = ref(new Set())
const activeTrailPointId = ref(null)
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

const visiblePoints = computed(() => {
  if (!mapData.value) return []
  if (hiddenCats.value.size === 0) return mapData.value.points
  return mapData.value.points.filter((p) => !hiddenCats.value.has(p.category))
})

watch(visiblePoints, (next) => {
  // Sync map markers: hide markers whose category is filtered out.
  const allowed = new Set(next.map((p) => p.id))
  for (const [id, marker] of pointMarkers.entries()) {
    const onMap = leaflet?.hasLayer(marker)
    if (allowed.has(id) && !onMap) marker.addTo(leaflet)
    else if (!allowed.has(id) && onMap) leaflet.removeLayer(marker)
  }
})

watch(
  () => mapData.value?.itinerary,
  () => renderItinerary(),
  { deep: true },
)

watch(theme, () => { if (leaflet) attachTiles() })

function toggleCat(key) {
  const s = new Set(hiddenCats.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  hiddenCats.value = s
}
function resetCats() { hiddenCats.value = new Set() }

const mapEl = ref(null)
let leaflet = null
let centerMarker = null
let circle = null
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
const pointMarkers = new Map()
const myDot = ref(false) // truthy when blue-dot is shown — used for button styling
let myDotMarker = null
let myAccuracyCircle = null
const trackLines = new Map() // track id → L.polyline
const itineraryMarkers = new Map() // day id → L.marker
let itineraryLine = null
const survivalGroup = ref(null)
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
const gpxDragging = ref(false)
const gpxError = ref('')
let dragCounter = 0

const emojiByCategory = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))

onMounted(async () => {
  try {
    const m = await api.getMap(props.slug)
    mapData.value = m
    titleDraft.value = m.title || ''
    radiusDraft.value = m.radius_m
    loading.value = false
    await nextTick()
    initLeaflet()

    const today = todayISO()
    const day = (mapData.value.itinerary || []).find((d) => d.date === today)
    if (day && day.lat != null && day.lng != null && leaflet) {
      leaflet.setView([day.lat, day.lng], 11)
    }
  } catch (e) {
    error.value = 'This map could not be found.'
    loading.value = false
  }
})

function initLeaflet() {
  leaflet = L.map(mapEl.value, {
    zoomControl: true,
    attributionControl: true,
  })
  attachTiles()

  const center = [mapData.value.center_lat, mapData.value.center_lng]
  leaflet.setView(center, zoomForRadius(mapData.value.radius_m))

  circle = L.circle(center, {
    radius: mapData.value.radius_m,
    color: '#e85d3c',
    weight: 2.5,
    fillColor: '#e85d3c',
    fillOpacity: 0.07,
    dashArray: '6 6',
    interactive: false,
  }).addTo(leaflet)

  centerMarker = L.marker(center, {
    icon: makePinIcon('⚑', 'center-pin'),
    draggable: true,
    title: 'Voyage center — drag to move',
  }).addTo(leaflet)
  centerMarker.on('drag', (e) => {
    const ll = e.target.getLatLng()
    circle.setLatLng(ll)
  })
  centerMarker.on('dragend', async (e) => {
    const ll = e.target.getLatLng()
    try {
      const updated = await api.patchMap(props.slug, { center_lat: ll.lat, center_lng: ll.lng })
      mapData.value = updated
    } catch {
      centerMarker.setLatLng([mapData.value.center_lat, mapData.value.center_lng])
      circle.setLatLng([mapData.value.center_lat, mapData.value.center_lng])
    }
  })

  leaflet.on('click', () => {
    // Empty-map click only dismisses an open detail card — no implicit pin drop.
    if (detail.value) closeDetail()
  })

  mapData.value.points.forEach(addPointMarker)
  trailPoints.value.forEach((p, i) => renderTrack(p, i))
  renderItinerary()
}

function makeItineraryIcon(num) {
  return L.divIcon({
    className: 'iti-pin-wrapper',
    html: `<div class="iti-pin"><span>${num}</span></div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

function renderItinerary() {
  if (!leaflet) return
  for (const m of itineraryMarkers.values()) leaflet.removeLayer(m)
  itineraryMarkers.clear()
  if (itineraryLine) { leaflet.removeLayer(itineraryLine); itineraryLine = null }

  const days = (mapData.value?.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))

  const coords = []
  days.forEach((d, i) => {
    const m = L.marker([d.lat, d.lng], {
      icon: makeItineraryIcon(i + 1),
      title: `${d.label || 'Day'} — ${d.date}`,
      zIndexOffset: 600,
    }).addTo(leaflet)
    m.on('click', () => onGoDay(d))
    itineraryMarkers.set(d.id, m)
    coords.push([d.lat, d.lng])
  })

  if (coords.length >= 2) {
    itineraryLine = L.polyline(coords, {
      color: '#1f3851',
      weight: 2.5,
      opacity: 0.9,
      dashArray: '4 8',
      lineCap: 'round',
      interactive: false,
    }).addTo(leaflet)
  }
}

function makePinIcon(glyph, extra = '') {
  return L.divIcon({
    className: `pin-wrapper ${extra}`,
    html: `<div class="pin"><span>${glyph}</span></div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  })
}

function addPointMarker(p) {
  const m = L.marker([p.lat, p.lng], {
    icon: makePinIcon(emojiByCategory[p.category] || '📍'),
  }).addTo(leaflet)
  m.on('click', (e) => {
    L.DomEvent.stop(e)
    openDetail(p)
  })
  pointMarkers.set(p.id, m)
}

function removePointMarker(id) {
  const m = pointMarkers.get(id)
  if (m) {
    leaflet.removeLayer(m)
    pointMarkers.delete(id)
  }
}

function openDetail(p) {
  // Always read the freshest version from state (in case it was edited).
  const fresh = mapData.value.points.find((x) => x.id === p.id) || p
  detail.value = { ...fresh }
  activeId.value = fresh.id
  modal.value = null
  if (leaflet) {
    leaflet.flyTo([fresh.lat, fresh.lng], Math.max(leaflet.getZoom(), 13), { duration: 0.4 })
  }
}

function closeDetail() {
  detail.value = null
  activeId.value = null
}

function onEdit() {
  if (!detail.value) return
  modal.value = { ...detail.value }
  detail.value = null
}

async function onDeleteDetail() {
  if (!detail.value?.id) return
  await deletePoint(detail.value.id)
  detail.value = null
  activeId.value = null
}

async function deletePoint(id) {
  try {
    await api.deletePoint(props.slug, id)
    mapData.value.points = mapData.value.points.filter((p) => p.id !== id)
    removePointMarker(id)
  } catch (e) {
    error.value = e.message
  }
}

function startNewPin() {
  const c = leaflet.getCenter()
  modal.value = { lat: c.lat, lng: c.lng, title: '', comment: '', category: 'note' }
  detail.value = null
}

function onSelectPoint(p) {
  openDetail(p)
}

function renderTrack(track, idx) {
  try {
    const { coords } = parseGPX(track.gpx_data)
    const line = L.polyline(coords, {
      color: track.color || trackColor(idx),
      weight: 4,
      opacity: 0.9,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(leaflet)
    trackLines.set(track.id, line)
    return line
  } catch (e) {
    console.warn('Skipping track', track.id, e)
    return null
  }
}

function removeTrackLine(id) {
  const line = trackLines.get(id)
  if (line && leaflet) {
    leaflet.removeLayer(line)
    trackLines.delete(id)
  }
}

function onGpxDragOver(e) {
  if (![...(e.dataTransfer?.types || [])].includes('Files')) return
  if (!gpxDragging.value) gpxDragging.value = true
}
function onGpxDragLeave(e) {
  // Only hide when leaving the wrap (not its children)
  if (e.currentTarget.contains(e.relatedTarget)) return
  gpxDragging.value = false
}
async function onGpxDrop(e) {
  gpxDragging.value = false
  dragCounter = 0
  const files = Array.from(e.dataTransfer?.files || []).filter((f) => /\.gpx$/i.test(f.name))
  if (files.length === 0) return
  for (const f of files) {
    await importGpxFile(f)
  }
}

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

async function deleteTrailPoint(id) {
  try {
    await api.deletePoint(props.slug, id)
    mapData.value.points = (mapData.value.points || []).filter((p) => p.id !== id)
    removeTrackLine(id)
  } catch (e) {
    error.value = e.message
  }
}

// Itinerary -----------------------------------------------------------
const today = computed(() => todayISO())
const todayBanner = computed(() => {
  const days = mapData.value?.itinerary || []
  if (!days.length) return null
  const t = today.value
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))
  const todayDay = sorted.find((d) => d.date === t)
  if (todayDay) {
    const idx = sorted.indexOf(todayDay)
    return {
      tag: `Day ${idx + 1} / ${sorted.length}`,
      text: (todayDay.label || 'On the road').toUpperCase(),
      notes: todayDay.notes || null,
      day: todayDay,
    }
  }
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
  return null
})

async function onAddDay(payload) {
  try {
    const day = await api.addItineraryDay(props.slug, payload)
    if (!mapData.value.itinerary) mapData.value.itinerary = []
    mapData.value.itinerary = [...mapData.value.itinerary, day].sort((a, b) => a.date.localeCompare(b.date))
  } catch (e) { error.value = e.message }
}

async function onAddBulk(rows) {
  try {
    const created = await api.addItineraryBulk(props.slug, rows)
    if (!mapData.value.itinerary) mapData.value.itinerary = []
    mapData.value.itinerary = [...mapData.value.itinerary, ...created].sort((a, b) => a.date.localeCompare(b.date))
  } catch (e) { error.value = e.message; throw e }
}

async function onDeleteDay(day) {
  try {
    await api.deleteItineraryDay(props.slug, day.id)
    mapData.value.itinerary = mapData.value.itinerary.filter((d) => d.id !== day.id)
  } catch (e) { error.value = e.message }
}

const candidatesFor = ref(null)

async function onGoDay(day) {
  if (!leaflet) return
  if (day.lat != null && day.lng != null) {
    leaflet.flyTo([day.lat, day.lng], Math.max(leaflet.getZoom(), 11), { duration: 0.6 })
    return
  }
  if (!day.label) return
  try {
    const results = await geocode(day.label)
    if (!results.length) {
      error.value = `No place found for "${day.label}".`
      return
    }
    if (results.length === 1) {
      await pickCandidate(day, results[0])
      return
    }
    candidatesFor.value = { day, results: results.slice(0, 6) }
  } catch (e) { error.value = e.message }
}

async function pickCandidate(day, choice) {
  try {
    const updated = await api.patchItineraryDay(props.slug, day.id, { lat: choice.lat, lng: choice.lng })
    const idx = mapData.value.itinerary.findIndex((d) => d.id === day.id)
    if (idx >= 0) mapData.value.itinerary.splice(idx, 1, updated)
    leaflet.flyTo([choice.lat, choice.lng], 11, { duration: 0.6 })
    candidatesFor.value = null
  } catch (e) { error.value = e.message }
}

async function onGpxFilePick(e) {
  const files = Array.from(e.target.files || []).filter((f) => /\.gpx$/i.test(f.name))
  for (const f of files) await importGpxFile(f)
  e.target.value = ''
}

async function showMeOnMap() {
  if (!leaflet) return
  locating.value = true
  locateError.value = ''
  try {
    const loc = await getMyLocation()
    const ll = [loc.lat, loc.lng]
    if (!myDotMarker) {
      myDotMarker = L.marker(ll, {
        icon: L.divIcon({
          className: 'me-wrapper',
          html: '<div class="me-dot"></div>',
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        interactive: false,
        zIndexOffset: 1000,
      }).addTo(leaflet)
      myAccuracyCircle = L.circle(ll, {
        radius: Math.max(loc.accuracy || 50, 30),
        color: '#3b82f6',
        weight: 1,
        fillColor: '#3b82f6',
        fillOpacity: 0.1,
        interactive: false,
      }).addTo(leaflet)
    } else {
      myDotMarker.setLatLng(ll)
      myAccuracyCircle.setLatLng(ll)
      myAccuracyCircle.setRadius(Math.max(loc.accuracy || 50, 30))
    }
    myDot.value = true
    leaflet.flyTo(ll, Math.max(leaflet.getZoom(), 14), { duration: 0.6 })
  } catch (e) {
    locateError.value = e.message
  } finally {
    locating.value = false
  }
}

async function markMyLocation() {
  locating.value = true
  locateError.value = ''
  try {
    const loc = await getMyLocation()
    if (leaflet) leaflet.flyTo([loc.lat, loc.lng], 15, { duration: 0.6 })
    detail.value = null
    activeId.value = null
    modal.value = {
      lat: loc.lat,
      lng: loc.lng,
      title: 'You are here',
      comment: '',
      category: 'note',
    }
  } catch (e) {
    locateError.value = e.message
  } finally {
    locating.value = false
  }
}

function onSearchPick(r) {
  // Picking a search result opens the new-point modal at that location, pre-titled.
  const name = r.label.split(',')[0]
  if (leaflet) leaflet.flyTo([r.lat, r.lng], 14, { duration: 0.5 })
  detail.value = null
  activeId.value = null
  modal.value = {
    lat: r.lat,
    lng: r.lng,
    title: name,
    comment: '',
    category: 'note',
  }
}

async function onSave(payload) {
  if (!modal.value) return
  try {
    if (modal.value.id) {
      const updated = await api.patchPoint(props.slug, modal.value.id, payload)
      const idx = mapData.value.points.findIndex((p) => p.id === updated.id)
      if (idx >= 0) mapData.value.points.splice(idx, 1, updated)
      removePointMarker(updated.id)
      addPointMarker(updated)
      // Re-open detail with the updated content.
      detail.value = { ...updated }
      activeId.value = updated.id
    } else {
      const created = await api.addPoint(props.slug, {
        ...payload,
        lat: modal.value.lat,
        lng: modal.value.lng,
      })
      mapData.value.points.push(created)
      addPointMarker(created)
      activeId.value = created.id
      detail.value = { ...created }
    }
    modal.value = null
  } catch (e) {
    error.value = e.message
  }
}

async function commitTitle() {
  const t = titleDraft.value.trim() || null
  if (t === (mapData.value.title || null)) return
  try {
    mapData.value = await api.patchMap(props.slug, { title: t })
  } catch {
    titleDraft.value = mapData.value.title || ''
  }
}

function liveRadius(v) {
  if (circle) circle.setRadius(v)
}

async function commitRadius(v) {
  if (v === mapData.value.radius_m) return
  try {
    mapData.value = await api.patchMap(props.slug, { radius_m: v })
    if (leaflet) leaflet.setView([mapData.value.center_lat, mapData.value.center_lng], zoomForRadius(mapData.value.radius_m), { animate: true })
  } catch {
    radiusDraft.value = mapData.value.radius_m
    if (circle) circle.setRadius(mapData.value.radius_m)
  }
}

function copyUrl() {
  navigator.clipboard.writeText(window.location.href)
  copied.value = true
  setTimeout(() => (copied.value = false), 1800)
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

function formatRadius(m) {
  if (m < 1000) return `${m} m`
  const km = m / 1000
  return `${km % 1 === 0 ? km : km.toFixed(1)} km`
}

onBeforeUnmount(() => {
  if (leaflet) {
    leaflet.remove()
    leaflet = null
  }
})
</script>

<style scoped>
.mapview {
  position: fixed;
  inset: 0;
  display: flex;
}
.map-wrap {
  flex: 1;
  position: relative;
  height: 100%;
}
.map {
  width: 100%;
  height: 100%;
  background: var(--cream-deep);
}
.sidebar {
  width: 380px;
  max-width: 86vw;
  height: 100%;
  border-right: 1px solid var(--cream-edge);
  border-top: none;
  border-bottom: none;
  border-left: none;
  padding: 1.1rem 1.4rem 1.6rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  overflow-y: auto;
  transition: width 220ms ease, padding 220ms ease;
  z-index: 2;
  box-shadow: 4px 0 18px -8px rgba(40, 20, 0, 0.28);
}
.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-track { background: transparent; }
.sidebar::-webkit-scrollbar-thumb { background: var(--cream-edge); border-radius: 3px; }
.sidebar::-webkit-scrollbar-thumb:hover { background: var(--ink-faded); }
.sidebar:not(.open) {
  width: 56px;
  padding: 1.2rem 0.5rem;
  overflow: hidden;
}
.sidebar:not(.open) > *:not(.side-head) { display: none; }

.side-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.head-actions { display: inline-flex; gap: 0.4rem; align-items: center; }
.back {
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-soft);
  border-bottom: none;
}
.back:hover { color: var(--vermillion); }
.btn-icon {
  background: transparent;
  border: 1px solid var(--ink-faded);
  border-radius: 2px;
  width: 2rem; height: 2rem;
  display: grid; place-items: center;
  font-family: var(--display);
  color: var(--ink-soft);
  cursor: pointer;
}
.btn-icon:hover { color: var(--vermillion); border-color: var(--vermillion); }

.loading, .error {
  padding: 2rem 0;
  font-style: italic;
  color: var(--ink-faded);
  text-align: center;
}
.error { color: var(--vermillion-deep); }

/* Voyage header --------------------------------------------------- */
.voyage-head { display: grid; gap: 0.45rem; }
.title { margin: 0; line-height: 0.94; }
.title-input {
  font-family: var(--display);
  font-size: 2.15rem;
  letter-spacing: 0.005em;
  color: var(--ink);
  background: transparent;
  border: none;
  border-bottom: 1px dotted transparent;
  width: 100%;
  padding: 0;
  outline: none;
  text-transform: uppercase;
}
.title-input:focus, .title-input:hover { border-bottom-color: var(--ink-faded); }
.title-input::placeholder { color: var(--ink-faded); font-style: italic; text-transform: none; }

.meta {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  font-family: var(--mono);
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
  margin: 0.15rem 0 0;
}
.meta-icon { color: var(--vermillion); font-weight: 700; }

.radius-row {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.25rem;
}
.radius-label {
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}

/* Major rule between voyage and the section catalog */
.major-rule {
  border: none;
  height: 3px;
  background: var(--ink);
  margin: 0.4rem 0 0.5rem;
  box-shadow: 0 5px 0 -1px var(--ink);
}

/* Section system --------------------------------------------------- */
.sec { display: grid; gap: 0.55rem; }
.sec-head {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: baseline;
  gap: 0.55rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--ink);
  position: relative;
}
.sec-head::after {
  content: '';
  position: absolute;
  left: 0; bottom: -1px;
  width: 42px;
  height: 2px;
  background: var(--vermillion);
}
.sec-num {
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  color: var(--vermillion);
  font-weight: 700;
  text-transform: uppercase;
}
.sec-title {
  font-family: var(--display);
  font-size: 1.05rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin: 0;
  color: var(--ink);
  font-weight: 400;
}
.sec-count {
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  color: var(--ink-faded);
  text-transform: uppercase;
  font-weight: 600;
}
.sec-action {
  justify-self: end;
  font-size: 0.7rem;
  padding: 0.32rem 0.7rem;
}

.locate-link {
  background: transparent;
  border: none;
  padding: 0.1rem 0;
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
  justify-self: start;
}
.locate-link:hover { color: var(--vermillion-deep); }
.locate-link:disabled { color: var(--ink-faded); cursor: wait; }
.error.sm { font-size: 0.82rem; margin: 0; }

/* Floating "show me" map control */
.locate-me {
  position: absolute;
  bottom: 1.4rem;
  right: 1.2rem;
  z-index: 700;
  width: 44px;
  height: 44px;
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  cursor: pointer;
  display: grid;
  place-items: center;
  box-shadow: 0 3px 0 var(--ink), 0 6px 12px rgba(0, 0, 0, 0.18);
  transition: transform 80ms ease, background 120ms ease, box-shadow 120ms ease;
}
.locate-me:hover { background: var(--ink); color: var(--paper); }
.locate-me:active { transform: translateY(2px); box-shadow: 0 1px 0 var(--ink); }
.locate-me:disabled { opacity: 0.5; cursor: wait; }
.locate-me.on { background: #3b82f6; border-color: #1e40af; color: #fff; box-shadow: 0 3px 0 #1e40af, 0 6px 12px rgba(0,0,0,0.18); }
.locate-me.on:hover { background: #1e40af; }
.locate-glyph { font-size: 1.3rem; line-height: 1; font-weight: 700; }

/* GPX dropzone */
.dropzone {
  position: absolute;
  inset: 12px;
  z-index: 750;
  border: 3px dashed var(--vermillion);
  background: rgba(243, 237, 228, 0.85);
  border-radius: 6px;
  display: grid;
  place-items: center;
  pointer-events: none;
}
.dropzone-inner { text-align: center; color: var(--ink); }
.dropzone-inner h3 { margin-top: 0.4rem; font-size: 1.6rem; }

.fade-enter-active, .fade-leave-active { transition: opacity 140ms ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Routes section */
.gpx-pick { cursor: pointer; }
.track-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }
.track-row {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem;
  border: 1px solid transparent;
  border-radius: 3px;
}
.track-row:hover { background: var(--cream); border-color: var(--cream-edge); }
.track-row.active { background: var(--cream); border-color: var(--vermillion); }
.track-row { cursor: pointer; }
.track-swatch {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid var(--ink);
  display: inline-block;
}
.track-name {
  font-family: var(--body);
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.track-del {
  background: transparent;
  border: none;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0 0.3rem;
  border-radius: 3px;
}
.track-del:hover { color: var(--vermillion); background: var(--cream); }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0.2rem 0 0; letter-spacing: 0.06em; }

/* Today banner */
.today-banner {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 700;
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
  background: var(--ink);
  color: var(--paper);
  padding: 0.5rem 0.9rem 0.5rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  max-width: 80%;
  white-space: nowrap;
  overflow: hidden;
}
.banner-tag {
  display: inline-block;
  background: var(--vermillion);
  color: var(--paper);
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  padding: 0.18rem 0.55rem;
  border-radius: 2px;
  font-weight: 700;
}
.banner-text {
  font-family: var(--display);
  font-size: 1rem;
  letter-spacing: 0.04em;
}
.banner-notes {
  font-family: var(--body);
  font-size: 0.85rem;
  color: var(--cream);
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
}
.today-banner:hover { background: var(--vermillion-deep); }
/* Footer ----------------------------------------------------------- */
.side-foot {
  margin-top: auto;
  padding-top: 1rem;
  display: grid;
  gap: 0.45rem;
  position: relative;
}
.side-foot::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: var(--ink);
  box-shadow: 0 4px 0 -1px var(--ink-faded);
}
.foot-lbl {
  font-size: 0.62rem;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--ink-faded);
  font-weight: 700;
  margin: 0.4rem 0 0;
}
.btn-share { width: 100%; }

.candidate-modal {
  width: min(560px, 100%);
  max-height: 80vh;
  overflow-y: auto;
  display: grid;
  gap: 0.55rem;
  padding: 1.4rem 1.5rem;
}
.candidate-title { margin: 0; font-size: 1.4rem; }
.candidate-list { list-style: none; margin: 0.2rem 0 0; padding: 0; display: grid; gap: 0.3rem; }
.candidate-btn {
  width: 100%;
  text-align: left;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
  align-items: baseline;
  font: inherit;
  color: var(--ink);
  border-radius: 3px;
}
.candidate-btn:hover { background: var(--paper); border-color: var(--ink); color: var(--vermillion); }
.cand-label {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cand-coord { font-size: 0.72rem; color: var(--ink-soft); }
.row { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.4rem; }

@media (max-width: 720px) {
  .mapview { flex-direction: column-reverse; }
  .sidebar { width: 100%; max-height: 50vh; border-right: none; border-top: 1px solid var(--cream-edge); }
  .sidebar:not(.open) { max-height: 56px; }
}
</style>
