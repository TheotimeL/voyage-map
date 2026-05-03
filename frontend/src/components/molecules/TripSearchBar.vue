<template>
  <div class="trip-search">
    <input
      ref="inp"
      v-model="query"
      class="field"
      :placeholder="placeholder"
      autocomplete="off"
      @input="onInput"
      @keydown.down.prevent="moveSel(1)"
      @keydown.up.prevent="moveSel(-1)"
      @keydown.enter.prevent="pickSel"
      @keydown.esc="reset"
      @focus="onFocus"
      @blur="onBlur"
    />
    <ul v-if="showResults && pendingDebounce" class="results hint mono">
      <li class="hint-line">Searching…</li>
    </ul>
    <ul
      v-else-if="showResults && committedQuery && results.length"
      class="results"
    >
      <li
        v-for="(r, i) in results"
        :key="r.slug"
        :class="{ sel: i === selectedIdx }"
        @mousedown.prevent="pick(r)"
        @mouseenter="selectedIdx = i"
      >
        <span class="r-name">{{ r.title || 'Untitled voyage' }}</span>
        <span v-if="r.stats" class="r-rest mono">
          <template v-if="r.stats.days">{{ r.stats.days }}d · </template>
          {{ r.stats.points }} pin{{ r.stats.points === 1 ? '' : 's' }}
        </span>
      </li>
    </ul>
    <ul
      v-else-if="showResults && committedQuery && !results.length"
      class="results hint mono"
    >
      <li class="hint-line">No matching voyage in your recents</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const props = defineProps({
  trips: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Search your voyages…' },
  debounceMs: { type: Number, default: 1000 },
})
const emit = defineEmits(['pick'])

const query = ref('')
// Only this committed query drives result rendering — query updates on every
// keystroke but committed only updates after the debounce window expires.
const committedQuery = ref('')
const pendingDebounce = ref(false)
const showResults = ref(false)
const selectedIdx = ref(-1)
const inp = ref(null)
let debounceTimer = null

const results = computed(() => {
  const q = committedQuery.value.trim().toLowerCase()
  if (!q) return []
  return props.trips.filter((t) => {
    const title = (t.title || '').toLowerCase()
    const slug = (t.slug || '').toLowerCase()
    return title.includes(q) || slug.includes(q)
  })
})

function onInput() {
  showResults.value = true
  pendingDebounce.value = true
  if (debounceTimer) clearTimeout(debounceTimer)
  if (!query.value.trim()) {
    committedQuery.value = ''
    pendingDebounce.value = false
    return
  }
  debounceTimer = setTimeout(() => {
    committedQuery.value = query.value
    pendingDebounce.value = false
    selectedIdx.value = -1
  }, props.debounceMs)
}

function onFocus() {
  showResults.value = !!committedQuery.value || pendingDebounce.value
}
function onBlur() {
  setTimeout(() => { showResults.value = false }, 120)
}

function moveSel(delta) {
  const n = results.value.length
  if (!n) return
  selectedIdx.value = (selectedIdx.value + delta + n) % n
}
function pickSel() {
  const r = results.value[selectedIdx.value]
  if (r) pick(r)
}
function pick(r) {
  emit('pick', r)
  reset()
}
function reset() {
  query.value = ''
  committedQuery.value = ''
  pendingDebounce.value = false
  showResults.value = false
  selectedIdx.value = -1
  if (debounceTimer) clearTimeout(debounceTimer)
  if (inp.value) inp.value.blur()
}

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<style scoped>
.trip-search {
  position: relative;
  width: 100%;
}
.field {
  width: 100%;
  font-size: 0.95rem;
}
.results {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 20;
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  box-shadow: 4px 4px 0 var(--ink);
  max-height: 50vh;
  overflow-y: auto;
}
.results li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  cursor: pointer;
  border-bottom: 1px dashed var(--cream-edge);
}
.results li:last-child { border-bottom: none; }
.results li.sel,
.results li:hover { background: var(--cream); }
.r-name {
  font-family: var(--display);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-size: 0.95rem;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-rest {
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.06em;
  white-space: nowrap;
}
.results.hint .hint-line {
  cursor: default;
  color: var(--ink-faded);
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.55rem 0.7rem;
}
.results.hint li:hover { background: transparent; }
</style>
