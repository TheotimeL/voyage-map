<template>
  <div class="geo">
    <input
      ref="inp"
      v-model="query"
      class="field"
      :placeholder="placeholder"
      autocomplete="off"
      @input="onSearch"
      @keydown.down.prevent="moveSel(1)"
      @keydown.up.prevent="moveSel(-1)"
      @keydown.enter.prevent="pickSel"
      @keydown.esc="reset"
      @focus="showResults = results.length > 0"
      @blur="onBlur"
    />
    <ul v-if="showResults && results.length" class="results">
      <li
        v-for="(r, i) in results"
        :key="`${r.kind}-${r.id ?? ''}-${r.lat}-${r.lng}-${i}`"
        :class="{ sel: i === selectedIdx, local: r.kind === 'local' }"
        @mousedown.prevent="pick(r)"
        @mouseenter="selectedIdx = i"
      >
        <span v-if="r.kind === 'local'" class="r-icon" aria-hidden="true">{{ r.icon || '📌' }}</span>
        <span class="r-name">
          {{ r.kind === 'local' ? r.label : r.label.split(',')[0] }}
          <em v-if="r.kind === 'local'" class="r-tag mono">already on map</em>
        </span>
        <span class="r-rest">
          {{ r.kind === 'local'
            ? (r.sublabel || `${r.lat.toFixed(3)}, ${r.lng.toFixed(3)}`)
            : r.label.split(',').slice(1).join(',').trim() }}
        </span>
      </li>
    </ul>
    <p v-else-if="searchError" class="results error-line mono">{{ searchError }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { geocode } from '@/api.js'

const props = defineProps({
  placeholder: { type: String, default: 'Search a place…' },
  // Optional bias passed straight to geocode(): { bbox } or { lat, lng, radiusKm }
  bias: { type: Object, default: null },
  // Optional list of "local" candidates (e.g. existing pins) prepended to
  // results. Each entry: { id, lat, lng, label, sublabel?, icon?, kind: 'local' }
  localCandidates: { type: Array, default: () => [] },
})
const emit = defineEmits(['pick'])

const query = ref('')
const results = ref([])
const showResults = ref(false)
const selectedIdx = ref(-1)
const searchError = ref('')
const inp = ref(null)
let t = null

function onSearch() {
  clearTimeout(t)
  searchError.value = ''
  if (!query.value || query.value.trim().length < 2) {
    results.value = []
    showResults.value = false
    return
  }
  t = setTimeout(async () => {
    const q = query.value.trim().toLowerCase()
    const locals = (props.localCandidates || [])
      .filter((p) => (p.label || '').toLowerCase().includes(q) || (p.sublabel || '').toLowerCase().includes(q))
      .slice(0, 4)
      .map((p) => ({ ...p, kind: 'local' }))
    let remote = []
    try {
      remote = await geocode(query.value, props.bias)
    } catch (e) {
      searchError.value = e?.code === 'rate_limited'
        ? 'Search rate-limited — try again in a moment'
        : 'Search unavailable. Check your connection?'
    }
    const r = [...locals, ...remote.map((x) => ({ ...x, kind: 'remote' }))]
    results.value = r
    selectedIdx.value = r.length ? 0 : -1
    showResults.value = r.length > 0 || !!searchError.value
  }, 280)
}

function moveSel(d) {
  if (!results.value.length) return
  showResults.value = true
  selectedIdx.value = (selectedIdx.value + d + results.value.length) % results.value.length
}

function pickSel() {
  if (selectedIdx.value >= 0 && results.value[selectedIdx.value]) {
    pick(results.value[selectedIdx.value])
  }
}

function pick(r) {
  emit('pick', r)
  reset()
}

function reset() {
  query.value = ''
  results.value = []
  showResults.value = false
  selectedIdx.value = -1
  inp.value?.blur()
}

function onBlur() {
  // Delay so mousedown selection still fires.
  setTimeout(() => (showResults.value = false), 120)
}
</script>

<style scoped>
.geo { position: relative; }
.results {
  position: absolute;
  top: calc(100% + 4px);
  left: 0; right: 0;
  list-style: none;
  margin: 0; padding: 0.3rem 0;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  box-shadow: 0 14px 30px -10px rgba(40, 20, 0, 0.3);
  max-height: 260px;
  overflow-y: auto;
  z-index: 10;
}
.results li {
  padding: 0.45rem 0.7rem;
  cursor: pointer;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem;
  align-items: baseline;
}
.results li.sel,
.results li:hover { background: var(--cream); }
.results li.local { border-left: 3px solid var(--vermillion); padding-left: 0.5rem; }
.r-icon { font-size: 1rem; line-height: 1; }
.r-name { font-family: var(--display); color: var(--ink); }
.r-rest { font-size: 0.82rem; color: var(--ink-faded); }
.r-tag {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--vermillion);
  margin-left: 0.4rem;
}
.error-line {
  margin: 0;
  padding: 0.5rem 0.7rem;
  font-size: 0.78rem;
  color: var(--vermillion-deep);
  letter-spacing: 0.04em;
}
</style>
