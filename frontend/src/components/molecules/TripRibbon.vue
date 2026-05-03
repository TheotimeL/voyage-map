<template>
  <div
    v-if="rows.length"
    class="ribbon-shell"
    :class="{ 'has-overflow-left': hasOverflowLeft, 'has-overflow-right': hasOverflowRight }"
  >
    <button
      v-if="hasOverflowLeft"
      type="button"
      class="ribbon-arrow ribbon-arrow-left mono"
      title="Scroll earlier stops into view"
      aria-label="Scroll left"
      @click="scrollByStep(-1)"
    >‹</button>
    <nav ref="ribEl" class="ribbon" aria-label="Trip overview" @scroll.passive="updateOverflow">
      <button
        v-for="r in rows"
        :key="r.day.id"
        type="button"
        class="rib-stop"
        :class="{ today: r.isToday, past: r.isPast, selected: selectedDayId === r.day.id }"
        :title="`${r.dateLine} · ${r.day.label || 'Untitled'}`"
        @click="$emit('go', r.day)"
      >
        <span class="rib-num mono">{{ r.numLabel }}</span>
        <span class="rib-name">{{ r.shortName || 'Untitled' }}</span>
        <span class="rib-date mono">{{ r.dateChip }}</span>
      </button>
    </nav>
    <button
      v-if="hasOverflowRight"
      type="button"
      class="ribbon-arrow ribbon-arrow-right mono"
      title="Scroll later stops into view"
      aria-label="Scroll right"
      @click="scrollByStep(1)"
    >›</button>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { todayISO } from '@/util.js'
import { formatDate } from '@/lib/settings.js'

const props = defineProps({
  days: { type: Array, default: () => [] },
  // Day id of the currently focused stop (the one the user just tapped).
  // Visualised as an outlined chip so the position-in-trip stays anchored
  // while the map zooms/pans away under the finger.
  selectedDayId: { type: [Number, String, null], default: null },
})
defineEmits(['go'])

const today = computed(() => todayISO())
const ribEl = ref(null)

// Overflow state — drives the left/right scroll arrows + edge fade gradients
// so a 21-stop trip stops silently clipping past the viewport edge.
const hasOverflowLeft = ref(false)
const hasOverflowRight = ref(false)
function updateOverflow() {
  const root = ribEl.value
  if (!root) return
  hasOverflowLeft.value = root.scrollLeft > 4
  hasOverflowRight.value = root.scrollLeft + root.clientWidth < root.scrollWidth - 4
}

function scrollByStep(dir) {
  const root = ribEl.value
  if (!root) return
  // ~75% of the visible width per click — enough to feel like real travel
  // along the trip without skipping past the chips at the new edge.
  const step = Math.max(120, Math.round(root.clientWidth * 0.75))
  root.scrollBy({ left: dir * step, behavior: 'smooth' })
}

// Center today's chip (or the next future stop, if today is between stops)
// in the visible ribbon so users don't have to scroll right mid-trip. If
// every stop is in the future the first chip stays at the left as-is.
function scrollActiveIntoView(behavior = 'auto') {
  const root = ribEl.value
  if (!root) return
  const target = root.querySelector('.rib-stop.selected')
    || root.querySelector('.rib-stop.today')
    || [...root.querySelectorAll('.rib-stop:not(.past)')][0]
  if (!target) {
    updateOverflow()
    return
  }
  // Don't scroll if the active stop is already the first one — keep the
  // natural left-anchored layout for pre-trip and just-started trips.
  if (target === root.firstElementChild) {
    updateOverflow()
    return
  }
  const left = target.offsetLeft - root.clientWidth / 2 + target.clientWidth / 2
  root.scrollTo({ left: Math.max(0, left), behavior })
  // scrollTo schedules a smooth animation; refresh state after it settles
  // (and once synchronously so arrows appear immediately on mount).
  updateOverflow()
  setTimeout(updateOverflow, 250)
}

let resizeObs = null
onMounted(() => {
  nextTick(() => {
    scrollActiveIntoView('auto')
    updateOverflow()
  })
  if (typeof ResizeObserver !== 'undefined' && ribEl.value) {
    resizeObs = new ResizeObserver(() => updateOverflow())
    resizeObs.observe(ribEl.value)
  }
})
onBeforeUnmount(() => {
  if (resizeObs) { resizeObs.disconnect(); resizeObs = null }
})
watch(() => props.days, () => nextTick(() => {
  scrollActiveIntoView('auto')
  updateOverflow()
}), { deep: true })
watch(() => props.selectedDayId, () => nextTick(() => {
  scrollActiveIntoView('smooth')
  updateOverflow()
}))

const rows = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let cumulative = 0
  return sorted.map((d) => {
    const end = d.end_date || d.date
    const span = Math.round((new Date(end) - new Date(d.date)) / 86400000) + 1
    const startNum = cumulative + 1
    const endNum = cumulative + span
    cumulative += span
    const isToday = today.value >= d.date && today.value <= end
    const isPast = end < today.value
    const dateChip = formatChip(d.date)
    const dateLine = span > 1 ? `${d.date} → ${end}` : d.date
    const shortName = (d.label || '').split(/[,·—-]/)[0].trim().slice(0, 18)
    return {
      day: d,
      numLabel: span > 1 ? `${startNum}–${endNum}` : `${startNum}`,
      shortName,
      dateChip,
      dateLine,
      isToday,
      isPast,
    }
  })
})

function formatChip(iso) {
  // Short date form to fit a phone-width chip; respects the user's dateFmt
  // setting ("9 May" / "May 9" / "2026-05-09").
  return formatDate(iso)
}
</script>

<style scoped>
.ribbon-shell {
  position: relative;
  background: var(--paper);
  border-bottom: 1px solid var(--cream-edge);
}
.ribbon {
  display: flex;
  gap: 0.2rem;
  align-items: stretch;
  overflow-x: auto;
  padding: 0.4rem 0.5rem 0.4rem 0;
  scrollbar-width: thin;
  scroll-behavior: smooth;
}
.ribbon::-webkit-scrollbar { height: 6px; }
.ribbon::-webkit-scrollbar-thumb { background: var(--cream-edge); border-radius: 3px; }

/* Edge fade gradients — only visible when the ribbon overflows in that
   direction, signalling to the user that more stops exist off-screen. */
.ribbon-shell::before,
.ribbon-shell::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 32px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 140ms ease;
  z-index: 2;
}
.ribbon-shell::before {
  left: 0;
  background: linear-gradient(to right, var(--paper) 30%, rgba(0, 0, 0, 0));
}
.ribbon-shell::after {
  right: 0;
  background: linear-gradient(to left, var(--paper) 30%, rgba(0, 0, 0, 0));
}
.ribbon-shell.has-overflow-left::before { opacity: 1; }
.ribbon-shell.has-overflow-right::after { opacity: 1; }

/* Scroll arrow buttons — only render when there's actually content to scroll
   to, so a 5-stop trip doesn't get useless chrome. */
.ribbon-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--cream-edge);
  border-radius: 50%;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  transition: background 90ms ease, color 90ms ease, border-color 90ms ease;
}
.ribbon-arrow:hover {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.ribbon-arrow-left { left: 4px; }
.ribbon-arrow-right { right: 4px; }
@media (max-width: 720px) {
  /* Phones: rely on touch scrolling + the fade gradient — the arrows would
     compete with the already-tight ribbon. */
  .ribbon-arrow { display: none; }
}

.rib-stop {
  flex: 0 0 auto;
  position: relative;
  display: grid;
  gap: 0.1rem;
  min-width: 100px;
  padding: 0.4rem 0.7rem;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
  text-align: left;
  transition: transform 80ms ease, border-color 90ms ease;
}
.rib-stop::after {
  /* Connector dot to next stop — small wedge on the right. */
  content: '›';
  position: absolute;
  right: -0.6rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--ink-faded);
  font-size: 0.85rem;
  pointer-events: none;
}
.rib-stop:last-child::after { display: none; }
.rib-stop:hover { transform: translateY(-1px); border-color: var(--ink); }
.rib-stop.today {
  background: var(--vermillion);
  border-color: var(--vermillion-deep);
  color: var(--paper);
}
.rib-stop.today .rib-num,
.rib-stop.today .rib-date { color: rgba(255, 255, 255, 0.85); }
.rib-stop.selected {
  /* Outlined ink ring rather than a colour swap so the .today red still
     dominates if the same stop happens to be both today AND selected. */
  border-color: var(--ink);
  border-width: 2px;
  box-shadow: 0 0 0 1px var(--paper) inset;
}
.rib-stop.past { opacity: 0.5; }
.rib-num {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: var(--ink-faded);
}
.rib-name {
  font-family: var(--display);
  font-size: 0.85rem;
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rib-date {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.06em;
}

/* Mobile: tightest pill variant — single line "D1 · ZION", ~24px tall, so
   ~5–6 chips fit on a 390px viewport instead of ~3. Date chip is dropped
   to save horizontal width; the "today" red fill stays so position-in-trip
   is still readable. The day number rejoins the name as a mono prefix. */
@media (max-width: 720px) {
  .ribbon { padding: 0.2rem 0.35rem 0.25rem 0; gap: 0.2rem; }
  .rib-stop {
    /* Single-line layout — number prefix sits inline with the name. */
    display: inline-flex;
    align-items: baseline;
    gap: 0.3rem;
    min-width: 0;
    max-width: 9.5rem;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
  }
  .rib-stop::after { display: none; }
  .rib-date { display: none; }
  .rib-num {
    /* Re-show as inline prefix; condensed "D1" / "D1–3" so it stays short. */
    display: inline;
    font-size: 0.62rem;
    letter-spacing: 0.04em;
  }
  .rib-num::before { content: 'D'; }
  .rib-name {
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    /* Ellipsis if a name is too long; the title attribute carries the full text. */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 7rem;
  }
}
</style>
