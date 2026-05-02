<template>
  <main class="mapview" :class="{ 'dock-collapsed': dockCollapsed, 'mode-plan': mode === 'plan' }">
    <!-- Plan mode: full-page editable planner. Mounted side-by-side with the
         map shell and toggled via v-show so Leaflet (initialized once on mount)
         is never torn down — switching modes is instant and the cached tiles
         + draggable day pins survive the swap. -->
    <PlanView
      v-if="mapData"
      v-show="mode === 'plan'"
      ref="planRef"
      class="plan-pane"
      :title="mapData.title"
      :days="mapData.itinerary || []"
      :points="mapData.points || []"
      :bias="searchBias"
      @update:title="onTitleSave"
      @add-day="onAddDay"
      @delete-day="onDeleteDay"
      @patch-day="({ day, payload }) => onPatchDay(day, payload)"
      @edit-day="(d) => editingDay = d"
      @add-pin="onAddPinToDay"
      @attach-pin="onAttachPoint"
      @detach-pin="onDetachPoint"
      @edit-pin="onEditPin"
      @delete-pin="onDeletePinFromList"
      @open-paste="showPaste = true"
    >
      <template #mode-toggle>
        <ModeToggleControl :mode="mode" @change="setMode" />
      </template>
      <template #head-tools>
        <button class="head-icon mono" type="button" :title="copied ? 'Read-only link copied' : 'Copy read-only share link'" @click="copyShareUrl">{{ copied ? '✓' : '↗' }}</button>
        <ThemeToggle class="head-icon" />
        <button class="head-icon mono" type="button" title="Tools — survival, sun, offline tiles" @click.stop="toolsOpen = !toolsOpen">⋯</button>
        <button class="head-icon mono" type="button" title="Re-fit map to all points and days" @click="recenter">↻</button>
        <RouterLink :to="{ path: '/', query: { home: 1 } }" class="head-icon mono" title="Start a new voyage" style="text-decoration: none;">＋</RouterLink>
      </template>
    </PlanView>

    <!-- Map shell: dockless. The InfoPanel/MobileSheet was the old "Trip /
         Pins / Tools" drawer; it now lives as PlanView (table) + the Tools
         popover triggered from the topbar. The map fills the screen. -->
    <div v-show="mode === 'map'" class="map-shell">
    <div
      class="map-wrap"
      @dragover.prevent="onGpxDragOver"
      @dragleave="onGpxDragLeave"
      @drop.prevent="onGpxDrop"
    >
      <TripRibbon
        v-if="(mapData?.itinerary || []).length"
        class="trip-ribbon"
        :days="mapData.itinerary"
        :selected-day-id="selectedRibbonDayId"
        @go="onGoDay"
      />
      <div
        v-if="todayBanner && !bannerDismissed"
        class="today-banner"
        :class="{ 'is-live': todayBanner.live, 'is-future': !todayBanner.live, 'with-ribbon': hasRibbon }"
      >
        <button class="banner-main" type="button" :title="`Center on ${todayBanner.day.label || 'this day'}`" @click="onGoDay(todayBanner.day)">
          <div class="banner-row banner-row-primary">
            <span class="banner-tag mono">{{ todayBanner.tag }}</span>
            <span class="banner-text">{{ todayBanner.text }}</span>
          </div>
          <div
            v-if="bannerWx || todayBanner.sun || todayBanner.notes || (todayBanner.live && nextLegInfo)"
            class="banner-row banner-row-meta mono"
          >
            <span v-if="bannerWx" class="banner-wx">
              {{ wxGlyph(bannerWx.code) }} {{ bannerWx.tMax }}° / {{ bannerWx.tMin }}°
            </span>
            <span v-if="todayBanner.sun" class="banner-sun">
              ☀ {{ todayBanner.sun.rise }} → {{ todayBanner.sun.set }}
              <template v-if="todayBanner.live && sunsetCountdown"> · sunset {{ sunsetCountdown }}</template>
            </span>
            <span v-if="todayBanner.live && nextLegInfo" class="banner-next">↳ next: {{ nextLegInfo }}</span>
            <span v-if="todayBanner.notes" class="banner-notes">{{ todayBanner.notes }}</span>
          </div>
        </button>
        <div class="banner-actions">
          <button
            v-if="todayBanner.live && nextStop"
            class="banner-advance mono"
            type="button"
            title="Mark this stop as completed"
            :aria-label="`Mark ${todayBanner.day.label || 'this stop'} as completed and jump to ${nextStop.label || 'the next stop'}`"
            @click="advanceToNextStop"
          ><span class="banner-advance-tick" aria-hidden="true">✓</span> Made it →</button>
          <button class="banner-action" type="button" title="Edit this day" @click="editingDay = todayBanner.day">✎</button>
          <button class="banner-close" type="button" title="Hide for this session" @click="dismissBanner">×</button>
        </div>
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
        :armed="dropMode"
        :hidden="!!detail"
        @drop="onFabDrop"
        @search="onFabSearch"
        @add-stop="onFabAddStop"
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

      <!-- Top-left: trip identity (editable title + offline badge). Kept thin
           and discreet so it doesn't compete with the ribbon for attention.
           On mobile, the trip ribbon already shows the trip identity at the
           top of the screen, and the title pill collides with the topbar
           pill on the right — so we hide it whenever the ribbon is present. -->
      <div v-if="mapData" class="map-topleft" :class="{ 'has-ribbon': hasRibbon }">
        <input
          v-model="titleDraft"
          class="map-topleft-title"
          placeholder="Untitled voyage"
          maxlength="120"
          :title="titleDraft || 'Untitled voyage'"
          @blur="commitTitle"
          @keydown.enter="$event.target.blur()"
        />
        <span v-if="offlineSnapshot" class="offline-badge mono" title="No network — showing the last copy saved on this device.">⤬ offline</span>
      </div>

      <!-- Map-mode floating top-right toolbar. Compact: just the mode toggle
           + the actions that need a home now that the dock is gone. -->
      <div v-if="mapData" class="map-topbar">
        <ModeToggleControl :mode="mode" @change="setMode" />
        <div class="map-topbar-actions">
          <button v-if="hasContent" class="head-icon mono" type="button" @click="recenter" title="Re-fit map to all points and days">↻</button>
          <button class="head-icon mono" type="button" :title="copied ? 'Read-only link copied' : 'Copy read-only share link'" @click="copyShareUrl">{{ copied ? '✓' : '↗' }}</button>
          <ThemeToggle class="head-icon" />
          <button class="head-icon mono" type="button" title="Tools — survival, sun, offline tiles" @click.stop="toolsOpen = !toolsOpen">⋯</button>
        </div>
        <span v-if="offlineSnapshot" class="offline-badge mono" title="No network — showing the last copy saved on this device.">⤬ offline</span>
      </div>
    </div>
    </div>

    <!-- Soft-delete toast: hoisted out of .map-shell so it stays visible in
         Plan mode too (the wishlist's × goes through the same scheduler).
         Both pin and day deletes funnel through here so the undo affordance
         is uniform. -->
    <Transition name="toast">
      <div v-if="pendingDelete" class="del-toast" role="status" aria-live="polite">
        <span class="del-toast-text">{{ pendingDelete.message }}</span>
        <button type="button" class="del-toast-undo mono" @click="undoDelete">Undo</button>
      </div>
    </Transition>

    <!-- Share-copy confirmation. The ↗→✓ icon swap on the button is easy to
         miss, so a small toast restates "Read-only link copied" near the
         topbar for the same 1.8s window the icon stays flipped. -->
    <Transition name="toast">
      <div v-if="copied" class="share-toast mono" role="status" aria-live="polite">
        ✓ Read-only link copied
      </div>
    </Transition>

    <!-- Tools popover — shared by both modes. Anchored to the ⋯ button in the
         topbar (Map mode) or in the Plan head-tools slot (Plan mode). Lives
         outside the map-shell so it floats above either layout. v-show (not
         v-if) so child state — like SurvivalLayer's selected-kinds set — is
         retained across open/close cycles. -->
    <Transition name="reveal">
      <div v-if="mapData" v-show="toolsOpen" class="tools-popover paper" @click.stop>
        <div class="tools-head">
          <p class="eyebrow">Tools</p>
          <button class="tools-close" type="button" @click="toolsOpen = false">×</button>
        </div>
        <MoreMenu
          :fallback-lat="mapData.center_lat"
          :fallback-lng="mapData.center_lng"
          :get-bounds="getMapBounds"
          :theme="theme"
          :place-name="todayBanner?.day?.label || ''"
          :next-leg-bbox="nextLegBbox"
          @render-survival="renderSurvival"
          @clear-survival="clearSurvival"
        />
        <div class="tools-extra">
          <button class="btn btn-tiny btn-ghost" type="button" @click="openPasteFromTools">Paste import…</button>
          <label class="btn btn-tiny btn-ghost" :title="`Drop a .gpx track on the map, or pick a file`">
            GPX import…
            <input type="file" accept=".gpx,application/gpx+xml" multiple class="hidden" @change="onGpxFilePick" />
          </label>
        </div>
      </div>
    </Transition>

    <!-- Hoisted PasteImportModal so it can be opened from Plan mode (PlanView
         emits @open-paste) or from the Tools popover in Map mode. The one
         inside Itinerary.vue still works for the mobile-sheet path. -->
    <PasteImportModal
      v-if="showPaste"
      :default-year="defaultYearForPaste"
      :bias="searchBias"
      @close="showPaste = false"
      @import="onPasteImportTopLevel"
    />

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
      :bias="searchBias"
      :existing-pins="pinCandidates"
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
import { CATEGORIES, formatLat, formatLng, getMyLocation, parseGPX, trackColor, todayISO, coordsToGPX } from '@/util.js'
import { geocode, categoryFromOSM, reverseGeocode } from '@/api.js'
import Itinerary from '@/components/organisms/Itinerary.vue'
import PointList from '@/components/molecules/PointList.vue'
import PointFormModal from '@/components/organisms/PointFormModal.vue'
import ItineraryDayModal from '@/components/organisms/ItineraryDayModal.vue'
import PointDetailCard from '@/components/organisms/PointDetailCard.vue'
import GeocoderSearch from '@/components/molecules/GeocoderSearch.vue'
import CategoryFilters from '@/components/molecules/CategoryFilters.vue'
import ElevationProfile from '@/components/molecules/ElevationProfile.vue'
import InfoPanel from '@/components/organisms/InfoPanel.vue'
import MoreMenu from '@/components/molecules/MoreMenu.vue'
import MapFab from '@/components/molecules/MapFab.vue'
import ThemeToggle from '@/components/atoms/ThemeToggle.vue'
import TripRibbon from '@/components/molecules/TripRibbon.vue'
import PlanView from '@/components/organisms/PlanView.vue'
import PasteImportModal from '@/components/organisms/PasteImportModal.vue'
import ModeToggleControl from '@/components/atoms/ModeToggleControl.vue'
import { RouterLink, useRouter } from 'vue-router'
import { theme } from '@/lib/theme.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'
import { rememberMap, updateRecentStats } from '@/lib/recents.js'
import { routeLeg, fmtMinutes } from '@/lib/routing.js'
import { writeSnapshot } from '@/lib/snapshot.js'
import { extractId, buildMapSlug } from '@/lib/slug.js'
import { dailyForecast, glyphFor as wxGlyph } from '@/lib/weather.js'
import { buildTipNode } from '@/lib/tooltip.js'

const props = defineProps({
  slug: { type: String, required: true },
})

// `slug.value` is the raw route param — may be either the canonical 8-char
// id (legacy URLs) or "name-slug-{id}" (the new readable format). Every
// API call, storage key, and recents lookup wants the canonical id; only
// the share URL wants a display-friendly form.
const slug = computed(() => extractId(slug.value))

const mapData = ref(null)
const loading = ref(true)
const error = ref('')
const titleDraft = ref('')
const activeTab = ref('itinerary')
const dockCollapsed = ref(false)

// View mode: 'plan' (full-page editable planner — table of stops + pin grid)
// or 'map' (map-first, no left dock on desktop). Persisted per slug because a
// trip in active travel wants Map by default; a trip being prepared wants Plan.
const modeStorageKey = computed(() => `voyage-mode:${slug.value}`)
const mode = ref('plan')
onMounted(() => {
  const saved = localStorage.getItem(modeStorageKey.value)
  if (saved === 'plan' || saved === 'map') mode.value = saved
})
function setMode(next) {
  mode.value = next
  try { localStorage.setItem(modeStorageKey.value, next) } catch { /* private mode */ }
}

// Mobile media query: drives whether the dock-vs-sheet variant of InfoPanel
// renders, and also whether the plan-mode top bar collapses to a tighter row.
const mqMobile = window.matchMedia('(max-width: 720px)')
const isMobile = ref(mqMobile.matches)
function onMqChange(e) { isMobile.value = e.matches }
onMounted(() => mqMobile.addEventListener('change', onMqChange))
onBeforeUnmount(() => mqMobile.removeEventListener('change', onMqChange))

// Tools popover state: holds the MoreMenu (survival, sun, precache) and Paste
// import — surfaced in both modes via a top-right ⋯ button so the dock-only
// tools don't disappear when the dock does.
const toolsOpen = ref(false)
const showPaste = ref(false)
function openPasteFromTools() { toolsOpen.value = false; showPaste.value = true }
// No emoji — the cream/ink palette plus typographic eyebrows do the visual
// work; color emoji clash with the paper aesthetic. Glyphs below are
// monoglyph unicode marks (chevron / pin-shape / dots) that pick up the
// surrounding text color.
const tabs = [
  { key: 'itinerary', label: 'Trip', icon: '◷' },
  { key: 'places', label: 'Pins', icon: '⌖' },
  { key: 'more', label: 'Tools', icon: '⋯' },
]
// Default to the Trip tab — users open the app to plan, not to browse pins.
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
  const series = buildElevationSeries(coords, elevations)
  // OSM-derived trails ship without elevation — the elevation profile would
  // render an empty SVG and bare meta line. Suppress it so the user isn't
  // greeted by a pointless empty card.
  if (!series.some((s) => s.ele != null)) return []
  return series
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
// Driving legs cache (pairKey → { km, minutes, source }). Refreshed lazily as
// itinerary days change.
const drivingLegs = ref({})
function legPairKey(a, b) { return `${a.id}>${b.id}` }
async function refreshDrivingLegs() {
  const days = (mapData.value?.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .sort((a, b) => a.date.localeCompare(b.date))
  for (let i = 0; i < days.length - 1; i++) {
    const a = days[i], b = days[i + 1]
    const k = legPairKey(a, b)
    if (drivingLegs.value[k]) continue
    const leg = await routeLeg({ lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng })
    if (leg) drivingLegs.value = { ...drivingLegs.value, [k]: leg }
  }
}
watch(() => mapData.value?.itinerary, () => refreshDrivingLegs(), { immediate: true, deep: true })

const tripStats = computed(() => {
  if (!mapData.value) return null
  const ps = mapData.value.points || []
  const trails = ps.filter((p) => p.category === 'trail')
  // Trail km / D+ rely on GPX. Points pinned via the Trail Finder don't have
  // GPX, so they count toward `trails` but not toward distance/elevation totals.
  const trailsWithGPX = trails.filter((p) => p.gpx_data)
  let trailKm = 0, trailDPlus = 0
  for (const t of trailsWithGPX) {
    try {
      const { coords, elevations } = parseGPX(t.gpx_data)
      const series = buildElevationSeries(coords, elevations)
      if (series.length) {
        trailKm += series[series.length - 1].dist / 1000
        trailDPlus += elevationStats(series).gain || 0
      }
    } catch { /* skip bad GPX */ }
  }
  // Match the Itinerary header: walk all days in date order, sum OSRM legs
  // only (no haversine fallback) so the two displays agree.
  const days = [...(mapData.value.itinerary || [])].sort((a, b) =>
    a.date.localeCompare(b.date),
  )
  let driveKm = 0, driveMin = 0
  for (let i = 0; i < days.length - 1; i++) {
    const a = days[i], b = days[i + 1]
    if (a.lat == null || a.lng == null || b.lat == null || b.lng == null) continue
    const leg = drivingLegs.value[legPairKey(a, b)]
    if (leg) {
      driveKm += leg.km
      driveMin += leg.minutes
    }
  }
  // Trip days = sum of every stop's span. Single-day stops contribute 1;
  // multi-day stops contribute (end_date - date + 1).
  const tripDays = days.reduce((acc, d) => acc + Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1, 0)
  return {
    points: ps.length - trails.length,
    trails: trails.length,
    trailKm: Math.round(trailKm * 10) / 10,
    trailDPlus: Math.round(trailDPlus),
    days: tripDays,
    driveKm: Math.round(driveKm),
    driveMin: driveMin > 0 ? driveMin : null,
    driveMinFmt: driveMin > 0 ? fmtMinutes(driveMin) : null,
  }
})

// "Wishlist only" toggle — when off, the Pins tab hides points already
// attached to an itinerary day (since those live under the Trip tab now).
const showAllPins = ref(false)

// Pool the Pins tab works from — wishlist (unattached) by default.
const pinsTabPoints = computed(() => {
  if (!mapData.value) return []
  if (showAllPins.value) return mapData.value.points
  return (mapData.value.points || []).filter((p) => p.itinerary_day_id == null)
})

// Map-marker visibility: every pin shows on the map by default; only the
// category filter hides markers. The Pins-tab Unplanned/All toggle is a
// LIST filter, not a map filter — attaching a pin to a day shouldn't make
// it disappear from the map.
const mapPoints = computed(() => {
  if (!mapData.value) return []
  const pool = mapData.value.points || []
  return hiddenCats.value.size === 0
    ? pool
    : pool.filter((p) => !hiddenCats.value.has(p.category))
})

const visiblePoints = computed(() => {
  if (!mapData.value) return []
  const pool = pinsTabPoints.value
  const filtered = hiddenCats.value.size === 0
    ? pool
    : pool.filter((p) => !hiddenCats.value.has(p.category))
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

watch(mapPoints, (next) => {
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

// Re-render itinerary markers whenever the day-attachment of a pin changes
// so the "+N" badge on each iti-pin stays accurate. Cheap key — just a
// stringified per-day count, so we re-render once per attach/detach.
watch(
  () => {
    const points = mapData.value?.points || []
    const counts = {}
    for (const p of points) {
      if (p.itinerary_day_id != null) {
        counts[p.itinerary_day_id] = (counts[p.itinerary_day_id] || 0) + 1
      }
    }
    return JSON.stringify(counts)
  },
  () => renderItinerary(),
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

// Keep the recents stats in sync as the user edits the map. Without this the
// home page would still report whatever counts existed when the map last
// loaded (a recurring "0 pins" bug).
function tripDaysOf(itin) {
  return (itin || []).reduce((acc, d) => acc + Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1, 0)
}
watch(
  () => mapData.value && [
    (mapData.value.points || []).length,
    (mapData.value.points || []).filter((p) => p.category === 'trail').length,
    tripDaysOf(mapData.value.itinerary),
  ],
  (next) => {
    if (!next || !mapData.value) return
    const trails = (mapData.value.points || []).filter((p) => p.category === 'trail').length
    updateRecentStats(slug.value, {
      points: (mapData.value.points || []).length - trails,
      trails,
      days: tripDaysOf(mapData.value.itinerary),
    })
  },
)

// Mirror the live in-memory map into IndexedDB so the next cold-start picks
// up every mutation, not just whatever the last server fetch returned.
// Fire-and-forget — storage failures (private mode, quota, etc.) shouldn't
// disturb the UI.
watch(
  () => mapData.value,
  (next) => { if (next) writeSnapshot(slug.value, next) },
  { deep: true },
)

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
const survivalGroup = ref(null)
function getMapBounds() { return leaflet?.getBounds() }

// Bias passed to geocoder: prefer the visible map area; fall back to the
// seed center with a generous radius so first-load searches still get results.
const mapBboxBumper = ref(0) // tick to invalidate searchBias when the map moves
const searchBias = computed(() => {
  // Touch the bumper so this re-evaluates on map move.
  mapBboxBumper.value
  if (leaflet) {
    const b = leaflet.getBounds()
    return { bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()] }
  }
  if (mapData.value) {
    return { lat: mapData.value.center_lat, lng: mapData.value.center_lng, radiusKm: 800 }
  }
  return null
})

// "Existing pins" candidates for the day editor and bulk import — non-trail
// pins, with the category emoji + a short location hint.
const pinCandidates = computed(() => {
  if (!mapData.value) return []
  return (mapData.value.points || [])
    .filter((p) => !p.gpx_data && p.title)
    .map((p) => ({
      id: p.id,
      lat: p.lat,
      lng: p.lng,
      label: p.title,
      sublabel: `${formatLat(p.lat)} · ${formatLng(p.lng)}`,
      icon: emojiByCategory[p.category] || '📍',
    }))
})
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

// True while we're showing data that came from IndexedDB without a fresh
// network round-trip. The banner flips off as soon as the background refresh
// resolves with a real server payload.
const offlineSnapshot = ref(false)

function adoptMap(m, { fromSnapshot = false } = {}) {
  mapData.value = m
  titleDraft.value = m.title || ''
  offlineSnapshot.value = fromSnapshot
  rememberMap(
    m.slug,
    m.title,
    {
      points: (m.points || []).filter((p) => p.category !== 'trail').length,
      trails: (m.points || []).filter((p) => p.category === 'trail').length,
      days: (m.itinerary || []).reduce((acc, d) => acc + Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1, 0),
    },
    { lastCenter: { lat: m.center_lat, lng: m.center_lng } },
  )
  // Upgrade legacy `/m/{id}` URLs to the readable `/m/{name-slug}-{id}` form
  // once we know the title. router.replace keeps history clean and doesn't
  // remount the view (the :slug param value is the id-equivalent, so route
  // resolution + loaded data don't change).
  syncUrlSlug(m)
}

const router = useRouter()
function syncUrlSlug(m) {
  const desired = buildMapSlug({ title: m.title, slug: m.slug })
  if (!desired || desired === props.slug) return
  const current = router.currentRoute.value
  // Only upgrade `/m/...` and `/v/...` routes — never push the user from
  // viewer to host or vice versa. Skip if a different route is active (the
  // user navigated mid-load).
  if (current.name !== 'map' && current.name !== 'viewer') return
  router.replace({ name: current.name, params: { slug: desired }, query: current.query, hash: current.hash })
}

onMounted(async () => {
  try {
    const { cached, refresh } = await api.getMapWithSnapshot(slug.value)

    // Render the snapshot immediately when we have one — this is the whole
    // point of the IndexedDB layer: cold-start in the van takes ~0ms instead
    // of waiting on a (possibly failing) request.
    if (cached) {
      adoptMap(cached, { fromSnapshot: true })
      loading.value = false
      await nextTick()
      initLeaflet()
      const today = todayISO()
      const day = (mapData.value.itinerary || []).find((d) => d.date === today)
      if (day && day.lat != null && day.lng != null && leaflet) {
        leaflet.setView([day.lat, day.lng], 11)
      }
    }

    let fresh = null
    try {
      fresh = await refresh
    } catch (netErr) {
      // No snapshot AND no network = real error. Otherwise leave the cached
      // copy in place and show the offline badge.
      if (!cached) throw netErr
      offlineSnapshot.value = true
      return
    }

    adoptMap(fresh, { fromSnapshot: false })
    if (!cached) {
      // First-ever load on this device — wait for the fresh payload before
      // mounting Leaflet, same flow as before the snapshot layer existed.
      loading.value = false
      await nextTick()
      initLeaflet()
      const today = todayISO()
      const day = (mapData.value.itinerary || []).find((d) => d.date === today)
      if (day && day.lat != null && day.lng != null && leaflet) {
        leaflet.setView([day.lat, day.lng], 11)
      }
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
  // Bottom-LEFT now that the dock is gone — leaves the bottom-right column
  // (locate-me + FAB) uncluttered, so the user's two main +/− interactions
  // (zoom map vs add to trip) don't visually compete.
  L.control.zoom({ position: 'bottomleft' }).addTo(leaflet)
  attachTiles()

  // Keep Leaflet's cached container size in sync with reality. Without this,
  // any resize that happens after init (ribbon mounts after first frame,
  // banner appears, viewport rotation, etc.) leaves the click→latlng math
  // anchored to the old size — so dropped pins land tens of pixels off
  // visually, which at zoom 12 means kilometres on the ground (the
  // "Angels Landing → Kane County" reverse-geocode bug).
  attachMapResizeObserver()

  const center = [mapData.value.center_lat, mapData.value.center_lng]
  // Initial view: fit to points + itinerary if any, otherwise centre on the map's saved center.
  fitToContent({ initial: true, fallbackCenter: center })

  leaflet.on('moveend', () => {
    mapBboxBumper.value++
    spreadOverlappingPins()
    hideOverlappingLabels()
  })
  leaflet.on('zoomend', () => {
    mapBboxBumper.value++
    applyZoomDensity()
    spreadOverlappingPins()
    hideOverlappingLabels()
  })
  applyZoomDensity()

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

let mapResizeObserver = null
function attachMapResizeObserver() {
  if (!mapEl.value || typeof ResizeObserver === 'undefined') return
  if (mapResizeObserver) mapResizeObserver.disconnect()
  // animate:false — invalidateSize on a first-load resize would otherwise pan
  // away from the freshly-fitted bounds.
  mapResizeObserver = new ResizeObserver(() => {
    if (leaflet) leaflet.invalidateSize({ animate: false, pan: false })
  })
  mapResizeObserver.observe(mapEl.value)
}

function makeItineraryIcon(num, isToday = false, attachedPinCount = 0) {
  // Decoration for days that have attached pins — at low zoom the actual
  // category pins overlap (and lose to) the iti-pin's z-index, so without
  // this badge users can't tell that any pins exist on a 10-stop overview
  // until they drill into a region.
  const badge = attachedPinCount > 0
    ? `<span class="iti-pin-pins" aria-hidden="true">+${attachedPinCount}</span>`
    : ''
  return L.divIcon({
    className: `iti-pin-wrapper${isToday ? ' is-today' : ''}`,
    html: `<div class="iti-pin"><span>${num}</span></div>${badge}`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

function renderItinerary() {
  if (!leaflet) return
  for (const m of itineraryMarkers.values()) leaflet.removeLayer(m)
  itineraryMarkers.clear()
  clearLegLines()

  const stops = (mapData.value?.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))

  const today = todayISO()
  // Count attached pins per day so the iti-pin badge can advertise them at
  // overview zoom (where the actual pins disappear under the day chip).
  const pinsByDay = new Map()
  for (const p of mapData.value?.points || []) {
    if (p.itinerary_day_id != null) {
      pinsByDay.set(p.itinerary_day_id, (pinsByDay.get(p.itinerary_day_id) || 0) + 1)
    }
  }
  let cumulative = 0
  stops.forEach((d) => {
    const end = d.end_date || d.date
    const span = Math.round((new Date(end) - new Date(d.date)) / 86400000) + 1
    const startNum = cumulative + 1
    const endNum = cumulative + span
    const isToday = today >= d.date && today <= end
    const pinCount = pinsByDay.get(d.id) || 0
    const m = L.marker([d.lat, d.lng], {
      icon: makeItineraryIcon(span > 1 ? `${startNum}–${endNum}` : startNum, isToday, pinCount),
      title: `${d.label || 'Stop'} — drag to refine, click to focus`,
      zIndexOffset: 600,
      draggable: true,
    }).addTo(leaflet)
    const dayChip = span > 1 ? `Day ${startNum}–${endNum}` : `Day ${startNum}`
    const cleanLabel = d.label
      ? d.label.replace(/^\s*Day\s*\d+(?:\s*[—\-–]\s*\d+)?\s*[—\-–:·]\s*/i, '').trim()
      : ''
    // Two-part tip so CSS can hide the label half at lower zooms — keeps
    // the trip readable when zoomed out while preserving detail when in.
    // Built as a DOM node (not innerHTML) so user-typed labels can't smuggle
    // <img onerror> or other HTML — Leaflet renders nodes as-is.
    m.bindTooltip(buildTipNode(dayChip, cleanLabel), {
      permanent: true,
      direction: 'right',
      offset: [10, 0],
      className: 'iti-tip',
    })
    m.on('click', () => onGoDay(d))
    m.on('dragend', async (e) => {
      const ll = e.target.getLatLng()
      try {
        const updated = await api.patchItineraryDay(slug.value, d.id, { lat: ll.lat, lng: ll.lng })
        const idx = (mapData.value.itinerary || []).findIndex((x) => x.id === d.id)
        if (idx >= 0) {
          mapData.value.itinerary[idx] = { ...mapData.value.itinerary[idx], ...updated }
        }
      } catch (err) {
        m.setLatLng([d.lat, d.lng])
        error.value = err?.message || 'Could not move that stop.'
      }
    })
    itineraryMarkers.set(d.id, m)
    cumulative += span
  })

  attachLegLines(stops)
  attachLegLabels(stops)
  applyZoomDensity()
  spreadOverlappingPins()
  hideOverlappingLabels()
}

// Hide stacked permanent tooltips: walk markers in trip order and hide the
// label of any whose rendered rect intersects an earlier (already-visible)
// label. Leaves the day pin itself visible — only the text label is hidden.
// Then sweep leg labels and hide any that overlap a still-visible day
// tooltip — leg chips read as supporting info, so they yield to the pin.
// Runs after every render and on zoom — collisions look different at every
// zoom level.
function rectsOverlap(a, b) {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom)
}
function hideOverlappingLabels() {
  if (!leaflet) return
  const placed = []
  const days = (mapData.value?.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
  for (const d of days) {
    const m = itineraryMarkers.get(d.id)
    const tip = m?.getTooltip()
    const el = tip?.getElement?.()
    if (!el) continue
    el.classList.remove('is-collided')
    const rect = el.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) continue
    const collides = placed.some((r) => rectsOverlap(rect, r))
    if (collides) {
      el.classList.add('is-collided')
    } else {
      placed.push(rect)
    }
  }
  // Leg labels yield to: any visible pin tooltip AND any earlier-placed leg.
  // Walk in array order so earlier (= earlier in trip) chips win ties.
  for (const m of legLabelMarkers) {
    const el = m?.getElement?.()
    if (!el) continue
    el.classList.remove('is-collided')
    const rect = el.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) continue
    const collides = placed.some((r) => rectsOverlap(rect, r))
    if (collides) {
      el.classList.add('is-collided')
    } else {
      placed.push(rect)
    }
  }
}

// Pin-overlap: when two day pins land within PIN_SPREAD_PX of each other in
// screen space (e.g. Mather + BLM ~6 km apart at zoom 7), nudge the later
// pin outward in a small circle so both stay clickable. Resets to true coords
// on zoom-in where they no longer overlap. Re-runs on every move/zoom.
const PIN_SPREAD_PX = 28
function spreadOverlappingPins() {
  if (!leaflet) return
  const days = (mapData.value?.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
  // Group days by approximate map-pixel cluster so we know how many to spread.
  const placed = []  // { d, x, y }
  for (const d of days) {
    const m = itineraryMarkers.get(d.id)
    if (!m) continue
    // Reset to the day's true position before measuring — yesterday's offset
    // would otherwise compound.
    m.setLatLng([d.lat, d.lng])
    const pt = leaflet.latLngToContainerPoint([d.lat, d.lng])
    placed.push({ d, m, x: pt.x, y: pt.y, true_: pt })
  }
  // For each pair within PIN_SPREAD_PX, push the later pin outward along the
  // vector from the earlier pin (or due-east when at the same point).
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      const a = placed[i], b = placed[j]
      const dx = b.x - a.x, dy = b.y - a.y
      const dist = Math.hypot(dx, dy)
      if (dist >= PIN_SPREAD_PX) continue
      // Spread on a circle: each subsequent collider gets an angle stepped
      // by 60°, large enough that 2-4 stacked pins all stay clickable.
      const angle = ((j - i) * 60) * Math.PI / 180
      const r = PIN_SPREAD_PX
      const nx = a.x + Math.cos(angle) * r
      const ny = a.y + Math.sin(angle) * r
      b.x = nx
      b.y = ny
      const ll = leaflet.containerPointToLatLng([nx, ny])
      b.m.setLatLng(ll)
    }
  }
}

// Per-leg polylines — uses the real OSRM road geometry when available,
// otherwise falls back to a dashed straight segment so the user sees the
// trip take shape immediately while routes resolve in the background.
const legLineMarkers = new Map() // pairKey → L.polyline
function clearLegLines() {
  for (const line of legLineMarkers.values()) {
    if (leaflet) leaflet.removeLayer(line)
  }
  legLineMarkers.clear()
}
function attachLegLines(days) {
  if (!leaflet || days.length < 2) return
  for (let i = 0; i < days.length - 1; i++) {
    const a = days[i], b = days[i + 1]
    const k = legPairKey(a, b)
    const leg = drivingLegs.value[k]
    const hasGeom = leg?.geometry && leg.geometry.length > 1
    const path = hasGeom ? leg.geometry : [[a.lat, a.lng], [b.lat, b.lng]]
    const line = L.polyline(path, {
      color: '#1f3851',
      weight: hasGeom ? 3 : 2.5,
      opacity: hasGeom ? 0.85 : 0.7,
      dashArray: hasGeom ? null : '4 8',
      lineCap: 'round',
      lineJoin: 'round',
      interactive: false,
    }).addTo(leaflet)
    legLineMarkers.set(k, line)
  }
}

// Per-segment leg labels (e.g. "4h 30 · 425 km") shown at the polyline
// midpoint. Re-rendered whenever days change or driving legs resolve.
const legLabelMarkers = []
function clearLegLabels() {
  while (legLabelMarkers.length) {
    const m = legLabelMarkers.pop()
    if (leaflet) leaflet.removeLayer(m)
  }
}
// Duration glyph stripped of its space ("4h30" instead of "4h 30") for the
// dense/compact zooms. Falls back to the standard fmt for shorter legs.
function fmtMinutesTight(min) {
  const std = fmtMinutes(min)
  return std.replace(/\s+/g, '')
}
function attachLegLabels(days) {
  clearLegLabels()
  if (!leaflet || days.length < 2) return
  for (let i = 0; i < days.length - 1; i++) {
    const a = days[i], b = days[i + 1]
    const leg = drivingLegs.value[legPairKey(a, b)]
    if (!leg) continue
    // Same-location stays produce 0-km / 0-min legs that just clutter the map.
    if (leg.km < 1) continue
    const midLat = (a.lat + b.lat) / 2
    const midLng = (a.lng + b.lng) / 2
    // Duration always renders (tight "4h30" form for narrow chips); km hides
    // at low zoom via .leg-label-km CSS rules. Short legs (<5km) collapse to
    // just the km — they're not really "drives", so duration is irrelevant.
    const isShort = leg.km < 5
    const cls = ['leg-label']
    if (leg.source === 'estimate') cls.push('is-est')
    if (isShort) cls.push('is-short')
    const html = isShort
      ? `<div class="${cls.join(' ')}"><span class="leg-label-km">${leg.km} km</span></div>`
      : `<div class="${cls.join(' ')}">` +
          `<span class="leg-label-dur">${fmtMinutesTight(leg.minutes)}</span>` +
          `<span class="leg-label-km"> · ${leg.km} km</span>` +
          `</div>`
    const m = L.marker([midLat, midLng], {
      icon: L.divIcon({
        className: 'leg-label-wrap',
        html,
        iconSize: null,
      }),
      interactive: false,
      zIndexOffset: 400,
    }).addTo(leaflet)
    legLabelMarkers.push(m)
  }
}

// Two-tier label density. Below ZOOM_PINS_ONLY everything is hidden — the
// route + numbered pins read on their own. Between ZOOM_PINS_ONLY and
// ZOOM_FULL_LABELS the tooltip shrinks to "Day N" (no place name) and leg
// distance chips stay hidden. At ZOOM_FULL_LABELS+ it's the full experience.
const ZOOM_PINS_ONLY = 7
const ZOOM_FULL_LABELS = 9
function applyZoomDensity() {
  if (!leaflet) return
  const c = leaflet.getContainer()
  if (!c) return
  const z = leaflet.getZoom()
  c.classList.toggle('iti-dense', z < ZOOM_PINS_ONLY)
  c.classList.toggle('iti-compact', z >= ZOOM_PINS_ONLY && z < ZOOM_FULL_LABELS)
}
watch(drivingLegs, () => {
  if (!leaflet || !mapData.value) return
  const days = (mapData.value.itinerary || [])
    .filter((d) => d.lat != null && d.lng != null)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
  // Re-paint the polylines so resolved legs swap from dashed straight to the
  // real road geometry, then re-attach the duration labels.
  clearLegLines()
  attachLegLines(days)
  attachLegLabels(days)
}, { deep: true })

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
  // Soft-delete: hide locally now, fire the server DELETE in 5s unless the
  // user clicks Undo. Avoids a confirm() dialog (bad UX for one-tap pin work)
  // while still being recoverable.
  const point = detail.value
  detail.value = null
  activeId.value = null
  scheduleSoftDelete({
    kind: 'point',
    message: `Pin "${point.title || 'untitled'}" deleted`,
    hide: () => removePointMarker(point.id),
    restore: () => addPointMarker(point),
    commit: () => api.deletePoint(slug.value, point.id),
    onCommit: () => {
      mapData.value.points = mapData.value.points.filter((p) => p.id !== point.id)
    },
  })
}

// Shared soft-delete state — only one delete can be pending at a time. If a
// new delete fires while one is pending, the previous one commits immediately
// (its server call still races; the user has already moved on).
const pendingDelete = ref(null)
let _pendingTimer = null
let _pendingResolved = false

function scheduleSoftDelete({ kind, message, hide, restore, commit, onCommit }) {
  // Flush any in-flight pending delete before starting a new one — we can
  // only show one toast at a time and the previous user has already moved on.
  if (pendingDelete.value && !_pendingResolved) {
    finalizeSoftDelete(/* commitNow */ true)
  }
  hide()
  _pendingResolved = false
  pendingDelete.value = { kind, message, hide, restore, commit, onCommit }
  _pendingTimer = setTimeout(() => finalizeSoftDelete(true), 5000)
}

async function finalizeSoftDelete(shouldCommit) {
  if (!pendingDelete.value || _pendingResolved) return
  const entry = pendingDelete.value
  _pendingResolved = true
  if (_pendingTimer) { clearTimeout(_pendingTimer); _pendingTimer = null }
  pendingDelete.value = null
  if (!shouldCommit) {
    // Undo path: restore the visible state.
    try { entry.restore() } catch (e) { error.value = e?.message || 'Could not restore.' }
    return
  }
  try {
    await entry.commit()
    if (entry.onCommit) entry.onCommit()
  } catch (e) {
    // Server rejected the delete — restore so the UI matches reality.
    try { entry.restore() } catch { /* swallow */ }
    error.value = e?.message || 'Could not delete.'
  }
}

function undoDelete() { finalizeSoftDelete(false) }

onBeforeUnmount(() => {
  // If we leave the page mid-undo-window, commit so the server stays in sync
  // with what the user already saw disappear.
  if (_pendingTimer) clearTimeout(_pendingTimer)
  if (pendingDelete.value && !_pendingResolved) {
    const entry = pendingDelete.value
    _pendingResolved = true
    pendingDelete.value = null
    entry.commit().catch(() => { /* best-effort */ })
    if (entry.onCommit) {
      try { entry.onCommit() } catch { /* swallow */ }
    }
  }
})

function startNewPin() {
  // Toggle drop-mode: next click on the map places the pin where the user
  // pointed instead of always at the current viewport centre.
  dropMode.value = !dropMode.value
  if (dropMode.value) detail.value = null
}

// FAB popover routes — each picks one entry point and focuses the right
// control so the user lands ready to type.
function onFabDrop({ cancel }) {
  if (cancel) {
    dropMode.value = false
    return
  }
  detail.value = null
  dropMode.value = true
}

// FAB → "Add a stop" / "Search a place": both jump to Plan mode and open
// the inline add-stop disclosure (which holds both the date input AND the
// geocoder). The legacy tab-content selectors no longer exist since the
// dock was removed; we now drive PlanView via a ref + exposed method.
const planRef = ref(null)
async function onFabAddStop() {
  setMode('plan')
  await nextTick()
  planRef.value?.openAddRow?.({ focus: 'date' })
}
async function onFabSearch() {
  setMode('plan')
  await nextTick()
  planRef.value?.openAddRow?.({ focus: 'search' })
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
    const created = await api.addPoint(slug.value, {
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

// Reverse-geocoded fallback names per day id, populated on demand for days
// that have coords but no user-given label.
const dayPlaceNames = ref({})
async function ensurePlaceName(day) {
  if (!day || day.lat == null || day.lng == null) return
  if (day.label) return
  if (dayPlaceNames.value[day.id]) return
  const name = await reverseGeocode(day.lat, day.lng)
  if (name) dayPlaceNames.value = { ...dayPlaceNames.value, [day.id]: name }
}

function bannerNameFor(day) {
  if (!day) return 'Untitled'
  if (day.label) return day.label
  return dayPlaceNames.value[day.id] || 'On the road'
}

// Used by the banner's CSS to push it below the trip ribbon (desktop only).
// The ribbon is only rendered when there are itinerary days, so when there
// are none we keep the banner at the smaller top offset.
const hasRibbon = computed(() => (mapData.value?.itinerary || []).length > 0)

// Day id of the stop the user just tapped from the ribbon, banner, or a stop
// marker. Drives the outlined-chip "selected" state in TripRibbon so users
// keep their place on a long trip, AND retargets the today-banner so weather/
// sunrise/next-leg meta reflect whichever stop they're inspecting (rather
// than staying frozen on today's stop).
const selectedRibbonDayId = ref(null)

const todayBanner = computed(() => {
  const days = mapData.value?.itinerary || []
  if (!days.length) return null
  const t = today.value
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))

  // If the user picked a stop (ribbon chip or marker), the banner follows
  // that selection. "live" stays true only when the chosen stop spans today —
  // otherwise the "Made it →" / sunset countdown affordances would be wrong.
  const selectedId = selectedRibbonDayId.value
  if (selectedId != null) {
    const sel = sorted.find((d) => d.id === selectedId)
    if (sel) {
      const idx = sorted.indexOf(sel)
      const selSpan = Math.round((new Date(sel.end_date || sel.date) - new Date(sel.date)) / 86400000) + 1
      let cumulative = 0
      let totalNights = 0
      for (let i = 0; i < sorted.length; i++) {
        const d = sorted[i]
        const span = Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1
        if (i < idx) cumulative += span
        totalNights += span
      }
      const isLive = t >= sel.date && t <= (sel.end_date || sel.date)
      const startNum = cumulative + 1
      const endNum = cumulative + selSpan
      const tag = selSpan > 1
        ? `Day ${startNum}–${endNum} / ${totalNights}`
        : `Day ${startNum} / ${totalNights}`
      return attachSun({
        tag,
        text: bannerNameFor(sel).toUpperCase(),
        notes: sel.notes || null,
        day: sel,
        live: isLive,
      })
    }
  }

  // Within a multi-day stop, today is "between" date and end_date (inclusive).
  const todayStop = sorted.find((d) => t >= d.date && t <= (d.end_date || d.date))
  if (todayStop) {
    let cumulative = 0
    let totalNights = 0
    for (const d of sorted) {
      const span = Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1
      if (d === todayStop) cumulative += Math.round((new Date(t) - new Date(d.date)) / 86400000) + 1
      else if (sorted.indexOf(d) < sorted.indexOf(todayStop)) cumulative += span
      totalNights += span
    }
    return attachSun({
      tag: `Day ${cumulative} / ${totalNights}`,
      text: bannerNameFor(todayStop).toUpperCase(),
      notes: todayStop.notes || null,
      day: todayStop,
      live: true,
    })
  }
  const future = sorted.find((d) => d.date > t)
  if (future) {
    const ms = new Date(future.date) - new Date(t)
    const days = Math.floor(ms / 86400000)
    const tag = days >= 1 ? `T-${days}d` : `T-<1d`
    return attachSun({
      tag,
      text: `Next: ${bannerNameFor(future).toUpperCase()}`,
      notes: future.notes || null,
      day: future,
      live: false,
    })
  }
  return null
})

// Live-mode helpers — only meaningful when `todayBanner.live`. These keep the
// banner useful as a trip companion: how long until sunset (a real safety
// concern during desert hikes), what's the next stop, and how far is it.
const nextStop = computed(() => {
  if (!todayBanner.value?.live) return null
  const sorted = [...(mapData.value?.itinerary || [])].sort((a, b) => a.date.localeCompare(b.date))
  const i = sorted.indexOf(todayBanner.value.day)
  return i >= 0 && i < sorted.length - 1 ? sorted[i + 1] : null
})
const nextLegInfo = computed(() => {
  if (!todayBanner.value?.live || !nextStop.value) return null
  const here = todayBanner.value.day
  const there = nextStop.value
  if (here.lat == null || there.lat == null) return null
  const k = legPairKey(here, there)
  const leg = drivingLegs.value[k]
  const name = there.label || dayPlaceNames.value[there.id] || 'next stop'
  if (leg) return `${name} · ${leg.km} km · ${fmtMinutes(leg.minutes)}`
  return name
})

// Tick every minute so the sunset countdown stays fresh without burning CPU.
const wallClock = ref(Date.now())
let _tick = null
onMounted(() => { _tick = setInterval(() => { wallClock.value = Date.now() }, 60_000) })
onBeforeUnmount(() => { if (_tick) clearInterval(_tick) })

const sunsetCountdown = computed(() => {
  if (!todayBanner.value?.live) return null
  const day = todayBanner.value.day
  if (day.lat == null || day.lng == null) return null
  // Touch the wall clock so we re-render every minute.
  const now = wallClock.value
  const t = SunCalc.getTimes(new Date(now), day.lat, day.lng)
  if (!t.sunset || isNaN(t.sunset)) return null
  const ms = t.sunset.getTime() - now
  if (ms < -30 * 60_000) return null   // already long past sunset
  const sign = ms < 0 ? 'past' : 'in'
  const min = Math.round(Math.abs(ms) / 60_000)
  if (min < 60) return `${sign} ${min}m`
  const h = Math.floor(min / 60)
  const m = min % 60
  return `${sign} ${h}h${m ? ' ' + m + 'm' : ''}`
})

// "Upcoming leg" — the next pair of stops the user will drive between.
// Works pre-trip (T-8d picks the first→second stop), mid-trip (today→next),
// and gracefully returns null when there's nothing left to drive. The pair
// is the first stop whose end_date >= today (call it B); the leg is
// (the stop just before B, when there is one) → B. If B is the very first
// stop, the leg is B → (the stop right after B) so we still get a valid bbox.
const upcomingLegPair = computed(() => {
  const sorted = [...(mapData.value?.itinerary || [])]
    .filter((d) => d.lat != null && d.lng != null)
    .sort((a, b) => a.date.localeCompare(b.date))
  if (sorted.length < 2) return null
  const t = today.value
  // Mid-trip: today is inside a stop, the leg is here→next.
  if (todayBanner.value?.live && nextStop.value) {
    return [todayBanner.value.day, nextStop.value]
  }
  // Find the first stop whose end_date is in the future (or today).
  const idx = sorted.findIndex((d) => (d.end_date || d.date) >= t)
  if (idx === -1) return null              // trip is already over
  if (idx === 0) return [sorted[0], sorted[1]]   // pre-trip: first leg
  return [sorted[idx - 1], sorted[idx]]    // about to drive prev→this
})

// Bbox for that upcoming leg, padded ~10% on each side so the cached tiles
// include road context, not just the endpoints. Used by the per-leg
// pre-cache option in MoreMenu.
const nextLegBbox = computed(() => {
  const pair = upcomingLegPair.value
  if (!pair) return null
  const [here, there] = pair
  const minLat = Math.min(here.lat, there.lat)
  const maxLat = Math.max(here.lat, there.lat)
  const minLng = Math.min(here.lng, there.lng)
  const maxLng = Math.max(here.lng, there.lng)
  const padLat = Math.max(0.05, (maxLat - minLat) * 0.1)
  const padLng = Math.max(0.05, (maxLng - minLng) * 0.1)
  return {
    minLat: minLat - padLat,
    maxLat: maxLat + padLat,
    minLng: minLng - padLng,
    maxLng: maxLng + padLng,
  }
})

// "Made it →" — when arriving at the next stop ahead of schedule. Centers
// the map there and dismisses the now-stale today banner; the next page
// reload will surface the new stop as today (or "next" if the user lingers).
function advanceToNextStop() {
  const ns = nextStop.value
  if (!ns) return
  if (leaflet && ns.lat != null && ns.lng != null) {
    leaflet.flyTo([ns.lat, ns.lng], Math.max(leaflet.getZoom(), 11), { duration: 0.6 })
  }
  dismissBanner()
}

watch(() => todayBanner.value?.day, (d) => { ensurePlaceName(d) }, { immediate: true })

// Banner dismissal — sticky for the session, keyed per voyage slug. The user
// can re-open by reloading. Avoids the banner being a permanent strip eating
// 40px on every tab switch.
const bannerDismissKey = computed(() => `voyage-banner-dismissed:${slug.value}`)
const bannerDismissed = ref(false)
onMounted(() => {
  bannerDismissed.value = sessionStorage.getItem(bannerDismissKey.value) === '1'
})
function dismissBanner() {
  bannerDismissed.value = true
  sessionStorage.setItem(bannerDismissKey.value, '1')
}

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
    const day = await api.addItineraryDay(slug.value, payload)
    if (!mapData.value.itinerary) mapData.value.itinerary = []
    mapData.value.itinerary = [...mapData.value.itinerary, day].sort((a, b) => a.date.localeCompare(b.date))
  } catch (e) { error.value = e.message }
}

async function onAddTrailPin(t) {
  // Overpass trails arrive with optional polyline geometry. Synthesise a
  // minimal GPX so the existing renderTrack pipeline draws the actual route
  // (not just a centroid pin) and the elevation overlay slot is populated.
  // No SAC jargon in the comment — `sacPlain` already translates it.
  try {
    const bits = []
    if (t.sacPlain) bits.push(t.sacPlain)
    else if (t.kind) bits.push(t.kind)
    if (t.lengthKm) bits.push(`${t.lengthKm} km`)
    if (t.ref) bits.push(t.ref)
    const idx = trailPoints.value.length
    const payload = {
      lat: t.lat,
      lng: t.lng,
      title: t.name,
      category: 'trail',
      comment: bits.length ? bits.join(' · ') : null,
      color: trackColor(idx),
    }
    if (t.coords && t.coords.length > 1) {
      payload.gpx_data = coordsToGPX(t.coords, t.name)
    }
    const created = await api.addPoint(slug.value, payload)
    mapData.value.points.push(created)
    if (created.gpx_data) {
      const line = renderTrack(created, idx)
      if (line && leaflet) leaflet.fitBounds(line.getBounds(), { padding: [40, 40], maxZoom: 14 })
    } else {
      addPointMarker(created)
      if (leaflet) leaflet.flyTo([t.lat, t.lng], 13, { duration: 0.5 })
    }
    activeId.value = created.id
    detail.value = { ...created }
  } catch (e) { error.value = e.message }
}

// Hover/focus preview from the trail finder: draws a temporary polyline so
// the user sees the route shape before clicking. Cleared on unhover or modal
// close.
let trailPreviewLine = null
function onTrailPreview(t) {
  if (!leaflet) return
  if (trailPreviewLine) {
    leaflet.removeLayer(trailPreviewLine)
    trailPreviewLine = null
  }
  if (!t || !t.coords || t.coords.length < 2) return
  trailPreviewLine = L.polyline(t.coords, {
    color: '#e85d3c',
    weight: 4,
    opacity: 0.9,
    dashArray: '6 6',
    lineCap: 'round',
    interactive: false,
  }).addTo(leaflet)
}

async function onAddDaysBulk(payload) {
  // Tolerate the legacy bare-rows signature.
  const rows = Array.isArray(payload) ? payload : payload?.rows
  const replace = Array.isArray(payload) ? false : !!payload?.replace
  if (!rows?.length) return
  try {
    const created = await api.addItineraryDaysBulk(slug.value, rows, { replace })
    if (!mapData.value.itinerary || replace) mapData.value.itinerary = []
    mapData.value.itinerary = [...mapData.value.itinerary, ...created].sort((a, b) => a.date.localeCompare(b.date))
    // Re-fit the map so the user sees their newly imported trip.
    await nextTick()
    fitToContent()
  } catch (e) { error.value = e.message }
}

async function onDeleteDay(day) {
  // Soft-delete with the same 5s undo toast as pins, so day removal is
  // recoverable and consistent. The full day record (including any attached
  // pin links — those references stay on the points; only the day row goes)
  // is captured for restoration if Undo is hit.
  const snapshot = { ...day }
  scheduleSoftDelete({
    kind: 'day',
    message: `Day "${day.label || day.date}" deleted`,
    hide: () => {
      mapData.value.itinerary = mapData.value.itinerary.filter((d) => d.id !== day.id)
    },
    restore: () => {
      // Re-insert with the original date so sorting puts it back where it was.
      mapData.value.itinerary = [...mapData.value.itinerary, snapshot]
        .sort((a, b) => a.date.localeCompare(b.date))
    },
    commit: () => api.deleteItineraryDay(slug.value, day.id),
    onCommit: () => { /* hide() already removed it from local state */ },
  })
}

async function onAttachPoint({ pointId, dayId }) {
  await patchPointDay(pointId, dayId)
}
async function onDetachPoint(pointId) {
  await patchPointDay(pointId, null)
}
async function patchPointDay(pointId, dayId) {
  try {
    const updated = await api.patchPoint(slug.value, pointId, { itinerary_day_id: dayId })
    const idx = mapData.value.points.findIndex((p) => p.id === pointId)
    if (idx >= 0) mapData.value.points.splice(idx, 1, updated)
  } catch (e) { error.value = e.message }
}

async function onPatchDay(day, payload) {
  try {
    const updated = await api.patchItineraryDay(slug.value, day.id, payload)
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
  selectedRibbonDayId.value = day?.id ?? null
  // The banner content keys off the selection — if the user dismissed the
  // banner earlier, surface it again so they actually see the new context.
  if (bannerDismissed.value) {
    bannerDismissed.value = false
    sessionStorage.removeItem(bannerDismissKey.value)
  }
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
    const updated = await api.patchItineraryDay(slug.value, day.id, { lat: choice.lat, lng: choice.lng })
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
  const name = r.kind === 'local' ? r.label : r.label.split(',')[0]
  if (leaflet) leaflet.flyTo([r.lat, r.lng], 14, { duration: 0.5 })
  detail.value = null
  activeId.value = null
  modal.value = {
    lat: r.lat,
    lng: r.lng,
    title: name,
    comment: '',
    category: categoryFromOSM(r.osmClass, r.osmType) || 'note',
  }
}

async function onSave(payload) {
  if (!modal.value) return
  try {
    if (modal.value.id) {
      const updated = await api.patchPoint(slug.value, modal.value.id, payload)
      const idx = mapData.value.points.findIndex((p) => p.id === updated.id)
      if (idx >= 0) mapData.value.points.splice(idx, 1, updated)
      removePointMarker(updated.id)
      addPointMarker(updated)
      // Re-open detail with the updated content.
      detail.value = { ...updated }
      activeId.value = updated.id
    } else {
      const created = await api.addPoint(slug.value, {
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
    mapData.value = await api.patchMap(slug.value, { title: t })
  } catch {
    titleDraft.value = mapData.value.title || ''
  }
}

// PlanView emits @update:title with its own draft. Funnel through commitTitle
// so the network call + rollback paths are shared with the Map-mode editor.
async function onTitleSave(next) {
  titleDraft.value = (next || '').trim()
  await commitTitle()
}

// PlanView's "+ pin to a stop" calls back here with the geocoded result + the
// target day id. We create the pin attached to that day, render its marker,
// and refresh map state. No detail card opens — the Plan table already shows
// the new chip on its row, which is the affordance the user is looking at.
async function onAddPinToDay({ dayId, lat, lng, title, category }) {
  try {
    const created = await api.addPoint(slug.value, {
      lat, lng,
      title: title || null,
      category: category || 'note',
      itinerary_day_id: dayId,
    })
    if (!mapData.value.points) mapData.value.points = []
    mapData.value.points.push(created)
    addPointMarker(created)
  } catch (e) { error.value = e.message }
}

// PlanView emits @edit-pin (clicking a pin chip or wishlist card) — open the
// shared PointFormModal in edit mode. The existing onSave path handles the
// patch + marker refresh.
function onEditPin(p) {
  modal.value = { ...p }
}

// PlanView's wishlist × button — funnel into the same soft-delete machinery
// as the map detail card so the user always gets the 5s undo toast.
function onDeletePinFromList(point) {
  if (!point?.id) return
  scheduleSoftDelete({
    kind: 'point',
    message: `Pin "${point.title || 'untitled'}" deleted`,
    hide: () => removePointMarker(point.id),
    restore: () => addPointMarker(point),
    commit: () => api.deletePoint(slug.value, point.id),
    onCommit: () => {
      mapData.value.points = mapData.value.points.filter((p) => p.id !== point.id)
    },
  })
}

// PasteImportModal hoisted at this level (so Plan mode can open it). The
// payload shape mirrors what Itinerary's onPasteImport produces.
const defaultYearForPaste = computed(() => {
  const days = mapData.value?.itinerary || []
  if (days.length) return parseInt(days[0].date.slice(0, 4), 10)
  return new Date().getFullYear()
})
function onPasteImportTopLevel(payload) {
  showPaste.value = false
  const rows = Array.isArray(payload) ? payload : payload?.rows
  const replace = Array.isArray(payload) ? false : !!payload?.replace
  if (rows && rows.length) onAddDaysBulk({ rows, replace })
}

// When the user switches to Map mode, Leaflet may have been hidden (the wrap
// was display:none) — invalidate so it recomputes its size against the visible
// container. Without this the tiles render only inside the original viewport
// and the rest stays grey. On the very first switch, we also re-fit to content
// because the initial bounds were computed against a hidden container.
const _mapInteracted = ref(false)
watch(mode, async (next) => {
  if (next === 'map' && leaflet) {
    await nextTick()
    leaflet.invalidateSize()
    if (!_mapInteracted.value) {
      fitToContent()
      _mapInteracted.value = true
    }
  }
})

// Click-outside handler for the tools popover.
function onDocClickTools(e) {
  if (!toolsOpen.value) return
  const inside = e.target.closest?.('.tools-popover, [title^="Tools"]')
  if (!inside) toolsOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocClickTools, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClickTools, true))

// Share URL: `/v/{slug}` is the read-only mirror; copying that instead of
// `/m/{slug}` means the recipient can't accidentally edit the host's trip.
// We share the display slug (name-slug + id) when the trip is titled so the
// link is human-readable; the viewer route resolves either form.
function copyShareUrl() {
  const display = mapData.value
    ? buildMapSlug({ title: mapData.value.title, slug: slug.value })
    : slug.value
  const url = `${window.location.origin}/v/${display}`
  navigator.clipboard.writeText(url)
  copied.value = true
  setTimeout(() => (copied.value = false), 1800)
}

const showOverview = ref(false)
const overviewLine = computed(() => {
  if (!mapData.value) return ''
  const stops = (mapData.value.itinerary || []).length
  const days = (mapData.value.itinerary || []).reduce(
    (acc, d) => acc + Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1,
    0,
  )
  const points = (mapData.value.points || []).filter((p) => p.category !== 'trail').length
  const trails = (mapData.value.points || []).filter((p) => p.category === 'trail').length
  const bits = []
  if (days) bits.push(`${days} day${days === 1 ? '' : 's'}`)
  if (stops) bits.push(`${stops} stop${stops === 1 ? '' : 's'}`)
  if (trails) bits.push(`${trails} trail${trails === 1 ? '' : 's'}`)
  if (points) bits.push(`${points} pin${points === 1 ? '' : 's'}`)
  return bits.join(' · ') || 'Empty trip'
})

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
  if (mapResizeObserver) {
    mapResizeObserver.disconnect()
    mapResizeObserver = null
  }
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
  /* Map mode (desktop): dock is gone, so the ribbon hugs the left edge with
     a small inset, and reserves the right strip for the floating topbar pill. */
  --ribbon-pad-left: 16px;
  --ribbon-pad-right: 16px;
}
@media (max-width: 720px) {
  .mapview { --ribbon-pad-left: 8px; --ribbon-pad-right: 8px; }
}
.mapview .map-shell {
  display: contents;
}
.mapview .map-shell .trip-ribbon {
  padding-left: var(--ribbon-pad-left);
  padding-right: var(--ribbon-pad-right);
}

/* Plan pane fills the viewport, scrolls independently. Sits above the map
   shell when active (the shell is v-show'd off, but the rule here makes the
   stacking unambiguous). */
.plan-pane {
  position: absolute;
  inset: 0;
  z-index: 900;
  overflow-y: auto;
}

/* Floating top-right toolbar in Map mode. Editorial paper card with the
   trip title + the same actions the dock used to host (mode toggle, recenter,
   share, theme, tools, new voyage). */
.map-topleft {
  position: absolute;
  top: 96px;
  left: 12px;
  z-index: 900;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  box-shadow: 0 3px 0 var(--ink), 0 6px 14px rgba(0, 0, 0, 0.12);
  /* Pill grows with the title rather than chopping it; the cap stays well
     short of the topbar pill on the right (which sits at right: 12px). */
  max-width: min(38rem, calc(50vw - 1.5rem));
}
.map-topleft-title {
  background: transparent;
  border: none;
  font-family: var(--display);
  font-size: 0.95rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--ink);
  /* Width follows content up to the pill's max-width. min-width keeps the
     placeholder readable when the trip is untitled; text-overflow ellipsises
     overflow rather than scroll-clipping mid-token. The native title attribute
     surfaces the full string on hover. */
  min-width: 8rem;
  width: 100%;
  max-width: 100%;
  padding: 0.05rem 0.1rem;
  border-bottom: 1px dashed transparent;
  text-overflow: ellipsis;
}
.map-topleft-title:focus { outline: none; border-bottom-color: var(--ink-faded); }
.map-topleft-title:hover { border-bottom-color: var(--cream-edge); }
@media (max-width: 720px) {
  .map-topleft {
    top: 64px;
    left: 8px;
    padding: 0.25rem 0.5rem;
  }
  .map-topleft-title { min-width: 7rem; font-size: 0.85rem; }
  /* When the ribbon is present it carries the trip identity (numbered chips
     of every stop) — the title pill becomes redundant and visibly collides
     with the topbar pill on the right, so we hide it. The user can still
     edit the title from Plan mode. */
  .map-topleft.has-ribbon { display: none; }
}

.map-topbar {
  position: absolute;
  top: 96px;
  right: 12px;
  z-index: 900;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.45rem;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  box-shadow: 0 3px 0 var(--ink), 0 6px 14px rgba(0, 0, 0, 0.12);
}
.map-topbar-actions { display: inline-flex; gap: 0.25rem; align-items: center; }
.map-topbar .head-icon {
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  width: 1.85rem; height: 1.85rem;
  display: grid; place-items: center;
  font-size: 0.8rem;
  color: var(--ink-soft);
  cursor: pointer;
  transition: color 90ms, border-color 90ms;
}
.map-topbar .head-icon:hover { color: var(--vermillion); border-color: var(--vermillion); }
@media (max-width: 720px) {
  .map-topbar {
    top: 64px;
    right: 8px;
    padding: 0.25rem 0.4rem;
    border-radius: 999px;
  }
}

.tools-popover {
  position: absolute;
  top: 70px;
  right: 16px;
  z-index: 950;
  width: min(360px, calc(100% - 32px));
  padding: 1rem 1.1rem 1.1rem;
  display: grid;
  gap: 0.8rem;
  border: 1.5px solid var(--ink);
  box-shadow: 0 12px 30px -10px rgba(0,0,0,0.22);
}
.tools-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px dashed var(--cream-edge);
  padding-bottom: 0.4rem;
}
.tools-close {
  background: transparent;
  border: none;
  font-size: 1.4rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
}
.tools-close:hover { color: var(--ink); background: var(--cream); }
.tools-extra {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding-top: 0.4rem;
  border-top: 1px dashed var(--cream-edge);
}
.tools-extra .btn {
  cursor: pointer;
}
.tools-extra label {
  cursor: pointer;
}
.hidden { display: none; }

.map-wrap {
  flex: 1;
  /* Flexbox gotcha: a flex item's default min-width is `auto`, which equals
     the *content's* min size. The ribbon's chips + the leaflet map together
     push the wrap wider than the viewport without this. */
  min-width: 0;
  overflow: hidden;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.map {
  flex: 1;
  width: 100%;
  background: var(--cream-deep);
}

/* Trip ribbon: stripe above the map. The dock is gone in Map mode, so we
   reserve a left inset (var --ribbon-pad-left) for breathing room and a right
   inset (var --ribbon-pad-right) so the floating topbar pill doesn't sit on
   top of the rightmost stops. The padding values are hoisted to .mapview so
   the responsive breakpoints can override them in one place. */
.trip-ribbon {
  position: relative;
  /* Above the today-banner (z-index: 700) so even if the banner offset is
     mis-tuned by a few pixels, the stop pillules win the stacking. */
  z-index: 760;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
}
.error { color: var(--vermillion-deep); }

.title { margin: 0; line-height: 0.94; }
.title-input {
  font-family: var(--display);
  font-size: 1.85rem;
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

.dock-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.dock-head-actions { display: inline-flex; gap: 0.3rem; align-items: center; }
.head-icon {
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  width: 2rem; height: 2rem;
  display: grid; place-items: center;
  font-size: 0.85rem;
  color: var(--ink-soft);
  cursor: pointer;
  transition: color 90ms, border-color 90ms;
}
.head-icon:hover { color: var(--vermillion); border-color: var(--vermillion); }

.dock-eyebrow {
  display: inline-block;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}

.dock-overview {
  margin: 0.25rem 0 0.45rem;
  padding: 0.55rem 0.65rem;
  background: var(--cream);
  border: 1px dashed var(--cream-edge);
  border-radius: 3px;
  display: grid;
  gap: 0.25rem;
}
.overview-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.overview-line {
  margin: 0;
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  color: var(--ink-soft);
}
.overview-link {
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  text-decoration: none;
}
.overview-link:hover { color: var(--vermillion-deep); }

.offline-badge {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--vermillion);
  background: var(--cream);
  border: 1px dashed var(--vermillion);
  border-radius: 2px;
  padding: 0.15rem 0.4rem;
  cursor: help;
}

.pins-search-row {
  display: flex;
  gap: 0.4rem;
  align-items: stretch;
  margin-bottom: 0.5rem;
}
.pins-search { flex: 1; min-width: 0; }
.pins-locate {
  flex: 0 0 32px;
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  cursor: pointer;
  font-size: 1rem;
  color: var(--vermillion);
  display: grid;
  place-items: center;
  transition: background 90ms ease, border-color 90ms ease;
}
.pins-locate:hover { background: var(--cream); border-color: var(--ink); color: var(--vermillion-deep); }
.pins-locate:disabled { color: var(--ink-faded); cursor: wait; }

.pins-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem 0.5rem;
  padding: 0.3rem 0 0.45rem;
  border-bottom: 1px dotted var(--cream-edge);
  margin-bottom: 0.5rem;
}
.seg {
  display: inline-flex;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  overflow: hidden;
}
.seg-btn {
  background: transparent;
  border: none;
  padding: 0.18rem 0.6rem;
  font-family: var(--mono);
  font-size: 0.66rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
}
.seg-btn:hover { color: var(--ink); }
.seg-btn.on { background: var(--ink); color: var(--paper); }
.filter-meta {
  font-size: 0.66rem;
  letter-spacing: 0.16em;
  color: var(--ink-faded);
}
.pins-cats { flex: 1 1 100%; min-width: 0; }
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
  margin-top: 0.6rem;
  border-top: 1px dotted var(--cream-edge);
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}
.gpx-hint code { font-family: var(--mono); color: var(--vermillion); padding: 0 2px; }

/* Drop-mode floating hint: on desktop it's pinned just left of the FAB so
   it reads as a tooltip on the action. On mobile the FAB column is more
   crowded (FAB + locate-me + Leaflet zoom controls at bottom-left) so we
   surface it as a centred top-of-map pill, well clear of every floating
   button. */
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
@media (max-width: 720px) {
  .drop-hint {
    right: auto;
    bottom: auto;
    top: calc(64px + 2.6rem);
    left: 50%;
    transform: translateX(-50%);
    padding: 0.5rem 0.9rem;
    font-size: 0.74rem;
    text-align: center;
    max-width: calc(100% - 2rem);
  }
}
@keyframes drop-hint-pop {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}
@media (max-width: 720px) {
  @keyframes drop-hint-pop {
    from { opacity: 0; transform: translate(-50%, -8px); }
    to { opacity: 1; transform: translate(-50%, 0); }
  }
}
.link-pick {
  cursor: pointer;
  color: var(--vermillion);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.link-pick:hover { color: var(--vermillion-deep); }

/* Today banner — 2-line stack: primary row (tag + name) carries the
   editorial weight; meta row (weather/sun/notes/next-leg) sits below in a
   quieter mono color so the banner reads as ~half its previous height.
   Sits below the trip ribbon when one is visible (desktop + itinerary
   present); the .with-ribbon class manually offsets past the ribbon since
   absolute positioning is relative to .map-wrap. Mobile hides the ribbon
   entirely so .with-ribbon is a no-op there. */
.today-banner {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 700;
  display: inline-flex;
  align-items: stretch;
  background: var(--ink);
  color: var(--paper);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  max-width: calc(100% - 2rem);
  overflow: hidden;
}
.today-banner.with-ribbon {
  /* Push past the trip ribbon (5.5rem ≈ 88px) plus an 8px breathing gap.
     Mobile drops back to the no-ribbon offset because the ribbon is hidden. */
  top: calc(5.5rem + 8px);
}
@media (max-width: 720px) {
  /* Mobile: ribbon is now visible too, so push the banner past it AND past
     the topbar/topleft pills row (~52px after ribbon's ~52px). */
  .today-banner.with-ribbon { top: calc(52px + 60px + 8px); }
}
.banner-main {
  background: transparent;
  border: none;
  color: inherit;
  padding: 0.4rem 0.7rem 0.4rem 0.5rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  cursor: pointer;
  overflow: hidden;
  font: inherit;
  text-align: left;
  min-width: 0;
}
@media (max-width: 560px) {
  /* Two-row layout on phones: tag stays inline with the title; the meta line
     (weather + sun) wraps below so temps stop getting clipped. */
  .today-banner { max-width: calc(100% - 1rem); }
  .banner-main {
    flex-wrap: wrap;
    white-space: normal;
    gap: 0.4rem 0.7rem;
    padding: 0.45rem 0.55rem 0.5rem 0.5rem;
  }
  .banner-text { font-size: 0.92rem; flex-basis: 100%; }
  .banner-tag { align-self: flex-start; }
  .banner-wx, .banner-sun { font-size: 0.74rem; }
}
.banner-main:hover { background: rgba(255,255,255,0.06); }
.banner-row {
  display: inline-flex;
  align-items: baseline;
  gap: 0.55rem;
  white-space: nowrap;
  overflow: hidden;
  max-width: 100%;
}
/* Meta row (weather / sun / next-leg / notes) wraps onto multiple lines when
   the banner can't fit them inline, instead of ellipsising mid-token (which
   produced output like "31° / ... * 04:49 → 1…"). Each child still keeps
   its own `nowrap` so individual values aren't broken across lines. */
.banner-row-meta {
  flex-wrap: wrap;
  gap: 0.25rem 0.7rem;
  white-space: normal;
  overflow: visible;
}
.banner-row-meta > * {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
@media (max-width: 560px) {
  /* Phones: drop the lower-priority "next leg" and free-form notes from the
     meta row so the temperature/sun pair has room to breathe. The banner is
     a glance affordance; the user can tap through for the full day card. */
  .banner-next,
  .banner-notes { display: none; }
}
.banner-actions { display: inline-flex; }
.banner-action,
.banner-close,
.banner-advance {
  background: transparent;
  border: none;
  border-left: 1px solid rgba(255,255,255,0.1);
  color: var(--cream);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}
.banner-action,
.banner-close { width: 2.2rem; }
.banner-advance {
  padding: 0 0.75rem;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  background: var(--vermillion);
  color: var(--paper);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.banner-advance:hover { background: var(--vermillion-deep); }
.banner-advance-tick {
  font-size: 0.85rem;
  line-height: 1;
  letter-spacing: 0;
}
.banner-action:hover { background: var(--vermillion-deep); color: var(--paper); }
.banner-close:hover { background: rgba(255,255,255,0.12); color: var(--paper); }
.banner-next {
  font-size: 0.74rem;
  color: var(--cream);
  opacity: 0.85;
}
.today-banner.is-live { background: var(--vermillion-deep); }
.today-banner.is-live .banner-tag { background: var(--paper); color: var(--vermillion-deep); }
.banner-tag {
  display: inline-block;
  background: var(--vermillion);
  color: var(--paper);
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  padding: 0.15rem 0.5rem;
  border-radius: 2px;
  font-weight: 700;
}
.banner-text {
  font-family: var(--display);
  font-size: 1rem;
  letter-spacing: 0.04em;
  overflow: hidden;
  text-overflow: ellipsis;
}
.banner-sun,
.banner-wx,
.banner-notes {
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  color: rgba(255,255,255,0.65);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
}
.banner-notes {
  font-family: var(--body);
  letter-spacing: 0.01em;
  color: rgba(255,255,255,0.55);
  font-style: italic;
}

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

/* Soft-delete toast — bottom-centre of the map. Stays in the cream/ink/
   vermillion palette; the Undo button is the click target so users can
   recover without thinking. 5s lifespan, configurable in script. */
.del-toast {
  position: fixed;
  bottom: 1.2rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  display: inline-flex;
  align-items: stretch;
  background: var(--ink);
  color: var(--paper);
  border-radius: 4px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
  max-width: calc(100% - 2rem);
  overflow: hidden;
}
.del-toast-text {
  padding: 0.55rem 0.7rem;
  font-size: 0.85rem;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.del-toast-undo {
  border: none;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  background: var(--vermillion);
  color: var(--paper);
  padding: 0 0.95rem;
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  font-family: var(--mono);
}
.del-toast-undo:hover { background: var(--vermillion-deep); }
.toast-enter-active, .toast-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

/* Share-copy toast — anchored under the top-right toolbar so it appears
   right where the ↗ icon flipped to ✓. Same ink/cream palette as the
   delete toast, scoped narrow so it can't bleed into other controls. */
.share-toast {
  position: absolute;
  top: calc(96px + 2.4rem + 0.4rem);
  right: 12px;
  z-index: 950;
  background: var(--ink);
  color: var(--paper);
  padding: 0.45rem 0.75rem;
  border-radius: 4px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);
  pointer-events: none;
  white-space: nowrap;
}
@media (max-width: 720px) {
  .share-toast { top: calc(64px + 2.2rem + 0.4rem); right: 8px; }
}
.share-toast.toast-enter-from,
.share-toast.toast-leave-to {
  /* Override the centred del-toast keyframes so this slides in from the
     button (no horizontal nudge). */
  transform: translateY(-6px);
}

</style>

<style>
/* Leaflet divIcons aren't scoped — keep this rule global. */
.leg-label-wrap {
  background: transparent !important;
  border: none !important;
}
.leg-label {
  display: inline-block;
  background: rgba(250, 246, 238, 0.92);
  color: var(--ink-soft, #4a4a4a);
  border: 1px solid var(--cream-edge, #d8cfc0);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
  padding: 0.06rem 0.32rem;
  border-radius: 2px;
  white-space: nowrap;
  transform: translate(-50%, -50%);
  pointer-events: none;
}
.leg-label.is-est {
  border-style: dashed;
  opacity: 0.7;
}
.leg-label.is-short {
  font-size: 0.6rem;
  opacity: 0.6;
  border-style: dotted;
}

/* Day-pin label collision: when two permanent tooltips overlap, the later
   one (in trip order) gets `.is-collided` and we hide just the label —
   the numbered pin underneath stays visible. */
.iti-tip.is-collided {
  visibility: hidden;
  pointer-events: none;
}
</style>
