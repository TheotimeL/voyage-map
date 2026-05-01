<template>
  <div class="survival">
    <div class="kind-chips">
      <button
        v-for="k in SURVIVAL_KINDS"
        :key="k.key"
        type="button"
        class="kind-chip"
        :class="{ on: selected.has(k.key) }"
        :title="`Toggle ${k.label.toLowerCase()}`"
        @click="toggleKind(k.key)"
      >
        <span class="kind-icon">{{ k.icon }}</span>
        <span class="kind-label">{{ k.label }}</span>
      </button>
    </div>
    <button
      class="btn btn-tiny"
      :class="{ on: enabled }"
      type="button"
      :disabled="loading || selected.size === 0"
      :title="enabled ? 'Hide nearby spots' : 'Search Overpass for the selected categories within the visible map area'"
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
import { fetchSurvival, SURVIVAL_KINDS } from '@/lib/overpass.js'

const emit = defineEmits(['render', 'clear'])
const props = defineProps({ getBounds: { type: Function, required: true } })

const enabled = ref(false)
const loading = ref(false)
const error = ref('')
const count = ref(0)
const selected = ref(new Set(['water', 'dump', 'toilet', 'trash']))

function toggleKind(k) {
  const next = new Set(selected.value)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  selected.value = next
  if (enabled.value) refresh()
}

async function toggle() {
  if (enabled.value) {
    enabled.value = false
    emit('clear')
    return
  }
  enabled.value = true
  await refresh()
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const items = await fetchSurvival(props.getBounds(), [...selected.value])
    count.value = items.length
    emit('render', items)
  } catch (e) {
    error.value = e.message
    enabled.value = false
    emit('clear')
  } finally { loading.value = false }
}
</script>

<style scoped>
.survival { display: grid; gap: 0.4rem; justify-items: start; }
.kind-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.kind-chip {
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-family: var(--mono);
}
.kind-chip:hover { border-color: var(--ink); color: var(--ink); }
.kind-chip.on {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.kind-icon { font-size: 0.95rem; }
.btn.on { background: var(--ink); color: var(--paper); box-shadow: 0 2px 0 #000; }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0; letter-spacing: 0.06em; }
.error.sm { font-size: 0.78rem; color: var(--vermillion-deep); margin: 0; }
</style>
