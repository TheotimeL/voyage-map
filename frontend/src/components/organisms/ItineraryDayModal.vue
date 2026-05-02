<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">Edit stop</p>

      <div class="date-row">
        <div class="date-cell">
          <label class="lbl">From</label>
          <input ref="dateInput" v-model="form.date" type="date" class="field" required />
        </div>
        <div class="date-cell">
          <label class="lbl">Until</label>
          <input v-model="form.end_date" type="date" class="field" :min="form.date" required />
        </div>
      </div>
      <p v-if="spanNights >= 1" class="hint mono">{{ spanNights }} night{{ spanNights === 1 ? '' : 's' }} at this stop</p>

      <label class="lbl">Name</label>
      <input v-model="form.label" class="field" maxlength="200" placeholder="e.g. Hôtel Paradiso, Camp Joshua, BLM…" />

      <label class="lbl">Location</label>
      <GeocoderSearch
        :placeholder="hasCoord ? 'Change the location…' : 'Search a place — your existing pins show first'"
        :bias="bias"
        :local-candidates="existingPins"
        @pick="onPick"
      />
      <div v-if="hasCoord" class="coord-readout">
        <span class="coord mono">{{ formatLat(form.lat) }} · {{ formatLng(form.lng) }}</span>
        <button type="button" class="coord-clear" @click="clearLocation" title="Clear location">×</button>
      </div>
      <p class="hint mono">After saving, drag the day's pin on the map to fine-tune.</p>

      <label class="lbl">Notes</label>
      <MarkdownEditor v-model="form.notes" placeholder="Plans, journal, photos…" @update:uploading="(v) => uploading = v" />

      <button v-if="hasCoord" type="button" class="btn directions" @click="onDirections">
        Directions →
      </button>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn" :disabled="uploading" :title="uploading ? 'Wait for image upload to finish' : null">
          {{ uploading ? 'Uploading…' : 'Save' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, onBeforeUnmount, useTemplateRef, computed, watch } from 'vue'
import { formatLat, formatLng, openInMaps } from '@/util.js'
import GeocoderSearch from '../molecules/GeocoderSearch.vue'
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  bias: { type: Object, default: null },
  existingPins: { type: Array, default: () => [] },
})
const emit = defineEmits(['save', 'close'])

// See PointFormModal: blocks Save while a markdown image is mid-upload so the
// user can't ship a comment that doesn't reference the file they just picked.
const uploading = ref(false)

const form = reactive({
  date: props.modelValue.date,
  end_date: props.modelValue.end_date || props.modelValue.date,
  label: props.modelValue.label || '',
  notes: props.modelValue.notes || '',
  lat: props.modelValue.lat ?? null,
  lng: props.modelValue.lng ?? null,
})

const hasCoord = computed(() => form.lat != null && form.lng != null)
// Nights at this stop = end - start (no +1). May 9 → May 10 is 1 night,
// not 2 — the trip-day count and the nights count are different things.
const spanNights = computed(() => {
  if (!form.date || !form.end_date) return 0
  return Math.max(0, Math.round((new Date(form.end_date) - new Date(form.date)) / 86400000))
})
// If the user shifts `From` past `Until`, snap `Until` along so the
// constraint never inverts mid-edit.
watch(() => form.date, (next) => {
  if (form.end_date && next > form.end_date) form.end_date = next
})

const dateInput = useTemplateRef('dateInput')
onMounted(() => dateInput.value?.focus())

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

function onPick(result) {
  form.lat = result.lat
  form.lng = result.lng
  // If the user has not given a name yet, seed it from the picked place's
  // first part — keeps "name" decoupled from "location" but bootstraps it
  // for the common case.
  if (!form.label.trim() && result.label) {
    form.label = result.label.split(',')[0].trim().slice(0, 200)
  }
}

function clearLocation() {
  form.lat = null
  form.lng = null
}

function onDirections() {
  openInMaps(form.lat, form.lng, form.label.trim() || 'Day')
}

function submit() {
  emit('save', {
    date: form.date,
    end_date: form.end_date || form.date,
    label: form.label.trim() || null,
    notes: form.notes.trim() || null,
    lat: form.lat,
    lng: form.lng,
  })
}
</script>

<style scoped>
.modal {
  width: min(440px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 0.7rem;
  padding: 1.4rem 1.5rem;
}
.date-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; }
.date-cell { display: grid; gap: 0.3rem; min-width: 0; }
/* Sub-480px viewports (most phones in portrait) couldn't fit two date inputs
   side-by-side without clipping the calendar icon — collapse to a stacked
   layout so both pickers stay fully usable. */
@media (max-width: 480px) {
  .modal { padding: 1.1rem 1.1rem 1.2rem; }
  .date-row { grid-template-columns: 1fr; gap: 0.5rem; }
}
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin-top: 0.1rem;
}
.coord-readout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
  padding: 0.35rem 0.7rem;
  background: var(--cream);
  border-radius: 3px;
  border: 1px dashed var(--cream-edge);
}
.coord-clear {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 0.3rem;
}
.coord-clear:hover { color: var(--vermillion); }
.directions {
  width: 100%;
  margin-top: 0.3rem;
}
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.5rem;
}
.hint { color: var(--ink-faded); font-size: 0.72rem; margin: 0; letter-spacing: 0.06em; }
</style>
