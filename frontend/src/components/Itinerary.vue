<template>
  <section class="iti">
    <div class="iti-head">
      <button v-if="todayDay" class="btn btn-tiny" type="button" @click="goToday">Today →</button>
      <button
        class="btn btn-tiny btn-add-day"
        type="button"
        :class="{ open: addOpen }"
        @click="addOpen = !addOpen"
      >{{ addOpen ? '× Close' : '+ Add stop' }}</button>
      <button class="btn btn-tiny btn-paste" type="button" @click="showPaste = true" title="Bulk import dates from a spreadsheet">Paste…</button>
    </div>

    <Transition name="reveal">
      <section v-if="addOpen" class="add-inline">
        <form class="iti-add" @submit.prevent="addEmptyDay">
          <input v-model="form.date" type="date" class="field add-date" :min="firstISO" required />
          <button class="btn btn-add" type="submit" title="Add an empty stop with no location">+ Stop</button>
        </form>
        <GeocoderSearch
          placeholder="…or search a place to drop on this date"
          :bias="bias"
          @pick="onAddPick"
        />
      </section>
    </Transition>

    <p v-if="days.length" class="iti-meta mono">
      {{ totalNights }} {{ totalNights === 1 ? 'day' : 'days' }} · {{ days.length }} {{ days.length === 1 ? 'stop' : 'stops' }}
      <template v-if="todayDayNum"> · Day {{ todayDayNum }} / {{ totalNights }}</template>
      <template v-else-if="firstFutureIdx >= 0"> · {{ daysUntil(days[firstFutureIdx].date) }}</template>
      <template v-if="totalDriveKm > 0"> · {{ totalDriveKm.toLocaleString() }} km · {{ fmtMinutes(totalDriveMin) }} drive</template>
      <template v-else-if="totalKm > 0"> · ≈ {{ totalKm.toLocaleString() }} km</template>
    </p>

    <ol v-if="rows.length" class="iti-list">
      <template v-for="r in rows" :key="r.day.id">
        <li
          class="iti-day"
          :class="{ today: isTodayInRange(r.day), past: isPastStop(r.day), future: isFutureStop(r.day) }"
        >
          <div class="iti-date" :title="r.spanISO">
            <span class="d-dow mono">{{ shortDow(r.day.date) }}</span>
            <span class="d-num">{{ shortDay(r.day.date) }}</span>
            <span class="d-mon mono">{{ shortMonth(r.day.date) }}</span>
          </div>
          <div class="iti-body">
            <button class="iti-label" type="button" @click="$emit('go', r.day)">
              <span class="day-num mono">{{ r.dayLabel }}</span>
              <span class="day-label">{{ r.cleanLabel || 'Untitled' }}</span>
              <span v-if="r.day.lat == null" class="locate-hint" title="No location yet — click to search">⌖</span>
            </button>
            <p v-if="forecastFor(r.day)" class="iti-wx mono">
              {{ glyphFor(forecastFor(r.day).code) }}
              {{ forecastFor(r.day).tMax }}° / {{ forecastFor(r.day).tMin }}°
              <template v-if="forecastFor(r.day).precip > 0.5"> · {{ forecastFor(r.day).precip.toFixed(1) }}mm</template>
            </p>
            <p v-else-if="weatherTooFar(r.day)" class="iti-wx mono is-faded" :title="`Forecast available within 16 days from today (${weatherStartDate})`">
              · weather in {{ weatherTooFar(r.day) }}d
            </p>
            <p v-if="r.day.notes" class="iti-notes">{{ r.day.notes }}</p>
          </div>
          <div class="iti-actions">
            <button
              class="iti-icon"
              type="button"
              :title="`Attach a pin to ${r.dayLabel}`"
              @click="attachOpenForDay = attachOpenForDay === r.day.id ? null : r.day.id"
            >+</button>
            <button
              v-if="r.day.lat != null && r.day.lng != null"
              class="iti-icon"
              type="button"
              :title="`Find trails near ${r.day.label || 'this stop'}`"
              @click="trailFor = r.day"
            >🥾</button>
            <button class="iti-icon" type="button" :title="`Edit ${r.dayLabel}`" @click="$emit('edit', r.day)">✎</button>
            <button class="iti-icon" type="button" :title="`Remove ${r.dayLabel}`" @click="del(r.day)">×</button>
          </div>
        </li>
        <ul v-if="(pinsByDay.get(r.day.id) || []).length || attachOpenForDay === r.day.id" class="day-pins">
          <li v-for="p in (pinsByDay.get(r.day.id) || [])" :key="p.id" class="day-pin" @click.stop="$emit('select-point', p)">
            <span class="day-pin-emoji">{{ pinEmoji(p) }}</span>
            <span class="day-pin-title">{{ p.title || 'Untitled' }}</span>
            <button
              type="button"
              class="day-pin-detach"
              title="Detach from this day"
              @click.stop="$emit('detach', p.id)"
            >−</button>
          </li>
          <li v-if="attachOpenForDay === r.day.id" class="day-pin-picker">
            <p v-if="!unattachedPins.length" class="picker-empty mono">
              No unattached pins. Drop one on the map first.
              <button type="button" class="picker-cancel" @click="attachOpenForDay = null">cancel</button>
            </p>
            <template v-else>
              <p class="picker-eyebrow mono">Attach a pin to {{ r.dayLabel }}</p>
              <ul class="picker-list">
                <li v-for="p in unattachedPins" :key="p.id">
                  <button type="button" class="picker-item" @click.stop="pickAttach(r.day.id, p.id)">
                    <span class="day-pin-emoji">{{ pinEmoji(p) }}</span>
                    <span>{{ p.title }}</span>
                  </button>
                </li>
              </ul>
              <button type="button" class="picker-cancel mono" @click="attachOpenForDay = null">cancel</button>
            </template>
          </li>
        </ul>
        <div
          v-if="legShouldShow(r)"
          class="iti-leg mono"
          :class="{ 'is-long': legIsLong(r) }"
          :title="r.legNext.title"
        >
          <template v-if="r.legNext.real">
            <span class="leg-glyph" aria-hidden="true">{{ legIsLong(r) ? '~' : '↓' }}</span>
            {{ r.legNext.real.km.toLocaleString() }} km · {{ fmtMinutes(r.legNext.real.minutes) }}
            <span v-if="r.legNext.real.source === 'estimate'" class="leg-est">est</span>
          </template>
          <template v-else>
            <span class="leg-glyph" aria-hidden="true">↓</span> ≈ {{ r.legNext.km }} km
          </template>
        </div>
      </template>
    </ol>
    <p v-else class="hint mono">
      No days yet —
      <button type="button" class="hint-link" @click="addOpen = true">add the first one</button>.
    </p>

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
import { CATEGORIES, todayISO } from '@/util.js'
import { dailyForecast, glyphFor } from '@/lib/weather.js'
import GeocoderSearch from './GeocoderSearch.vue'
import PasteImportModal from './PasteImportModal.vue'
import TrailFinderModal from './TrailFinderModal.vue'
import { routeLeg, fmtMinutes } from '@/lib/routing.js'

const props = defineProps({
  days: { type: Array, default: () => [] },
  points: { type: Array, default: () => [] },
  bias: { type: Object, default: null },
  slug: { type: String, default: null },
})
const emit = defineEmits([
  'add', 'add-bulk', 'add-trail-pin', 'delete', 'go', 'edit',
  'select-point', 'attach', 'detach',
])

const emojiByCategory = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function pinEmoji(p) { return p?.gpx_data ? '🥾' : (emojiByCategory[p?.category] || '📍') }

// Per-day attached pins, keyed by day id. Each list keeps insertion order
// (= creation time on the backend, which matches when the user attached it).
const pinsByDay = computed(() => {
  const map = new Map()
  for (const p of props.points) {
    if (p.itinerary_day_id == null) continue
    const arr = map.get(p.itinerary_day_id) || []
    arr.push(p)
    map.set(p.itinerary_day_id, arr)
  }
  return map
})
const unattachedPins = computed(() =>
  (props.points || []).filter((p) => p.itinerary_day_id == null && p.title),
)

// Open-state: when set, that day's "attach" picker is open. Clicking outside
// or selecting a pin closes it.
const attachOpenForDay = ref(null)
function pickAttach(dayId, pointId) {
  emit('attach', { pointId, dayId })
  attachOpenForDay.value = null
}

const showPaste = ref(false)
// Inline add-day disclosure — collapsed by default so the list breathes.
// Auto-opens when the trip is empty so the first add still feels obvious.
const addOpen = ref(false)
watch(() => props.days?.length, (n) => {
  if (!n) addOpen.value = true
}, { immediate: true })
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

function endOf(d) { return d.end_date || d.date }

function nextDateAfter(iso) {
  if (!iso) return today.value
  const d = new Date(iso)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
const suggestedNewDate = computed(() => {
  if (!props.days.length) return today.value
  const last = [...props.days].sort((a, b) => a.date.localeCompare(b.date)).at(-1)
  return nextDateAfter(endOf(last))
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

// A stop is "today" when today is within [date, end_date] inclusive.
const todayDay = computed(() => props.days.find((d) => today.value >= d.date && today.value <= endOf(d)) || null)
const firstFutureIdx = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  return sorted.findIndex((d) => d.date > today.value)
})

// Total number of trip-days (sum of every stop's span). "1-day per stop" → days
// equals stops; multi-day stops add their full span.
const totalNights = computed(() => {
  let n = 0
  for (const d of props.days) n += daysInSpan(d.date, endOf(d))
  return n
})
const todayDayNum = computed(() => {
  const t = today.value
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let n = 0
  for (const d of sorted) {
    const span = daysInSpan(d.date, endOf(d))
    if (t >= d.date && t <= endOf(d)) {
      const offset = daysBetween(d.date, t)
      return n + offset + 1
    }
    n += span
  }
  return 0
})

function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86400000)
}
function daysInSpan(start, end) { return daysBetween(start, end) + 1 }

const totalKm = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const km = legKm(sorted[i], sorted[i + 1])
    if (km != null) sum += km
  }
  return sum
})

// Render rows: one row per stop, sorted by start date. Each stop owns its
// full span; the day chip reads "DAY N" for single-day stops and "DAY N–M"
// for multi-day stops.
//   cleanLabel: strip a leading "Day N — " from any user-typed label so we
//     don't double-print the day number in the body
//   legNext: distance + drive estimate to the next stop (when both have coords)
const rows = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  const out = []
  let cumulative = 0
  for (let i = 0; i < sorted.length; i++) {
    const day = sorted[i]
    const next = i < sorted.length - 1 ? sorted[i + 1] : null
    const span = daysInSpan(day.date, endOf(day))
    const startNum = cumulative + 1
    const endNum = cumulative + span
    const dayLabel = span > 1 ? `DAY ${startNum}–${endNum}` : `DAY ${startNum}`
    const spanISO = span > 1 ? `${day.date} → ${endOf(day)}` : day.date
    const cleanLabel = day.label
      ? day.label.replace(/^\s*Day\s*\d+(?:\s*[—\-–]\s*\d+)?\s*[—\-–:·]\s*/i, '').trim()
      : ''
    let legNext = null
    if (next && day.lat != null && day.lng != null && next.lat != null && next.lng != null) {
      const km = legKm(day, next)
      const real = legFor(day, next)
      legNext = { km, real, title: legTitle(day, next) }
    }
    out.push({ day, dayLabel, spanISO, cleanLabel, legNext })
    cumulative += span
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

function isTodayInRange(d) { return today.value >= d.date && today.value <= endOf(d) }
function isPastStop(d) { return endOf(d) < today.value }
function isFutureStop(d) { return d.date > today.value }

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
  // Stay open after empty-day adds — the user is likely adding several in a row.
}
function onAddPick(result) {
  if (!form.date) return
  const label = result.label.split(',')[0].trim().slice(0, 200) || null
  emit('add', { date: form.date, label, lat: result.lat, lng: result.lng })
  form.date = suggestedNewDate.value
  // Picking a place is a "completion" gesture — collapse so the new row is visible.
  addOpen.value = false
}

function del(d) {
  if (confirm(`Remove ${d.label || 'this day'}?`)) emit('delete', d)
}

function goToday() {
  if (todayDay.value) emit('go', todayDay.value)
}

// Great-circle distance between two days that both carry coords. Returns
// null when either day lacks a position.
// Hide same-spot legs (e.g. Day 1 Excalibur → Day 2 Excalibur) — they print
// as "↓ 0 km · 0 min" and clutter the list. Mirrors the map's silencing rule.
function legShouldShow(row) {
  if (!row.legNext || row.legNext.km == null) return false
  if (row.legNext.real && row.legNext.real.km < 1) return false
  if (!row.legNext.real && row.legNext.km < 1) return false
  return true
}

// "Long-haul" legs (>= 3 hours OR >= 250 km) get a quieter typographic bump
// — heavier weight + a route-style ~ glyph + more vertical breathing — so
// the trip reads as "stop · drive · stop · drive" instead of one flat list.
const LONG_LEG_MIN = 180
const LONG_LEG_KM = 250
function legIsLong(row) {
  const real = row?.legNext?.real
  if (!real) return false
  return real.minutes >= LONG_LEG_MIN || real.km >= LONG_LEG_KM
}

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
.btn-add-day {
  background: var(--vermillion);
  color: var(--paper);
  border: none;
  box-shadow: 0 1px 0 var(--vermillion-deep);
}
.btn-add-day:hover { background: var(--vermillion-deep); }
.btn-add-day.open {
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--ink);
  box-shadow: none;
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

.add-inline {
  display: grid;
  gap: 0.5rem;
  padding: 0.7rem 0.7rem 0.8rem;
  margin-bottom: 0.4rem;
  background: var(--cream);
  border: 1px dashed var(--cream-edge);
  border-radius: 4px;
}
.reveal-enter-active, .reveal-leave-active {
  transition: opacity 160ms ease, transform 160ms ease, max-height 200ms ease;
  overflow: hidden;
}
.reveal-enter-from, .reveal-leave-to { opacity: 0; transform: translateY(-4px); }
.hint-link {
  background: transparent;
  border: none;
  color: var(--vermillion);
  text-decoration: underline;
  font: inherit;
  cursor: pointer;
  padding: 0;
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
  gap: 0.35rem;
}
.iti-day {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 0.6rem;
  align-items: start;
  padding: 0.4rem 0.4rem;
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
  padding-top: 0.1rem;
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
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  flex-wrap: wrap;
  max-width: 100%;
  line-height: 1.25;
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
  /* Allow up to two lines so long stop names like "Excalibur Lodge"
     don't truncate to "Excalibur ..." in the ~360px desktop dock. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  flex: 1 1 auto;
  min-width: 0;
  word-break: break-word;
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
@media (max-width: 720px) {
  .iti-icon { padding: 0.55rem 0.55rem; font-size: 1rem; }
}

.iti-leg {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.14em;
  padding: 0.15rem 0 0.15rem 2.6rem;
  display: inline-flex;
  align-items: baseline;
  gap: 0.4rem;
}
.iti-leg .leg-glyph {
  display: inline-block;
  width: 0.85rem;
  text-align: center;
  color: var(--ink-faded);
}
/* Long-haul drive day: a quiet emphasis, not a heading. Slightly heavier
   text, more vertical room, and a dashed rule above so the eye reads the
   trip as alternating "stop · drive". */
.iti-leg.is-long {
  font-size: 0.7rem;
  color: var(--ink-soft);
  font-weight: 600;
  padding: 0.45rem 0 0.5rem 2.6rem;
  position: relative;
}
.iti-leg.is-long::before {
  content: "";
  position: absolute;
  left: 2.6rem;
  right: 0.4rem;
  top: 0.18rem;
  border-top: 1px dashed var(--cream-edge);
}
.iti-leg.is-long .leg-glyph {
  font-family: var(--display);
  color: var(--ink-soft);
  font-weight: 700;
}

/* Attached pins displayed inline under a day card. */
.day-pins, .day-pin-add-only {
  list-style: none;
  margin: 0 0 0.4rem 2.6rem;
  padding: 0.25rem 0 0.1rem;
  display: grid;
  gap: 0.15rem;
  border-left: 2px solid var(--cream-edge);
  padding-left: 0.6rem;
}
.day-pin-add-only { padding-bottom: 0.1rem; }
.day-pin {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.45rem;
  align-items: center;
  font-size: 0.85rem;
  color: var(--ink);
  cursor: pointer;
  padding: 0.15rem 0.2rem;
  border-radius: 2px;
}
.day-pin:hover { background: var(--cream); color: var(--vermillion); }
.day-pin-emoji { font-size: 0.9rem; }
.day-pin-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.day-pin-detach {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 0.95rem;
  cursor: pointer;
  padding: 0 0.2rem;
  line-height: 1;
}
.day-pin-detach:hover { color: var(--vermillion); }
.day-pin-add-wrap { padding-top: 0.1rem; }
.day-pin-add {
  background: transparent;
  border: 1px dashed var(--ink-faded);
  border-radius: 2px;
  color: var(--ink-faded);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  cursor: pointer;
}
.day-pin-add:hover { color: var(--vermillion); border-color: var(--vermillion); }

.day-pin-picker {
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  padding: 0.4rem 0.5rem;
  display: grid;
  gap: 0.3rem;
  margin: 0.2rem 0;
}
.picker-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.picker-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.15rem;
  max-height: 12rem;
  overflow-y: auto;
}
.picker-item {
  width: 100%;
  background: transparent;
  border: none;
  text-align: left;
  font: inherit;
  font-size: 0.85rem;
  color: var(--ink);
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.45rem;
  align-items: center;
  padding: 0.25rem 0.3rem;
  border-radius: 2px;
  cursor: pointer;
}
.picker-item:hover { background: var(--paper); color: var(--vermillion); }
.picker-empty {
  margin: 0;
  font-size: 0.74rem;
  color: var(--ink-faded);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: space-between;
}
.picker-cancel {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  justify-self: end;
  padding: 0.15rem 0.4rem;
}
.picker-cancel:hover { color: var(--vermillion); }
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
