<template>
  <section class="iti">
    <div class="iti-head">
      <button v-if="todayDay" class="btn btn-tiny" type="button" @click="goToday">Today →</button>
      <button class="btn btn-tiny btn-paste" type="button" @click="showPaste = true" title="Bulk import dates from a spreadsheet">Paste schedule…</button>
    </div>

    <p v-if="days.length" class="iti-meta mono">
      {{ uniqueDateCount }} {{ uniqueDateCount === 1 ? 'day' : 'days' }}
      <template v-if="days.length > uniqueDateCount"> · {{ days.length }} stops</template>
      <template v-if="todayDayNum"> · Day {{ todayDayNum }} / {{ uniqueDateCount }}</template>
      <template v-else-if="firstFutureIdx >= 0"> · {{ daysUntil(days[firstFutureIdx].date) }}</template>
      <template v-if="totalDriveKm > 0"> · {{ totalDriveKm.toLocaleString() }} km · {{ fmtMinutes(totalDriveMin) }} drive</template>
      <template v-else-if="totalKm > 0"> · ≈ {{ totalKm.toLocaleString() }} km</template>
    </p>

    <ol v-if="rows.length" class="iti-list">
      <template v-for="(r, i) in rows" :key="r.day.id">
        <li
          class="iti-day"
          :class="{ today: isToday(r.day.date), past: isPast(r.day.date), future: isFuture(r.day.date), 'is-stop': !r.dateHead }"
        >
          <div v-if="r.dateHead" class="iti-date" :title="r.day.date">
            <span class="d-dow mono">{{ shortDow(r.day.date) }}</span>
            <span class="d-num">{{ shortDay(r.day.date) }}</span>
            <span class="d-mon mono">{{ shortMonth(r.day.date) }}</span>
          </div>
          <div v-else class="iti-date is-cont" aria-hidden="true">
            <span class="cont-rule"></span>
          </div>
          <div class="iti-body">
            <button class="iti-label" type="button" @click="$emit('go', r.day)">
              <span class="day-num mono">DAY {{ r.dayIndex }}</span>
              <span class="day-label">{{ r.cleanLabel || 'Untitled' }}</span>
              <span v-if="r.day.lat == null" class="locate-hint" title="No location yet — click to search">⌖</span>
            </button>
            <p v-if="forecastFor(r.day)" class="iti-wx mono">
              {{ glyphFor(forecastFor(r.day).code) }}
              {{ forecastFor(r.day).tMax }}° / {{ forecastFor(r.day).tMin }}°
              <template v-if="forecastFor(r.day).precip > 0.5"> · {{ forecastFor(r.day).precip.toFixed(1) }}mm</template>
            </p>
            <p v-else-if="weatherTooFar(r.day)" class="iti-wx mono is-faded" :title="`Forecast available within 16 days — checks back from ${weatherStartDate}`">
              · forecast in {{ weatherTooFar(r.day) }}d
            </p>
            <p v-if="r.day.notes" class="iti-notes">{{ r.day.notes }}</p>
          </div>
          <div class="iti-actions">
            <button
              v-if="r.day.lat != null && r.day.lng != null"
              class="iti-icon"
              type="button"
              :title="`Find trails near ${r.day.label || 'this day'}`"
              @click="trailFor = r.day"
            >🥾</button>
            <button class="iti-icon" type="button" :title="`Edit day ${r.dayIndex}`" @click="$emit('edit', r.day)">✎</button>
            <button class="iti-icon" type="button" :title="`Remove day ${r.dayIndex}`" @click="del(r.day)">×</button>
          </div>
        </li>
        <div
          v-if="r.legNext && r.legNext.km != null"
          class="iti-leg mono"
          :title="r.legNext.title"
        >
          <template v-if="r.legNext.real">
            ↓ {{ r.legNext.real.km.toLocaleString() }} km · {{ fmtMinutes(r.legNext.real.minutes) }}
            <span v-if="r.legNext.real.source === 'estimate'" class="leg-est">est</span>
          </template>
          <template v-else>
            ↓ ≈ {{ r.legNext.km }} km
          </template>
        </div>
      </template>
    </ol>
    <p v-else class="hint mono">No days yet — add one below.</p>

    <section class="add-block">
      <p class="add-eyebrow mono">Add a day</p>
      <form class="iti-add" @submit.prevent="addEmptyDay">
        <input v-model="form.date" type="date" class="field add-date" :min="firstISO" required />
        <button class="btn btn-add" type="submit" title="Add an empty day with no location">+ Day</button>
      </form>
      <GeocoderSearch
        placeholder="…or search a place to drop on this day"
        :bias="bias"
        @pick="onAddPick"
      />
    </section>

    <PasteImportModal
      v-if="showPaste"
      :default-year="defaultYear"
      :bias="bias"
      @close="showPaste = false"
      @import="onPasteImport"
    />

    <TrailFinderModal
      v-if="trailFor"
      :lat="trailFor.lat"
      :lng="trailFor.lng"
      :name="trailFor.label || 'this day'"
      @close="trailFor = null"
      @pick="onTrailPick"
    />
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { todayISO } from '@/util.js'
import { dailyForecast, glyphFor } from '@/lib/weather.js'
import GeocoderSearch from './GeocoderSearch.vue'
import PasteImportModal from './PasteImportModal.vue'
import TrailFinderModal from './TrailFinderModal.vue'
import { routeLeg, fmtMinutes } from '@/lib/routing.js'

const props = defineProps({
  days: { type: Array, default: () => [] },
  bias: { type: Object, default: null },
  slug: { type: String, default: null },
})
const emit = defineEmits(['add', 'add-bulk', 'add-trail-pin', 'delete', 'go', 'edit'])

const showPaste = ref(false)
const defaultYear = computed(() => {
  if (props.days.length) return parseInt(props.days[0].date.slice(0, 4), 10)
  return new Date().getFullYear()
})

function onPasteImport(payload) {
  showPaste.value = false
  // Tolerate the legacy bare-rows signature too.
  const rows = Array.isArray(payload) ? payload : payload?.rows
  const replace = Array.isArray(payload) ? false : !!payload?.replace
  if (rows && rows.length) emit('add-bulk', { rows, replace })
}

const trailFor = ref(null)
function onTrailPick(t) {
  trailFor.value = null
  emit('add-trail-pin', t)
}

const today = computed(() => todayISO())

function nextDateAfter(iso) {
  if (!iso) return today.value
  const d = new Date(iso)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
const suggestedNewDate = computed(() => {
  if (!props.days.length) return today.value
  const last = [...props.days].sort((a, b) => a.date.localeCompare(b.date)).at(-1)
  return nextDateAfter(last.date)
})

// Lazy weather lookup for days within the forecast window. Stored as a
// reactive map of "id" → forecast object so the template re-renders as
// fetches resolve.
const wxMap = ref({})
function forecastFor(d) { return wxMap.value[d.id] || null }
const FORECAST_HORIZON_DAYS = 16
const weatherStartDate = today.value
function weatherTooFar(d) {
  if (!d.date) return 0
  const ms = new Date(d.date).getTime() - new Date(today.value).getTime()
  const days = Math.ceil(ms / (24 * 3600 * 1000))
  return days > FORECAST_HORIZON_DAYS ? days - FORECAST_HORIZON_DAYS : 0
}
async function refreshWeather(days) {
  for (const d of days) {
    if (d.id == null || d.lat == null || d.lng == null) continue
    if (wxMap.value[d.id]) continue
    const wx = await dailyForecast(d.lat, d.lng, d.date)
    if (wx) wxMap.value = { ...wxMap.value, [d.id]: wx }
  }
}
watch(() => props.days, (next) => { refreshWeather(next || []) }, { immediate: true })

const form = reactive({ date: today.value, label: '' })
// Once `days` is populated, default the form to "next day after the last".
watch(() => props.days, (next) => {
  if (next && next.length) form.date = nextDateAfter([...next].sort((a, b) => a.date.localeCompare(b.date)).at(-1).date)
}, { immediate: true })

const firstISO = computed(() => '2020-01-01')

const todayIdx = computed(() => props.days.findIndex((d) => d.date === today.value))
const todayDay = computed(() => (todayIdx.value >= 0 ? props.days[todayIdx.value] : null))
const firstFutureIdx = computed(() => props.days.findIndex((d) => d.date > today.value))

// Unique calendar-date count — used in the meta line and "Day N / M" label.
// Differs from days.length when the user has multiple stops on the same date.
const uniqueDateCount = computed(() => new Set(props.days.map((d) => d.date)).size)
const todayDayNum = computed(() => {
  const t = today.value
  const dates = [...new Set(props.days.map((d) => d.date))].sort()
  const idx = dates.indexOf(t)
  return idx >= 0 ? idx + 1 : 0
})

const totalKm = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const km = legKm(sorted[i], sorted[i + 1])
    if (km != null) sum += km
  }
  return sum
})

// Render rows: sorted by date with two derived flags per row.
//   dateHead: true on the first row of each calendar date — controls whether
//     the date badge column is shown (continuation rows render a hairline rule)
//   cleanLabel: strip a leading "Day N — " from any user-typed label so we
//     don't double-print the day number in the body
//   legNext: only set when the next row is on a *different* date AND both
//     sides have coords — silences the noisy "↓ 0 km" leg between same-day
//     stops (e.g. Vegas → Excalibur Hotel on day 1).
const rows = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  // Number unique calendar dates, not rows — two stops on the same date share
  // their Day N. So "Day 1: Vegas" + "Day 1: Excalibur Hotel" both render Day 1.
  const dayOfTrip = new Map()
  let n = 0
  for (const d of sorted) {
    if (!dayOfTrip.has(d.date)) {
      n += 1
      dayOfTrip.set(d.date, n)
    }
  }
  const out = []
  for (let i = 0; i < sorted.length; i++) {
    const day = sorted[i]
    const prev = i > 0 ? sorted[i - 1] : null
    const next = i < sorted.length - 1 ? sorted[i + 1] : null
    const dateHead = !prev || prev.date !== day.date
    const cleanLabel = day.label
      ? day.label.replace(/^\s*Day\s*\d+\s*[—\-–:·]\s*/i, '').trim()
      : ''
    let legNext = null
    if (next && next.date !== day.date && day.lat != null && day.lng != null && next.lat != null && next.lng != null) {
      const km = legKm(day, next)
      const real = legFor(day, next)
      legNext = { km, real, title: legTitle(day, next) }
    }
    out.push({ day, dayIndex: dayOfTrip.get(day.date), dateHead, cleanLabel, legNext })
  }
  return out
})

// Real driving legs (cached). Loaded async; null until first resolution.
const legCache = ref({}) // pairKey → { km, minutes, source }
function pairKey(a, b) { return `${a.id}>${b.id}` }
function legFor(a, b) { return legCache.value[pairKey(a, b)] || null }
function legTitle(a, b) {
  const leg = legFor(a, b)
  if (leg) {
    const tag = leg.source === 'osrm' ? 'driving' : 'estimate (no OSRM)'
    return `${tag}: ${leg.km} km · ${fmtMinutes(leg.minutes)}`
  }
  return `Straight-line distance from ${a.label || 'this day'} to ${b.label || 'the next day'} — actual driving will be longer.`
}
async function refreshLegs(days) {
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date))
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i], b = sorted[i + 1]
    if (a.lat == null || a.lng == null || b.lat == null || b.lng == null) continue
    const k = pairKey(a, b)
    if (legCache.value[k]) continue
    const leg = await routeLeg({ lat: a.lat, lng: a.lng }, { lat: b.lat, lng: b.lng })
    if (leg) legCache.value = { ...legCache.value, [k]: leg }
  }
}
watch(() => props.days, (next) => { refreshLegs(next || []) }, { immediate: true })

const totalDriveKm = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const leg = legFor(sorted[i], sorted[i + 1])
    if (leg) sum += leg.km
  }
  return sum
})
const totalDriveMin = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const leg = legFor(sorted[i], sorted[i + 1])
    if (leg) sum += leg.minutes
  }
  return sum
})

function isToday(date) { return date === today.value }
function isPast(date) { return date < today.value }
function isFuture(date) { return date > today.value }

function shortDay(iso) { return parseInt(iso.slice(8, 10), 10) }
function shortMonth(iso) {
  const m = parseInt(iso.slice(5, 7), 10) - 1
  return ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'][m] || ''
}
function shortDow(iso) {
  // Build a UTC date so the weekday isn't off-by-one in negative-offset zones.
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  return ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'][dt.getUTCDay()] || ''
}

function daysUntil(iso) {
  const a = new Date(today.value), b = new Date(iso)
  const diff = Math.round((b - a) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff > 0) return `T-${diff} days`
  return `T+${-diff} days`
}

function addEmptyDay() {
  if (!form.date) return
  emit('add', { date: form.date, label: null })
  form.date = suggestedNewDate.value
}
function onAddPick(result) {
  if (!form.date) return
  const label = result.label.split(',')[0].trim().slice(0, 200) || null
  emit('add', { date: form.date, label, lat: result.lat, lng: result.lng })
  form.date = suggestedNewDate.value
}

function del(d) {
  if (confirm(`Remove ${d.label || 'this day'}?`)) emit('delete', d)
}

function goToday() {
  if (todayDay.value) emit('go', todayDay.value)
}

// Great-circle distance between two days that both carry coords. Returns
// null when either day lacks a position.
function legKm(a, b) {
  if (a.lat == null || a.lng == null || b.lat == null || b.lng == null) return null
  const R = 6371
  const toRad = (deg) => deg * Math.PI / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat)
  const lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  const km = 2 * R * Math.asin(Math.sqrt(h))
  return Math.round(km)
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
  flex-wrap: wrap;
}
.btn-paste {
  background: var(--paper);
  color: var(--ink);
  border: 1px dashed var(--ink);
  box-shadow: none;
}
.btn-paste:hover {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
  border-style: solid;
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
.iti-day.today .d-mon, .iti-day.today .iti-notes,
.iti-day.today .day-num { color: rgba(255,255,255,0.8); }
.iti-day.today .iti-label { color: var(--paper); }
.iti-day.past { opacity: 0.55; }
.iti-day.is-stop { padding-top: 0; padding-bottom: 0.3rem; }

.iti-date {
  display: grid;
  text-align: center;
  line-height: 1;
}
.iti-date.is-cont { align-items: stretch; padding-block: 0.4rem; }
.cont-rule {
  width: 1px;
  background: var(--cream-edge);
  margin: 0 auto;
  display: block;
  align-self: stretch;
  min-height: 14px;
}
.d-dow { font-size: 0.55rem; letter-spacing: 0.18em; color: var(--ink-faded); margin-bottom: -0.05rem; }
.d-num { font-family: var(--display); font-size: 1.3rem; }
.d-mon { font-size: 0.62rem; letter-spacing: 0.16em; color: var(--ink-faded); }
.iti-day.today .d-dow { color: rgba(255,255,255,0.6); }

.iti-body { min-width: 0; }
.iti-label {
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
  display: inline-flex;
  align-items: baseline;
  gap: 0.45rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.day-num {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: var(--ink-faded);
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 2px;
  padding: 0.05rem 0.3rem;
  flex-shrink: 0;
  align-self: center;
  line-height: 1.4;
}
.day-label {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.iti-label:hover .day-label { color: var(--vermillion); }
.iti-day.today .iti-label:hover .day-label { color: var(--paper); text-decoration: underline; }
.iti-day.today .day-num {
  background: var(--vermillion-deep);
  border-color: var(--vermillion-deep);
  color: rgba(255,255,255,0.85);
}
.locate-hint { font-size: 0.85em; opacity: 0.55; }
.iti-notes {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.iti-actions { display: inline-flex; gap: 0.1rem; }
.iti-icon {
  background: transparent;
  border: none;
  font-size: 0.9rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.25rem 0.35rem;
  border-radius: 3px;
}
.iti-icon:hover { color: var(--vermillion); background: var(--cream); }
.iti-day.today .iti-icon { color: rgba(255,255,255,0.7); }
.iti-day.today .iti-icon:hover { color: var(--paper); background: var(--vermillion-deep); }

.iti-leg {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.14em;
  padding: 0.15rem 0 0.15rem 2.6rem;
  display: inline-flex;
  align-items: baseline;
  gap: 0.4rem;
}
.leg-est {
  font-size: 0.55rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  background: var(--cream);
  padding: 0 0.3rem;
  border-radius: 2px;
  border: 1px dotted var(--cream-edge);
}

.iti-wx {
  margin: 0.15rem 0 0;
  font-size: 0.72rem;
  color: var(--ink-soft);
  letter-spacing: 0.04em;
}
.iti-wx.is-faded { color: var(--ink-faded); font-style: italic; }

.add-block {
  position: sticky;
  bottom: 0;
  margin-top: 1rem;
  padding: 0.8rem 0 0.4rem;
  border-top: 1px dashed var(--cream-edge);
  background: var(--paper);
  display: grid;
  gap: 0.5rem;
  z-index: 2;
}
.add-eyebrow {
  font-size: 0.65rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0;
}
.iti-add {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: stretch;
  gap: 0.5rem;
}
.field.tiny { padding: 0.45rem 0.6rem; font-size: 0.88rem; }
.field.add-date {
  padding: 0.55rem 0.7rem;
  font-size: 0.92rem;
  height: 38px;
  box-sizing: border-box;
}
.btn-add {
  height: 38px;
  padding: 0 1rem;
  font-size: 0.85rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--vermillion);
  color: var(--paper);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-family: var(--display);
  box-shadow: 0 2px 0 var(--vermillion-deep);
  transition: background 90ms ease;
}
.btn-add:hover { background: var(--vermillion-deep); }
.btn-add:active { transform: translateY(1px); box-shadow: 0 1px 0 var(--vermillion-deep); }

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
