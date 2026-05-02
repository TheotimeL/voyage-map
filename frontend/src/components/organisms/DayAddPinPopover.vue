<template>
  <div class="dap" @click.stop>
    <div class="dap-tabs mono">
      <button
        type="button"
        class="dap-tab"
        :class="{ on: tab === 'new' }"
        @click="tab = 'new'"
      >Search a place</button>
      <button
        type="button"
        class="dap-tab"
        :class="{ on: tab === 'existing' }"
        :disabled="!candidates.length"
        @click="tab = 'existing'"
      >From wishlist <span v-if="candidates.length" class="dap-count">{{ candidates.length }}</span></button>
      <button type="button" class="dap-close" :title="`Cancel`" @click="$emit('close')">×</button>
    </div>

    <p class="dap-eyebrow mono">Add a pin to {{ dayLabel }}</p>

    <section v-if="tab === 'new'" class="dap-section">
      <GeocoderSearch
        ref="geo"
        placeholder="Search anywhere — café, trail, viewpoint…"
        :bias="bias"
        @pick="onPick"
      />
      <p class="dap-hint mono">Picks a location and creates a new pin attached to this stop.</p>
    </section>

    <section v-else class="dap-section">
      <input
        v-model="filter"
        type="text"
        class="field dap-filter"
        placeholder="Filter by title…"
        @keydown.esc.stop.prevent="$emit('close')"
      />
      <div v-if="!filteredCandidates.length" class="dap-empty mono">
        <template v-if="filter">No matches.</template>
        <template v-else>No pins on the wishlist yet.</template>
      </div>
      <template v-else>
        <p v-if="visibleUnattached.length" class="dap-section-eyebrow mono">Unattached</p>
        <ul v-if="visibleUnattached.length" class="dap-list">
          <li v-for="p in visibleUnattached" :key="p.id">
            <button type="button" class="dap-item" @click="$emit('attach', { pointId: p.id })">
              <span class="dap-emoji">{{ pinEmoji(p) }}</span>
              <span class="dap-title">{{ p.title || 'Untitled' }}</span>
            </button>
          </li>
        </ul>
        <p v-if="visibleAttachedElsewhere.length" class="dap-section-eyebrow mono">On other days</p>
        <ul v-if="visibleAttachedElsewhere.length" class="dap-list">
          <li v-for="p in visibleAttachedElsewhere" :key="p.id">
            <button
              type="button"
              class="dap-item dap-item-elsewhere"
              :title="`Move from ${dayLabelById.get(p.itinerary_day_id) || 'another day'} to ${dayLabel}`"
              @click="$emit('attach', { pointId: p.id })"
            >
              <span class="dap-emoji">{{ pinEmoji(p) }}</span>
              <span class="dap-title">{{ p.title || 'Untitled' }}</span>
              <span class="dap-where mono">{{ dayLabelById.get(p.itinerary_day_id) || '' }}</span>
            </button>
          </li>
        </ul>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { CATEGORIES } from '@/util.js'
import GeocoderSearch from '../molecules/GeocoderSearch.vue'

const props = defineProps({
  day: { type: Object, required: true },
  dayLabel: { type: String, default: 'this stop' },
  // All points on the trip; we filter to wishlist + other-days candidates.
  allPoints: { type: Array, default: () => [] },
  // Day rows so we can hint "Day 3" when offering to move a pin.
  days: { type: Array, default: () => [] },
  bias: { type: Object, default: null },
})
const emit = defineEmits(['close', 'add-new', 'attach'])

const tab = ref('new')
const filter = ref('')
const geo = ref(null)

onMounted(async () => {
  await nextTick()
  // Focus the search field on open so the user can just start typing.
  geo.value?.$el?.querySelector?.('input')?.focus?.()
})

const emojiByCategory = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function pinEmoji(p) { return p?.gpx_data ? '🥾' : (emojiByCategory[p?.category] || '📍') }

// Excluding pins already on THIS day (those show as chips next to the row).
const candidates = computed(() =>
  (props.allPoints || []).filter((p) => p.title && p.itinerary_day_id !== props.day.id),
)
const filteredCandidates = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return candidates.value
  return candidates.value.filter((p) => (p.title || '').toLowerCase().includes(q))
})
const visibleUnattached = computed(() => filteredCandidates.value.filter((p) => p.itinerary_day_id == null))
const visibleAttachedElsewhere = computed(() => filteredCandidates.value.filter((p) => p.itinerary_day_id != null))

const dayLabelById = computed(() => {
  const m = new Map()
  for (const d of props.days || []) m.set(d.id, d.label || d.date)
  return m
})

function onPick(result) {
  // The geocoder returns either a remote result (name/lat/lng) or a "local"
  // result (existing pin). Treat both as add-new: a local pick from this
  // popover means "make a copy attached to this day" — the existing-pin path
  // is the other tab.
  emit('add-new', {
    lat: result.lat,
    lng: result.lng,
    title: (result.label || '').split(',')[0].trim().slice(0, 200) || null,
    category: 'note',
  })
}

watch(() => props.day?.id, () => { filter.value = '' ; tab.value = 'new' })
</script>

<style scoped>
.dap {
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  padding: 0.7rem 0.75rem 0.85rem;
  display: grid;
  gap: 0.55rem;
  box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.22);
  min-width: 280px;
}
.dap-tabs {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}
.dap-tab {
  flex: 0 1 auto;
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  padding: 0.18rem 0.6rem;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.dap-tab.on {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.dap-tab[disabled] { opacity: 0.4; cursor: not-allowed; }
.dap-count {
  background: var(--cream);
  color: var(--ink);
  border-radius: 999px;
  padding: 0 0.4rem;
  font-size: 0.62rem;
  min-width: 1rem;
  text-align: center;
}
.dap-tab.on .dap-count { background: var(--paper); color: var(--ink); }
.dap-close {
  margin-left: auto;
  background: transparent;
  border: none;
  font-size: 1.3rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}
.dap-close:hover { color: var(--ink); background: var(--cream); }

.dap-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}

.dap-section { display: grid; gap: 0.45rem; }
.dap-hint {
  margin: 0;
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}

.dap-filter {
  padding: 0.5rem 0.7rem;
  font-size: 0.88rem;
  border-width: 1px;
}

.dap-empty {
  font-size: 0.72rem;
  color: var(--ink-faded);
  letter-spacing: 0.05em;
  padding: 0.4rem 0.2rem;
}
.dap-section-eyebrow {
  margin: 0.2rem 0 -0.1rem;
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.dap-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.2rem;
  max-height: 240px;
  overflow-y: auto;
}
.dap-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.5rem;
  align-items: center;
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 3px;
  padding: 0.4rem 0.55rem;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
}
.dap-item:hover { background: var(--cream); border-color: var(--cream-edge); }
.dap-emoji { font-size: 1.05rem; line-height: 1; }
.dap-title { font-size: 0.92rem; }
.dap-where {
  font-size: 0.66rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.dap-item-elsewhere { border-style: dashed; border-color: var(--cream-edge); }
</style>
