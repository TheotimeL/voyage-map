<template>
  <div class="precache">
    <div class="seg" role="tablist">
      <button
        type="button"
        class="seg-btn"
        :class="{ on: scope === 'trip' }"
        :aria-pressed="scope === 'trip'"
        :disabled="running"
        title="Cache the entire trip bbox at zoom 6–12 (~5–20k tiles)"
        @click="scope = 'trip'"
      >Whole trip</button>
      <button
        type="button"
        class="seg-btn"
        :class="{ on: scope === 'leg' }"
        :aria-pressed="scope === 'leg'"
        :disabled="running || !nextLegBbox"
        :title="nextLegBbox ? `Cache only the next leg at higher zoom (~${tileEstimateForLeg} tiles)` : 'No upcoming leg yet'"
        @click="scope = 'leg'"
      >Next leg</button>
    </div>
    <button
      class="btn btn-tiny"
      :disabled="running || (scope === 'leg' && !nextLegBbox)"
      type="button"
      @click="run"
    >
      {{ buttonLabel }}
    </button>
    <div v-if="running || lastDone" class="precache-bar">
      <div class="bar-fill" :style="{ width: pct + '%' }"></div>
      <span class="bar-text mono">
        {{ pct }}% · {{ done }} / {{ total }}<template v-if="failed"> · {{ failed }} failed</template>
      </span>
    </div>
    <p v-if="error" class="error sm">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { tilesForBbox, preloadTiles } from '@/lib/precache.js'

const props = defineProps({
  bbox: {
    type: Object,
    default: () => ({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }),
  },
  // Bounding box of the next leg (today→next stop). Optional; when null the
  // "Next leg" segment is disabled. Comes from the parent because computing
  // it requires the live itinerary state.
  nextLegBbox: { type: Object, default: null },
  theme: { type: String, default: 'light' },
})

const running = ref(false)
const done = ref(0)
const total = ref(0)
const failed = ref(0)
const error = ref('')
const scope = ref('leg') // default to the smaller, faster option
const lastDone = ref(localStorage.getItem('voyage:precache:done') || '')

const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))
const buttonLabel = computed(() => {
  if (running.value) return 'Caching…'
  if (scope.value === 'leg') return lastDone.value ? 'Re-cache next leg' : 'Pre-cache next leg'
  return lastDone.value ? 'Re-cache whole trip' : 'Pre-cache whole trip'
})

// Rough tile estimate for the next leg at zooms 8–13 — enough resolution to
// read road labels, small enough to fit in the SW cache.
const tileEstimateForLeg = computed(() => {
  if (!props.nextLegBbox) return 0
  return tilesForBbox(props.nextLegBbox, [8, 13]).length
})

async function run() {
  running.value = true
  done.value = 0; failed.value = 0
  error.value = ''
  try {
    let tiles
    if (scope.value === 'leg' && props.nextLegBbox) {
      // Higher zoom for the leg — the user is about to look at this area
      // closely, so 8–13 buys turn-by-turn legibility without ballooning size.
      tiles = tilesForBbox(props.nextLegBbox, [8, 13])
    } else {
      tiles = tilesForBbox(props.bbox, [6, 12])
    }
    total.value = tiles.length
    await preloadTiles(tiles, props.theme, {
      onProgress: ({ done: d, failed: f }) => { done.value = d; failed.value = f },
    })
    lastDone.value = new Date().toISOString()
    localStorage.setItem('voyage:precache:done', lastDone.value)
  } catch (e) {
    error.value = e?.message || 'Pre-cache failed.'
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.precache { display: grid; gap: 0.4rem; justify-items: start; }
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
.seg-btn:hover:not(:disabled) { color: var(--ink); }
.seg-btn.on { background: var(--ink); color: var(--paper); }
.seg-btn:disabled { color: var(--ink-faded); cursor: not-allowed; }
.btn { font-family: var(--display); }
.precache-bar {
  position: relative;
  height: 18px;
  width: 100%;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 2px;
  overflow: hidden;
}
.bar-fill { height: 100%; background: var(--vermillion); transition: width 120ms linear; }
.bar-text {
  position: absolute;
  inset: 0;
  font-size: 0.66rem;
  letter-spacing: 0.1em;
  display: grid;
  place-items: center;
  color: var(--ink);
  font-weight: 700;
  mix-blend-mode: multiply;
}
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
