<template>
  <main class="mapview">
    <aside class="sidebar paper" :class="{ open: sidebarOpen }">
      <div class="side-head">
        <router-link to="/" class="back">← Home</router-link>
        <button class="btn-icon" @click="sidebarOpen = !sidebarOpen" :aria-label="sidebarOpen ? 'Collapse' : 'Expand'">
          {{ sidebarOpen ? '⟨' : '⟩' }}
        </button>
      </div>

      <div v-if="loading" class="loading">Charting…</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <template v-else-if="mapData">
        <p class="eyebrow">Voyage</p>
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
          centred {{ formatLat(mapData.center_lat) }} · {{ formatLng(mapData.center_lng) }}
          <br />radius {{ formatRadius(mapData.radius_m) }}
        </p>

        <RadiusSlider v-model="radiusDraft" @update:modelValue="liveRadius" @change="commitRadius" />

        <hr class="rule" />

        <p class="eyebrow tight">Add a place</p>
        <GeocoderSearch placeholder="Search a spot to mark…" @pick="onSearchPick" />
        <button class="locate-link" type="button" @click="markMyLocation" :disabled="locating">
          ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
        </button>
        <p v-if="locateError" class="error sm">{{ locateError }}</p>

        <hr class="rule" />

        <div class="list-head">
          <p class="eyebrow">
            {{ visiblePoints.length }}{{ hiddenCats.size > 0 ? ` / ${mapData.points.length}` : '' }}
            {{ visiblePoints.length === 1 ? 'mark' : 'marks' }}
          </p>
          <button class="btn btn-tiny" @click="startNewPin">+ Drop here</button>
        </div>

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

        <hr class="rule" />

        <div class="list-head">
          <p class="eyebrow">Routes</p>
          <label class="btn btn-tiny gpx-pick">
            + GPX
            <input type="file" accept=".gpx,application/gpx+xml" multiple class="hidden" @change="onGpxFilePick" />
          </label>
        </div>
        <p v-if="gpxError" class="error sm">{{ gpxError }}</p>
        <ul v-if="mapData.tracks && mapData.tracks.length" class="track-list">
          <li v-for="(t, i) in mapData.tracks" :key="t.id" class="track-row">
            <span class="track-swatch" :style="{ background: t.color || trackColor(i) }"></span>
            <span class="track-name">{{ t.name || `Track ${i + 1}` }}</span>
            <button class="track-del" type="button" :title="`Delete ${t.name || 'track'}`" @click="deleteTrack(t.id)">×</button>
          </li>
        </ul>
        <p v-else class="hint mono">Drop a .gpx anywhere on the map.</p>

        <div class="share">
          <p class="lbl">Share this map</p>
          <button class="btn btn-ghost" @click="copyUrl">
            {{ copied ? 'Copied ✓' : 'Copy link' }}
          </button>
        </div>
      </template>
    </aside>

    <div
      class="map-wrap"
      @dragover.prevent="onGpxDragOver"
      @dragleave="onGpxDragLeave"
      @drop.prevent="onGpxDrop"
    >
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
    </div>

    <PointFormModal
      v-if="modal"
      :model-value="modal"
      :is-new="modal.id == null"
      @save="onSave"
      @close="modal = null"
    />
  </main>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import L from 'leaflet'
import { api } from '@/api.js'
import { CATEGORIES, formatLat, formatLng, getMyLocation, parseGPX, trackColor } from '@/util.js'
import PointList from '@/components/PointList.vue'
import PointFormModal from '@/components/PointFormModal.vue'
import PointDetailCard from '@/components/PointDetailCard.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'
import RadiusSlider from '@/components/RadiusSlider.vue'
import CategoryFilters from '@/components/CategoryFilters.vue'

const props = defineProps({
  slug: { type: String, required: true },
})

const mapData = ref(null)
const loading = ref(true)
const error = ref('')
const titleDraft = ref('')
const radiusDraft = ref(5000)
const sidebarOpen = ref(true)
const activeId = ref(null)
const modal = ref(null)
const detail = ref(null)
const copied = ref(false)
const locating = ref(false)
const locateError = ref('')
const hiddenCats = ref(new Set())

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
const pointMarkers = new Map()
const myDot = ref(false) // truthy when blue-dot is shown — used for button styling
let myDotMarker = null
let myAccuracyCircle = null
const trackLines = new Map() // track id → L.polyline
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
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(leaflet)

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
  ;(mapData.value.tracks || []).forEach((t, i) => renderTrack(t, i))
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
    const idx = (mapData.value.tracks || []).length
    const created = await api.addTrack(props.slug, {
      name: name || file.name.replace(/\.gpx$/i, ''),
      color: trackColor(idx),
      gpx_data: text,
    })
    if (!mapData.value.tracks) mapData.value.tracks = []
    mapData.value.tracks.push(created)
    const line = renderTrack(created, idx)
    if (line && leaflet) leaflet.fitBounds(line.getBounds(), { padding: [40, 40] })
  } catch (e) {
    gpxError.value = e.message || 'Could not import GPX.'
  }
}

async function deleteTrack(id) {
  try {
    await api.deleteTrack(props.slug, id)
    mapData.value.tracks = (mapData.value.tracks || []).filter((t) => t.id !== id)
    removeTrackLine(id)
  } catch (e) {
    error.value = e.message
  }
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
  width: 360px;
  max-width: 86vw;
  height: 100%;
  border-right: 1px solid var(--cream-edge);
  border-top: none;
  border-bottom: none;
  border-left: none;
  padding: 1.2rem 1.3rem 1.4rem;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  overflow-y: auto;
  transition: width 220ms ease, padding 220ms ease;
  z-index: 2;
  box-shadow: 4px 0 18px -8px rgba(40, 20, 0, 0.28);
}
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

.title { margin: 0; }
.title-input {
  font-family: var(--display);
  font-size: 1.7rem;
  color: var(--ink);
  background: transparent;
  border: none;
  border-bottom: 1px dotted transparent;
  width: 100%;
  padding: 0.05em 0;
  outline: none;
}
.title-input:focus, .title-input:hover { border-bottom-color: var(--ink-faded); }
.title-input::placeholder { color: var(--ink-faded); font-style: italic; }

.meta { margin: 0.2rem 0 0.4rem; font-size: 0.85rem; line-height: 1.55; }
.rule {
  border: none;
  border-top: 1px solid var(--cream-edge);
  margin: 0.4rem 0 0.2rem;
}
.list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.eyebrow.tight { margin: 0; }

.locate-link {
  background: transparent;
  border: none;
  padding: 0.1rem 0;
  font-family: var(--mono);
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
  justify-self: start;
  margin-top: -0.2rem;
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
.share { margin-top: auto; padding-top: 0.6rem; display: grid; gap: 0.4rem; }

@media (max-width: 720px) {
  .mapview { flex-direction: column-reverse; }
  .sidebar { width: 100%; max-height: 50vh; border-right: none; border-top: 1px solid var(--cream-edge); }
  .sidebar:not(.open) { max-height: 56px; }
}
</style>
