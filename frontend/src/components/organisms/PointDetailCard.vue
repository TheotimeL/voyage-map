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

    <p v-if="point.comment" class="comment">{{ point.comment }}</p>
    <p v-else class="comment muted"><em>No notes yet.</em></p>

    <p class="coord meta">
      <span v-if="placeName" class="place-name">{{ placeName }}</span>
      <span class="coord-text">{{ formatLat(point.lat) }} · {{ formatLng(point.lng) }}</span>
    </p>

    <button class="btn directions" type="button" @click="onDirections">Directions →</button>

    <div class="actions">
      <button class="btn btn-ghost" @click="$emit('edit')">Edit</button>
      <button class="btn btn-ghost danger" @click="$emit('delete')">Delete</button>
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
defineEmits(['edit', 'delete', 'close'])

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

function onDirections() {
  openInMaps(props.point.lat, props.point.lng, props.point.title || cat.value.label)
}
</script>

<style scoped>
.detail {
  position: absolute;
  /* The map-topbar pill (mode toggle + tools, in MapView.vue) sits at top:
     96px and is roughly 36px tall — its bottom edge is around 132px. We
     park the detail card just below that so the title doesn't disappear
     behind the pill on desktop. */
  top: 9rem;
  right: 1rem;
  width: min(320px, calc(100% - 2rem));
  z-index: 800;
  padding: 1rem 1.1rem 0.9rem;
  display: grid;
  gap: 0.55rem;
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
  width: 2.4rem;
  height: 2.4rem;
  display: grid;
  place-items: center;
  font-size: 1.15rem;
  background: var(--paper);
  border: 2.5px solid var(--vermillion);
  border-radius: 50%;
  flex-shrink: 0;
}

.title {
  margin: 0.1rem 0 0;
  font-size: 1.35rem;
  line-height: 1.05;
  text-transform: uppercase;
}
.prio-chip {
  display: inline-block;
  margin-top: 0.3rem;
  padding: 0.08rem 0.45rem;
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  border: 1px solid currentColor;
  border-radius: 999px;
  line-height: 1.4;
}
.prio-chip.prio-must { color: var(--vermillion); }
.prio-chip.prio-maybe { color: var(--ink-faded); }

.comment {
  font-size: 0.96rem;
  color: var(--ink-soft);
  margin: 0;
  white-space: pre-wrap;
}
.comment.muted { color: var(--ink-faded); }

.meta {
  margin: 0;
  font-size: 0.78rem;
  display: grid;
  gap: 0.1rem;
}
.place-name { color: var(--ink-soft); font-weight: 500; }
.coord-text { color: var(--ink-faded); font-family: var(--mono); font-size: 0.7rem; }

.trail-line {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
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

.directions {
  width: 100%;
  margin-top: 0.2rem;
}
.actions {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
  margin-top: 0.2rem;
}
.danger { color: var(--vermillion); border-color: var(--vermillion); }
.danger:hover { background: var(--vermillion); color: var(--paper); border-color: var(--vermillion); }

@media (max-width: 720px) {
  .detail { top: auto; bottom: 1rem; right: 1rem; left: 1rem; width: auto; }
}
</style>
