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
        <li v-if="r.weekHeader" class="iti-week-sep mono">
          <span>Week {{ r.weekNum }}</span>
          <span class="week-meta">{{ r.weekRange }}</span>
        </li>
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
              <span
                v-if="bestMorning(r.day)"
                class="iti-run mono"
                :title="`Calmest 3-hour window for an early effort, by mean temp + rain probability`"
              >▸ run {{ bestMorning(r.day) }}</span>
            </p>
            <p v-else-if="weatherTooFar(r.day)" class="iti-wx mono is-faded" :title="`Forecast available within 16 days from today (${weatherStartDate})`">
              · weather in {{ weatherTooFar(r.day) }}d
            </p>
            <p v-if="sunFor(r.day)" class="iti-sun mono" title="Sunrise → sunset (solar time at this stop)">☀ {{ sunFor(r.day) }}</p>
            <p v-if="r.day.notes" class="iti-notes">{{ r.day.notes }}</p>
            <ul v-if="photoCount(r.day)" class="iti-photo-strip" :title="`${photoCount(r.day)} photo${photoCount(r.day) === 1 ? '' : 's'}`">
              <li v-for="(thumb, i) in photoThumbs(r.day)" :key="i" class="iti-photo">
                <img :src="thumb" alt="" />
              </li>
              <li v-if="photoCount(r.day) > 4" class="iti-photo-more mono">+{{ photoCount(r.day) - 4 }}</li>
            </ul>
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
              class="iti-icon iti-icon-trail"
              type="button"
              :title="`Find trails near ${r.day.label || 'this stop'}`"
              @click="trailFor = r.day"
            >△</button>
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
            <p v-if="!pickerCandidatesAll.length" class="picker-empty mono">
              No pins yet. Drop one on the map first.
              <button type="button" class="picker-cancel" @click="closePicker">cancel</button>
            </p>
            <template v-else>
              <p class="picker-eyebrow mono">Attach or move a pin to {{ r.dayLabel }}</p>
              <input
                v-model="pickerQuery"
                type="text"
                class="field picker-filter"
                placeholder="Filter by title…"
                @click.stop
                @keydown.esc.stop.prevent="closePicker"
              />
              <p
                v-if="!pickerVisible(r.day.id).length"
                class="picker-empty mono"
              >No matches.</p>
              <template v-else>
                <p
                  v-if="pickerVisible(r.day.id, 'unattached').length"
                  class="picker-section mono"
                >Unattached</p>
                <ul v-if="pickerVisible(r.day.id, 'unattached').length" class="picker-list">
                  <li v-for="p in pickerVisible(r.day.id, 'unattached')" :key="p.id">
                    <button type="button" class="picker-item" @click.stop="pickAttach(r.day.id, p.id)">
                      <span class="day-pin-emoji">{{ pinEmoji(p) }}</span>
                      <span class="picker-item-title">{{ p.title }}</span>
                    </button>
                  </li>
                </ul>
                <p
                  v-if="pickerVisible(r.day.id, 'attached').length"
                  class="picker-section mono"
                >Already attached elsewhere</p>
                <ul v-if="pickerVisible(r.day.id, 'attached').length" class="picker-list">
                  <li v-for="p in pickerVisible(r.day.id, 'attached')" :key="p.id">
                    <button
                      type="button"
                      class="picker-item picker-item-attached"
                      :title="`Move from ${otherDayLabel(p) || 'another day'} to ${r.dayLabel}`"
                      @click.stop="pickAttach(r.day.id, p.id)"
                    >
                      <span class="day-pin-emoji">{{ pinEmoji(p) }}</span>
                      <span class="picker-item-title">{{ p.title }}</span>
                      <span class="picker-item-where mono">{{ otherDayLabel(p) }}</span>
                    </button>
                  </li>
                </ul>
              </template>
              <button type="button" class="picker-cancel mono" @click="closePicker">cancel</button>
            </template>
          </li>
        </ul>
        <div
          v-if="legShouldShow(r)"
          class="iti-leg mono"
          :class="{ 'is-short': isShortLeg(r) }"
          :title="r.legNext.title"
        >
          <template v-if="r.legNext.real">
            <template v-if="isShortLeg(r)">
              ↓ same area · {{ r.legNext.real.km }} km
            </template>
            <template v-else>
              ↓ {{ r.legNext.real.km.toLocaleString() }} km · {{ fmtMinutes(r.legNext.real.minutes) }}
              <span v-if="r.legNext.real.source === 'estimate'" class="leg-est">est</span>
            </template>
          </template>
          <template v-else>
            ↓ ≈ {{ r.legNext.km }} km
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
      @close="onTrailFinderClose"
      @pick="onTrailPick"
      @preview="(t) => $emit('trail-preview', t)"
    />
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import SunCalc from 'suncalc'
import { CATEGORIES, todayISO } from '@/util.js'
import { dailyForecast, hourlyForecast, glyphFor } from '@/lib/weather.js'
import { formatTime } from '@/lib/sun.js'
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
  'add', 'add-bulk', 'add-trail-pin', 'trail-preview', 'delete', 'go', 'edit',
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

// All titled pins, regardless of attachment — the picker shows both groups
// so the user can move a pin from one day to another in a single tap rather
// than the previous detach-then-reattach dance.
const pickerCandidatesAll = computed(() =>
  (props.points || []).filter((p) => p.title),
)

// Map day-id → display label so "Already attached elsewhere" rows can hint
// at the current owner. Falls back to date when there's no label.
const dayLabelById = computed(() => {
  const m = new Map()
  for (const d of props.days || []) m.set(d.id, d.label || d.date)
  return m
})
function otherDayLabel(pin) {
  if (pin.itinerary_day_id == null) return ''
  return dayLabelById.value.get(pin.itinerary_day_id) || ''
}

// Debounced filter — typed via picker-filter input, applied case-insensitively
// against pin titles. 100ms is enough to absorb a fast typist's keystrokes
// without making the list feel laggy.
const pickerQuery = ref('')
const pickerQueryDebounced = ref('')
let _pickerDebounce = null
watch(pickerQuery, (v) => {
  if (_pickerDebounce) clearTimeout(_pickerDebounce)
  _pickerDebounce = setTimeout(() => { pickerQueryDebounced.value = v }, 100)
})

function pickerVisible(currentDayId, group) {
  const q = pickerQueryDebounced.value.trim().toLowerCase()
  let pins = pickerCandidatesAll.value
  if (q) pins = pins.filter((p) => (p.title || '').toLowerCase().includes(q))
  // The picker is opened from a specific day — drop pins already attached to
  // *that* day from both groups (they're listed above the picker as removable
  // chips). Pins on other days fall into "attached", everything else into
  // "unattached".
  if (group === 'unattached') {
    return pins.filter((p) => p.itinerary_day_id == null)
  }
  if (group === 'attached') {
    return pins.filter((p) =>
      p.itinerary_day_id != null && p.itinerary_day_id !== currentDayId,
    )
  }
  // No group passed — used by template's "any matches?" check.
  return pins.filter((p) => p.itinerary_day_id !== currentDayId)
}

// Open-state: when set, that day's "attach" picker is open. Clicking outside
// or selecting a pin closes it.
const attachOpenForDay = ref(null)
function pickAttach(dayId, pointId) {
  // MapView's onAttachPoint just PATCHes itinerary_day_id, so the same call
  // path handles both first-time attach and reparent-from-another-day.
  emit('attach', { pointId, dayId })
  closePicker()
}
function closePicker() {
  attachOpenForDay.value = null
  pickerQuery.value = ''
  pickerQueryDebounced.value = ''
}
// Reset the filter when switching between days' pickers, so each fresh open
// starts empty.
watch(attachOpenForDay, (next) => {
  if (next == null) return
  pickerQuery.value = ''
  pickerQueryDebounced.value = ''
})

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
  emit('trail-preview', null)
  emit('add-trail-pin', t)
}
function onTrailFinderClose() {
  trailFor.value = null
  // Closing the modal must also clear the hover preview line on the map.
  emit('trail-preview', null)
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

// Per-stop sunrise/sunset (string "HH:MM → HH:MM" in solar time at the stop's
// longitude) and a "best 3-hour morning slot" from hourly weather. Both are
// loaded lazily so the row paints immediately and the chip appears as data
// arrives.
const sunMap = computed(() => {
  const out = {}
  for (const d of props.days) {
    if (d.id == null || d.lat == null || d.lng == null) continue
    const t = SunCalc.getTimes(new Date(d.date + 'T12:00:00Z'), d.lat, d.lng)
    if (!t.sunrise || !t.sunset || isNaN(t.sunrise) || isNaN(t.sunset)) continue
    out[d.id] = `${formatTime(t.sunrise, d.lng)} → ${formatTime(t.sunset, d.lng)}`
  }
  return out
})

const morningMap = ref({}) // day.id → "best run window" string ("06–08 · 12°")
async function refreshMorningHours(days) {
  for (const d of days) {
    if (d.id == null || d.lat == null || d.lng == null) continue
    if (morningMap.value[d.id]) continue
    const hours = await hourlyForecast(d.lat, d.lng, d.date)
    if (!hours.length) continue
    const morning = hours.filter((h) => h.hour >= 5 && h.hour <= 11)
    if (morning.length < 3) continue
    let best = null
    for (let i = 0; i <= morning.length - 3; i++) {
      const slot = morning.slice(i, i + 3)
      const meanTemp = slot.reduce((s, h) => s + h.temp, 0) / 3
      const meanRain = slot.reduce((s, h) => s + (h.rainPct || 0), 0) / 3
      const score = Math.abs(meanTemp - 14) + Math.min(meanRain, 60) * 0.5
      if (!best || score < best.score) {
        best = { startHour: slot[0].hour, endHour: slot[2].hour + 1, meanTemp: Math.round(meanTemp), score }
      }
    }
    if (best) {
      const startStr = String(best.startHour).padStart(2, '0')
      const endStr = String(best.endHour).padStart(2, '0')
      morningMap.value = {
        ...morningMap.value,
        [d.id]: `${startStr}–${endStr} · ${best.meanTemp}°`,
      }
    }
  }
}
watch(() => props.days, (next) => { refreshMorningHours(next || []) }, { immediate: true })
function bestMorning(d) { return morningMap.value[d.id] || null }
function sunFor(d) { return sunMap.value[d.id] || null }

// Photo journal: parse the JSON-encoded array on demand. Cached per (id, raw)
// so we don't re-parse on every keystroke when notes change.
const photoCache = new Map()
function parsePhotos(d) {
  if (!d.photos) return []
  const cacheKey = `${d.id}:${d.photos.length}`
  if (photoCache.has(cacheKey)) return photoCache.get(cacheKey)
  try {
    const parsed = JSON.parse(d.photos)
    const arr = Array.isArray(parsed) ? parsed.filter((u) => typeof u === 'string') : []
    photoCache.set(cacheKey, arr)
    return arr
  } catch {
    return []
  }
}
function photoCount(d) { return parsePhotos(d).length }
function photoThumbs(d) { return parsePhotos(d).slice(0, 4) }

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
//   weekHeader/weekNum/weekRange: set on the first row of each new trip-week
//     so the template can render a quiet "Week 1 / 9–15 May" divider above
//     the row. Trip-week is anchored on the first stop's date, not ISO weeks,
//     so the trip's first week starts on day 1 regardless of weekday.
const rows = computed(() => {
  const sorted = [...props.days].sort((a, b) => a.date.localeCompare(b.date))
  if (!sorted.length) return []
  const tripStart = new Date(sorted[0].date)
  const out = []
  let cumulative = 0
  let lastWeekNum = 0
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
    const dayOffset = Math.floor((new Date(day.date) - tripStart) / 86400000)
    const weekNum = Math.floor(dayOffset / 7) + 1
    const weekHeader = weekNum !== lastWeekNum
    let weekRange = ''
    if (weekHeader) {
      const weekStart = new Date(tripStart)
      weekStart.setUTCDate(weekStart.getUTCDate() + (weekNum - 1) * 7)
      const weekEnd = new Date(weekStart)
      weekEnd.setUTCDate(weekEnd.getUTCDate() + 6)
      weekRange = `${weekStart.getUTCDate()}–${weekEnd.getUTCDate()} ${shortMonth(weekEnd.toISOString().slice(0, 10))}`
      lastWeekNum = weekNum
    }
    out.push({ day, dayLabel, spanISO, cleanLabel, legNext, weekHeader, weekNum, weekRange })
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
  // No confirm() — MapView handles a 5s undo toast instead. Keeps deletes
  // single-tap-recoverable and consistent with pin delete UX.
  emit('delete', d)
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

// "Short" = under 5 km, e.g. Mather Campground (36.05) → BLM (36.10) at the
// Grand Canyon. These aren't really driving "legs" — flag visually so the
// trip reads as one extended stop, not two punctuated days.
function isShortLeg(row) {
  const km = row.legNext?.real?.km ?? row.legNext?.km
  return km != null && km < 5
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
  gap: 0.25rem;
}
.iti-week-sep {
  margin: 0.5rem 0 0.1rem;
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.iti-week-sep::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--cream-edge);
}
.iti-week-sep .week-meta { color: var(--ink-faded); opacity: 0.8; }
.iti-list > .iti-week-sep:first-child { margin-top: 0; }
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
.iti-leg.is-short {
  opacity: 0.55;
  font-style: italic;
  letter-spacing: 0.06em;
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
.picker-item-attached {
  /* Slightly faded so the unattached group reads as the primary action,
     while still being one click to reparent. */
  grid-template-columns: auto 1fr auto;
  opacity: 0.85;
}
.picker-item-attached:hover { opacity: 1; }
.picker-item-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.picker-item-where {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 8rem;
}
.picker-section {
  margin: 0.15rem 0 0;
  font-size: 0.58rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.picker-filter {
  font-size: 0.85rem;
  padding: 0.25rem 0.4rem;
  width: 100%;
}
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
.iti-sun {
  margin: 0.05rem 0 0;
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.06em;
}
.iti-day.today .iti-sun { color: rgba(255,255,255,0.75); }
.iti-run {
  display: inline-block;
  margin-left: 0.4rem;
  padding: 0.02rem 0.35rem;
  font-size: 0.66rem;
  letter-spacing: 0.06em;
  color: var(--vermillion);
  background: var(--paper);
  border: 1px dotted var(--cream-edge);
  border-radius: 2px;
}
.iti-day.today .iti-run {
  color: var(--paper);
  border-color: rgba(255,255,255,0.5);
  background: var(--vermillion-deep);
}

.iti-photo-strip {
  list-style: none;
  margin: 0.3rem 0 0;
  padding: 0;
  display: flex;
  gap: 0.2rem;
  align-items: center;
}
.iti-photo {
  width: 36px;
  height: 36px;
  border-radius: 3px;
  overflow: hidden;
  border: 1px solid var(--cream-edge);
}
.iti-photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.iti-photo-more {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  color: var(--ink-faded);
  margin-left: 0.2rem;
}
.iti-day.today .iti-photo-more { color: rgba(255,255,255,0.8); }

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
