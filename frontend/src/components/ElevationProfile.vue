<template>
  <section v-if="series.length" class="elev">
    <div class="elev-head">
      <p class="eyebrow">{{ name || 'Elevation' }}</p>
      <p class="elev-stats mono">
        ↑ {{ stats.gain }} m · ↓ {{ stats.loss }} m · {{ stats.distanceKm.toFixed(1) }} km
      </p>
      <button class="btn-icon-tiny" @click="$emit('close')" aria-label="Close">×</button>
    </div>
    <svg
      class="elev-svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      @mousemove="onMove"
      @mouseleave="onLeave"
    >
      <path :d="areaPath" class="area" />
      <path :d="linePath" class="line" />
      <line v-if="hover" :x1="hover.x" :x2="hover.x" :y1="0" :y2="H" class="cursor" />
      <circle v-if="hover" :cx="hover.x" :cy="hover.y" r="3" class="dot" />
    </svg>
    <p v-if="hover" class="elev-readout mono">
      {{ (hover.point.dist / 1000).toFixed(2) }} km · {{ Math.round(hover.point.ele) }} m
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { elevationStats } from '@/lib/elevation.js'

const props = defineProps({
  series: { type: Array, required: true },
  name: { type: String, default: '' },
})
const emit = defineEmits(['hover', 'close'])

const W = 800, H = 140, PAD = 6
const stats = computed(() => elevationStats(props.series))

const yMin = computed(() => stats.value.min ?? 0)
const yMax = computed(() => Math.max(stats.value.max ?? 0, yMin.value + 50))
const xMax = computed(() => props.series.at(-1)?.dist ?? 1)

function xFor(d) { return PAD + (d / xMax.value) * (W - 2 * PAD) }
function yFor(e) { return H - PAD - ((e - yMin.value) / (yMax.value - yMin.value)) * (H - 2 * PAD) }

const linePath = computed(() => {
  let d = ''
  for (let i = 0; i < props.series.length; i++) {
    const p = props.series[i]
    if (p.ele == null) continue
    d += (d ? 'L' : 'M') + xFor(p.dist) + ',' + yFor(p.ele)
  }
  return d
})

const areaPath = computed(() => {
  if (!linePath.value) return ''
  return linePath.value + ` L ${xFor(xMax.value)},${H - PAD} L ${xFor(0)},${H - PAD} Z`
})

const hover = ref(null)
function onMove(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const px = ((e.clientX - rect.left) / rect.width) * W
  const target = ((px - PAD) / (W - 2 * PAD)) * xMax.value
  let best = props.series[0], bestDelta = Infinity
  for (const p of props.series) {
    const d = Math.abs(p.dist - target)
    if (d < bestDelta) { bestDelta = d; best = p }
  }
  if (best?.ele == null) return
  hover.value = { x: xFor(best.dist), y: yFor(best.ele), point: best }
  emit('hover', best.coord)
}
function onLeave() {
  hover.value = null
  emit('hover', null)
}
</script>

<style scoped>
.elev {
  position: absolute;
  left: 1rem; right: 1rem; bottom: 1rem;
  z-index: 700;
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  box-shadow: 0 6px 20px rgba(0,0,0,0.18);
  display: grid;
  gap: 0.3rem;
}
.elev-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: baseline;
  gap: 0.6rem;
}
.elev-stats { color: var(--ink-soft); font-size: 0.78rem; }
.btn-icon-tiny {
  background: transparent; border: none; cursor: pointer;
  font-size: 1.1rem; line-height: 1; color: var(--ink-faded);
}
.btn-icon-tiny:hover { color: var(--vermillion); }
.elev-svg { width: 100%; height: 110px; display: block; }
.area { fill: rgba(232, 93, 60, 0.15); }
.line { fill: none; stroke: var(--vermillion); stroke-width: 1.6; }
.cursor { stroke: var(--ink-faded); stroke-width: 1; stroke-dasharray: 3 3; }
.dot { fill: var(--vermillion); stroke: var(--paper); stroke-width: 1.5; }
.elev-readout { font-size: 0.8rem; color: var(--ink-soft); margin: 0; }
</style>
