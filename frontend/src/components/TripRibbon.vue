<template>
  <nav v-if="rows.length" ref="ribEl" class="ribbon" aria-label="Trip overview">
    <button
      v-for="r in rows"
      :key="r.day.id"
      type="button"
      class="rib-stop"
      :class="{ today: r.isToday, past: r.isPast }"
      :title="`${r.dateLine} · ${r.day.label || 'Untitled'}`"
      @click="$emit('go', r.day)"
    >
      <span class="rib-num mono">{{ r.numLabel }}</span>
      <span class="rib-name">{{ r.shortName || 'Untitled' }}</span>
      <span class="rib-date mono">{{ r.dateChip }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { todayISO } from '@/util.js'

const props = defineProps({
  days: { type: Array, default: () => [] },
})
defineEmits(['go'])

const today = computed(() => todayISO())
const ribEl = ref(null)

// Center today's chip (or the next future stop, if today is between stops)
// in the visible ribbon so users don't have to scroll right mid-trip. If
// every stop is in the future the first chip stays at the left as-is.
function scrollActiveIntoView() {
  const root = ribEl.value
  if (!root) return
  const target = root.querySelector('.rib-stop.today')
    || [...root.querySelectorAll('.rib-stop:not(.past)')][0]
  if (!target) return
  // Don't scroll if the active stop is already the first one — keep the
  // natural left-anchored layout for pre-trip and just-started trips.
  if (target === root.firstElementChild) return
  const left = target.offsetLeft - root.clientWidth / 2 + target.clientWidth / 2
  root.scrollTo({ left: Math.max(0, left), behavior: 'auto' })
}

onMounted(() => nextTick(scrollActiveIntoView))
watch(() => props.days, () => nextTick(scrollActiveIntoView), { deep: true })

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
  // "9 May" — short form to fit a phone-width chip.
  const [y, m, d] = iso.split('-').map(Number)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${d} ${months[m - 1]}`
}
</script>

<style scoped>
.ribbon {
  display: flex;
  gap: 0.2rem;
  align-items: stretch;
  overflow-x: auto;
  padding: 0.4rem 0.5rem 0.4rem 0;
  background: var(--paper);
  border-bottom: 1px solid var(--cream-edge);
  scrollbar-width: thin;
}
.ribbon::-webkit-scrollbar { height: 6px; }
.ribbon::-webkit-scrollbar-thumb { background: var(--cream-edge); border-radius: 3px; }

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

/* Mobile: thinner variant — name-only chips, ~28px tall, scrollable.
   Day-number badge and date chip are dropped to save horizontal width;
   the "today" red fill stays so position-in-trip is still readable. */
@media (max-width: 720px) {
  .ribbon { padding: 0.2rem 0.4rem 0.25rem 0; gap: 0.25rem; }
  .rib-stop {
    min-width: 72px;
    padding: 0.25rem 0.55rem;
    border-radius: 999px;
  }
  .rib-stop::after { display: none; }
  .rib-num,
  .rib-date { display: none; }
  .rib-name {
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
}
</style>
