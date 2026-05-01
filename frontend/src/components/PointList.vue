<template>
  <div class="point-list-wrap">
    <div v-if="points.length === 0" class="empty-card">
      <p class="empty-eyebrow mono">№ 003 · Wishlist</p>
      <h4 class="empty-title">Empty list.</h4>
      <p class="empty-hint mono">Drop a pin from the map, or paste a link.</p>
    </div>
    <template v-else>
      <section v-for="g in groups" :key="g.key" class="group">
        <h5 v-if="g.title" class="group-title mono">{{ g.title }} · {{ g.items.length }}</h5>
        <ul class="point-list">
          <li
            v-for="p in g.items"
            :key="p.id"
            class="point"
            :class="{ active: p.id === activeId, 'is-trail': !!p.gpx_data }"
            :style="p.gpx_data && p.color ? { '--swatch': p.color } : null"
            @click="$emit('select', p)"
          >
            <span class="pin-mini">{{ emojiFor(p.category) }}</span>
            <div class="text">
              <div class="title">{{ p.title || untitled(p) }}</div>
              <div v-if="p.gpx_data" class="trail-stats mono">
                <template v-if="trailStats(p)">
                  {{ trailStats(p).km }} km<template v-if="trailStats(p).gain != null"> · D+ {{ trailStats(p).gain }} m</template>
                </template>
              </div>
              <div v-if="p.comment" class="comment">{{ p.comment }}</div>
              <div class="coord">
                <template v-if="p._distKm != null"><span class="dist mono">{{ fmtDist(p._distKm) }}</span> · </template>
                {{ formatLat(p.lat) }} · {{ formatLng(p.lng) }}
              </div>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CATEGORIES, formatLat, formatLng, parseGPX } from '@/util.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'

const props = defineProps({
  points: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
})
defineEmits(['select'])

// Group into Pins vs Trails when the list isn't already sorted by distance
// (when myLocation is shared, _distKm is set on every row and grouping would
// undo that ordering — so we keep the flat sort instead).
const isDistanceSorted = computed(() =>
  props.points.length > 0 && props.points.every((p) => p._distKm != null),
)
const groups = computed(() => {
  if (isDistanceSorted.value) {
    return [{ key: 'all', title: '', items: props.points }]
  }
  const trails = props.points.filter((p) => p.gpx_data || p.category === 'trail')
  const pins = props.points.filter((p) => !p.gpx_data && p.category !== 'trail')
  const out = []
  if (pins.length) out.push({ key: 'pins', title: 'Pins', items: pins })
  if (trails.length) out.push({ key: 'trails', title: 'Trails', items: trails })
  // If only one of the two, drop the title — no point in a single-section heading.
  if (out.length === 1) out[0].title = ''
  return out
})

const emojiMap = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function emojiFor(key) {
  return emojiMap[key] || '📍'
}
function untitled(p) {
  const cat = CATEGORIES.find((c) => c.key === p.category)
  return cat ? cat.label : 'Untitled'
}

function fmtDist(km) {
  if (km < 1) return `${Math.round(km * 1000)} m`
  if (km < 10) return `${km.toFixed(1)} km`
  return `${Math.round(km)} km`
}

// Trail-stats memo: parse each gpx_data once.
const trailMemo = new Map() // id → { km, gain } | null
function trailStats(p) {
  if (!p.gpx_data) return null
  if (trailMemo.has(p.id)) return trailMemo.get(p.id)
  try {
    const { coords, elevations } = parseGPX(p.gpx_data)
    const series = buildElevationSeries(coords, elevations)
    if (!series.length) { trailMemo.set(p.id, null); return null }
    const km = (series[series.length - 1].dist / 1000).toFixed(1)
    const { gain } = elevationStats(series)
    const out = { km, gain: gain == null ? null : Math.round(gain) }
    trailMemo.set(p.id, out)
    return out
  } catch {
    trailMemo.set(p.id, null)
    return null
  }
}
</script>

<style scoped>
.point-list-wrap { display: grid; gap: 0.9rem; }
.group { display: grid; gap: 0.4rem; }
.group-title {
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0;
  padding-bottom: 0.15rem;
  border-bottom: 1px dotted var(--cream-edge);
}
.point-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}
/* Empty-list card — editorial-cartographer style: cream/ink only, no
   vermillion accent, eyebrow + display-font line + mono one-liner hint. */
.empty-card {
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  padding: 1rem 0.95rem 1.05rem;
  display: grid;
  gap: 0.25rem;
  text-align: left;
}
.empty-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.empty-title {
  font-family: var(--display);
  margin: 0;
  font-size: 1.4rem;
  line-height: 1;
  letter-spacing: 0.005em;
  color: var(--ink);
  text-transform: uppercase;
}
.empty-hint {
  margin: 0.25rem 0 0;
  font-size: 0.74rem;
  letter-spacing: 0.05em;
  color: var(--ink-soft);
}
.point {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.7rem;
  align-items: start;
  padding: 0.55rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 2px;
  cursor: pointer;
  transition: background 90ms ease, border-color 90ms ease;
}
.point:hover { background: var(--cream); border-color: var(--cream-edge); }
.point.active { background: var(--cream); border-color: var(--ink); }
.pin-mini {
  font-size: 1rem;
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  background: var(--paper);
  border: 2px solid var(--vermillion);
  border-radius: 50%;
  flex-shrink: 0;
}
.title {
  font-family: var(--body);
  font-weight: 600;
  font-size: 1rem;
  color: var(--ink);
  line-height: 1.2;
}
.comment {
  font-size: 0.92rem;
  color: var(--ink-soft);
  margin-top: 0.15rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.coord { margin-top: 0.2rem; font-size: 0.78rem; }
.dist { font-weight: 700; color: var(--vermillion); }
.trail-stats {
  font-size: 0.76rem;
  color: var(--swatch, var(--ink-faded));
  margin-top: 0.2rem;
  letter-spacing: 0.04em;
  font-weight: 600;
}
.point.is-trail { border-left: 4px solid var(--swatch, var(--ink-faded)); padding-left: 0.6rem; }
</style>
