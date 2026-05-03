<template>
  <section class="journal paper" aria-label="Journal">
    <header class="journal-head">
      <div class="journal-headline">
        <span class="eyebrow">Field journal</span>
        <h1 class="journal-title" :title="title">{{ title || 'Untitled voyage' }}</h1>
        <p v-if="metaLine" class="journal-meta mono">{{ metaLine }}</p>
      </div>
      <div class="journal-tools">
        <slot name="mode-toggle" />
        <slot name="head-tools" />
      </div>
    </header>

    <div class="journal-body">
      <p v-if="!groups.length && !wishlistPins.length" class="journal-empty">
        No stops or pins yet — switch to <strong>Plan</strong> to start your itinerary,
        or to <strong>Map</strong> to drop pins.
      </p>

      <!-- Wishlist (unattached pins) — rendered as a static section header
           with each pin as its own JournalNode so editing is inline. -->
      <section v-if="wishlistPins.length" class="jgroup is-wishlist">
        <h2 class="jgroup-head">
          <span class="eyebrow">Wishlist</span>
          <span class="jgroup-count mono">{{ wishlistPins.length }} pin{{ wishlistPins.length === 1 ? '' : 's' }} not yet scheduled</span>
        </h2>
        <JournalNode
          v-for="pin in wishlistPins"
          :key="`w${pin.id}`"
          :ref="(el) => registerRef(`pin:${pin.id}`, el)"
          kind="pin"
          :value="pin"
          :slug="slug"
          @save="bubbleSave"
        />
      </section>

      <!-- Stops in chronological order. Each stop is a JournalNode; its
           pin children are rendered into the #children slot so they appear
           inside the expanded body. -->
      <section v-if="groups.length" class="jgroup is-stops">
        <JournalNode
          v-for="g in groups"
          :key="`s${g.day.id}`"
          :ref="(el) => registerRef(`stop:${g.day.id}`, el)"
          kind="stop"
          :value="g.day"
          :slug="slug"
          :badge="String(g.dayIndex + 1).padStart(2, '0')"
          :child-count-label="g.pins.length ? `${g.pins.length} pin${g.pins.length === 1 ? '' : 's'}` : ''"
          :default-expanded="false"
          @save="bubbleSave"
        >
          <template #children>
            <div v-if="g.pins.length" class="jstop-children">
              <h3 class="jstop-children-head eyebrow">Pins</h3>
              <JournalNode
                v-for="pin in g.pins"
                :key="`sp${pin.id}`"
                :ref="(el) => registerRef(`pin:${pin.id}`, el)"
                kind="pin"
                :value="pin"
                :slug="slug"
                @save="bubbleSave"
                @delete="bubbleDelete"
              />
            </div>
            <p v-else class="jstop-no-pins mono">No pins on this stop yet — drop one from the map, or attach from the wishlist.</p>
          </template>
        </JournalNode>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import JournalNode from '@/components/molecules/JournalNode.vue'

const props = defineProps({
  slug: { type: String, required: true },
  title: { type: String, default: '' },
  days: { type: Array, default: () => [] },
  points: { type: Array, default: () => [] },
})
const emit = defineEmits(['save'])

const sortedDays = computed(() =>
  [...(props.days || [])].sort((a, b) => (a.date || '').localeCompare(b.date || '')),
)

const groups = computed(() => {
  const byDay = new Map()
  for (const d of sortedDays.value) byDay.set(d.id, [])
  for (const p of props.points || []) {
    if (p.itinerary_day_id != null && byDay.has(p.itinerary_day_id)) {
      byDay.get(p.itinerary_day_id).push(p)
    }
  }
  const prioRank = { must: 0, maybe: 1 }
  return sortedDays.value.map((day, dayIndex) => ({
    day,
    dayIndex,
    pins: (byDay.get(day.id) || []).slice().sort((a, b) => {
      const ra = prioRank[a.priority] ?? 2
      const rb = prioRank[b.priority] ?? 2
      if (ra !== rb) return ra - rb
      return (a.title || '').localeCompare(b.title || '')
    }),
  }))
})

const wishlistPins = computed(() => {
  const prioRank = { must: 0, maybe: 1 }
  return (props.points || [])
    .filter((p) => p.itinerary_day_id == null)
    .slice()
    .sort((a, b) => {
      const ra = prioRank[a.priority] ?? 2
      const rb = prioRank[b.priority] ?? 2
      if (ra !== rb) return ra - rb
      return (a.title || '').localeCompare(b.title || '')
    })
})

const metaLine = computed(() => {
  const stops = sortedDays.value.length
  const pins = (props.points || []).length
  const wish = wishlistPins.value.length
  const bits = []
  if (stops) bits.push(`${stops} stop${stops === 1 ? '' : 's'}`)
  if (pins) bits.push(`${pins} pin${pins === 1 ? '' : 's'}`)
  if (wish) bits.push(`${wish} on wishlist`)
  return bits.join(' · ')
})

// --- Ref registry: parent (MapView) needs to call markSaved/markError on the
// specific node that emitted a save, so we maintain a key→child-component map.
const nodeRefs = new Map()
function registerRef(key, el) {
  if (el) nodeRefs.set(key, el)
  else nodeRefs.delete(key)
}

function nodeKeyFor(kind, id) { return `${kind}:${id}` }

function bubbleSave(payload) {
  emit('save', payload)
}

defineExpose({
  markSaved(kind, id) { nodeRefs.get(nodeKeyFor(kind, id))?.markSaved?.() },
  markError(kind, id) { nodeRefs.get(nodeKeyFor(kind, id))?.markError?.() },
  flushAll() {
    for (const ref of nodeRefs.values()) ref?.flush?.()
  },
})
</script>

<style scoped>
.journal {
  position: absolute;
  inset: 0;
  z-index: 900;
  overflow-y: auto;
  background: var(--paper);
  padding: 1rem 1.25rem 4rem;
}

.journal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  max-width: 56rem;
  margin: 0 auto 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1.5px dashed var(--cream-edge);
}
.journal-headline { min-width: 0; }
.journal-title {
  font-family: var(--display);
  font-size: 1.5rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--ink);
  margin: 0.15rem 0 0.2rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 38rem;
}
.journal-meta {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faded, #666);
}
.journal-tools {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.journal-body {
  max-width: 56rem;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.journal-empty {
  padding: 2rem 0;
  text-align: center;
  color: var(--ink-faded, #666);
  font-size: 0.95rem;
}

.jgroup { display: flex; flex-direction: column; }
.jgroup-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin: 0 0 0.25rem;
  padding: 0 0.25rem;
}
.jgroup-count {
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faded, #888);
}

.jstop-children {
  display: flex;
  flex-direction: column;
  margin-top: 0.5rem;
  padding-left: 0.4rem;
  border-left: 1.5px dashed var(--cream-edge);
}
.jstop-children-head {
  margin: 0.25rem 0 0.1rem 0.4rem;
  font-size: 0.65rem;
}
.jstop-no-pins {
  margin-top: 0.4rem;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  color: var(--ink-faded, #999);
  font-style: italic;
}

@media (max-width: 720px) {
  .journal { padding: 0.65rem 0.75rem 5rem; }
  .journal-head {
    flex-direction: column;
    gap: 0.6rem;
    margin-bottom: 0.85rem;
  }
  .journal-tools { align-self: flex-end; }
  .journal-title { font-size: 1.15rem; max-width: 100%; }
  .jstop-children { padding-left: 0.2rem; }
}
</style>
