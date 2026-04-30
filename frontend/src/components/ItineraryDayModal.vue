<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">Edit day</p>

      <label class="lbl">Date</label>
      <input ref="dateInput" v-model="form.date" type="date" class="field" required />

      <label class="lbl">Label (just a name)</label>
      <input v-model="form.label" class="field" maxlength="200" placeholder="e.g. Las Vegas" />

      <label class="lbl">Notes</label>
      <textarea
        v-model="form.notes"
        class="field"
        maxlength="500"
        rows="3"
        placeholder="Hotel, plan, anything to remember"
      />

      <label class="lbl">Location on the map</label>
      <div class="loc-row">
        <span v-if="hasCoord" class="coord mono">
          {{ formatLat(modelValue.lat) }} · {{ formatLng(modelValue.lng) }}
        </span>
        <span v-else class="coord muted mono">— no location yet —</span>
        <button
          type="button"
          class="btn btn-tiny btn-ghost"
          :disabled="!form.label.trim() || locating"
          @click="locateFromLabel"
        >
          {{ locating ? 'Searching…' : 'Locate from label' }}
        </button>
      </div>
      <p class="hint mono">
        After saving, drag the day's pin on the map to refine the spot.
      </p>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">Save</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, useTemplateRef, computed } from 'vue'
import { formatLat, formatLng } from '@/util.js'
import { geocode } from '@/api.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['save', 'close', 'locate-candidates'])

const form = reactive({
  date: props.modelValue.date,
  label: props.modelValue.label || '',
  notes: props.modelValue.notes || '',
  lat: props.modelValue.lat ?? null,
  lng: props.modelValue.lng ?? null,
})
const hasCoord = computed(() => form.lat != null && form.lng != null)
const locating = ref(false)
const locateError = ref('')

const dateInput = useTemplateRef('dateInput')
onMounted(() => dateInput.value?.focus())

async function locateFromLabel() {
  const q = form.label.trim()
  if (!q) return
  locating.value = true
  locateError.value = ''
  try {
    const results = await geocode(q)
    if (!results.length) { locateError.value = 'No match found.'; return }
    if (results.length === 1 || results[0].importance > (results[1]?.importance ?? 0) + 0.15) {
      // Strong winner — apply immediately.
      form.lat = results[0].lat
      form.lng = results[0].lng
    } else {
      // Multiple candidates — bubble up to MapView so it can show its picker.
      emit('locate-candidates', { day: props.modelValue, results: results.slice(0, 6) })
    }
  } catch (e) {
    locateError.value = e?.message || 'Search failed.'
  } finally {
    locating.value = false
  }
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
  gap: 0.85rem;
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
.loc-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  flex-wrap: wrap;
}
.coord { font-size: 0.85rem; color: var(--ink); }
.coord.muted { color: var(--ink-faded); }
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.4rem;
}
.hint { color: var(--ink-faded); font-size: 0.72rem; margin: 0; letter-spacing: 0.06em; }
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
