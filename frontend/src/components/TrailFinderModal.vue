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

      <div class="filter-row mono">
        <label class="filter-eyebrow">Length</label>
        <div class="seg" role="tablist">
          <button
            v-for="b in lengthBands"
            :key="b.key"
            type="button"
            class="seg-btn"
            :class="{ on: lengthBand === b.key }"
            :aria-pressed="lengthBand === b.key"
            @click="lengthBand = b.key"
          >{{ b.label }}</button>
        </div>
      </div>

      <p v-if="loading" class="hint mono">Searching OSM for hiking routes…</p>
      <p v-else-if="error" class="error sm">{{ error }}</p>
      <p v-else-if="!loading && filtered.length === 0" class="hint mono">
        <template v-if="results.length">No trails match this length filter — try Any.</template>
        <template v-else>No named trails returned. Widen the radius, or pan/zoom the map and use a different anchor.</template>
      </p>

      <ol v-if="filtered.length" class="trails">
        <li v-for="t in filtered" :key="t.id">
          <button
            class="trail-row"
            type="button"
            @mouseenter="$emit('preview', t)"
            @mouseleave="$emit('preview', null)"
            @focus="$emit('preview', t)"
            @blur="$emit('preview', null)"
            @click="onPick(t)"
          >
            <span class="trail-row-head">
              <span class="trail-name">{{ t.name }}</span>
              <span v-if="t.lengthKm" class="trail-len mono">{{ t.lengthKm }} km</span>
            </span>
            <span class="trail-tags mono">
              <template v-if="t.sacPlain">{{ t.sacPlain }}</template>
              <template v-if="t.distFromOrigin != null"><template v-if="t.sacPlain"> · </template>{{ t.distFromOrigin }} km away</template>
              <template v-if="t.ref"> · {{ t.ref }}</template>
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
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { fetchTrails } from '@/lib/overpass.js'
import { formatLat, formatLng } from '@/util.js'

const props = defineProps({
  lat: { type: Number, required: true },
  lng: { type: Number, required: true },
  name: { type: String, default: 'this day' },
})
const emit = defineEmits(['close', 'pick', 'preview'])

const radiusKm = ref(10)
const loading = ref(false)
const error = ref('')
const results = ref([])

// Length-band filter — the bands match common trail-running targets so a
// runner planning their week scrolls less. "Any" keeps the unfiltered list.
const lengthBands = [
  { key: 'any', label: 'Any', test: () => true },
  { key: 's',   label: '< 5 km',  test: (km) => km != null && km < 5 },
  { key: 'm',   label: '5–15 km', test: (km) => km != null && km >= 5 && km < 15 },
  { key: 'l',   label: '15–30 km',test: (km) => km != null && km >= 15 && km < 30 },
  { key: 'xl',  label: '30+ km',  test: (km) => km != null && km >= 30 },
]
const lengthBand = ref('any')
const filtered = computed(() => {
  const band = lengthBands.find((b) => b.key === lengthBand.value) || lengthBands[0]
  return results.value.filter((t) => band.test(t.lengthKm))
})

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

// Translate the SAC mountaineering scale (`hiking`, `mountain_hiking`,
// `demanding_mountain_hiking`, `alpine_hiking`, …) into the plain words a
// real walker would use. Anything we don't recognise gets dropped — empty
// space beats "SAC mountain_hiking" jargon in the trail list.
const SAC_PLAIN = {
  hiking: 'easy',
  mountain_hiking: 'moderate',
  demanding_mountain_hiking: 'demanding',
  alpine_hiking: 'alpine',
  demanding_alpine_hiking: 'demanding alpine',
  difficult_alpine_hiking: 'difficult alpine',
}
function sacPlain(sac) {
  if (!sac) return null
  return SAC_PLAIN[sac] || null
}

// The chip after each trail name. We deliberately drop the raw OSM `kind`
// (values like "mountain_hiking" leaked through) and only keep tags a user
// can act on: the human-friendly difficulty, distance, and route ref.
function trailTags(t) {
  const out = []
  const sp = sacPlain(t.sac)
  if (sp) out.push(sp)
  if (t.distance) out.push(`${t.distance} km`)
  if (t.ref) out.push(`#${t.ref}`)
  return out
}

function onPick(t) {
  // Drop any preview line so the parent can replace with the persistent pin.
  emit('preview', null)
  emit('pick', t)
}

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEsc)
  emit('preview', null)
})
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
.trail-row:hover,
.trail-row:focus-visible {
  background: var(--paper);
  border-color: var(--ink);
  color: var(--vermillion);
  outline: none;
}
.trail-row-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  justify-content: space-between;
}
.trail-name { font-weight: 600; }
.trail-len {
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: var(--vermillion);
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  padding: 0.05rem 0.35rem;
  border-radius: 2px;
  flex-shrink: 0;
}
.trail-tags { font-size: 0.72rem; color: var(--ink-soft); letter-spacing: 0.04em; }

.filter-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0;
  border-bottom: 1px dotted var(--cream-edge);
  margin-bottom: 0.3rem;
}
.filter-eyebrow {
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.seg {
  display: inline-flex;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  overflow: hidden;
  flex-wrap: wrap;
}
.seg-btn {
  background: transparent;
  border: none;
  padding: 0.18rem 0.6rem;
  font-family: var(--mono);
  font-size: 0.66rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
}
.seg-btn:hover { color: var(--ink); }
.seg-btn.on { background: var(--ink); color: var(--paper); }
.row { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.4rem; }
.hint { font-size: 0.78rem; color: var(--ink-faded); margin: 0.5rem 0; letter-spacing: 0.06em; }
.error.sm { font-size: 0.85rem; color: var(--vermillion-deep); margin: 0.4rem 0; }
</style>
