<template>
  <Teleport to="body">
    <Transition :name="isMobile ? 'sheet-up' : 'panel-slide'" appear>
      <aside
        v-if="target"
        class="detail-panel paper"
        :class="[isMobile ? 'is-mobile' : 'is-desktop']"
        :style="panelStyle"
        role="dialog"
        :aria-label="headerLabel"
      >
        <header class="dp-head">
          <span class="eyebrow">{{ headerLabel }}</span>
          <span class="dp-status mono" :class="`status-${saveState}`">{{ statusText }}</span>
          <button class="dp-close btn-icon" type="button" aria-label="Close" @click="onClose">×</button>
        </header>

        <div class="dp-body">
          <!-- Title (pin) / label (stop) -->
          <input
            ref="titleInput"
            v-model="form.title"
            class="dp-title field"
            :maxlength="form.kind === 'stop' ? 200 : 120"
            :placeholder="form.kind === 'stop' ? 'Stop name (e.g. Camp Joshua, BLM…)' : 'e.g. Café A Brasileira'"
          />

          <!-- Pin: priority chips + flag chips + category grid -->
          <template v-if="form.kind === 'pin'">
            <label class="lbl">Priority</label>
            <div class="flag-chips priority-chips">
              <button
                type="button"
                class="flag-chip priority-chip prio-must"
                :class="{ on: form.priority === 'must' }"
                title="Must-see — high priority"
                @click="form.priority = form.priority === 'must' ? null : 'must'"
              >★ Must</button>
              <button
                type="button"
                class="flag-chip priority-chip prio-maybe"
                :class="{ on: form.priority === 'maybe' }"
                title="Maybe — nice to have"
                @click="form.priority = form.priority === 'maybe' ? null : 'maybe'"
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
            <MarkdownEditor
              v-model="form.comment"
              placeholder="Notes, links, photos…"
              @update:uploading="(v) => uploading = v"
            />

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
          </template>

          <!-- Stop: dates + location + sleep location + notes -->
          <template v-else>
            <div class="date-row">
              <div class="date-cell">
                <label class="lbl">From</label>
                <input v-model="form.date" type="date" class="field" required />
              </div>
              <div class="date-cell">
                <label class="lbl">Until</label>
                <input v-model="form.end_date" type="date" class="field" :min="form.date" required />
              </div>
            </div>
            <p v-if="spanNights >= 1" class="hint mono">{{ spanNights }} night{{ spanNights === 1 ? '' : 's' }} at this stop</p>

            <label class="lbl">Location</label>
            <GeocoderSearch
              :placeholder="hasCoord ? 'Change the location…' : 'Search a place — your existing pins show first'"
              :bias="bias"
              :local-candidates="existingPins"
              @pick="onPickLocation"
            />
            <div v-if="hasCoord" class="coord-readout">
              <span class="coord mono">{{ formatLat(form.lat) }} · {{ formatLng(form.lng) }}</span>
              <button type="button" class="coord-clear" title="Clear location" @click="clearLocation">×</button>
            </div>

            <label class="lbl">Sleep location</label>
            <input
              v-model="form.sleep_location"
              class="field"
              maxlength="200"
              placeholder="e.g. Watchman Campground, BLM off Hwy 9…"
            />

            <label class="lbl">Notes</label>
            <MarkdownEditor
              v-model="form.notes"
              placeholder="Plans, journal, photos…"
              @update:uploading="(v) => uploading = v"
            />
          </template>

          <!-- Coords + directions (both kinds, when present) -->
          <p v-if="form.kind === 'pin' && form.lat != null" class="dp-coord mono">
            {{ formatLat(form.lat) }} · {{ formatLng(form.lng) }}
          </p>
          <button v-if="hasCoord" type="button" class="btn directions" @click="onDirections">
            Directions →
          </button>

          <!-- Delete -->
          <div v-if="canDelete" class="dp-actions">
            <button type="button" class="btn btn-ghost danger" @click="onDelete">
              Delete {{ form.kind === 'pin' ? 'pin' : 'stop' }}
            </button>
          </div>
        </div>

        <!-- Resize handle (desktop only) -->
        <div
          v-if="!isMobile"
          class="dp-resize"
          @pointerdown="resize.onPointerDown"
          @pointermove="resize.onPointerMove"
          @pointerup="resize.onPointerUp"
          @pointercancel="resize.onPointerUp"
        />
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useTemplateRef, watch } from 'vue'
import { CATEGORIES, formatLat, formatLng, openInMaps } from '@/util.js'
import MarkdownEditor from '@/components/molecules/MarkdownEditor.vue'
import GeocoderSearch from '@/components/molecules/GeocoderSearch.vue'
import { useResizablePanel } from '@/lib/useResizablePanel.js'

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
  // { kind: 'pin' | 'stop', value: { ... } } — value is the Pin or ItineraryDay
  // object. For new pins/stops, value carries lat/lng/date but no id; the
  // first emit('save', ...) in that case is a create — parent flips id back
  // and subsequent saves patch.
  target: { type: Object, default: null },
  bias: { type: Object, default: null },
  existingPins: { type: Array, default: () => [] },
})
const emit = defineEmits(['save', 'delete', 'close'])

const categories = CATEGORIES

// Mobile vs desktop layout — mobile is fullscreen, desktop is a resizable left
// panel. The matchMedia listener mirrors InfoPanel.vue's pattern.
const mq = window.matchMedia('(max-width: 720px)')
const isMobile = ref(mq.matches)
function onMQ(e) { isMobile.value = e.matches }
onMounted(() => mq.addEventListener('change', onMQ))
onBeforeUnmount(() => mq.removeEventListener('change', onMQ))

const resize = useResizablePanel()
const panelStyle = computed(() =>
  isMobile.value ? null : { width: `${resize.width.value}px` }
)

// Internal form state. Initialized from props.target on mount and on
// target-key changes. NOT re-synced from prop value updates (the parent
// re-emits the updated value back after save, which would otherwise clobber
// any in-flight typing the user did during the network round-trip).
const form = reactive({
  kind: 'pin',
  id: null,
  title: '',
  comment: '',
  category: 'note',
  priority: null,
  // stop-only
  date: '',
  end_date: '',
  notes: '',
  sleep_location: '',
  lat: null,
  lng: null,
})

// Save-state machine — hoisted above seedFrom because the immediate watch
// below calls seedFrom → resetDirty, which reads saveState. Declaring those
// later would trigger a temporal-dead-zone ReferenceError on first mount.
const uploading = ref(false)
// 'idle' | 'dirty' | 'saving' | 'saved' | 'error'
const saveState = ref('idle')
let dirtyTimer = null
let savedTimer = null

// Set during seedFrom() so the form-change watcher (which fires async after
// the reactive assignments below) doesn't treat the seed itself as user
// edits. Without this guard, opening a pin/stop schedules a phantom save 800
// ms later that sends the seeded values back to the server.
let seeding = false

function resetDirty() {
  saveState.value = 'idle'
  if (dirtyTimer) { clearTimeout(dirtyTimer); dirtyTimer = null }
}

function buildPayload() {
  if (form.kind === 'pin') {
    return {
      title: form.title.trim() || null,
      comment: (form.comment || '').trim() || null,
      category: form.category,
      priority: form.priority || null,
    }
  }
  return {
    date: form.date,
    end_date: form.end_date || form.date,
    label: form.title.trim() || null,
    notes: (form.notes || '').trim() || null,
    sleep_location: form.sleep_location.trim() || null,
    lat: form.lat,
    lng: form.lng,
  }
}

function fireSave() {
  if (uploading.value) return
  if (form.kind === 'stop' && (!form.date || !form.end_date)) {
    saveState.value = 'idle'
    return
  }
  if (!form.id && isNewEmpty.value) {
    saveState.value = 'idle'
    return
  }
  saveState.value = 'saving'
  emit('save', { kind: form.kind, id: form.id, payload: buildPayload() })
}

function seedFrom(target) {
  if (!target) return
  seeding = true
  const v = target.value || {}
  form.kind = target.kind
  form.id = v.id ?? null
  form.lat = v.lat ?? null
  form.lng = v.lng ?? null
  if (target.kind === 'pin') {
    form.title = v.title || ''
    form.comment = v.comment || ''
    form.category = v.category || 'note'
    form.priority = v.priority ?? (v.id ? null : 'must')
  } else {
    form.title = v.label || ''
    form.date = v.date || ''
    form.end_date = v.end_date || v.date || ''
    form.notes = v.notes || ''
    form.sleep_location = v.sleep_location || ''
  }
  resetDirty()
  // Wait for Vue's batched watcher tick to drain before re-arming the dirty
  // flag — the watcher runs once for all the reactive assignments above, so
  // a single nextTick is enough.
  nextTick(() => { seeding = false })
}

// Re-seed only when the panel is opened on a *different* target object — not
// on every prop tick. Object-identity is the right key here: a parent that
// patches a pin shouldn't clobber the in-flight form. Parent uses assignId()
// (exposed below) to thread the new id back after a create.
let seededForTarget = null
watch(() => props.target, (next) => {
  if (!next) { seededForTarget = null; return }
  if (next === seededForTarget) return
  // Pending edit on the previous target — flush so it isn't dropped when the
  // user pivots to a different pin/stop.
  if (seededForTarget && saveState.value === 'dirty') {
    if (dirtyTimer) { clearTimeout(dirtyTimer); dirtyTimer = null }
    fireSave()
  }
  seedFrom(next)
  seededForTarget = next
}, { immediate: true })

const titleInput = useTemplateRef('titleInput')
onMounted(() => titleInput.value?.focus?.())

// ESC closes the panel (with a flush of pending edits).
function onEsc(e) { if (e.key === 'Escape') onClose() }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

// ---------- Pin flag-chip prefix logic ----------
const showFlagChips = computed(() => form.kind === 'pin' && ['camp', 'stay'].includes(form.category))
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

// ---------- Stop helpers ----------
const hasCoord = computed(() => form.lat != null && form.lng != null)
const spanNights = computed(() => {
  if (form.kind !== 'stop' || !form.date || !form.end_date) return 0
  return Math.max(0, Math.round((new Date(form.end_date) - new Date(form.date)) / 86400000))
})
watch(() => form.date, (next) => {
  if (form.kind === 'stop' && form.end_date && next > form.end_date) form.end_date = next
})

function onPickLocation(r) {
  form.lat = r.lat
  form.lng = r.lng
  if (!form.title.trim() && r.label) {
    form.title = r.label.split(',')[0].trim().slice(0, 200)
  }
}

function clearLocation() {
  form.lat = null
  form.lng = null
}

function onDirections() {
  openInMaps(form.lat, form.lng, form.title.trim() || 'Place')
}

const statusText = computed(() => {
  switch (saveState.value) {
    case 'saving': return 'saving…'
    case 'saved': return '✓ saved'
    case 'error': return '! save failed'
    case 'dirty': return uploading.value ? 'uploading…' : 'unsaved'
    default: return form.id ? '' : (isNewEmpty.value ? 'new — start typing' : 'unsaved')
  }
})

const isNewEmpty = computed(() => {
  if (form.id) return false
  if (form.kind === 'pin') return !form.title.trim() && !(form.comment || '').trim()
  return !form.title.trim() && !(form.notes || '').trim() && !form.sleep_location.trim()
})

const canDelete = computed(() => form.id != null)

// Watch for any form change → 800 ms idle → fire save. Skipped while
// seeding (see flag above) so opening the panel doesn't queue a no-op save
// of the values we just hydrated from props.
watch(
  () => [form.title, form.comment, form.category, form.priority, form.date, form.end_date, form.notes, form.sleep_location, form.lat, form.lng],
  () => {
    if (seeding) return
    if (saveState.value !== 'saving') saveState.value = 'dirty'
    if (dirtyTimer) clearTimeout(dirtyTimer)
    if (savedTimer) { clearTimeout(savedTimer); savedTimer = null }
    dirtyTimer = setTimeout(fireSave, 800)
  },
  { deep: false }
)

// If the upload state flips back to idle while we have pending dirt, fire.
watch(uploading, (v) => {
  if (!v && saveState.value === 'dirty') {
    if (dirtyTimer) clearTimeout(dirtyTimer)
    dirtyTimer = setTimeout(fireSave, 200)
  }
})

defineExpose({
  // Parent calls these after the api round-trip resolves.
  markSaved: () => {
    saveState.value = 'saved'
    if (savedTimer) clearTimeout(savedTimer)
    savedTimer = setTimeout(() => {
      if (saveState.value === 'saved') saveState.value = 'idle'
    }, 1500)
  },
  markError: () => { saveState.value = 'error' },
  // Threads the server-assigned id back after a create so the next debounced
  // save emits a patch instead of another create. Doesn't touch other fields,
  // so the user's in-flight typing during the round-trip is preserved.
  assignId: (id) => { if (id != null) form.id = id },
  // Force-flush before close so unsaved edits don't get dropped.
  flush: () => {
    if (dirtyTimer) { clearTimeout(dirtyTimer); dirtyTimer = null }
    if (saveState.value === 'dirty') fireSave()
  },
})

function onClose() {
  if (dirtyTimer) { clearTimeout(dirtyTimer); dirtyTimer = null }
  if (saveState.value === 'dirty' && !isNewEmpty.value) fireSave()
  emit('close')
}

function onDelete() {
  if (!form.id) { emit('close'); return }
  emit('delete', { kind: form.kind, id: form.id })
}

const headerLabel = computed(() => {
  if (form.kind === 'pin') return form.id ? 'Edit place' : 'Mark a place'
  return form.id ? 'Edit stop' : 'New stop'
})
</script>

<style scoped>
.detail-panel {
  position: fixed;
  z-index: 950;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--vermillion);
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.06);
  background: var(--paper);
  overflow: hidden;
}
.detail-panel.is-desktop {
  top: 0;
  left: 0;
  bottom: 0;
  height: 100vh;
  /* width set inline by useResizablePanel */
}
.detail-panel.is-mobile {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  border-right: none;
  border-radius: 0;
  box-shadow: none;
}

/* Slide-in transitions */
.panel-slide-enter-active, .panel-slide-leave-active { transition: transform 220ms ease, opacity 220ms ease; }
.panel-slide-enter-from, .panel-slide-leave-to { transform: translateX(-100%); opacity: 0; }
.sheet-up-enter-active, .sheet-up-leave-active { transition: transform 240ms ease, opacity 240ms ease; }
.sheet-up-enter-from, .sheet-up-leave-to { transform: translateY(8%); opacity: 0; }

.dp-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 0.9rem 0.55rem;
  border-bottom: 1px solid var(--cream-edge);
  flex-shrink: 0;
}
.eyebrow {
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.dp-status {
  margin-left: auto;
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  color: var(--ink-faded);
  font-style: italic;
  min-width: 5rem;
  text-align: right;
}
.dp-status.status-saving { color: var(--ink-soft); }
.dp-status.status-saved { color: var(--moss, #4a7a4a); font-style: normal; }
.dp-status.status-error { color: var(--vermillion); font-style: normal; }
.dp-status.status-dirty { color: var(--ink-soft); }

.dp-close {
  background: transparent;
  border: none;
  font-size: 1.4rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
}
.dp-close:hover { color: var(--ink); background: var(--cream); }

.dp-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.9rem 1rem 1.4rem;
  display: grid;
  gap: 0.7rem;
}

.dp-title {
  font-family: var(--display, var(--body));
  font-size: 1.15rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  padding: 0.55rem 0.7rem;
}

.lbl {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0.3rem 0 -0.2rem;
}

.flag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.priority-chips { margin-top: 0; }
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
.priority-chip { font-family: var(--body); font-size: 0.78rem; padding: 0.25rem 0.7rem; }
.priority-chip.prio-must { color: var(--vermillion); border-color: var(--vermillion); }
.priority-chip.prio-must.on {
  background: var(--vermillion);
  color: var(--paper);
  border-color: var(--vermillion);
}

.cat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.4rem;
}
.cat {
  background: var(--cream);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  padding: 0.5rem 0.25rem;
  cursor: pointer;
  display: grid;
  gap: 0.2rem;
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
.cat-emoji { font-size: 1.05rem; }
.cat-label { font-size: 0.7rem; letter-spacing: 0.04em; }

.date-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; }
.date-cell { display: grid; gap: 0.25rem; min-width: 0; }
@media (max-width: 480px) {
  .date-row { grid-template-columns: 1fr; }
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

.dp-coord {
  margin: 0;
  font-size: 0.7rem;
  color: var(--ink-faded);
}

.directions { width: 100%; margin-top: 0.2rem; }

.hint { color: var(--ink-faded); font-size: 0.72rem; margin: 0; letter-spacing: 0.06em; }

.dp-actions {
  margin-top: 0.6rem;
  padding-top: 0.7rem;
  border-top: 1px dashed var(--cream-edge);
  display: flex;
  justify-content: flex-end;
}
.danger { color: var(--vermillion); border-color: var(--vermillion); }
.danger:hover { background: var(--vermillion); color: var(--paper); border-color: var(--vermillion); }

.dp-resize {
  position: absolute;
  top: 0;
  right: 0;
  width: 8px;
  height: 100%;
  cursor: ew-resize;
  background: transparent;
  z-index: 1;
}
.dp-resize:hover { background: rgba(232, 93, 60, 0.18); }
</style>
