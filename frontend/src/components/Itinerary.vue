<template>
  <section class="iti">
    <div class="iti-head">
      <button v-if="todayDay" class="btn btn-tiny" type="button" @click="goToday">Today →</button>
      <button class="btn btn-tiny btn-ghost" type="button" @click="showPaste = true">Paste</button>
    </div>

    <p v-if="days.length" class="iti-meta mono">
      {{ days.length }} {{ days.length === 1 ? 'day' : 'days' }}
      <template v-if="todayIdx >= 0"> · Day {{ todayIdx + 1 }} / {{ days.length }}</template>
      <template v-else-if="firstFutureIdx >= 0"> · {{ daysUntil(days[firstFutureIdx].date) }}</template>
    </p>

    <ol v-if="days.length" class="iti-list">
      <li
        v-for="(d, i) in days"
        :key="d.id"
        class="iti-day"
        :class="{ today: isToday(d.date), past: isPast(d.date), future: isFuture(d.date) }"
      >
        <div class="iti-date" :title="d.date">
          <span class="d-num">{{ shortDay(d.date) }}</span>
          <span class="d-mon mono">{{ shortMonth(d.date) }}</span>
        </div>
        <div class="iti-body">
          <button class="iti-label" type="button" @click="$emit('go', d)">
            {{ d.label || 'Untitled' }}
            <span v-if="d.lat == null" class="locate-hint" title="Click to locate via search">⌖</span>
          </button>
          <p v-if="d.notes" class="iti-notes">{{ d.notes }}</p>
        </div>
        <button class="iti-del" type="button" :title="`Remove day ${i + 1}`" @click="del(d)">×</button>
      </li>
    </ol>
    <p v-else class="hint mono">Paste your trip schedule, or add days one at a time.</p>

    <form class="iti-add" @submit.prevent="addDay">
      <input v-model="form.date" type="date" class="field tiny" :min="firstISO" required />
      <input v-model="form.label" type="text" class="field tiny" placeholder="Where?" maxlength="200" />
      <button class="btn btn-tiny" type="submit">+ Add</button>
    </form>

    <Teleport to="body">
      <div v-if="showPaste" class="scrim" @click.self="showPaste = false">
        <form class="paper paste-modal" @submit.prevent="doPaste">
          <p class="eyebrow">Paste itinerary</p>
          <h3>Bulk import</h3>
          <p class="paste-help">
            Paste rows from your spreadsheet — tab, comma, or semicolon separated.
            Header row optional. Recognised columns: <span class="mono">date · lieu de dodo · lieu · lieu prévu · notes</span>.
          </p>
          <textarea
            v-model="pasteText"
            class="field"
            rows="8"
            placeholder="Date&#9;Lieu de dodo&#9;Lieu&#9;Lieu Dodo prévu&#9;Notes&#10;samedi 9 mai&#9;Excalibur Hotel&#9;Las Vegas&#9;Las Vegas&#10;…"
          />
          <label class="row-inline">
            <span class="lbl">Year</span>
            <input v-model.number="pasteYear" type="number" min="2000" max="2100" class="field tiny year-field" />
            <span v-if="parsedPreview.length" class="parsed mono">{{ parsedPreview.length }} day{{ parsedPreview.length === 1 ? '' : 's' }} detected</span>
          </label>
          <p v-if="pasteError" class="error sm">{{ pasteError }}</p>
          <div class="row">
            <button type="button" class="btn btn-ghost" @click="showPaste = false">Cancel</button>
            <button type="submit" class="btn" :disabled="!parsedPreview.length || importing">
              {{ importing ? 'Importing…' : `Import ${parsedPreview.length} days` }}
            </button>
          </div>
        </form>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { parseItineraryPaste, todayISO } from '@/util.js'

const props = defineProps({
  days: { type: Array, default: () => [] },
})
const emit = defineEmits(['add', 'add-bulk', 'delete', 'go'])

const today = computed(() => todayISO())
const showPaste = ref(false)
const pasteText = ref('')
const pasteYear = ref(new Date().getFullYear())
const pasteError = ref('')
const importing = ref(false)

const form = reactive({ date: today.value, label: '' })

const firstISO = computed(() => '2020-01-01')

const todayIdx = computed(() => props.days.findIndex((d) => d.date === today.value))
const todayDay = computed(() => (todayIdx.value >= 0 ? props.days[todayIdx.value] : null))
const firstFutureIdx = computed(() => props.days.findIndex((d) => d.date > today.value))

const parsedPreview = computed(() => {
  if (!pasteText.value.trim()) return []
  try { return parseItineraryPaste(pasteText.value, pasteYear.value) }
  catch { return [] }
})

function isToday(date) { return date === today.value }
function isPast(date) { return date < today.value }
function isFuture(date) { return date > today.value }

function shortDay(iso) { return parseInt(iso.slice(8, 10), 10) }
function shortMonth(iso) {
  const m = parseInt(iso.slice(5, 7), 10) - 1
  return ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'][m] || ''
}

function daysUntil(iso) {
  const a = new Date(today.value), b = new Date(iso)
  const diff = Math.round((b - a) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff > 0) return `T-${diff} days`
  return `T+${-diff} days`
}

async function addDay() {
  if (!form.date) return
  emit('add', { date: form.date, label: form.label.trim() || null })
  form.label = ''
}

function del(d) {
  if (confirm(`Remove ${d.label || 'this day'}?`)) emit('delete', d)
}

function goToday() {
  if (todayDay.value) emit('go', todayDay.value)
}

async function doPaste() {
  if (!parsedPreview.value.length) return
  importing.value = true
  pasteError.value = ''
  try {
    await emit('add-bulk', parsedPreview.value)
    showPaste.value = false
    pasteText.value = ''
  } catch (e) {
    pasteError.value = e?.message || 'Import failed.'
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.iti { display: grid; gap: 0.45rem; }
.iti-head {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.35rem;
  margin-top: -0.1rem;
}
.iti-meta {
  margin: 0;
  color: var(--ink-faded);
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.iti-list {
  list-style: none;
  margin: 0.2rem 0;
  padding: 0;
  display: grid;
  gap: 0.25rem;
  max-height: 28vh;
  overflow-y: auto;
}
.iti-day {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 0.6rem;
  align-items: center;
  padding: 0.35rem 0.4rem;
  border: 1px solid transparent;
  border-radius: 3px;
}
.iti-day:hover { background: var(--cream); border-color: var(--cream-edge); }
.iti-day.today {
  background: var(--vermillion);
  border-color: var(--vermillion-deep);
  color: var(--paper);
}
.iti-day.today .d-mon, .iti-day.today .iti-notes { color: rgba(255,255,255,0.8); }
.iti-day.today .iti-label { color: var(--paper); }
.iti-day.past { opacity: 0.55; }

.iti-date {
  display: grid;
  text-align: center;
  line-height: 1;
}
.d-num { font-family: var(--display); font-size: 1.3rem; }
.d-mon { font-size: 0.62rem; letter-spacing: 0.16em; color: var(--ink-faded); }

.iti-body { min-width: 0; }
.iti-label {
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.iti-label:hover { color: var(--vermillion); }
.iti-day.today .iti-label:hover { color: var(--paper); text-decoration: underline; }
.locate-hint { font-size: 0.85em; opacity: 0.55; }
.iti-notes {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.iti-del {
  background: transparent;
  border: none;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0 0.3rem;
  border-radius: 3px;
}
.iti-del:hover { color: var(--vermillion); background: var(--cream); }
.iti-day.today .iti-del { color: rgba(255,255,255,0.7); }
.iti-day.today .iti-del:hover { color: var(--paper); background: var(--vermillion-deep); }

.iti-add {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.35rem;
  margin-top: 0.4rem;
}
.field.tiny { padding: 0.45rem 0.6rem; font-size: 0.88rem; }

.hint { font-size: 0.74rem; color: var(--ink-faded); margin: 0.2rem 0 0; letter-spacing: 0.06em; }

.paste-modal {
  width: min(580px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 0.6rem;
  padding: 1.4rem 1.5rem;
}
.paste-help { color: var(--ink-soft); font-size: 0.9rem; margin: 0; }
.row-inline { display: flex; align-items: center; gap: 0.6rem; }
.year-field { width: 90px; }
.parsed { color: var(--ink-soft); }
.row { display: flex; gap: 0.5rem; justify-content: flex-end; flex-wrap: wrap; margin-top: 0.4rem; }
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.error.sm { font-size: 0.85rem; color: var(--vermillion-deep); margin: 0; }
</style>
