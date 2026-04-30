<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">Edit day</p>
      <p v-if="hasCoord" class="coord">
        {{ formatLat(modelValue.lat) }} · {{ formatLng(modelValue.lng) }}
      </p>
      <p v-else class="hint mono">No location yet — drop the pin on the map to anchor this day.</p>

      <label class="lbl">Date</label>
      <input ref="dateInput" v-model="form.date" type="date" class="field" required />

      <label class="lbl">Where (label)</label>
      <input v-model="form.label" class="field" maxlength="200" placeholder="e.g. Las Vegas" />

      <label class="lbl">Notes</label>
      <textarea
        v-model="form.notes"
        class="field"
        maxlength="500"
        rows="3"
        placeholder="Hotel, plan, anything to remember"
      />

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">Save</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, onMounted, useTemplateRef, computed } from 'vue'
import { formatLat, formatLng } from '@/util.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['save', 'close'])

const form = reactive({
  date: props.modelValue.date,
  label: props.modelValue.label || '',
  notes: props.modelValue.notes || '',
})
const hasCoord = computed(() => props.modelValue.lat != null && props.modelValue.lng != null)
const dateInput = useTemplateRef('dateInput')
onMounted(() => dateInput.value?.focus())

function submit() {
  emit('save', {
    date: form.date,
    label: form.label.trim() || null,
    notes: form.notes.trim() || null,
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
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.4rem;
}
.hint { color: var(--ink-faded); font-size: 0.78rem; margin: 0; letter-spacing: 0.06em; }
</style>
