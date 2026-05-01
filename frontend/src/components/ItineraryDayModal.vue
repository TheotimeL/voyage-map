<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">Edit day</p>

      <label class="lbl">Date</label>
      <input ref="dateInput" v-model="form.date" type="date" class="field" required />

      <label class="lbl">Name</label>
      <input v-model="form.label" class="field" maxlength="200" placeholder="e.g. Hôtel Paradiso, Day 3, Camp Joshua…" />

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
      <textarea
        v-model="form.notes"
        class="field"
        maxlength="500"
        rows="3"
        placeholder="Hotel, plan, anything to remember"
      />

      <button v-if="hasCoord" type="button" class="btn directions" @click="onDirections">
        Directions →
      </button>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">Save</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, onMounted, onBeforeUnmount, useTemplateRef, computed } from 'vue'
import { formatLat, formatLng, openInMaps } from '@/util.js'
import GeocoderSearch from './GeocoderSearch.vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  bias: { type: Object, default: null },
  existingPins: { type: Array, default: () => [] },
})
const emit = defineEmits(['save', 'close'])

const form = reactive({
  date: props.modelValue.date,
  label: props.modelValue.label || '',
  notes: props.modelValue.notes || '',
  lat: props.modelValue.lat ?? null,
  lng: props.modelValue.lng ?? null,
})
const hasCoord = computed(() => form.lat != null && form.lng != null)

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
