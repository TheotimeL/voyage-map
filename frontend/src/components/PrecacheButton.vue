<template>
  <div class="precache">
    <button
      class="btn btn-tiny"
      :disabled="running"
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
  theme: { type: String, default: 'light' },
})

const running = ref(false)
const done = ref(0)
const total = ref(0)
const failed = ref(0)
const error = ref('')
const lastDone = ref(localStorage.getItem('voyage:precache:done') || '')

const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))
const buttonLabel = computed(() => {
  if (running.value) return 'Caching…'
  if (lastDone.value) return 'Re-cache trip area'
  return 'Pre-cache trip area'
})

async function run() {
  running.value = true
  done.value = 0; failed.value = 0
  error.value = ''
  try {
    const tiles = tilesForBbox(props.bbox, [6, 12])
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
.precache { display: grid; gap: 0.3rem; }
.precache-bar {
  position: relative;
  height: 4px;
  background: var(--cream-edge);
  border-radius: 2px;
  overflow: hidden;
}
.bar-fill { height: 100%; background: var(--vermillion); transition: width 120ms linear; }
.bar-text {
  position: absolute;
  inset: 0;
  font-size: 0.65rem;
  display: grid;
  place-items: center;
  color: var(--ink-soft);
}
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
