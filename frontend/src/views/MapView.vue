<template>
  <main class="mapview">
    <InfoPanel
      v-if="mapData"
      :tabs="tabs"
      :active="activeTab"
      @update:active="(k) => activeTab = k"
    >
      <template #header>
        <RouterLink to="/" class="dock-back mono" title="Back to all voyages">← Voyages</RouterLink>
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
          <button v-if="hasContent" class="recenter mono" type="button" @click="recenter" title="Re-fit to points + itinerary">↻ Fit</button>
        </p>
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
        <p class="hint mono gpx-hint">
          <span>Trails:</span>
          <span>drop a <code>.gpx</code> on the map</span>
          <span class="sep">·</span>
          <label class="link-pick">
            <span>pick a file</span>
            <input type="file" accept=".gpx,application/gpx+xml" multiple class="hidden" @change="onGpxFilePick" />
          </label>
        </p>
      </template>

      <template #itinerary>
        <Itinerary
          :days="mapData.itinerary || []"
          @add="onAddDay"
          @delete="onDeleteDay"
          @go="onGoDay"
          @edit="(d) => editingDay = d"
        />
      </template>
      <template #more>
        <MoreMenu
          :fallback-lat="mapData.center_lat"
          :fallback-lng="mapData.center_lng"
          :get-bounds="getMapBounds"
          :theme="theme"
          :copied="copied"
          :stats="tripStats"
          :place-name="todayBanner?.day?.label || mapData.title || ''"
          @render-survival="renderSurvival"
          @clear-survival="clearSurvival"
          @copy-url="copyUrl"
        />
      </template>
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
        <span v-if="bannerWx" class="banner-wx mono">
          {{ wxGlyph(bannerWx.code) }} {{ bannerWx.tMax }}° / {{ bannerWx.tMin }}°
        </span>
        <span v-if="todayBanner.sun" class="banner-sun mono">☀ {{ todayBanner.sun.rise }} → {{ todayBanner.sun.set }}</span>
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

      <MapFab
        :glyph="dropMode ? '×' : '+'"
        :title="dropMode ? 'Click the map to drop — or × to cancel' : 'Drop a pin'"
        :class="{ 'is-armed': dropMode }"
        @click="startNewPin"
      />
      <div v-if="dropMode" class="drop-hint mono">Click anywhere on the map to drop your pin</div>

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
        :color="activeTrackColor"
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

    <ItineraryDayModal
      v-if="editingDay"
      :model-value="editingDay"
      @save="(payload) => onPatchDay(editingDay, payload)"
      @locate-candidates="(c) => candidatesFor = c"
      @close="editingDay = null"
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
import SunCalc from 'suncalc'
import { api } from '@/api.js'
// Itinerary + geocode helpers imported below.
import { CATEGORIES, formatLat, formatLng, getMyLocation, parseGPX, trackColor, todayISO } from '@/util.js'
import { geocode } from '@/api.js'
import Itinerary from '@/components/Itinerary.vue'
import PointList from '@/components/PointList.vue'
import PointFormModal from '@/components/PointFormModal.vue'
import ItineraryDayModal from '@/components/ItineraryDayModal.vue'
import PointDetailCard from '@/components/PointDetailCard.vue'
import GeocoderSearch from '@/components/GeocoderSearch.vue'
import CategoryFilters from '@/components/CategoryFilters.vue'
import ElevationProfile from '@/components/ElevationProfile.vue'
import InfoPanel from '@/components/InfoPanel.vue'
import MoreMenu from '@/components/MoreMenu.vue'
import MapFab from '@/components/MapFab.vue'
import { theme } from '@/lib/theme.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'
import { rememberMap } from '@/lib/recents.js'
import { dailyForecast, glyphFor as wxGlyph } from '@/lib/weather.js'

const props = defineProps({
  slug: { type: String, required: true },
})

const mapData = ref(null)
const loading = ref(true)
const error = ref('')
const titleDraft = ref('')
const activeTab = ref('places')
const tabs = [
  { key: 'places', label: 'Places', icon: '📍' },
  { key: 'itinerary', label: 'Itinerary', icon: '🗓' },
  { key: 'more', label: 'More', icon: '⋯' },
]
const activeId = ref(null)
const modal = ref(null)
const detail = ref(null)
const editingDay = ref(null)
const dropMode = ref(false)
watch(dropMode, (on) => {
  document.body.classList.toggle('drop-mode', on)
})
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
const activeTrackColor = computed(() => {
  const t = trailPoints.value.find((x) => x.id === activeTrailPointId.value)
  return t?.color || null
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

function haversineKm(a, b) {
  const R = 6371, toRad = (x) => x * Math.PI / 180
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat), lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}
const tripStats = computed(() => {
  if (!mapData.value) return null
  const ps = mapData.value.points || []
  const trails = ps.filter((p) => p.gpx_data)
  let trailKm = 0, trailDPlus = 0
  for (const t of trails) {
    try {
      const { coords, elevations } = parseGPX(t.gpx_data)
      const series = buildElevationSeries(coords, elevations)
      if (series.length) {
        trailKm += series[series.length - 1].dist / 1000
        trailDPlus += elevationStats(series).gain
      }
    } catch { /* skip bad GPX */ }
  }
  const days = (mapData.value.itinerary || [])
  const located = days.filter((d) => d.lat != null && d.lng != null)
    .sort((a, b) => a.date.localeCompare(b.date))
  let driveKm = 0
  for (let i = 0; i < located.length - 1; i++) driveKm += haversineKm(located[i], located[i + 1])
  return {
    points: ps.length - trails.length,
    trails: trails.length,
    trailKm: Math.round(trailKm * 10) / 10,
    trailDPlus: Math.round(trailDPlus),
    days: days.length,
    driveKm: Math.round(driveKm),
  }
})

const visiblePoints = computed(() => {
  if (!mapData.value) return []
  const filtered = hiddenCats.value.size === 0
    ? mapData.value.points
    : mapData.value.points.filter((p) => !hiddenCats.value.has(p.category))
  // When the user has shared their location, sort by ascending distance —
  // most relevant places first.
  if (myLocation.value) {
    const me = myLocation.value
    return [...filtered].map((p) => ({
      ...p,
      _distKm: haversineKm({ lat: me.lat, lng: me.lng }, { lat: p.lat, lng: p.lng }),
    })).sort((a, b) => a._distKm - b._distKm)
  }
  return filtered
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

// Highlight the active trail polyline (thicken + bring to front) and reset
// the others.
watch(activeTrailPointId, (next) => {
  for (const [id, line] of trackLines.entries()) {
    if (id === next) {
      line.setStyle({ weight: 5, opacity: 1 })
      line.bringToFront()
    } else {
      line.setStyle({ weight: 3, opacity: 0.55 })
    }
  }
})

// Highlight the active point's marker (scale + ring) when it changes.
watch(activeId, (next, prev) => {
  if (prev != null) {
    const prevM = pointMarkers.get(prev)
    prevM?.getElement()?.classList.remove('is-active')
  }
  if (next != null) {
    const nextM = pointMarkers.get(next)
    nextM?.getElement()?.classList.add('is-active')
  }
})

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
const myLocation = ref(null) // { lat, lng } when the user has shared their position
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
    rememberMap(m.slug, m.title, {
      points: (m.points || []).filter((p) => !p.gpx_data).length,
      trails: (m.points || []).filter((p) => p.gpx_data).length,
      days: (m.itinerary || []).length,
    })
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
    zoomControl: false,
    attributionControl: true,
  })
  L.control.zoom({ position: 'topright' }).addTo(leaflet)
  attachTiles()

  const center = [mapData.value.center_lat, mapData.value.center_lng]
  // Initial view: fit to points + itinerary if any, otherwise centre on the map's saved center.
  fitToContent({ initial: true, fallbackCenter: center })

  leaflet.on('click', (e) => {
    if (dropMode.value) {
      // Place a new pin at the clicked location and exit drop mode.
      modal.value = { lat: e.latlng.lat, lng: e.latlng.lng, title: '', comment: '', category: 'note' }
      detail.value = null
      dropMode.value = false
      return
    }
    if (detail.value) closeDetail()
  })

  mapData.value.points.forEach(addPointMarker)
  trailPoints.value.forEach((p, i) => renderTrack(p, i))
  renderItinerary()
}

function makeItineraryIcon(num, isToday = false) {
  return L.divIcon({
    className: `iti-pin-wrapper${isToday ? ' is-today' : ''}`,
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

  const today = todayISO()
  const coords = []
  days.forEach((d, i) => {
    const m = L.marker([d.lat, d.lng], {
      icon: makeItineraryIcon(i + 1, d.date === today),
      title: `${d.label || 'Day'} — drag to refine, click to focus`,
      zIndexOffset: 600,
      draggable: true,
    }).addTo(leaflet)
    if (d.label) {
      m.bindTooltip(d.label, {
        permanent: true,
        direction: 'right',
        offset: [10, 0],
        className: 'iti-tip',
      })
    }
    m.on('click', () => onGoDay(d))
    m.on('dragend', async (e) => {
      const ll = e.target.getLatLng()
      try {
        const updated = await api.patchItineraryDay(props.slug, d.id, { lat: ll.lat, lng: ll.lng })
        const idx = (mapData.value.itinerary || []).findIndex((x) => x.id === d.id)
        if (idx >= 0) {
          mapData.value.itinerary[idx] = { ...mapData.value.itinerary[idx], ...updated }
        }
      } catch (err) {
        // Snap back on failure.
        m.setLatLng([d.lat, d.lng])
        error.value = err?.message || 'Could not move that day.'
      }
    })
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
  // Toggle drop-mode: next click on the map places the pin where the user
  // pointed instead of always at the current viewport centre.
  dropMode.value = !dropMode.value
  if (dropMode.value) detail.value = null
}

function onSelectPoint(p) {
  openDetail(p)
  if (p.gpx_data) {
    activeTrailPointId.value = p.id
    if (leaflet) {
      const line = trackLines.get(p.id)
      if (line) leaflet.fitBounds(line.getBounds(), { padding: [60, 60], animate: true, maxZoom: 14 })
    }
  } else {
    // Switching to a non-trail point: drop any open elevation profile so the
    // map view stays focused on the new pin.
    activeTrailPointId.value = null
    if (leaflet) leaflet.panTo([p.lat, p.lng], { animate: true })
  }
}

function renderTrack(track, idx) {
  try {
    const { coords } = parseGPX(track.gpx_data)
    const isActive = activeTrailPointId.value === track.id
    const line = L.polyline(coords, {
      color: track.color || trackColor(idx),
      weight: isActive ? 5 : 3,
      opacity: isActive ? 1 : (activeTrailPointId.value == null ? 0.85 : 0.5),
      lineCap: 'round',
      lineJoin: 'round',
      bubblingMouseEvents: false,
    }).addTo(leaflet)
    line.on('mouseover', () => line.setStyle({ weight: 5 }))
    line.on('mouseout', () => {
      line.setStyle({ weight: activeTrailPointId.value === track.id ? 5 : 3 })
    })
    line.on('click', (e) => {
      L.DomEvent.stopPropagation(e)
      activeTrailPointId.value = activeTrailPointId.value === track.id ? null : track.id
    })
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

// Itinerary -----------------------------------------------------------
const today = computed(() => todayISO())

// Format an absolute Date as HH:MM in the local civil time at the given
// longitude — mean solar time approximation, accurate enough for sunrise/
// sunset display when the user is browsing from a different timezone.
function fmtHMatLng(d, lng) {
  const utcMin = d.getUTCHours() * 60 + d.getUTCMinutes()
  const offsetMin = Math.round(lng / 15) * 60
  const total = ((utcMin + offsetMin) % 1440 + 1440) % 1440
  const h = Math.floor(total / 60)
  const m = total % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}
function attachSun(banner) {
  if (!banner) return banner
  if (window.matchMedia('(max-width: 720px)').matches) return banner
  const lat = banner.day.lat ?? mapData.value?.center_lat
  const lng = banner.day.lng ?? mapData.value?.center_lng
  if (lat == null || lng == null) return banner
  const t = SunCalc.getTimes(new Date(banner.day.date), lat, lng)
  if (!t.sunrise || !t.sunset || isNaN(t.sunrise) || isNaN(t.sunset)) return banner
  return { ...banner, sun: { rise: fmtHMatLng(t.sunrise, lng), set: fmtHMatLng(t.sunset, lng) } }
}

const todayBanner = computed(() => {
  const days = mapData.value?.itinerary || []
  if (!days.length) return null
  const t = today.value
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))
  const todayDay = sorted.find((d) => d.date === t)
  if (todayDay) {
    const idx = sorted.indexOf(todayDay)
    return attachSun({
      tag: `Day ${idx + 1} / ${sorted.length}`,
      text: (todayDay.label || 'On the road').toUpperCase(),
      notes: todayDay.notes || null,
      day: todayDay,
    })
  }
  const future = sorted.find((d) => d.date > t)
  if (future) {
    const ms = new Date(future.date) - new Date(t)
    const days = Math.floor(ms / 86400000)
    const tag = days >= 1 ? `T-${days}d` : `T-<1d`
    return attachSun({
      tag,
      text: `Next: ${(future.label || 'Untitled').toUpperCase()}`,
      notes: future.notes || null,
      day: future,
    })
  }
  return null
})

// Forecast for today's banner — populated lazily on day change.
const bannerWx = ref(null)
watch(
  () => todayBanner.value?.day,
  async (day) => {
    if (!day || day.lat == null || day.lng == null) { bannerWx.value = null; return }
    bannerWx.value = await dailyForecast(day.lat, day.lng, day.date)
  },
  { immediate: true },
)

async function onAddDay(payload) {
  try {
    const day = await api.addItineraryDay(props.slug, payload)
    if (!mapData.value.itinerary) mapData.value.itinerary = []
    mapData.value.itinerary = [...mapData.value.itinerary, day].sort((a, b) => a.date.localeCompare(b.date))
  } catch (e) { error.value = e.message }
}

async function onDeleteDay(day) {
  try {
    await api.deleteItineraryDay(props.slug, day.id)
    mapData.value.itinerary = mapData.value.itinerary.filter((d) => d.id !== day.id)
  } catch (e) { error.value = e.message }
}

async function onPatchDay(day, payload) {
  try {
    const updated = await api.patchItineraryDay(props.slug, day.id, payload)
    const idx = (mapData.value.itinerary || []).findIndex((d) => d.id === day.id)
    if (idx >= 0) {
      mapData.value.itinerary[idx] = { ...mapData.value.itinerary[idx], ...updated }
      mapData.value.itinerary = [...mapData.value.itinerary].sort((a, b) => a.date.localeCompare(b.date))
    }
    editingDay.value = null
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
    myLocation.value = { lat: loc.lat, lng: loc.lng }
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
    myLocation.value = { lat: loc.lat, lng: loc.lng }
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

function copyUrl() {
  navigator.clipboard.writeText(window.location.href)
  copied.value = true
  setTimeout(() => (copied.value = false), 1800)
}

const hasContent = computed(() => {
  if (!mapData.value) return false
  const ps = mapData.value.points || []
  const its = (mapData.value.itinerary || []).filter((d) => d.lat != null && d.lng != null)
  return ps.length > 0 || its.length > 0
})

function collectFitCoords() {
  if (!mapData.value) return []
  const out = []
  for (const p of mapData.value.points || []) out.push([p.lat, p.lng])
  for (const d of mapData.value.itinerary || []) {
    if (d.lat != null && d.lng != null) out.push([d.lat, d.lng])
  }
  return out
}

function fitToContent({ initial = false, fallbackCenter = null } = {}) {
  if (!leaflet) return
  const coords = collectFitCoords()
  if (coords.length === 0) {
    if (initial && fallbackCenter) leaflet.setView(fallbackCenter, 6)
    return
  }
  if (coords.length === 1) {
    leaflet.setView(coords[0], 11, { animate: !initial })
    return
  }
  const bounds = L.latLngBounds(coords)
  leaflet.fitBounds(bounds, { padding: [60, 60], animate: !initial, maxZoom: 13 })
}

function recenter() { fitToContent() }

// Escape: cancel drop-mode > close detail card > close active trail.
function onEsc(e) {
  if (e.key !== 'Escape') return
  if (dropMode.value) { dropMode.value = false; return }
  if (detail.value) { closeDetail(); return }
  if (activeTrailPointId.value != null) { activeTrailPointId.value = null; return }
}
onMounted(() => window.addEventListener('keydown', onEsc))

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEsc)
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
.error { color: var(--vermillion-deep); }

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

.recenter {
  margin-left: auto;
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  color: var(--ink-soft);
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: color 90ms, border-color 90ms;
}
.recenter:hover { color: var(--vermillion); border-color: var(--vermillion); }

.dock-back {
  display: inline-block;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  text-decoration: none;
  margin-bottom: 0.35rem;
  align-self: flex-start;
}
.dock-back:hover { color: var(--vermillion); }

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

/* Floating "show me" map control — aligns under the 56px FAB at right: 16px */
.locate-me {
  position: absolute;
  bottom: 88px; /* sits 16px above the FAB top edge (FAB: bottom 16 + 56 = 72) */
  right: 16px;
  z-index: 700;
  width: 56px;
  height: 56px;
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--ink);
  border-radius: 50%;
  cursor: pointer;
  display: grid;
  place-items: center;
  box-shadow: 0 3px 0 var(--ink), 0 6px 12px rgba(0, 0, 0, 0.18);
  transition: transform 80ms ease, background 120ms ease, box-shadow 120ms ease;
}
.locate-me:hover { background: var(--ink); color: var(--paper); }
@media (max-width: 720px) {
  .locate-me { bottom: 152px; } /* FAB top (80+56=136) + 16px gap */
}
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
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0.2rem 0 0; letter-spacing: 0.06em; }
.gpx-hint {
  padding-top: 0.5rem;
  border-top: 1px dashed var(--cream-edge);
  margin-top: 0.6rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: baseline;
}
.gpx-hint code { font-family: var(--mono); color: var(--vermillion); padding: 0 2px; }
.gpx-hint .sep { color: var(--ink-faded); opacity: 0.6; }

/* Drop-mode floating hint: pinned just above the FAB. */
.drop-hint {
  position: absolute;
  right: 88px;
  bottom: 28px;
  padding: 0.55rem 0.85rem;
  background: var(--ink);
  color: var(--paper);
  border-radius: 4px;
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  z-index: 850;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25);
  animation: drop-hint-pop 200ms ease-out;
}
@keyframes drop-hint-pop {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}
:deep(.map-fab.is-armed) {
  background: var(--ink) !important;
  box-shadow: 0 0 0 4px var(--vermillion), 0 2px 8px rgba(0, 0, 0, 0.3) !important;
}
.link-pick {
  cursor: pointer;
  color: var(--vermillion);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.link-pick:hover { color: var(--vermillion-deep); }

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
.banner-sun { font-size: 0.78rem; color: var(--ink-soft); }
.banner-wx { font-size: 0.82rem; color: var(--paper); font-weight: 600; }
.banner-notes {
  font-family: var(--body);
  font-size: 0.85rem;
  color: var(--cream);
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
}
.today-banner:hover { background: var(--vermillion-deep); }

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

</style>
