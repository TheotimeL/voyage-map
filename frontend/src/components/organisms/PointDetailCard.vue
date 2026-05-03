<template>
  <article class="detail paper">
    <button class="close" type="button" aria-label="Close" @click="$emit('close')">×</button>

    <div class="head">
      <span class="badge"><span>{{ emoji }}</span></span>
      <div>
        <p class="eyebrow">{{ catLabel }}</p>
        <h3 class="title">{{ point.title || `Untitled ${catLabel.toLowerCase()}` }}</h3>
        <span
          v-if="point.priority === 'must'"
          class="prio-chip prio-must"
          title="Must-see — high priority"
        >★ Must-see</span>
        <span
          v-else-if="point.priority === 'maybe'"
          class="prio-chip prio-maybe"
          title="Maybe — nice to have"
        >○ Maybe</span>
      </div>
    </div>

    <p v-if="trailStats" class="trail-line mono" :style="point.color ? { '--swatch': point.color } : null">
      <span class="trail-swatch" />
      <span>{{ trailStats.km }} km<template v-if="trailStats.gain != null"> · D+ {{ trailStats.gain }} m</template></span>
    </p>

    <p v-if="excerpt" class="excerpt">{{ excerpt }}</p>

    <p class="coord meta">
      <span v-if="placeName" class="place-name">{{ placeName }}</span>
      <span class="coord-text">{{ formatLat(point.lat) }} · {{ formatLng(point.lng) }}</span>
    </p>

    <div class="actions">
      <button class="btn btn-ghost" type="button" @click="onDirections">Directions →</button>
      <button class="btn directions-fill" type="button" @click="$emit('open-panel')">↗ Open</button>
    </div>
  </article>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { CATEGORIES, formatLat, formatLng, openInMaps, parseGPX } from '@/util.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'
import { reverseGeocode } from '@/api.js'

const props = defineProps({
  point: { type: Object, required: true },
})
defineEmits(['open-panel', 'close'])

function onDirections() {
  openInMaps(props.point.lat, props.point.lng, props.point.title || 'Place')
}

// Reverse-geocoded place name — useful for trail-finder pins (no GPX) where
// coords alone leave you wondering "where exactly is this?". Cached per
// point id since the user may flip between cards.
const placeNameCache = new Map()
const placeName = ref('')
async function resolvePlaceName(p) {
  placeName.value = ''
  if (!p) return
  if (placeNameCache.has(p.id)) {
    placeName.value = placeNameCache.get(p.id)
    return
  }
  const name = await reverseGeocode(p.lat, p.lng)
  if (name && p.id === props.point.id) {
    placeNameCache.set(p.id, name)
    placeName.value = name
  }
}
watch(() => props.point.id, () => resolvePlaceName(props.point), { immediate: true })

const fallback = CATEGORIES[CATEGORIES.length - 1]
const cat = computed(() => CATEGORIES.find((c) => c.key === props.point.category) || fallback)
const emoji = computed(() => cat.value.emoji)
const catLabel = computed(() => cat.value.label)

// Plain-text excerpt for the popover (full markdown rendering moved into the
// DetailPanel — keeping the card narrow so it doesn't fight the map for room).
const excerpt = computed(() => {
  const s = props.point.comment || ''
  if (!s.trim()) return ''
  // Strip the `[FLAG, FLAG]` prefix and basic markdown for a clean preview line.
  const stripped = s
    .replace(/^\s*\[[^\]]+\]\s*/, '')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[*_#`>~]/g, '')
    .trim()
  if (!stripped) return ''
  return stripped.length > 140 ? stripped.slice(0, 140) + '…' : stripped
})

const trailStats = computed(() => {
  if (!props.point.gpx_data) return null
  try {
    const { coords, elevations } = parseGPX(props.point.gpx_data)
    const series = buildElevationSeries(coords, elevations)
    if (!series.length) return null
    const { gain } = elevationStats(series)
    return {
      km: (series[series.length - 1].dist / 1000).toFixed(1),
      gain: gain == null ? null : Math.round(gain),
    }
  } catch { return null }
})
</script>

<style scoped>
.detail {
  position: absolute;
  /* Top-of-map chrome (mode toggle pill) sits at top: 96px and is ~36px tall
     — its bottom edge is around 132px. Park the card just below so the title
     doesn't disappear behind the pill on desktop. */
  top: 9rem;
  right: 1rem;
  width: min(300px, calc(100% - 2rem));
  z-index: 800;
  padding: 0.85rem 1rem 0.7rem;
  display: grid;
  gap: 0.5rem;
}
.close {
  position: absolute;
  top: 0.4rem;
  right: 0.6rem;
  background: transparent;
  border: none;
  font-family: var(--body);
  font-size: 1.4rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
}
.close:hover { color: var(--ink); background: var(--cream); }

.head { display: flex; gap: 0.7rem; align-items: center; }
.badge {
  width: 2.2rem;
  height: 2.2rem;
  display: grid;
  place-items: center;
  font-size: 1.05rem;
  background: var(--paper);
  border: 2.5px solid var(--vermillion);
  border-radius: 50%;
  flex-shrink: 0;
}

.title {
  margin: 0.1rem 0 0;
  font-size: 1.15rem;
  line-height: 1.05;
  text-transform: uppercase;
}
.prio-chip {
  display: inline-block;
  margin-top: 0.25rem;
  padding: 0.06rem 0.4rem;
  font-family: var(--mono);
  font-size: 0.66rem;
  letter-spacing: 0.04em;
  border: 1px solid currentColor;
  border-radius: 999px;
  line-height: 1.4;
}
.prio-chip.prio-must { color: var(--vermillion); }
.prio-chip.prio-maybe { color: var(--ink-faded); }

.excerpt {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.35;
  color: var(--ink-soft);
  /* Clamp to 2 lines so the popover stays small — if you want more, hit Open. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta {
  margin: 0;
  font-size: 0.75rem;
  display: grid;
  gap: 0.1rem;
}
.place-name { color: var(--ink-soft); font-weight: 500; }
.coord-text { color: var(--ink-faded); font-family: var(--mono); font-size: 0.68rem; }

.trail-line {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--swatch, var(--ink-faded));
}
.trail-swatch {
  display: inline-block;
  width: 14px;
  height: 4px;
  background: var(--swatch, var(--ink-faded));
  border-radius: 2px;
}

.actions {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.2rem;
}
.actions .btn-ghost { flex: 1; }
.directions-fill { flex: 1.2; }

@media (max-width: 720px) {
  .detail { top: auto; bottom: 1rem; right: 1rem; left: 1rem; width: auto; }
}
</style>
