<template>
  <main class="viewer">
    <header class="viewer-bar">
      <div class="viewer-bar-left">
        <span class="viewer-eyebrow mono">Voyage Map · view-only</span>
        <h2 v-if="mapData" class="viewer-title">{{ mapData.title || 'Untitled voyage' }}</h2>
      </div>
      <div class="viewer-bar-right">
        <p v-if="mapData" class="viewer-stats mono">{{ statsLine }}</p>
        <RouterLink :to="{ name: 'map', params: { slug } }" class="viewer-edit mono">Open editor →</RouterLink>
      </div>
    </header>

    <div v-if="loading" class="viewer-loading mono">Loading…</div>
    <div v-else-if="error" class="viewer-loading mono error">{{ error }}</div>

    <div v-else class="viewer-body">
      <div ref="mapEl" class="map"></div>

      <aside v-if="mapData?.itinerary?.length" class="viewer-list">
        <p class="viewer-list-eyebrow mono">Stops</p>
        <ol class="viewer-stop-list">
          <li v-for="row in stopRows" :key="row.day.id">
            <button class="viewer-stop" type="button" @click="flyToDay(row.day)">
              <span class="viewer-stop-num mono">{{ row.label }}</span>
              <span class="viewer-stop-body">
                <span class="viewer-stop-name">{{ row.day.label || 'Untitled' }}</span>
                <span class="viewer-stop-date mono">{{ formatDateRange(row.day) }}</span>
              </span>
            </button>
          </li>
        </ol>
      </aside>
    </div>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import L from 'leaflet'
import { api } from '@/api.js'
import { parseGPX, trackColor } from '@/util.js'

const props = defineProps({
  slug: { type: String, required: true },
})

const mapData = ref(null)
const loading = ref(true)
const error = ref('')
const mapEl = ref(null)
let leaflet = null

const sortedDays = computed(() => {
  if (!mapData.value?.itinerary) return []
  return [...mapData.value.itinerary].sort((a, b) => a.date.localeCompare(b.date))
})

const statsLine = computed(() => {
  if (!mapData.value) return ''
  const stops = (mapData.value.itinerary || []).length
  const points = (mapData.value.points || []).filter((p) => p.category !== 'trail').length
  const trails = (mapData.value.points || []).filter((p) => p.category === 'trail').length
  const bits = []
  if (stops) bits.push(`${stops} stop${stops === 1 ? '' : 's'}`)
  if (trails) bits.push(`${trails} trail${trails === 1 ? '' : 's'}`)
  if (points) bits.push(`${points} pin${points === 1 ? '' : 's'}`)
  return bits.join(' · ')
})

// Stop labels accumulate the trip-day number across spans, so a 2-day stop
// "1–2" is followed by "3–4", not "2–3" (which would re-use day 2 — the
// off-by-one I shipped first time).
const stopRows = computed(() => {
  let cumulative = 0
  return sortedDays.value.map((d) => {
    const span = Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1
    const startNum = cumulative + 1
    const endNum = cumulative + span
    cumulative += span
    return { day: d, label: span > 1 ? `${startNum}–${endNum}` : `${startNum}` }
  })
})

function formatDateRange(d) {
  if (!d.end_date || d.end_date === d.date) return d.date
  return `${d.date} → ${d.end_date}`
}

function flyToDay(d) {
  if (!leaflet || d.lat == null || d.lng == null) return
  leaflet.flyTo([d.lat, d.lng], Math.max(leaflet.getZoom(), 11), { duration: 0.5 })
}

onMounted(async () => {
  try {
    // Reuse the snapshot-first loader so the viewer is fast on repeat visits
    // and works fully offline once cached.
    const { cached, refresh } = await api.getMapWithSnapshot(props.slug)
    if (cached) {
      mapData.value = cached
      loading.value = false
      await nextTick()
      initLeaflet()
    }
    const fresh = await refresh.catch(() => null)
    if (fresh) {
      mapData.value = fresh
      if (!cached) {
        loading.value = false
        await nextTick()
        initLeaflet()
      } else {
        // Refresh markers if data changed.
        renderAll()
      }
    } else if (!cached) {
      throw new Error('Map not found')
    }
  } catch (e) {
    error.value = e.message || 'Could not load this voyage.'
    loading.value = false
  }
})

function initLeaflet() {
  leaflet = L.map(mapEl.value, { zoomControl: false, attributionControl: true })
  L.control.zoom({ position: 'topright' }).addTo(leaflet)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(leaflet)
  renderAll()
  fitToContent()
}

function renderAll() {
  if (!leaflet || !mapData.value) return
  // Day pins (numbered)
  const stops = sortedDays.value.filter((d) => d.lat != null && d.lng != null)
  let cumulative = 0
  for (const d of stops) {
    const span = Math.round((new Date(d.end_date || d.date) - new Date(d.date)) / 86400000) + 1
    const startNum = cumulative + 1
    const endNum = cumulative + span
    const num = span > 1 ? `${startNum}–${endNum}` : `${startNum}`
    const m = L.marker([d.lat, d.lng], {
      icon: L.divIcon({
        className: 'iti-pin-wrapper',
        html: `<div class="iti-pin"><span>${num}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      }),
      title: d.label || 'Stop',
      zIndexOffset: 600,
    }).addTo(leaflet)
    if (d.label) {
      m.bindTooltip(`<span class="iti-tip-num">Day ${num}</span><span class="iti-tip-label">${d.label}</span>`, {
        permanent: true,
        direction: 'right',
        offset: [10, 0],
        className: 'iti-tip',
      })
    }
    cumulative += span
  }
  // Pins + trails
  let trailIdx = 0
  for (const p of mapData.value.points || []) {
    if (p.gpx_data) {
      try {
        const { coords } = parseGPX(p.gpx_data)
        L.polyline(coords, {
          color: p.color || trackColor(trailIdx),
          weight: 3,
          opacity: 0.85,
          lineCap: 'round',
        }).addTo(leaflet)
        trailIdx++
      } catch { /* skip bad GPX */ }
    } else {
      L.marker([p.lat, p.lng]).addTo(leaflet)
    }
  }
}

function fitToContent() {
  if (!leaflet || !mapData.value) return
  const coords = []
  for (const p of mapData.value.points || []) coords.push([p.lat, p.lng])
  for (const d of mapData.value.itinerary || []) {
    if (d.lat != null && d.lng != null) coords.push([d.lat, d.lng])
  }
  if (coords.length === 0) {
    leaflet.setView([mapData.value.center_lat, mapData.value.center_lng], 6)
    return
  }
  if (coords.length === 1) {
    leaflet.setView(coords[0], 11)
    return
  }
  leaflet.fitBounds(L.latLngBounds(coords), { padding: [60, 60], maxZoom: 13 })
}

onBeforeUnmount(() => {
  if (leaflet) { leaflet.remove(); leaflet = null }
})
</script>

<style scoped>
.viewer {
  position: fixed;
  inset: 0;
  display: grid;
  grid-template-rows: auto 1fr;
}
.viewer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--cream-edge);
  background: var(--paper);
  z-index: 700;
}
.viewer-bar-left { display: grid; gap: 0.1rem; min-width: 0; }
.viewer-bar-right { display: inline-flex; gap: 1rem; align-items: center; }
.viewer-eyebrow {
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.viewer-title {
  font-family: var(--display);
  font-size: 1.2rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.viewer-stats {
  font-size: 0.74rem;
  color: var(--ink-soft);
  letter-spacing: 0.06em;
  margin: 0;
}
.viewer-edit {
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--vermillion);
  text-decoration: none;
}
.viewer-edit:hover { color: var(--vermillion-deep); }

.viewer-body {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 280px;
}
.map {
  width: 100%;
  height: 100%;
  background: var(--cream-deep);
}
.viewer-list {
  border-left: 1px solid var(--cream-edge);
  background: var(--paper);
  padding: 0.7rem 0.8rem;
  overflow-y: auto;
}
.viewer-list-eyebrow {
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0 0 0.4rem;
}
.viewer-stop-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.3rem; }
.viewer-stop {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.55rem;
  align-items: center;
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  padding: 0.4rem 0.5rem;
  border-radius: 3px;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--ink);
}
.viewer-stop:hover { background: var(--cream); border-color: var(--cream-edge); }
.viewer-stop-num {
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  color: var(--ink-faded);
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  padding: 0.05rem 0.3rem;
  border-radius: 2px;
}
.viewer-stop-body { display: grid; gap: 0.05rem; min-width: 0; }
.viewer-stop-name {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.viewer-stop-date { font-size: 0.7rem; color: var(--ink-faded); letter-spacing: 0.04em; }
.viewer-loading {
  display: grid;
  place-items: center;
  font-size: 0.85rem;
  color: var(--ink-faded);
  letter-spacing: 0.1em;
}
.viewer-loading.error { color: var(--vermillion-deep); }

@media (max-width: 720px) {
  .viewer-body { grid-template-columns: 1fr; grid-template-rows: 1fr auto; }
  .viewer-list {
    border-left: none;
    border-top: 1px solid var(--cream-edge);
    max-height: 35vh;
  }
}
</style>
