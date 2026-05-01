<template>
  <div class="scrim" @click.self="$emit('close')">
    <div class="paper trail-modal">
      <p class="eyebrow">Trails near</p>
      <h3 class="trail-title">{{ name }}</h3>
      <p class="trail-meta mono">
        {{ formatLat(lat) }} · {{ formatLng(lng) }} · within
        <select v-model.number="radiusKm" class="radius-select">
          <option :value="5">5 km</option>
          <option :value="10">10 km</option>
          <option :value="20">20 km</option>
          <option :value="40">40 km</option>
        </select>
      </p>

      <p v-if="loading" class="hint mono">Searching OSM for hiking routes…</p>
      <p v-else-if="error" class="error sm">{{ error }}</p>
      <p v-else-if="!loading && results.length === 0" class="hint mono">
        No named trails returned. Widen the radius, or pan/zoom the map and use a different anchor.
      </p>

      <ol v-if="results.length" class="trails">
        <li v-for="t in results" :key="t.id">
          <button class="trail-row" type="button" @click="onPick(t)">
            <span class="trail-name">{{ t.name }}</span>
            <span class="trail-tags mono">
              <template v-if="t.kind">{{ t.kind }}</template>
              <template v-if="t.sac"> · SAC {{ t.sac }}</template>
              <template v-if="t.distance"> · {{ t.distance }} km</template>
              <template v-if="t.ref"> · #{{ t.ref }}</template>
            </span>
          </button>
        </li>
      </ol>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { fetchTrails } from '@/lib/overpass.js'
import { formatLat, formatLng } from '@/util.js'

const props = defineProps({
  lat: { type: Number, required: true },
  lng: { type: Number, required: true },
  name: { type: String, default: 'this day' },
})
const emit = defineEmits(['close', 'pick'])

const radiusKm = ref(10)
const loading = ref(false)
const error = ref('')
const results = ref([])

async function search() {
  loading.value = true
  error.value = ''
  results.value = []
  try {
    results.value = await fetchTrails(props.lat, props.lng, radiusKm.value)
  } catch (e) {
    error.value = e.message || 'Could not search trails.'
  } finally { loading.value = false }
}
watch(radiusKm, search)
onMounted(search)

function onPick(t) {
  emit('pick', t)
}

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
</script>

<style scoped>
.trail-modal {
  width: min(560px, 100%);
  max-height: 88vh;
  overflow-y: auto;
  display: grid;
  gap: 0.5rem;
  padding: 1.4rem 1.5rem;
}
.trail-title { margin: 0; font-size: 1.4rem; }
.trail-meta {
  font-size: 0.78rem;
  color: var(--ink-soft);
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.radius-select {
  font-family: var(--mono);
  font-size: 0.78rem;
  border: 1px dashed var(--cream-edge);
  background: var(--paper);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  cursor: pointer;
}
.trails {
  list-style: none;
  margin: 0.4rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.2rem;
  max-height: 50vh;
  overflow-y: auto;
}
.trail-row {
  width: 100%;
  text-align: left;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  padding: 0.55rem 0.7rem;
  cursor: pointer;
  display: grid;
  gap: 0.15rem;
  font: inherit;
  color: var(--ink);
}
.trail-row:hover {
  background: var(--paper);
  border-color: var(--ink);
  color: var(--vermillion);
}
.trail-name { font-weight: 600; }
.trail-tags { font-size: 0.72rem; color: var(--ink-soft); letter-spacing: 0.04em; }
.row { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.4rem; }
.hint { font-size: 0.78rem; color: var(--ink-faded); margin: 0.5rem 0; letter-spacing: 0.06em; }
.error.sm { font-size: 0.85rem; color: var(--vermillion-deep); margin: 0.4rem 0; }
</style>
