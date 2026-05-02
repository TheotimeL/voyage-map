<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">{{ isNew ? 'Mark a place' : 'Edit place' }}</p>
      <p class="coord">
        {{ formatLat(modelValue.lat) }} · {{ formatLng(modelValue.lng) }}
      </p>

      <label class="lbl">Title</label>
      <input
        ref="titleInput"
        v-model="form.title"
        class="field"
        maxlength="120"
        placeholder="e.g. Café A Brasileira"
      />

      <label class="lbl">Priority</label>
      <div class="flag-chips priority-chips">
        <button
          type="button"
          class="flag-chip priority-chip prio-must"
          :class="{ on: form.priority === 'must' }"
          title="Must-see — high priority"
          @click="form.priority = 'must'"
        >★ Must</button>
        <button
          type="button"
          class="flag-chip priority-chip prio-maybe"
          :class="{ on: form.priority === 'maybe' }"
          title="Maybe — nice to have"
          @click="form.priority = 'maybe'"
        >○ Maybe</button>
      </div>

      <label class="lbl">Notes</label>
      <div v-if="showFlagChips" class="flag-chips">
        <button
          v-for="f in FLAG_CHIPS"
          :key="f.key"
          type="button"
          class="flag-chip"
          :class="{ on: hasFlag(f.key) }"
          :title="f.title"
          @click="toggleFlag(f.key)"
        >{{ f.label }}</button>
      </div>
      <MarkdownEditor v-model="form.comment" placeholder="Notes, links, photos…" />

      <label class="lbl">Category</label>
      <div class="cat-grid">
        <button
          v-for="c in categories"
          :key="c.key"
          type="button"
          class="cat"
          :class="{ active: form.category === c.key }"
          @click="form.category = c.key"
        >
          <span class="cat-emoji">{{ c.emoji }}</span>
          <span class="cat-label">{{ c.label }}</span>
        </button>
      </div>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">{{ isNew ? 'Drop pin' : 'Save' }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, reactive, onMounted, onBeforeUnmount, useTemplateRef } from 'vue'
import { CATEGORIES, formatLat, formatLng } from '@/util.js'
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'

// Vanlife/trip shorthand chips that prepend to the comment as `[FLAG] …`.
// Limited set so the field stays scannable.
const FLAG_CHIPS = [
  { key: 'BLM',         label: 'BLM',         title: 'Free dispersed camping on Bureau of Land Management land' },
  { key: 'Free',        label: 'Free',        title: 'No fee' },
  { key: 'Paid',        label: 'Paid',        title: 'Has a nightly fee' },
  { key: 'Electricity', label: 'Electricity', title: 'Powered hookup available' },
  { key: 'Water',       label: 'Water',       title: 'Potable water on site' },
  { key: 'Reserved',    label: 'Reserved',    title: 'Booking confirmed' },
]
const FLAG_KEYS = new Set(FLAG_CHIPS.map((f) => f.key))

const props = defineProps({
  modelValue: { type: Object, required: true },
  isNew: { type: Boolean, default: true },
})
const emit = defineEmits(['save', 'close'])

const categories = CATEGORIES

const form = reactive({
  title: props.modelValue.title || '',
  comment: props.modelValue.comment || '',
  category: props.modelValue.category || 'note',
  // New pins default to must-see; existing pins keep whatever priority they
  // had (including null for legacy pins predating this field).
  priority: props.modelValue.priority || (props.isNew ? 'must' : null),
})

// Flag chips only make sense for sleep/camp categories — they're driven by
// the spreadsheet's "BLM"/"ELECTRICITE" notes so the user can tap them on
// instead of typing.
const showFlagChips = computed(() => ['camp', 'stay'].includes(form.category))

// Flags live as a `[FLAG_A, FLAG_B] …` prefix in the comment. We keep the
// rest of the note untouched, even when the user types around the prefix.
const flagPrefixRe = /^\s*\[([^\]]+)\]\s*/
function readFlags(text) {
  const m = flagPrefixRe.exec(text || '')
  if (!m) return new Set()
  return new Set(m[1].split(',').map((s) => s.trim()).filter((k) => FLAG_KEYS.has(k)))
}
function writeFlags(text, flags) {
  const stripped = (text || '').replace(flagPrefixRe, '').trimStart()
  if (!flags.size) return stripped
  const ordered = FLAG_CHIPS.map((f) => f.key).filter((k) => flags.has(k))
  return `[${ordered.join(', ')}]${stripped ? ' ' + stripped : ''}`
}
function hasFlag(k) { return readFlags(form.comment).has(k) }
function toggleFlag(k) {
  const next = readFlags(form.comment)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  form.comment = writeFlags(form.comment, next)
}

const titleInput = useTemplateRef('titleInput')
onMounted(() => titleInput.value?.focus())

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

function submit() {
  emit('save', {
    title: form.title.trim() || null,
    comment: form.comment.trim() || null,
    category: form.category,
    priority: form.priority || null,
  })
}
</script>

<style scoped>
.modal {
  width: min(540px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 1rem;
  padding: 1.4rem 1.5rem;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin-top: 0.2rem;
}
.cat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
}
.cat {
  background: var(--cream);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  padding: 0.6rem 0.3rem;
  cursor: pointer;
  display: grid;
  gap: 0.25rem;
  font-family: var(--body);
  color: var(--ink-soft);
  transition: all 90ms ease;
}
.cat:hover { border-color: var(--vermillion); color: var(--ink); }
.cat.active {
  background: var(--vermillion);
  border-color: var(--vermillion-deep);
  color: var(--paper);
}
.cat-emoji { font-size: 1.2rem; }
.cat-label { font-size: 0.78rem; letter-spacing: 0.04em; }
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.6rem;
  flex-wrap: wrap;
}
.flag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin: -0.3rem 0 0.4rem;
}
.flag-chip {
  background: transparent;
  border: 1px dashed var(--cream-edge);
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
  cursor: pointer;
  font-family: var(--mono);
}
.flag-chip:hover { border-color: var(--ink); color: var(--ink); border-style: solid; }
.flag-chip.on {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
  border-style: solid;
}
.priority-chips { margin: -0.3rem 0 0; }
.priority-chip { font-family: var(--body); font-size: 0.78rem; padding: 0.25rem 0.7rem; }
.priority-chip.prio-must { color: var(--vermillion); border-color: var(--vermillion); }
.priority-chip.prio-must.on {
  background: var(--vermillion);
  color: var(--paper);
  border-color: var(--vermillion);
}
</style>
