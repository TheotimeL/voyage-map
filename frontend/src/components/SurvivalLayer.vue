<template>
  <div class="survival">
    <button
      class="btn btn-tiny"
      :class="{ on: enabled }"
      type="button"
      :disabled="loading"
      :title="enabled ? 'Hide nearby water / toilets / trash / dump stations' : 'Show nearby water / toilets / trash / dump stations'"
      @click="toggle"
    >
      {{ loading ? 'Searching…' : enabled ? '✓ Showing' : 'Find nearby' }}
    </button>
    <p v-if="error" class="error sm">{{ error }}</p>
    <p v-else-if="enabled && !loading" class="hint mono">
      {{ count }} spot{{ count === 1 ? '' : 's' }} in view
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { fetchSurvival } from '@/lib/overpass.js'

const emit = defineEmits(['render', 'clear'])
const props = defineProps({ getBounds: { type: Function, required: true } })

const enabled = ref(false)
const loading = ref(false)
const error = ref('')
const count = ref(0)

async function toggle() {
  if (enabled.value) {
    enabled.value = false
    emit('clear')
    return
  }
  enabled.value = true
  loading.value = true
  error.value = ''
  try {
    const items = await fetchSurvival(props.getBounds())
    count.value = items.length
    emit('render', items)
  } catch (e) {
    error.value = e.message
    enabled.value = false
  } finally { loading.value = false }
}
</script>

<style scoped>
.survival { display: grid; gap: 0.35rem; justify-items: start; }
.btn.on { background: var(--ink); color: var(--paper); box-shadow: 0 2px 0 #000; }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0; letter-spacing: 0.06em; }
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
