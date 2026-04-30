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
        :key="`${r.lat}-${r.lng}-${i}`"
        :class="{ sel: i === selectedIdx }"
        @mousedown.prevent="pick(r)"
        @mouseenter="selectedIdx = i"
      >
        <span class="r-name">{{ r.label.split(',')[0] }}</span>
        <span class="r-rest">{{ r.label.split(',').slice(1).join(',').trim() }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { geocode } from '@/api.js'

defineProps({
  placeholder: { type: String, default: 'Search a place…' },
})
const emit = defineEmits(['pick'])

const query = ref('')
const results = ref([])
const showResults = ref(false)
const selectedIdx = ref(-1)
const inp = ref(null)
let t = null

function onSearch() {
  clearTimeout(t)
  if (!query.value || query.value.trim().length < 2) {
    results.value = []
    showResults.value = false
    return
  }
  t = setTimeout(async () => {
    const r = await geocode(query.value).catch(() => [])
    results.value = r
    selectedIdx.value = r.length ? 0 : -1
    showResults.value = r.length > 0
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
.r-name { font-family: var(--display); color: var(--ink); }
.r-rest { font-size: 0.82rem; color: var(--ink-faded); }
</style>
