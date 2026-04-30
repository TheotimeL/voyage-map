<template>
  <div class="radius">
    <div class="row">
      <span class="lbl">Radius</span>
      <span class="coord">{{ formatRadius(modelValue) }}</span>
    </div>
    <input
      type="range"
      :min="0"
      :max="1000"
      :step="1"
      :value="tick"
      @input="onInput"
      @change="onChange"
    />
    <div class="ticks">
      <button v-for="p in presets" :key="p" type="button" class="tick-btn" @click="setRadius(p)">
        {{ formatRadius(p, true) }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, required: true },
})
const emit = defineEmits(['update:modelValue', 'change'])

const RADIUS_MIN = 500           // 500 m
const RADIUS_MAX = 2_000_000     // 2 000 km

const presets = [2000, 10000, 50000, 250000, 1000000]

const tick = computed(() => radiusToTick(props.modelValue))

function tickToRadius(t) {
  const lo = Math.log(RADIUS_MIN), hi = Math.log(RADIUS_MAX)
  const raw = Math.exp(lo + ((hi - lo) * t) / 1000)
  // Snap nicely depending on magnitude.
  if (raw < 2000) return Math.round(raw / 100) * 100        // 100 m
  if (raw < 20000) return Math.round(raw / 500) * 500       // 500 m
  if (raw < 200000) return Math.round(raw / 1000) * 1000    // 1 km
  return Math.round(raw / 5000) * 5000                       // 5 km
}

function radiusToTick(r) {
  const lo = Math.log(RADIUS_MIN), hi = Math.log(RADIUS_MAX)
  const v = Math.max(RADIUS_MIN, Math.min(RADIUS_MAX, r))
  return Math.round(((Math.log(v) - lo) / (hi - lo)) * 1000)
}

function onInput(e) {
  emit('update:modelValue', tickToRadius(Number(e.target.value)))
}
function onChange(e) {
  emit('change', tickToRadius(Number(e.target.value)))
}
function setRadius(r) {
  emit('update:modelValue', r)
  emit('change', r)
}

function formatRadius(m, compact = false) {
  if (m < 1000) return `${m} m`
  const km = m / 1000
  if (compact) {
    if (km >= 100) return `${Math.round(km)}km`
    return `${km % 1 === 0 ? km : km.toFixed(1)}km`
  }
  return `${km % 1 === 0 ? km : km.toFixed(1)} km`
}
</script>

<style scoped>
.radius { display: grid; gap: 0.35rem; }
.row { display: flex; justify-content: space-between; align-items: baseline; }
.lbl {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.ticks {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
  margin-top: 0.2rem;
}
.tick-btn {
  font-family: var(--mono);
  font-size: 0.72rem;
  font-weight: 500;
  background: transparent;
  border: 1.25px solid var(--ink);
  border-radius: 3px;
  padding: 0.22rem 0.5rem;
  color: var(--ink);
  cursor: pointer;
  transition: all 90ms ease;
}
.tick-btn:hover { background: var(--ink); color: var(--paper); }
</style>
