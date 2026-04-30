<template>
  <ul class="point-list">
    <li v-if="points.length === 0" class="empty">
      <em>No marks yet. Click the map to drop one.</em>
    </li>
    <li
      v-for="p in points"
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
            {{ trailStats(p).km }} km · D+ {{ trailStats(p).gain }} m
          </template>
        </div>
        <div v-if="p.comment" class="comment">{{ p.comment }}</div>
        <div class="coord">
          {{ formatLat(p.lat) }} · {{ formatLng(p.lng) }}
        </div>
      </div>
    </li>
  </ul>
</template>

<script setup>
import { CATEGORIES, formatLat, formatLng, parseGPX } from '@/util.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'

defineProps({
  points: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
})
defineEmits(['select'])

const emojiMap = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function emojiFor(key) {
  return emojiMap[key] || '📍'
}
function untitled(p) {
  const cat = CATEGORIES.find((c) => c.key === p.category)
  return cat ? cat.label : 'Untitled'
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
    const out = { km, gain: Math.round(gain) }
    trailMemo.set(p.id, out)
    return out
  } catch {
    trailMemo.set(p.id, null)
    return null
  }
}
</script>

<style scoped>
.point-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
}
.empty {
  font-family: var(--body);
  color: var(--ink-faded);
  padding: 1rem 0.2rem;
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
.trail-stats {
  font-size: 0.76rem;
  color: var(--swatch, var(--ink-faded));
  margin-top: 0.2rem;
  letter-spacing: 0.04em;
  font-weight: 600;
}
.point.is-trail { border-left: 4px solid var(--swatch, var(--ink-faded)); padding-left: 0.6rem; }
</style>
