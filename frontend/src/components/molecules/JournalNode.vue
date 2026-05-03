<template>
  <article class="jnode" :class="[`jnode--${kind}`, { 'is-expanded': expanded }]">
    <header class="jnode-row">
      <button
        type="button"
        class="jnode-toggle mono"
        :aria-expanded="expanded"
        :aria-label="expanded ? 'Collapse' : 'Expand'"
        @click="setExpanded(!expanded)"
      >{{ expanded ? '▾' : '▸' }}</button>

      <span class="jnode-icon" aria-hidden="true">{{ headerIcon }}</span>

      <button type="button" class="jnode-summary" @click="setExpanded(!expanded)">
        <div class="jnode-title">
          <span v-if="badge" class="jnode-badge mono">{{ badge }}</span>
          <span class="jnode-label">{{ displayTitle }}</span>
          <span v-if="kind === 'pin' && value.priority === 'must'" class="jnode-prio prio-must mono" title="Must-see">★</span>
          <span v-else-if="kind === 'pin' && value.priority === 'maybe'" class="jnode-prio prio-maybe mono" title="Maybe">○</span>
        </div>
        <div class="jnode-sub mono">
          <span v-for="(bit, i) in metaBits" :key="i" class="jnode-meta-bit">
            <span v-if="i > 0" class="jnode-sep">·</span>
            <span>{{ bit }}</span>
          </span>
          <span v-if="childCountLabel" class="jnode-meta-bit">
            <span class="jnode-sep">·</span>
            <span>{{ childCountLabel }}</span>
          </span>
        </div>
      </button>

      <span v-if="statusText" class="jnode-status mono" :class="`status-${saveState}`">{{ statusText }}</span>
    </header>

    <div v-if="expanded" class="jnode-body">
      <MarkdownEditor
        v-model="notesValue"
        :placeholder="kind === 'stop' ? 'Plans, journal, photos…' : 'Notes, links, photos…'"
        @update:uploading="(v) => uploading = v"
      />
      <slot name="children" />
    </div>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'
import { CATEGORIES } from '@/util.js'
import { formatDate } from '@/lib/settings.js'
import { isJournalExpanded, setJournalExpanded } from '@/lib/uiSettings.js'

const props = defineProps({
  kind: { type: String, required: true }, // 'stop' | 'pin'
  value: { type: Object, required: true },
  slug: { type: String, required: true },
  badge: { type: String, default: '' },
  childCountLabel: { type: String, default: '' },
  defaultExpanded: { type: Boolean, default: false },
})
const emit = defineEmits(['save'])

const EMOJI = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
const CATEGORY_LABEL = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]))

const nodeKey = computed(() => `${props.kind}:${props.value.id}`)
const expanded = computed(() => isJournalExpanded(props.slug, nodeKey.value, props.defaultExpanded))
function setExpanded(next) { setJournalExpanded(props.slug, nodeKey.value, next) }

const headerIcon = computed(() => {
  if (props.kind === 'stop') return '◷'
  return EMOJI[props.value.category] || '📍'
})

const displayTitle = computed(() => {
  if (props.kind === 'stop') return props.value.label || 'Untitled stop'
  return props.value.title || 'Untitled pin'
})

// Header metadata bits — read-only, separator-joined. Kept short so the row
// stays one line on a normal viewport.
const metaBits = computed(() => {
  const bits = []
  if (props.kind === 'stop') {
    const start = formatDate(props.value.date)
    if (props.value.end_date && props.value.end_date !== props.value.date) {
      bits.push(`${start} → ${formatDate(props.value.end_date)}`)
    } else if (start) {
      bits.push(start)
    }
    if (props.value.sleep_location) bits.push(`🛏️ ${props.value.sleep_location}`)
  } else {
    const cat = CATEGORY_LABEL[props.value.category]
    if (cat) bits.push(cat)
  }
  return bits
})

// ---- Notes-only inline editor ----
// Only the notes/comment field is editable from journal mode. Everything else
// is structural and lives in Plan/Map. This keeps the journal focused on
// long-form writing.

const notesField = computed(() => (props.kind === 'stop' ? 'notes' : 'comment'))

const notesValue = ref('')
const uploading = ref(false)
// 'idle' | 'dirty' | 'saving' | 'saved' | 'error'
const saveState = ref('idle')
let dirtyTimer = null
let savedTimer = null
let seeding = false

function seedFromValue(v) {
  seeding = true
  notesValue.value = v?.[notesField.value] || ''
  Promise.resolve().then(() => { seeding = false })
}

let seededId = null
watch(
  () => props.value?.id,
  (id) => {
    if (id !== seededId) {
      seedFromValue(props.value || {})
      seededId = id
    }
  },
  { immediate: true },
)

function buildPayload() {
  // Minimal patch — only the notes/comment field. The PATCH endpoints accept
  // partial updates so date/title/category/etc. stay untouched server-side.
  return { [notesField.value]: notesValue.value.trim() || null }
}

function fireSave() {
  if (uploading.value) return
  if (!props.value?.id) return
  saveState.value = 'saving'
  emit('save', { kind: props.kind, id: props.value.id, payload: buildPayload() })
}

watch(notesValue, () => {
  if (seeding) return
  if (saveState.value !== 'saving') saveState.value = 'dirty'
  if (dirtyTimer) clearTimeout(dirtyTimer)
  if (savedTimer) { clearTimeout(savedTimer); savedTimer = null }
  dirtyTimer = setTimeout(fireSave, 800)
})

watch(uploading, (v) => {
  if (!v && saveState.value === 'dirty') {
    if (dirtyTimer) clearTimeout(dirtyTimer)
    dirtyTimer = setTimeout(fireSave, 200)
  }
})

const statusText = computed(() => {
  switch (saveState.value) {
    case 'saving': return 'saving…'
    case 'saved': return '✓ saved'
    case 'error': return '! save failed'
    case 'dirty': return uploading.value ? 'uploading…' : 'unsaved'
    default: return ''
  }
})

function flushIfDirty() {
  if (dirtyTimer) { clearTimeout(dirtyTimer); dirtyTimer = null }
  if (saveState.value === 'dirty') fireSave()
}

onBeforeUnmount(() => { flushIfDirty() })

defineExpose({
  markSaved: () => {
    saveState.value = 'saved'
    if (savedTimer) clearTimeout(savedTimer)
    savedTimer = setTimeout(() => {
      if (saveState.value === 'saved') saveState.value = 'idle'
    }, 1500)
  },
  markError: () => { saveState.value = 'error' },
  flush: flushIfDirty,
})
</script>

<style scoped>
.jnode { position: relative; }

.jnode-row {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.5rem 0.25rem;
  border-bottom: 1px solid var(--cream-edge);
}
.jnode--stop > .jnode-row { padding-top: 0.7rem; padding-bottom: 0.7rem; }

.jnode-toggle {
  flex-shrink: 0;
  width: 1.4rem;
  height: 1.4rem;
  display: grid;
  place-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: var(--ink);
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1;
}
.jnode-toggle:hover { background: var(--cream); border-color: var(--cream-edge); }

.jnode-icon {
  flex-shrink: 0;
  margin-top: 0.1rem;
  font-size: 1rem;
  line-height: 1;
}

.jnode-summary {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 0.05rem 0.4rem;
  margin: -0.05rem -0.4rem;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}
.jnode-summary:hover { background: var(--cream); }
.jnode-summary:focus-visible { outline: 2px solid var(--ink); outline-offset: 1px; }

.jnode-title {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  font-family: var(--display);
  font-size: 0.95rem;
  color: var(--ink);
  letter-spacing: 0.01em;
}
.jnode--stop .jnode-title { font-size: 1rem; text-transform: uppercase; }
.jnode-badge {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  color: var(--ink-faded, #888);
}
.jnode-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.jnode-prio {
  font-size: 0.72rem;
  flex-shrink: 0;
}
.prio-must { color: #c2410c; }
.prio-maybe { color: var(--ink-faded, #888); }

.jnode-sub {
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  color: var(--ink-faded, #777);
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.jnode-meta-bit {
  display: inline-flex;
  align-items: baseline;
  gap: 0.3rem;
}
.jnode-sep {
  color: var(--cream-edge);
}

.jnode-status {
  flex-shrink: 0;
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-faded, #888);
  align-self: center;
}
.jnode-status.status-saving { color: #b48a00; }
.jnode-status.status-saved { color: #1b7a3a; }
.jnode-status.status-error { color: var(--vermillion, #c2410c); }
.jnode-status.status-dirty { color: var(--ink-faded, #888); }

.jnode-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.6rem 0.25rem 0.85rem 2.05rem;
  border-bottom: 1px solid var(--cream-edge);
}
.jnode--pin .jnode-body { padding-left: 1.85rem; }

@media (max-width: 720px) {
  .jnode-body { padding-left: 1.4rem; padding-right: 0; }
  .jnode--pin .jnode-body { padding-left: 1.2rem; }
  .jnode-label { white-space: normal; }
}
</style>
