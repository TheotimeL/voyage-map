<template>
  <main class="plan paper">
    <header class="plan-head">
      <div class="plan-head-row">
        <div class="plan-title-wrap">
          <p class="plan-eyebrow mono">Trip planner</p>
          <input
            class="plan-title"
            v-model="titleDraft"
            placeholder="Untitled voyage"
            maxlength="120"
            @blur="emit('update:title', titleDraft)"
            @keydown.enter="$event.target.blur()"
          />
          <p
            v-if="metaLine"
            class="plan-meta mono"
            title="Days planned = calendar span (start → end). Scheduled = days that actually have a stop assigned."
          >{{ metaLine }}</p>
        </div>
        <div class="plan-head-actions">
          <slot name="mode-toggle" />
          <slot name="head-tools" />
        </div>
      </div>
    </header>

    <section class="plan-stops">
      <div class="plan-stops-head">
        <h2 class="plan-h2">Stops</h2>
      </div>

      <div v-if="!rows.length" class="plan-empty">
        <p class="mono">No stops yet — start your trip</p>
        <form class="empty-form" @submit.prevent="addEmptyStop">
          <input
            v-model="addDate"
            type="date"
            class="field add-date"
            required
          />
          <button class="btn btn-tiny" type="submit">+ Begin trip</button>
        </form>
      </div>

      <table v-else class="plan-table" :class="{ 'is-dragging': dragSourceId != null || dragPinId != null }">
        <thead>
          <tr>
            <th class="c-grip" aria-hidden="true"></th>
            <th class="c-date">Date</th>
            <th class="c-day">D</th>
            <th class="c-place">Stop</th>
            <th class="c-location">Location</th>
            <th class="c-sleep">Sleep</th>
            <th class="c-wx">Wx</th>
            <th class="c-notes">Notes</th>
            <th class="c-leg">Drive</th>
            <th class="c-act"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="r in rows" :key="r.key">
            <tr v-if="r.weekHeader" class="plan-week">
              <td colspan="9">
                <span class="week-tag mono">Week {{ r.weekNum }}</span>
                <span class="week-meta mono">{{ r.weekRange }}</span>
                <span v-if="r.weekSummary" class="week-summary mono">{{ r.weekSummary }}</span>
              </td>
            </tr>
            <tr
              v-if="r.isGhost"
              class="plan-row plan-ghost"
              :class="{ 'drop-target': dropTargetKey === r.key }"
              @dragover.prevent="onGhostDragOver(r, $event)"
              @dragleave="onRowDragLeave(r)"
              @drop.prevent="onGhostDrop(r)"
            >
              <td class="c-grip" aria-hidden="true"></td>
              <td class="c-date">
                <div class="date-cell ghost-date">
                  <span class="d-dow mono">{{ r.dow }}</span>
                  <span class="d-num">{{ r.dayNum }}</span>
                  <span class="d-mon mono">{{ r.mon }}</span>
                </div>
              </td>
              <td class="c-day mono">—</td>
              <td class="c-place ghost-place" colspan="7">
                <button class="ghost-add mono" type="button" @click="addStopOnDate(r.date)">
                  + add stop on {{ r.dayNum }} {{ r.mon }}
                </button>
              </td>
              <td class="c-act"></td>
            </tr>
            <tr
              v-else-if="r.isPin"
              class="plan-row plan-pin-row"
              @click="emit('edit-pin', r.pin)"
            >
              <td class="c-grip"></td>
              <td class="c-date pin-indent" colspan="2">
                <span class="pin-row-arrow mono" aria-hidden="true">↳</span>
                <span class="pin-row-emoji">{{ pinEmoji(r.pin) }}</span>
              </td>
              <td class="c-place pin-name">
                <span class="pin-row-title">{{ r.pin.title || 'Untitled pin' }}</span>
                <span v-if="r.pin.comment" class="pin-row-comment mono">— {{ markdownExcerpt(r.pin.comment, 60) }}</span>
              </td>
              <td class="c-location" colspan="5"></td>
              <td class="c-act">
                <button
                  class="iti-icon"
                  type="button"
                  title="Detach from this stop"
                  aria-label="Detach pin"
                  @click.stop="emit('detach-pin', r.pin.id)"
                >−</button>
              </td>
            </tr>
            <tr
              v-else
              class="plan-row"
              :class="{
                today: r.isToday,
                past: r.isPast,
                future: r.isFuture,
                'is-selected': selectedDayId === r.day.id,
                'is-dragged': dragSourceId === r.day.id,
                'drop-target': dropTargetKey === r.key,
              }"
              @dragover.prevent="onRowDragOver(r, $event)"
              @dragleave="onRowDragLeave(r)"
              @drop.prevent="onRowDrop(r)"
            >
              <td class="c-grip">
                <span
                  v-if="!r.isContinuation"
                  class="grip"
                  draggable="true"
                  :title="`Drag to reorder ${r.cleanLabel || r.day.label || 'this stop'}`"
                  aria-label="Drag to reorder"
                  role="button"
                  @dragstart="onRowDragStart(r, $event)"
                  @dragend="onRowDragEnd"
                >⋮</span>
              </td>
              <td class="c-date">
                <label class="date-cell" :title="`Click to change date`">
                  <input
                    type="date"
                    class="date-cell-input themed-date"
                    :value="r.dayDate"
                    :min="firstISO"
                    :max="lastISO"
                    @change="onDayDateChange(r, $event.target.value)"
                  />
                  <span class="d-inline mono"><span class="d-dow">{{ r.dow }}</span> <span class="d-num">{{ r.dayNum }}</span> <span class="d-mon">{{ r.mon }}</span></span>
                </label>
              </td>
              <td class="c-day mono">{{ r.dayLabel }}</td>
              <td class="c-place">
                <div class="place-cell">
                  <input
                    class="cell-input cell-name"
                    :value="r.cleanLabel || r.day.label || ''"
                    :placeholder="r.day.lat == null ? 'Untitled stop' : 'Name…'"
                    @blur="onLabelBlur(r.day, $event.target.value)"
                    @keydown.enter="$event.target.blur()"
                  />
                  <button
                    v-if="!r.isContinuation && (pinsByDay.get(r.day.id) || []).length"
                    class="pin-toggle mono"
                    type="button"
                    :title="(pinExpanded.has(r.day.id) ? 'Hide pins' : 'Show pins')"
                    @click.stop="togglePinExpand(r.day.id)"
                  >{{ pinExpanded.has(r.day.id) ? '▾' : '▸' }} {{ (pinsByDay.get(r.day.id) || []).length }}</button>
                  <button
                    v-if="!r.isContinuation"
                    class="pin-toggle pin-add mono"
                    type="button"
                    :class="{ on: popoverFor === r.day.id }"
                    title="Add a pin to this stop"
                    @click.stop="togglePopover(r.day.id)"
                  >+</button>
                </div>
                <div v-if="!r.isContinuation && popoverFor === r.day.id" class="popover-anchor">
                  <DayAddPinPopover
                    :day="r.day"
                    :day-label="r.day.label || r.dayLabel"
                    :all-points="points"
                    :days="days"
                    :bias="bias"
                    @close="popoverFor = null"
                    @add-new="onAddPinNew(r.day, $event)"
                    @attach="onAttachPin(r.day, $event)"
                  />
                </div>
                <button
                  v-if="!r.isContinuation"
                  class="row-insert above mono"
                  type="button"
                  title="Insert a new stop above"
                  aria-label="Insert a new stop above this row"
                  @click.stop="insertAbove(r)"
                >+</button>
                <span
                  v-if="!r.isContinuation"
                  class="row-insert below"
                  :title="`Add the next day — choose new stop or extend ${r.cleanLabel || r.day.label || 'this stop'}`"
                >
                  <button
                    type="button"
                    class="row-insert-btn extend mono"
                    title="Extend this stop by one day"
                    aria-label="Extend stop"
                    @click.stop="extendBelow(r)"
                  >↪</button>
                  <button
                    type="button"
                    class="row-insert-btn new mono"
                    title="Insert a new stop below"
                    aria-label="Insert a new stop below"
                    @click.stop="insertBelow(r)"
                  >+</button>
                </span>
              </td>
              <td class="c-location">
                <button
                  type="button"
                  class="cell-location"
                  :class="{ on: locationPopoverFor === r.day.id, missing: r.day.lat == null }"
                  :title="r.day.lat == null ? 'Set the location' : (placeNameFor(r.day) || 'Change the location')"
                  @click.stop="toggleLocationPopover(r.day.id)"
                >{{ r.day.lat != null ? (placeNameFor(r.day) || `${formatLat(r.day.lat)} · ${formatLng(r.day.lng)}`) : '—' }}</button>
                <div v-if="locationPopoverFor === r.day.id" class="popover-anchor">
                  <div class="loc-popover paper" @click.stop>
                    <p class="dap-eyebrow mono">Set the location</p>
                    <GeocoderSearch
                      placeholder="Search a town, viewpoint, campground…"
                      :bias="bias"
                      @pick="onLocationPick(r.day, $event)"
                    />
                    <button type="button" class="loc-popover-close mono" @click="locationPopoverFor = null">cancel</button>
                  </div>
                </div>
              </td>
              <td class="c-sleep">
                <input
                  class="cell-input"
                  :value="r.day.sleep_location || ''"
                  placeholder="—"
                  maxlength="200"
                  :title="r.day.sleep_location || 'Where you sleep that night (free text)'"
                  @blur="onSleepBlur(r.day, $event.target.value)"
                  @keydown.enter="$event.target.blur()"
                />
              </td>
              <td class="c-wx mono">
                <span
                  v-if="r.wxForDay && r.wxForDay.forecast"
                  class="wx-chip"
                  :title="`${r.wxForDay.date} forecast`"
                >{{ glyphFor(r.wxForDay.forecast.code) }} {{ formatTempValue(r.wxForDay.forecast.tMax) }}°/{{ formatTempValue(r.wxForDay.forecast.tMin) }}°</span>
                <span v-else-if="r.wxForDay && r.wxForDay.tooFarDays != null" class="wx-faded">+{{ r.wxForDay.tooFarDays }}d</span>
                <span v-else class="wx-faded">—</span>
              </td>
              <td class="c-notes">
                <button
                  type="button"
                  class="cell-notes-display"
                  :class="{ 'is-empty': !r.day.notes }"
                  :title="r.day.notes ? 'Open journal' : 'Add a journal entry'"
                  @click="emit('edit-day', r.day)"
                >{{ r.day.notes ? markdownExcerpt(r.day.notes, 60) : '—' }}</button>
              </td>
              <td class="c-leg mono">
                <template v-if="r.legNext && r.legNext.real">
                  <span class="leg-cell" :class="{ 'is-short': r.legNext.real.km < 5, 'is-long': r.legNext.real.minutes >= 180 || r.legNext.real.km >= 250 }">{{ formatDistance(r.legNext.real.km) }} · {{ fmtMinutesTight(r.legNext.real.minutes) }}</span>
                </template>
                <span v-else-if="r.legNext" class="leg-faded">≈ {{ formatDistance(r.legNext.km) }}</span>
                <span v-else class="leg-faded">—</span>
              </td>
              <td class="c-act">
                <button
                  v-if="!r.isContinuation && pendingDeleteId !== r.day.id"
                  class="iti-icon"
                  type="button"
                  title="Remove this stop"
                  aria-label="Remove this stop"
                  @click="armDelete(r.day)"
                >×</button>
                <button
                  v-else-if="!r.isContinuation"
                  class="iti-icon iti-icon-confirm mono"
                  type="button"
                  title="Click again to confirm"
                  @click="confirmDelete(r.day)"
                >×?</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </section>

    <section class="plan-pins">
      <div class="plan-pins-head">
        <h2 class="plan-h2">Wishlist</h2>
        <div class="plan-pins-controls">
          <div class="seg mono">
            <button
              type="button"
              class="seg-btn"
              :class="{ on: !showAllPins }"
              @click="showAllPins = false"
            >Unplanned <span class="seg-count">{{ unattachedPoints.length }}</span></button>
            <button
              type="button"
              class="seg-btn"
              :class="{ on: showAllPins }"
              @click="showAllPins = true"
            >All <span class="seg-count">{{ points.length }}</span></button>
          </div>
        </div>
      </div>
      <CategoryFilters :points="filteredPool" :hidden="hiddenCats" @toggle="toggleCat" @reset="resetCats" />
      <div v-if="visiblePins.length" class="pins-grid">
        <article
          v-for="p in visiblePins"
          :key="p.id"
          class="pin-card"
          :class="{ 'is-trail': !!p.gpx_data, 'is-dragged': dragPinId === p.id }"
          :style="p.gpx_data && p.color ? { '--swatch': p.color } : null"
          draggable="true"
          @dragstart="onPinDragStart(p, $event)"
          @dragend="onPinDragEnd"
          @click="emit('edit-pin', p)"
        >
          <button
            class="pin-card-del"
            type="button"
            :title="`Delete this pin`"
            aria-label="Delete pin"
            @click.stop="emit('delete-pin', p)"
          >×</button>
          <div class="pin-card-top">
            <span class="pin-card-emoji">{{ pinEmoji(p) }}</span>
            <strong class="pin-card-title">{{ p.title || 'Untitled' }}</strong>
            <span v-if="p.itinerary_day_id != null" class="pin-card-attached mono" :title="dayLabelById.get(p.itinerary_day_id) || ''">
              ↳ {{ shortDayLabel(p.itinerary_day_id) }}
            </span>
          </div>
          <p v-if="p.comment" class="pin-card-comment">{{ p.comment }}</p>
          <p class="pin-card-meta mono">
            <span v-if="trailStats(p)" class="pin-card-trail">{{ formatDistance(trailStats(p).km) }}<template v-if="trailStats(p).gain != null"> · D+ {{ trailStats(p).gain }} m</template></span>
            <span class="pin-card-coord">{{ formatLat(p.lat) }} · {{ formatLng(p.lng) }}</span>
          </p>
          <div v-if="p.itinerary_day_id != null" class="pin-card-actions">
            <button
              type="button"
              class="pin-card-detach mono"
              :title="`Detach from ${dayLabelById.get(p.itinerary_day_id) || 'its stop'}`"
              @click.stop="emit('detach-pin', p.id)"
            >− detach</button>
          </div>
        </article>
      </div>
      <div v-else class="plan-empty mono">
        <template v-if="!points.length">No pins yet — go to Map mode and drop one, or use a stop's "+ pin" above.</template>
        <template v-else>No pins match these filters.</template>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { CATEGORIES, formatLat, formatLng, parseGPX, todayISO, markdownExcerpt } from '@/util.js'
import { buildElevationSeries, elevationStats } from '@/lib/elevation.js'
import { fmtMinutes, routeLeg } from '@/lib/routing.js'
import { dailyForecast, glyphFor } from '@/lib/weather.js'
import { formatDistance, formatTempValue } from '@/lib/settings.js'
import { reverseGeocodeLabel, geocode as forwardGeocode } from '@/api.js'
import GeocoderSearch from '../molecules/GeocoderSearch.vue'
import CategoryFilters from '../molecules/CategoryFilters.vue'
import DayAddPinPopover from './DayAddPinPopover.vue'

const props = defineProps({
  title: { type: String, default: '' },
  days: { type: Array, default: () => [] },
  points: { type: Array, default: () => [] },
  bias: { type: Object, default: null },
})
const emit = defineEmits([
  'update:title',
  'add-day', 'delete-day', 'patch-day', 'edit-day',
  'add-pin', 'attach-pin', 'detach-pin', 'edit-pin', 'delete-pin',
  'schedule-pin',
  'open-paste',
])

const titleDraft = ref(props.title || '')
watch(() => props.title, (v) => { titleDraft.value = v || '' })

// Two-tap stop delete: first click on × turns the button into a "Delete?"
// confirm pill; a second click within ~4s commits (which then runs through
// MapView's 5s soft-delete toast for a final undo). Without the confirm
// step a single misclick on a tightly-packed row was wiping notes/pins.
const pendingDeleteId = ref(null)
let _pendingDeleteTimer = null
function armDelete(day) {
  if (_pendingDeleteTimer) clearTimeout(_pendingDeleteTimer)
  pendingDeleteId.value = day.id
  _pendingDeleteTimer = setTimeout(() => {
    pendingDeleteId.value = null
    _pendingDeleteTimer = null
  }, 4000)
}
function confirmDelete(day) {
  if (_pendingDeleteTimer) { clearTimeout(_pendingDeleteTimer); _pendingDeleteTimer = null }
  pendingDeleteId.value = null
  emit('delete-day', day)
}

const today = computed(() => todayISO())
const emojiByCategory = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function pinEmoji(p) { return p?.gpx_data ? '🥾' : (emojiByCategory[p?.category] || '📍') }

// Pins by day for inline chip rendering on each row.
const pinsByDay = computed(() => {
  const map = new Map()
  for (const p of props.points || []) {
    if (p.itinerary_day_id == null) continue
    const arr = map.get(p.itinerary_day_id) || []
    arr.push(p)
    map.set(p.itinerary_day_id, arr)
  }
  return map
})
const unattachedPoints = computed(() => (props.points || []).filter((p) => p.itinerary_day_id == null))

const dayLabelById = computed(() => {
  const m = new Map()
  for (const d of props.days || []) m.set(d.id, d.label || d.date)
  return m
})
function shortDayLabel(id) {
  const lbl = dayLabelById.value.get(id) || ''
  return lbl.length > 24 ? lbl.slice(0, 22) + '…' : lbl
}

// Wishlist filtering: Unplanned vs All, plus category chips.
const showAllPins = ref(false)
const hiddenCats = ref(new Set())
function toggleCat(key) {
  const s = new Set(hiddenCats.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  hiddenCats.value = s
}
function resetCats() { hiddenCats.value = new Set() }
const filteredPool = computed(() => showAllPins.value ? (props.points || []) : unattachedPoints.value)
const visiblePins = computed(() => {
  if (hiddenCats.value.size === 0) return filteredPool.value
  return filteredPool.value.filter((p) => !hiddenCats.value.has(p.category))
})

// "Add a stop" disclosure — auto-open when the trip is empty. The FAB in
// MapView calls openAddRow() to surface this same disclosure from Map mode
// (the dock-era selectors are gone).
const addOpen = ref(false)
watch(() => props.days?.length, (n) => { if (!n) addOpen.value = true }, { immediate: true })

async function openAddRow({ focus = 'date' } = {}) {
  addOpen.value = true
  await nextTick()
  const sel = focus === 'search'
    ? '.add-row .geo input.field'
    : '.add-row .add-date'
  const el = document.querySelector(sel) || document.querySelector('.add-row .add-date')
  el?.focus()
  el?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}
defineExpose({ openAddRow })

const addDate = ref(today.value)
function endOf(d) { return d.end_date || d.date }
function nextDateAfter(iso) {
  const d = new Date(iso)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
const suggestedNewDate = computed(() => {
  if (!props.days.length) return today.value
  const last = [...props.days].sort((a, b) => a.date.localeCompare(b.date)).at(-1)
  return nextDateAfter(endOf(last))
})
watch(suggestedNewDate, (d) => { addDate.value = d }, { immediate: true })

const firstISO = computed(() => {
  if (!props.days.length) return today.value
  return [...props.days].sort((a, b) => a.date.localeCompare(b.date))[0].date
})
const lastISO = computed(() => {
  if (!props.days.length) return ''
  const latest = [...props.days].sort((a, b) => endOf(a).localeCompare(endOf(b))).at(-1)
  const d = new Date(endOf(latest))
  d.setUTCDate(d.getUTCDate() + 30)
  return d.toISOString().slice(0, 10)
})

function addEmptyStop() {
  if (!addDate.value) return
  emit('add-day', { date: addDate.value, label: null })
  addDate.value = nextDateAfter(addDate.value)
}
function onAddSearchPick(result) {
  if (!addDate.value) return
  const label = (result.label || '').split(',')[0].trim().slice(0, 200) || null
  emit('add-day', { date: addDate.value, label, lat: result.lat, lng: result.lng })
  addDate.value = nextDateAfter(addDate.value)
  addOpen.value = false
}

// "+" pin popover anchored to a row.
const popoverFor = ref(null)
const selectedDayId = computed(() => popoverFor.value)
function togglePopover(id) {
  popoverFor.value = popoverFor.value === id ? null : id
}

// Expand/collapse pin sub-rows under each stop. Set of day ids whose pins
// are currently shown as indented child rows.
const pinExpanded = ref(new Set())
function togglePinExpand(id) {
  const next = new Set(pinExpanded.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  pinExpanded.value = next
}
function onAddPinNew(day, payload) {
  emit('add-pin', { dayId: day.id, ...payload })
  popoverFor.value = null
}
function onAttachPin(day, { pointId }) {
  emit('attach-pin', { pointId, dayId: day.id })
  popoverFor.value = null
}

// Inline date edits — clicking the date cell triggers a native date picker
// (the input is overlayed, transparent). Changing the start date preserves the
// span, shifting end_date by the same delta. End date has its own popover.
const endPickerFor = ref(null)
function onDateChange(day, newDate) {
  if (!newDate || newDate === day.date) return
  let payload = { date: newDate }
  if (day.end_date) {
    const delta = (new Date(newDate) - new Date(day.date)) / 86400000
    const newEnd = new Date(day.end_date)
    newEnd.setUTCDate(newEnd.getUTCDate() + delta)
    payload.end_date = newEnd.toISOString().slice(0, 10)
  }
  emit('patch-day', { day, payload })
}
function openEndPicker(day) {
  endPickerFor.value = day.id
  // Native picker pops on focus + click — defer focus so the input mounts first.
  setTimeout(() => {
    const el = document.querySelector('input.end-picker')
    if (el) { el.focus(); el.showPicker?.() }
  }, 0)
}
function onEndDateChange(day, newEnd) {
  endPickerFor.value = null
  if (!newEnd) return
  const payload = { end_date: newEnd === day.date ? null : newEnd }
  emit('patch-day', { day, payload })
}

// Compact "5h27" form for the drive column — saves a wrap when the column is
// narrow. Falls back to fmtMinutes for the few minute-only legs.
function fmtMinutesTight(min) {
  return fmtMinutes(min).replace(/\s+/g, '')
}

// Reverse-geocoded place name per day id. Lazy + cached, fed lat/lng changes.
// Used by the "Stop" cell's italic subtitle so the user sees a real-place
// hint without typing it ("Las Vegas, NV").
const placeNames = ref({})
function placeNameFor(day) { return placeNames.value[day.id] || '' }
async function refreshPlaceNames(days) {
  for (const d of days) {
    if (d.id == null || d.lat == null || d.lng == null) continue
    if (placeNames.value[d.id]) continue
    const name = await reverseGeocodeLabel(d.lat, d.lng)
    if (name) placeNames.value = { ...placeNames.value, [d.id]: name }
  }
}
watch(() => props.days, (next) => refreshPlaceNames(next || []), { immediate: true, deep: true })

// Inline "Set location" popover state — separate from the pin popover.
const locationPopoverFor = ref(null)
function toggleLocationPopover(id) {
  locationPopoverFor.value = locationPopoverFor.value === id ? null : id
  // Mutually exclusive with the pin popover so the row doesn't render two
  // overlapping panels.
  if (locationPopoverFor.value != null) popoverFor.value = null
}
function onLocationPick(day, result) {
  emit('patch-day', { day, payload: { lat: result.lat, lng: result.lng } })
  // Seed the cache with the picked result's full label — that's what the user
  // just selected, so it should be the displayed location text. (Otherwise we
  // 'd display the old reverse-geocode name until the next refresh.)
  if (result.label) {
    placeNames.value = { ...placeNames.value, [day.id]: result.label }
  } else if (placeNames.value[day.id]) {
    const next = { ...placeNames.value }
    delete next[day.id]
    placeNames.value = next
  }
  locationPopoverFor.value = null
}

// Click-outside handler — closes both popovers when the user taps elsewhere.
function onDocClick(e) {
  if (popoverFor.value == null && locationPopoverFor.value == null) return
  const inside = e.target.closest?.('.popover-anchor, .add-pin-btn, .loc-btn, .cell-location, .pin-add')
  if (!inside) { popoverFor.value = null; locationPopoverFor.value = null }
}
import { onMounted, onBeforeUnmount } from 'vue'
onMounted(() => document.addEventListener('click', onDocClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))

// Inline label / notes edits — only patch when the value actually changed.
// Side effect: when the stop has no coords yet, forward-geocode the label
// and set lat/lng from the first result. User can override via the Location
// column popover. We don't re-geocode on subsequent label edits — that would
// surprise the user by moving their pin every time they tweak the name.
async function onLabelBlur(day, value) {
  const next = (value || '').trim()
  const current = (day.label || '').trim()
  if (next === current) return
  emit('patch-day', { day, payload: { label: next || null } })
  if (next && day.lat == null) {
    try {
      const results = await forwardGeocode(next, props.bias)
      if (results && results.length > 0) {
        const top = results[0]
        emit('patch-day', { day, payload: { lat: top.lat, lng: top.lng } })
        // Seed the location-display cache so the Location column shows the
        // full geocoded label immediately (no second round-trip to reverse).
        if (top.label) placeNames.value = { ...placeNames.value, [day.id]: top.label }
      }
    } catch (_) { /* silent — user can pick manually from Location popover */ }
  }
}
function onSleepBlur(day, value) {
  const next = (value || '').trim()
  const current = (day.sleep_location || '').trim()
  if (next === current) return
  emit('patch-day', { day, payload: { sleep_location: next || null } })
}

// Hover-row insertion. The new stop's date is suggested from the neighbour:
// "above" = day before this row's start; "below" = day after this row's end.
// If the suggested date overlaps an existing stop, the API responds 409 and
// MapView surfaces an error toast — the user can then pick another date via
// the top "+ Add stop" panel.
function insertAbove(row) {
  if (!row?.day) return
  const iso = shiftDate(row.day.date, -1)
  emit('add-day', { date: iso, label: null })
}
function insertBelow(row) {
  if (!row?.day) return
  const iso = shiftDate(endOf(row.day), 1)
  emit('add-day', { date: iso, label: null })
}
// Extend the stop's span by one day instead of creating a new neighbour stop.
// Used by the "↪" button next to "+" in the row's below-hover affordance.
function extendBelow(row) {
  if (!row?.day) return
  const newEnd = shiftDate(endOf(row.day), 1)
  emit('patch-day', { day: row.day, payload: { end_date: newEnd } })
}
// Date edit on any day-row, including continuations. Editing a continuation
// date shifts the whole stop by the same delta (so the chosen day lands on
// the new date). This keeps the span intact.
function onDayDateChange(row, newDate) {
  if (!newDate || !row?.day) return
  if (newDate === row.dayDate) return
  const delta = Math.round((new Date(newDate) - new Date(row.dayDate)) / 86400000)
  if (!delta) return
  const payload = { date: shiftDate(row.day.date, delta) }
  if (row.day.end_date) payload.end_date = shiftDate(row.day.end_date, delta)
  emit('patch-day', { day: row.day, payload })
}
// Notes cell: read-only excerpt that opens the day modal (full markdown
// editor) on click. The plan table stays scannable; rich notes/photos live
// in the modal so they don't tax the row layout.

// Mobile collapse: each row starts collapsed (slim summary) on small viewports.
// Tap the chevron — or anywhere on the date column — to expand. The set is
// shared with desktop but harmless there since the CSS only listens to it
// inside the @media block.
const mobileExpanded = ref(new Set())
function toggleMobileExpand(id) {
  const next = new Set(mobileExpanded.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  mobileExpanded.value = next
}

// Ghost rows + drag-to-reorder ------------------------------------------------
// The native HTML5 drag API only fires drag events on elements with
// draggable=true. We bind that to the row only while a grip is held — letting
// inputs inside the row stay clickable/selectable normally. A second drag
// source — `.pin-card` from the wishlist — sets `dragPinId` instead and the
// drop handlers branch on which one is set.
const dragSourceId = ref(null)
const dragPinId = ref(null)
const dropTargetKey = ref(null)
function onRowDragStart(r, e) {
  if (r.isGhost) return
  dragSourceId.value = r.day.id
  dragPinId.value = null
  e.dataTransfer.effectAllowed = 'move'
  // Required for Firefox to fire dragstart at all.
  try { e.dataTransfer.setData('text/plain', `row:${r.day.id}`) } catch {}
}
function onRowDragEnd() {
  dragSourceId.value = null
  dropTargetKey.value = null
}
function onPinDragStart(p, e) {
  dragPinId.value = p.id
  dragSourceId.value = null
  e.dataTransfer.effectAllowed = 'move'
  try { e.dataTransfer.setData('text/plain', `pin:${p.id}`) } catch {}
}
function onPinDragEnd() {
  dragPinId.value = null
  dropTargetKey.value = null
}
function onRowDragOver(r, e) {
  if (dragSourceId.value == null && dragPinId.value == null) return
  if (dragSourceId.value != null && r.day.id === dragSourceId.value) return
  e.dataTransfer.dropEffect = 'move'
  dropTargetKey.value = r.key
}
function onGhostDragOver(r, e) {
  if (dragSourceId.value == null && dragPinId.value == null) return
  e.dataTransfer.dropEffect = 'move'
  dropTargetKey.value = r.key
}
function onRowDragLeave(r) {
  if (dropTargetKey.value === r.key) dropTargetKey.value = null
}
function shiftDate(iso, deltaDays) {
  const d = new Date(iso)
  d.setUTCDate(d.getUTCDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}
function onRowDrop(targetRow) {
  const srcId = dragSourceId.value
  const pinId = dragPinId.value
  dragSourceId.value = null
  dragPinId.value = null
  dropTargetKey.value = null
  // Wishlist pin → existing stop row: attach.
  if (pinId != null) {
    emit('attach-pin', { pointId: pinId, dayId: targetRow.day.id })
    return
  }
  if (srcId == null || targetRow.day.id === srcId) return
  const src = (props.days || []).find((d) => d.id === srcId)
  const tgt = targetRow.day
  if (!src || !tgt) return
  // Swap start dates between the two stops; preserve each stop's span by
  // shifting end_date along by the same delta. Multi-day overlaps after the
  // swap are the user's call — they can fine-tune from there.
  const srcSpan = src.end_date ? Math.round((new Date(src.end_date) - new Date(src.date)) / 86400000) : 0
  const tgtSpan = tgt.end_date ? Math.round((new Date(tgt.end_date) - new Date(tgt.date)) / 86400000) : 0
  const srcPayload = { date: tgt.date, end_date: srcSpan ? shiftDate(tgt.date, srcSpan) : null }
  const tgtPayload = { date: src.date, end_date: tgtSpan ? shiftDate(src.date, tgtSpan) : null }
  emit('patch-day', { day: src, payload: srcPayload })
  emit('patch-day', { day: tgt, payload: tgtPayload })
}
function onGhostDrop(ghostRow) {
  const srcId = dragSourceId.value
  const pinId = dragPinId.value
  dragSourceId.value = null
  dragPinId.value = null
  dropTargetKey.value = null
  // Wishlist pin → empty date: ask MapView to create a stop on that date
  // anchored to the pin's coords + label, and attach the pin to it.
  if (pinId != null) {
    const pin = (props.points || []).find((p) => p.id === pinId)
    if (!pin) return
    emit('schedule-pin', { pointId: pin.id, date: ghostRow.date, lat: pin.lat, lng: pin.lng, title: pin.title })
    return
  }
  if (srcId == null) return
  const src = (props.days || []).find((d) => d.id === srcId)
  if (!src) return
  // Drop onto a ghost (empty) date — just reschedule the source stop to that
  // date, preserving its span.
  const srcSpan = src.end_date ? Math.round((new Date(src.end_date) - new Date(src.date)) / 86400000) : 0
  emit('patch-day', { day: src, payload: { date: ghostRow.date, end_date: srcSpan ? shiftDate(ghostRow.date, srcSpan) : null } })
}
function addStopOnDate(iso) {
  emit('add-day', { date: iso, label: null })
}

// Per-row weather forecast (lazy, capped to the Open-Meteo horizon).
// Multi-day stops get one chip per day in the span — for a Vegas warm-up
// dated May 16 → 17, we show two rows ("D1: ☀ …", "D2: 🌤 …") so the
// user sees how the weather evolves across the stay, not just the
// arrival day.
//
// Cache key is `${dayId}:${dateISO}` to support per-date entries; the
// underlying lib/weather.js cache is keyed by lat/lng so all dates for
// one stop share a single network round-trip.
const wxMap = ref({})
// Open-Meteo's forecast_days=16 returns today + 15 days (16 entries).
const FORECAST_HORIZON_DAYS = 15
function spanDates(day) {
  const start = day.date
  const end = day.end_date || day.date
  const span = Math.max(0, daysBetween(start, end))
  const out = []
  for (let i = 0; i <= span; i++) {
    const d = new Date(start)
    d.setUTCDate(d.getUTCDate() + i)
    out.push(d.toISOString().slice(0, 10))
  }
  return out
}
function tooFarDaysFor(dateISO) {
  const ms = new Date(dateISO).getTime() - new Date(today.value).getTime()
  const days = Math.ceil(ms / (24 * 3600 * 1000))
  return days > FORECAST_HORIZON_DAYS ? days - FORECAST_HORIZON_DAYS : null
}
function spanWeather(day) {
  if (!day || day.lat == null || day.lng == null) return []
  const dates = spanDates(day)
  return dates.map((date, idx) => ({
    date,
    tag: `D${idx + 1}`,
    forecast: wxMap.value[`${day.id}:${date}`] || null,
    tooFarDays: tooFarDaysFor(date),
  }))
}
// Back-compat helper retained for `weatherTooFar` callers (other rows /
// future use). Returns days past horizon for the stop's start date.
function weatherTooFar(d) {
  if (!d.date) return 0
  return tooFarDaysFor(d.date) || 0
}
async function refreshWeather(days) {
  for (const d of days) {
    if (d.id == null || d.lat == null || d.lng == null) continue
    for (const date of spanDates(d)) {
      const k = `${d.id}:${date}`
      if (wxMap.value[k]) continue
      const wx = await dailyForecast(d.lat, d.lng, date)
      if (wx) wxMap.value = { ...wxMap.value, [k]: wx }
    }
  }
}
watch(() => props.days, (next) => { refreshWeather(next || []) }, { immediate: true })

// Driving legs (cached per pair). Computed locally to avoid plumbing the cache
// from MapView; the data is derived from props.days so it refreshes with edits.
const legCache = ref({})
function pairKey(a, b) { return `${a.id}>${b.id}` }
function legFor(a, b) { return legCache.value[pairKey(a, b)] || null }
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
watch(() => props.days, (next) => refreshLegs(next || []), { immediate: true })
function legKm(a, b) {
  if (a.lat == null || a.lng == null || b.lat == null || b.lng == null) return null
  const R = 6371
  const toRad = (deg) => deg * Math.PI / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat)
  const lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return Math.round(2 * R * Math.asin(Math.sqrt(h)))
}

// Row builder — sorted by date, with day numbers, week separators, and the
// next-leg meta. Same shape as Itinerary.vue rows so the layout reads as one trip.
function shortDay(iso) { return parseInt(iso.slice(8, 10), 10) }
function shortMonth(iso) {
  const m = parseInt(iso.slice(5, 7), 10) - 1
  return ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'][m] || ''
}
function shortDow(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  return ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'][dt.getUTCDay()] || ''
}
function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000) }
function daysInSpan(start, end) { return daysBetween(start, end) + 1 }

const rows = computed(() => {
  const sorted = [...(props.days || [])].sort((a, b) => a.date.localeCompare(b.date))
  if (!sorted.length) return []
  const tripStart = new Date(sorted[0].date)
  const weekStats = new Map()
  for (let i = 0; i < sorted.length; i++) {
    const day = sorted[i]
    const next = i < sorted.length - 1 ? sorted[i + 1] : null
    const wn = Math.floor((new Date(day.date) - tripStart) / 86400000 / 7) + 1
    const ws = weekStats.get(wn) || { stops: 0, km: 0 }
    ws.stops += 1
    if (next && day.lat != null && day.lng != null && next.lat != null && next.lng != null) {
      const real = legFor(day, next)
      ws.km += real ? real.km : (legKm(day, next) || 0)
    }
    weekStats.set(wn, ws)
  }
  const out = []
  let lastWeekNum = 0
  // Per-stop loop emits one row per calendar day in the span. The first day
  // of a span is the editable parent; subsequent days are continuation rows
  // (visually muted; date + weather only).
  for (let i = 0; i < sorted.length; i++) {
    const day = sorted[i]
    const next = i < sorted.length - 1 ? sorted[i + 1] : null
    const span = daysInSpan(day.date, endOf(day))
    const startNum = daysBetween(sorted[0].date, day.date) + 1
    const endNum = startNum + span - 1
    const dayLabel = span > 1 ? `D${startNum}–${endNum}` : `D${startNum}`
    const spanLabel = span > 1 ? `+${span - 1}d` : ''
    const cleanLabel = day.label
      ? day.label.replace(/^\s*Day\s*\d+(?:\s*[—\-–]\s*\d+)?\s*[—\-–:·]\s*/i, '').trim()
      : ''
    let legNext = null
    if (next && day.lat != null && day.lng != null && next.lat != null && next.lng != null) {
      legNext = { km: legKm(day, next), real: legFor(day, next) }
    }
    const dayOffset = Math.floor((new Date(day.date) - tripStart) / 86400000)
    const weekNum = Math.floor(dayOffset / 7) + 1
    const weekHeader = weekNum !== lastWeekNum
    let weekRange = '', weekSummary = ''
    if (weekHeader) {
      const weekStart = new Date(tripStart)
      weekStart.setUTCDate(weekStart.getUTCDate() + (weekNum - 1) * 7)
      const weekEnd = new Date(weekStart)
      weekEnd.setUTCDate(weekEnd.getUTCDate() + 6)
      weekRange = `${weekStart.getUTCDate()}–${weekEnd.getUTCDate()} ${shortMonth(weekEnd.toISOString().slice(0, 10))}`
      const ws = weekStats.get(weekNum)
      if (ws) {
        const km = Math.round(ws.km)
        const stopsLbl = `${ws.stops} stop${ws.stops === 1 ? '' : 's'}`
        weekSummary = km > 0 ? `${stopsLbl} · ${formatDistance(km)}` : stopsLbl
      }
      lastWeekNum = weekNum
    }
    // Emit one row per calendar day in the span. The first day is the
    // editable parent; subsequent days are continuation rows (visually
    // muted, only date + weather populated). Drive-next leg only attaches
    // to the LAST day of the span (the actual departure day).
    for (let off = 0; off < span; off++) {
      const isoDate = shiftDate(day.date, off)
      const isContinuation = off > 0
      const isLastDay = off === span - 1
      const wxForDay = {
        date: isoDate,
        forecast: wxMap.value[`${day.id}:${isoDate}`] || null,
        tooFarDays: tooFarDaysFor(isoDate),
      }
      const dayOffset = Math.floor((new Date(isoDate) - tripStart) / 86400000)
      const weekNumDay = Math.floor(dayOffset / 7) + 1
      out.push({
        key: `d:${day.id}:${off}`,
        isGhost: false,
        isContinuation,
        isLastDayOfSpan: isLastDay,
        day,
        dayDate: isoDate,
        dayLabel: isContinuation ? '' : dayLabel,
        cleanLabel,
        legNext: isLastDay ? legNext : null,
        dow: shortDow(isoDate),
        dayNum: shortDay(isoDate),
        mon: shortMonth(isoDate),
        wxForDay,
        isToday: today.value === isoDate,
        isPast: isoDate < today.value,
        isFuture: isoDate > today.value,
        weekNum: weekNumDay,
      })
    }
  }
  // Pin sub-row injection happens after the day-row + ghost-row merge below
  // so we can splice them in at the right place. Marker: keep a weekHeader
  // pass-through for the merge phase.
  for (const r of out) { r.weekHeader = false }
  // First-of-week marker for sequential weeks (used after merge)
  // (computed during the merge pass)

  // Inject ghost rows for unscheduled dates between the first stop and the
  // last stop's end, so a "May 2-22 trip" with a gap between May 11 and May
  // 22 still renders the missing days as muted placeholders. Ghost rows are
  // not real DB entities; they get a click-to-add button + accept wishlist
  // drops to materialise.
  const lastSorted = sorted[sorted.length - 1]
  const tripEnd = new Date(endOf(lastSorted))
  const covered = new Set()
  for (const d of sorted) {
    let cur = new Date(d.date)
    const stop = new Date(endOf(d))
    while (cur <= stop) {
      covered.add(cur.toISOString().slice(0, 10))
      cur.setUTCDate(cur.getUTCDate() + 1)
    }
  }
  const ghostRows = []
  for (let cur = new Date(tripStart); cur <= tripEnd; cur.setUTCDate(cur.getUTCDate() + 1)) {
    const iso = cur.toISOString().slice(0, 10)
    if (covered.has(iso)) continue
    const dayOffset = Math.floor((new Date(iso) - tripStart) / 86400000)
    const weekNum = Math.floor(dayOffset / 7) + 1
    ghostRows.push({
      key: `g:${iso}`,
      isGhost: true,
      date: iso,
      dow: shortDow(iso),
      dayNum: shortDay(iso),
      mon: shortMonth(iso),
      weekNum,
      isToday: today.value === iso,
      isPast: iso < today.value,
      isFuture: iso > today.value,
    })
  }
  // Merge real day-rows + ghost rows in date order. Each iso-date now maps
  // to exactly one row (per-day expansion makes stop dates unique across
  // real rows; ghosts only fill uncovered dates).
  const realByDate = new Map()
  for (const r of out) realByDate.set(r.dayDate, r)
  const ghostByDate = new Map()
  for (const g of ghostRows) ghostByDate.set(g.date, g)
  const allDates = [...realByDate.keys(), ...ghostByDate.keys()].sort()
  const merged = []
  let lastWk = 0
  for (const iso of allDates) {
    const row = realByDate.get(iso) || ghostByDate.get(iso)
    const wk = row.weekNum
    // First row of a new week wears the divider. Continuation day-rows
    // never get headers (they're under the parent's week).
    if (wk !== lastWk && !row.isContinuation) {
      row.weekHeader = true
      const ws = new Date(tripStart)
      ws.setUTCDate(ws.getUTCDate() + (wk - 1) * 7)
      const we = new Date(ws); we.setUTCDate(we.getUTCDate() + 6)
      row.weekRange = `${ws.getUTCDate()}–${we.getUTCDate()} ${shortMonth(we.toISOString().slice(0, 10))}`
      const wsSum = weekStats.get(wk)
      if (wsSum) {
        const km = Math.round(wsSum.km)
        const stopsLbl = `${wsSum.stops} stop${wsSum.stops === 1 ? '' : 's'}`
        row.weekSummary = km > 0 ? `${stopsLbl} · ${formatDistance(km)}` : stopsLbl
      } else {
        row.weekSummary = ''
      }
      lastWk = wk
    } else {
      row.weekHeader = false
    }
    merged.push(row)
    // Splice pin sub-rows in just after a stop's last calendar day, when
    // the user has expanded that stop's pin dropdown.
    if (!row.isGhost && row.isLastDayOfSpan) {
      const dayId = row.day.id
      if (pinExpanded.value.has(dayId)) {
        const pins = pinsByDay.value.get(dayId) || []
        for (const p of pins) {
          merged.push({
            key: `p:${dayId}:${p.id}`,
            isGhost: false,
            isPin: true,
            parentDayId: dayId,
            pin: p,
          })
        }
      }
    }
  }
  return merged
})

// Trip meta line — derived numbers; mirrors what the dock used to show.
const totalNights = computed(() => {
  let n = 0
  for (const d of (props.days || [])) n += daysInSpan(d.date, endOf(d))
  return n
})
const totalDriveKm = computed(() => {
  const sorted = [...(props.days || [])].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const leg = legFor(sorted[i], sorted[i + 1])
    if (leg) sum += leg.km
  }
  return sum
})
const totalDriveMin = computed(() => {
  const sorted = [...(props.days || [])].sort((a, b) => a.date.localeCompare(b.date))
  let sum = 0
  for (let i = 0; i < sorted.length - 1; i++) {
    const leg = legFor(sorted[i], sorted[i + 1])
    if (leg) sum += leg.minutes
  }
  return sum
})
// Calendar span: earliest start_date → latest end_date, inclusive. This is
// the "trip length on the wall calendar" — distinct from `totalNights`, which
// only sums the days that actually have a stop scheduled. A 21-day road trip
// with only 10 stop-days would otherwise read as "10 days", which contradicts
// the start/end dates and reliably confuses people.
const calendarSpan = computed(() => {
  const days = props.days || []
  if (!days.length) return 0
  let min = days[0].date
  let max = endOf(days[0])
  for (const d of days) {
    if (d.date < min) min = d.date
    const e = endOf(d)
    if (e > max) max = e
  }
  return Math.round((new Date(max) - new Date(min)) / 86400000) + 1
})
const metaLine = computed(() => {
  const parts = []
  if (props.days?.length) {
    parts.push(`${calendarSpan.value} day${calendarSpan.value === 1 ? '' : 's'} planned`)
    // Only call out "scheduled" when it differs from the calendar span —
    // otherwise the two numbers are the same and the extra pill is noise.
    if (totalNights.value && totalNights.value !== calendarSpan.value) {
      parts.push(`${totalNights.value} scheduled`)
    }
    parts.push(`${props.days.length} stop${props.days.length === 1 ? '' : 's'}`)
  }
  if (totalDriveKm.value > 0) parts.push(`${formatDistance(totalDriveKm.value)} · ${fmtMinutes(totalDriveMin.value)}`)
  if ((props.points || []).length) parts.push(`${props.points.length} pin${props.points.length === 1 ? '' : 's'}`)
  return parts.join(' · ')
})

// Trail-stats memo for the wishlist cards.
const trailMemo = new Map()
function trailStats(p) {
  if (!p.gpx_data) return null
  if (trailMemo.has(p.id)) return trailMemo.get(p.id)
  try {
    const { coords, elevations } = parseGPX(p.gpx_data)
    const series = buildElevationSeries(coords, elevations)
    if (!series.length) { trailMemo.set(p.id, null); return null }
    const km = (series[series.length - 1].dist / 1000).toFixed(1)
    const { gain } = elevationStats(series)
    const out = { km, gain: gain == null ? null : Math.round(gain) }
    trailMemo.set(p.id, out)
    return out
  } catch { trailMemo.set(p.id, null); return null }
}
</script>

<style scoped>
.plan {
  position: relative;
  min-height: 100vh;
  padding: 0.5rem 0 1rem;
  display: grid;
  gap: 0.5rem;
  align-content: start;
  background: var(--paper);
}
.plan-head { padding: 0 0.6rem; }
.plan-stops, .plan-pins { padding: 0; }
.plan-stops-head, .plan-pins-head, .plan-empty { padding-left: 0.6rem; padding-right: 0.6rem; }
.plan-head { display: grid; gap: 0.2rem; }
.plan-head-row {
  display: flex;
  align-items: flex-start;
  align-content: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  flex-wrap: wrap;
}
.plan-title-wrap { display: grid; gap: 0.15rem; flex: 1 1 auto; min-width: 0; }
.plan-eyebrow {
  margin: 0;
  font-size: 0.66rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.plan-title {
  background: transparent;
  border: none;
  font-family: var(--display);
  font-size: clamp(1rem, 1.6vw, 1.3rem);
  letter-spacing: 0.005em;
  text-transform: uppercase;
  color: var(--ink);
  width: 100%;
  padding: 0;
  border-bottom: 1px dashed transparent;
  line-height: 1.1;
}
.plan-title:focus {
  outline: none;
  border-bottom-color: var(--cream-edge);
}
.plan-meta {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-faded);
  line-height: 1.2;
}
.plan-head-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.plan-h2 {
  margin: 0;
  font-family: var(--display);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink);
}

.plan-stops { display: grid; gap: 0.25rem; }
.plan-stops-head, .plan-pins-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.plan-stops-actions { display: inline-flex; gap: 0.35rem; flex-wrap: wrap; }
.plan-empty {
  padding: 1.4rem 1rem;
  text-align: center;
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  color: var(--ink-faded);
  border: 1px dashed var(--cream-edge);
  border-radius: 4px;
}

.add-row {
  display: grid;
  gap: 0.55rem;
  padding: 0.7rem 0.8rem;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 4px;
}
.add-form { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.add-date { max-width: 11rem; }
.reveal-enter-active, .reveal-leave-active {
  transition: opacity 160ms ease, transform 160ms ease, max-height 200ms ease;
  overflow: hidden;
}
.reveal-enter-from, .reveal-leave-to { opacity: 0; transform: translateY(-4px); max-height: 0; }

.plan-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  table-layout: fixed;
}
.plan-table thead th {
  position: sticky;
  top: 0;
  background: var(--paper);
  text-align: left;
  font-family: var(--mono);
  font-size: 0.58rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  padding: 0.25rem 0.4rem;
  border-bottom: 1px solid var(--ink);
  z-index: 2;
}
.plan-table tbody td {
  padding: 0.18rem 0.4rem;
  border-bottom: 1px solid var(--cream-edge);
  vertical-align: middle;
  line-height: 1.25;
  white-space: nowrap;
  /* No overflow:hidden here — popovers rendered inside cells need to bleed
     out below their row. Ellipsis is handled per-cell by the inner inputs /
     button (.cell-input, .cell-location, .cell-notes-display). */
}
.plan-row { height: 1.85rem; }
.plan-row.today {
  background: rgba(232, 93, 60, 0.06);
}
.plan-row.today .c-day { color: var(--vermillion-deep); font-weight: 700; }
.plan-row.past td { opacity: 0.5; }
.plan-row.is-selected { background: var(--cream); }
.plan-row:hover { background: var(--cream); }

/* (Continuation rows render the same content as their parent — no muting.
    Edits to label/sleep/notes/location all patch the same parent stop record;
    per-day data divergence is a future enhancement.) */

.plan-week td {
  padding: 0.45rem 0.4rem 0.25rem;
  border-bottom: 1px solid var(--ink);
  background: var(--paper);
  white-space: normal;
}
.week-tag {
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink);
  font-weight: 700;
  margin-right: 0.5rem;
}
.week-meta { font-size: 0.6rem; color: var(--ink-faded); margin-right: 0.5rem; }
.week-summary { font-size: 0.6rem; color: var(--ink-faded); float: right; }

.c-grip { width: 1.2rem; padding-right: 0 !important; padding-left: 0.4rem !important; }
.c-date { width: 5.6rem; }
.c-day { width: 2.4rem; font-size: 0.62rem; letter-spacing: 0.1em; color: var(--ink-faded); text-transform: uppercase; }
.c-place { width: 16rem; position: relative; }
.c-location { font-size: 0.72rem; color: var(--ink-soft); position: relative; }
.c-sleep { width: 12rem; }
.c-wx { width: 6.2rem; font-size: 0.72rem; color: var(--ink-soft); }
.c-notes { width: 12rem; }
.c-leg { width: 6.4rem; font-size: 0.7rem; color: var(--ink-soft); }
.c-act { width: 1.6rem; padding-right: 0.6rem !important; text-align: right; }

/* Location cell: italic full-display label so the user sees context, not just
   "Clark County". Click → opens the geocoder popover. */
.cell-location {
  background: transparent;
  border: 1px dashed transparent;
  border-radius: 3px;
  padding: 0.08rem 0.3rem;
  font: inherit;
  font-style: italic;
  font-size: 0.72rem;
  color: var(--ink-soft);
  text-align: left;
  width: 100%;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-location:hover { border-color: var(--cream-edge); color: var(--ink); }
.cell-location.on { border-color: var(--ink); background: var(--paper); }
.cell-location.missing { color: var(--vermillion); font-style: italic; }

/* Single-line date display: "SAT 9 MAY". The native date input is overlayed
   transparently so clicking the cell opens the picker. */
.d-inline { display: inline-flex; gap: 0.3rem; align-items: baseline; font-size: 0.74rem; letter-spacing: 0.04em; font-family: var(--mono); }
.d-inline .d-dow { color: var(--ink-faded); font-size: 0.7rem; font-family: var(--mono); letter-spacing: 0.06em; }
.d-inline .d-num { font-weight: 600; color: var(--ink); font-size: 0.82rem; font-family: var(--mono); letter-spacing: 0; }
.d-inline .d-mon { color: var(--ink-faded); font-size: 0.7rem; font-family: var(--mono); letter-spacing: 0.06em; }
.d-inline.is-cont { opacity: 0.6; }

/* Pin sub-row — indented under parent, click → edit. */
.plan-pin-row { background: rgba(0, 0, 0, 0.02); cursor: pointer; }
.plan-pin-row:hover { background: var(--cream); }
.plan-pin-row td { padding: 0.12rem 0.4rem; }
.pin-indent { padding-left: 1.6rem !important; color: var(--ink-faded); }
.pin-row-arrow { margin-right: 0.3rem; color: var(--ink-faded); }
.pin-row-emoji { font-size: 0.85rem; }
.pin-name { font-size: 0.76rem; }
.pin-row-title { color: var(--ink); font-weight: 500; }
.pin-row-comment { color: var(--ink-faded); margin-left: 0.3rem; }

/* Pin dropdown affordances inside parent stop row. */
.pin-toggle {
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 3px;
  font-family: var(--mono);
  font-size: 0.6rem;
  letter-spacing: 0.06em;
  color: var(--ink-faded);
  padding: 0.05rem 0.3rem;
  cursor: pointer;
  margin-left: 0.2rem;
  line-height: 1.2;
}
.pin-toggle:hover { color: var(--ink); border-color: var(--ink); }
.pin-toggle.on { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.pin-toggle.pin-add { color: var(--vermillion); border-color: var(--vermillion); }

/* Single-cell weather chip. */
.wx-chip { font-size: 0.72rem; color: var(--ink); }
.wx-faded { font-size: 0.7rem; color: var(--ink-faded); }

/* Hover-row insert buttons — small "+" affordances above and below each real
 * row that surface on hover. Anchored to c-place (which is the only cell
 * `position: relative`) so they sit roughly in the middle of the row width. */
/* Row-insert affordances. Above = single "+" (insert NEW stop above).
   Below = pair of buttons "↪" (extend this stop +1 day) and "+" (insert NEW
   stop after this stop). All hover-only; pinned to row mid-edges. */
.row-insert {
  position: absolute;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 6;
  display: inline-flex;
  gap: 0.2rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease;
}
.row-insert.above { top: 0; }
.row-insert.below { top: 100%; }
.plan-row:hover .row-insert,
.row-insert:focus-within { opacity: 1; pointer-events: auto; }

/* Single-button "above" affordance is itself a button (no wrapper) — inherit
   the same round chip styling as the paired buttons. */
button.row-insert,
.row-insert-btn {
  width: 1.2rem;
  height: 1.2rem;
  border-radius: 50%;
  background: var(--paper);
  border: 1px solid var(--ink);
  color: var(--ink);
  font-size: 0.78rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
button.row-insert:hover,
.row-insert-btn:hover {
  background: var(--vermillion);
  color: var(--paper);
  border-color: var(--vermillion);
}
.row-insert-btn.extend { font-size: 0.7rem; }

.date-cell {
  position: relative;
  display: grid;
  grid-template-areas: "dow num" "mon num" "span num";
  grid-template-columns: 1fr auto;
  align-items: baseline;
  gap: 0 0.4rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.2rem 0.3rem;
  border-radius: 3px;
  border: 1px dashed transparent;
}
.date-cell:hover { background: var(--paper); border-color: var(--cream-edge); }
.date-cell-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  border: none;
  padding: 0;
  font: inherit;
  background: transparent;
  /* Keep native picker UI but invisible — clicking the cell opens it. */
}
.d-dow { font-size: 0.55rem; letter-spacing: 0.18em; color: var(--ink-faded); grid-area: dow; }
.d-num { font-family: var(--display); font-size: 1.5rem; grid-area: num; align-self: center; }
.d-mon { font-size: 0.62rem; letter-spacing: 0.16em; color: var(--ink-faded); grid-area: mon; }
.d-span { font-size: 0.6rem; letter-spacing: 0.12em; color: var(--vermillion); grid-area: span; }
.end-edit {
  display: inline-block;
  margin-top: 0.25rem;
  background: transparent;
  border: 1px dashed var(--cream-edge);
  border-radius: 999px;
  font-size: 0.6rem;
  letter-spacing: 0.1em;
  color: var(--ink-faded);
  padding: 0.1rem 0.45rem;
  cursor: pointer;
}
.end-edit:hover { color: var(--vermillion); border-color: var(--vermillion); border-style: solid; }
.end-picker {
  display: block;
  margin-top: 0.25rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  padding: 0.25rem 0.45rem;
  border: 1.5px solid var(--ink);
  border-radius: 3px;
  background: var(--paper);
  color: var(--ink);
  width: 9.5rem;
  letter-spacing: 0.04em;
  box-shadow: 0 1px 0 var(--cream-edge);
}
.end-picker:focus { outline: none; border-color: var(--vermillion); box-shadow: 0 0 0 2px rgba(232, 93, 60, 0.18); }

/* Native date inputs are themed via the calendar-picker indicator (recoloured
   to match the vermillion accent) and by stripping the spinner. The
   `themed-date` class is applied to both the inline date cell and the
   "+ extend" picker so they read as one ribbon of UI even though the cell
   input is invisible by design. */
.themed-date {
  color-scheme: light;
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--mono);
}
.themed-date::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 0.7;
  filter: invert(46%) sepia(78%) saturate(1789%) hue-rotate(338deg) brightness(96%) contrast(89%);
}
.themed-date::-webkit-calendar-picker-indicator:hover { opacity: 1; }
.themed-date::-webkit-inner-spin-button,
.themed-date::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.themed-date::-webkit-datetime-edit { color: var(--ink); }
.themed-date::-webkit-datetime-edit-fields-wrapper { padding: 0; }
.themed-date::-webkit-datetime-edit-text { color: var(--ink-faded); padding: 0 0.1rem; }
.themed-date::-webkit-datetime-edit-month-field,
.themed-date::-webkit-datetime-edit-day-field,
.themed-date::-webkit-datetime-edit-year-field { color: var(--ink); }

/* Drag-to-reorder grip. Hidden until the row is hovered so the table stays
   clean — appears as a low-key two-dot handle the user can grab to drag. */
.grip {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1.1rem;
  line-height: 0.7;
  letter-spacing: -0.05em;
  cursor: grab;
  padding: 0.2rem 0.15rem;
  opacity: 0;
  transition: opacity 90ms ease, color 90ms ease;
  user-select: none;
  -webkit-user-select: none;
}
.plan-row:hover .grip,
.plan-row.is-dragged .grip { opacity: 0.85; }
.grip:hover { color: var(--vermillion); }
.grip:active { cursor: grabbing; color: var(--vermillion); }
.plan-row.is-dragged { opacity: 0.5; }
.plan-row.drop-target td { box-shadow: inset 0 2px 0 var(--vermillion); }
.plan-table.is-dragging .plan-row:not(.is-dragged) { cursor: grabbing; }

.mobile-expand {
  display: none;
  background: transparent;
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  font-size: 0.7rem;
  color: var(--ink-faded);
  padding: 0.05rem 0.45rem;
  cursor: pointer;
  margin-top: 0.25rem;
}
.mobile-expand:hover { color: var(--vermillion); border-color: var(--vermillion); }

.place-cell { display: grid; gap: 0.1rem; position: relative; }
.cell-name { font-size: 1rem; font-weight: 600; }
.place-loc {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding-left: 0.4rem;
  flex-wrap: wrap;
  min-height: 1.1rem;
}
.place-loc-text {
  font-style: italic;
  font-size: 0.74rem;
  color: var(--ink-faded);
  letter-spacing: 0.02em;
  font-family: var(--body);
  font-weight: 400;
}
.place-loc-missing { color: var(--vermillion); font-style: italic; }
.place-wx {
  margin: 0.05rem 0 0 0.4rem;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}
.place-wx + .place-wx { margin-top: 0.02rem; }
.place-wx.is-faded { color: var(--ink-faded); font-style: italic; }
.place-wx .wx-tag {
  display: inline-block;
  min-width: 1.6rem;
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  color: var(--ink-faded);
  margin-right: 0.3rem;
}
.loc-btn {
  background: transparent;
  border: 1px dashed var(--cream-edge);
  border-radius: 999px;
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-faded);
  padding: 0.1rem 0.5rem;
  cursor: pointer;
}
.loc-btn:hover, .loc-btn.on {
  color: var(--vermillion);
  border-color: var(--vermillion);
  border-style: solid;
}
.loc-btn.missing {
  color: var(--vermillion);
  border-color: var(--vermillion);
  border-style: solid;
}
.loc-popover {
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  padding: 0.7rem 0.75rem 0.85rem;
  box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.22);
  display: grid;
  gap: 0.55rem;
  width: min(380px, 95vw);
  background: var(--paper);
}
.loc-popover-hint {
  margin: 0;
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}
.loc-popover-close {
  justify-self: flex-end;
  background: transparent;
  border: none;
  color: var(--ink-faded);
  cursor: pointer;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.2rem 0.4rem;
}
.loc-popover-close:hover { color: var(--vermillion); }
.dap-eyebrow {
  margin: 0;
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}

.cell-input {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  padding: 0.3rem 0.4rem;
  font: inherit;
  font-size: 0.92rem;
  color: var(--ink);
  border-radius: 2px;
}
.cell-input:hover { border-color: var(--cream-edge); }
.cell-input:focus {
  border-color: var(--ink);
  outline: none;
  background: var(--paper);
  box-shadow: 0 0 0 2px rgba(232, 93, 60, 0.1);
}
.mobile-name { display: none; }

/* Read-only excerpt of a note. Click → opens the day modal (full markdown
   editor). Empty notes render as a faint placeholder so the cell still reads
   as actionable. */
.cell-notes-display {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  padding: 0.3rem 0.4rem;
  font: inherit;
  font-size: 0.86rem;
  color: var(--ink-soft);
  text-align: left;
  cursor: pointer;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  line-height: 1.3;
}
.cell-notes-display.is-empty { color: var(--ink-faded); }
.cell-notes-display:hover { border-color: var(--cream-edge); }

/* Mobile-only inline drive-time line under the stop name. Hidden on desktop
   (the "Drive next" column already shows it); revealed inside @media below. */
.mobile-summary { display: none; margin: 0; font-size: 0.7rem; color: var(--ink-faded); letter-spacing: 0.04em; }

/* Ghost rows for unscheduled trip days. Muted typography, dashed border on
   the date cell, and an inline "+ add stop" button so a user planning a
   "May 2-22" trip with stops only on May 2-11 still sees May 12-21 and can
   one-click attach a place to any of them. Also accepts wishlist drops via
   the row-level @drop handler. */
.plan-row.plan-ghost td {
  background: transparent;
  color: var(--ink-faded);
  border-bottom: 1px dashed var(--cream-edge);
}
.plan-row.plan-ghost:hover td { background: var(--cream); }
.plan-row.plan-ghost .ghost-date {
  border: 1px dashed var(--cream-edge);
  border-radius: 3px;
  opacity: 0.7;
}
.plan-row.plan-ghost .d-num { font-size: 1.2rem; color: var(--ink-faded); }
.ghost-add {
  background: transparent;
  border: 1px dashed var(--cream-edge);
  border-radius: 999px;
  color: var(--ink-faded);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.2rem 0.7rem;
  cursor: pointer;
  margin-right: 0.5rem;
}
.ghost-add:hover {
  color: var(--vermillion);
  border-color: var(--vermillion);
  border-style: solid;
  background: var(--paper);
}
.ghost-hint {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
  font-style: italic;
}
.plan-row.plan-ghost.drop-target td {
  background: rgba(232, 93, 60, 0.08);
  box-shadow: inset 0 0 0 2px var(--vermillion);
}
.cell-hint {
  display: inline-block;
  margin-left: 0.4rem;
  font-size: 0.62rem;
  color: var(--vermillion);
  letter-spacing: 0.1em;
}

.pins-cell { position: relative; display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; }
.pin-chips { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.25rem; }
.pin-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--cream);
  border: 1px solid var(--cream-edge);
  border-radius: 999px;
  padding: 0.18rem 0.55rem 0.18rem 0.5rem;
  font-size: 0.78rem;
  cursor: pointer;
  max-width: 14rem;
}
.pin-chip:hover { border-color: var(--ink); }
.pin-chip-emoji { font-size: 0.85rem; line-height: 1; }
.pin-chip-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pin-chip-detach {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  cursor: pointer;
  font-size: 0.95rem;
  line-height: 1;
  padding: 0 0.1rem;
}
.pin-chip-detach:hover { color: var(--vermillion); }

.add-pin-btn {
  background: transparent;
  border: 1px dashed var(--ink-faded);
  border-radius: 999px;
  color: var(--ink-faded);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.2rem 0.65rem;
  cursor: pointer;
}
.add-pin-btn:hover, .add-pin-btn.on {
  color: var(--vermillion);
  border-color: var(--vermillion);
  border-style: solid;
  background: var(--paper);
}

.popover-anchor {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 80;
  width: min(380px, 95vw);
}

.c-leg .leg-est { color: var(--ink-faded); font-size: 0.7em; margin-left: 0.2rem; }
.c-leg .leg-faded { color: var(--ink-faded); }
.leg-cell {
  display: grid;
  gap: 0.05rem;
  line-height: 1.05;
  white-space: nowrap;
}
.leg-km {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.02em;
}
.leg-time {
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}
.leg-cell.is-short .leg-km { color: var(--ink-faded); font-style: italic; font-weight: 500; }
.leg-cell.is-short .leg-time { display: none; }
.leg-cell.is-long .leg-km { color: var(--vermillion-deep); }

.row-actions { display: inline-flex; gap: 0.1rem; }
.iti-icon {
  background: transparent;
  border: none;
  font-size: 0.95rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.3rem 0.4rem;
  border-radius: 3px;
}
.iti-icon:hover { color: var(--vermillion); background: var(--paper); }
.iti-icon-confirm {
  /* Armed state — vermillion fill + uppercase mono so the user reads it as
     "this is the destructive click" before committing. Auto-reverts after
     ~4s (handled in script) if they walk away. */
  background: var(--vermillion);
  color: var(--paper);
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.3rem 0.55rem;
  font-weight: 700;
  animation: iti-confirm-pulse 1.4s ease-in-out infinite;
}
.iti-icon-confirm:hover { background: var(--vermillion-deep); color: var(--paper); }
@keyframes iti-confirm-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(232, 93, 60, 0.45); }
  50%      { box-shadow: 0 0 0 4px rgba(232, 93, 60, 0); }
}

.plan-pins { display: grid; gap: 0.6rem; }
.plan-pins-controls { display: flex; gap: 0.4rem; align-items: center; }
.seg {
  display: inline-flex;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  overflow: hidden;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.seg-btn {
  background: transparent;
  border: none;
  padding: 0.25rem 0.7rem;
  cursor: pointer;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.seg-btn.on { background: var(--ink); color: var(--paper); }
.seg-count {
  background: var(--cream);
  color: var(--ink);
  border-radius: 999px;
  padding: 0 0.4rem;
  font-size: 0.62rem;
  min-width: 1rem;
  text-align: center;
}
.seg-btn.on .seg-count { background: var(--vermillion); color: var(--paper); }

.pins-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.6rem;
}
.pin-card {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  border-radius: 4px;
  padding: 0.6rem 0.7rem;
  display: grid;
  gap: 0.3rem;
  cursor: pointer;
  transition: border-color 90ms ease, box-shadow 90ms ease, transform 60ms ease;
}
.pin-card:hover {
  border-color: var(--ink);
  box-shadow: 2px 2px 0 var(--cream-edge);
  transform: translate(-1px, -1px);
}
.pin-card.is-trail { border-left: 4px solid var(--swatch, var(--ink-faded)); }
.pin-card { cursor: grab; }
.pin-card:active { cursor: grabbing; }
.pin-card.is-dragged { opacity: 0.4; transform: scale(0.97); }
.pin-card-del {
  position: absolute;
  top: 4px;
  right: 4px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--ink-faded);
  width: 1.5rem;
  height: 1.5rem;
  display: grid;
  place-items: center;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 90ms ease, color 90ms ease, border-color 90ms ease, background 90ms ease;
}
.pin-card:hover .pin-card-del { opacity: 1; }
.pin-card-del:hover {
  color: var(--paper);
  background: var(--vermillion);
  border-color: var(--vermillion);
}
.pin-card-actions {
  display: flex;
  justify-content: flex-end;
}
.pin-card-detach {
  background: transparent;
  border: 1px dashed var(--cream-edge);
  border-radius: 999px;
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-faded);
  padding: 0.15rem 0.55rem;
  cursor: pointer;
}
.pin-card-detach:hover {
  color: var(--vermillion);
  border-color: var(--vermillion);
  border-style: solid;
}
.pin-card-top { display: flex; align-items: baseline; gap: 0.4rem; }
.pin-card-emoji {
  font-size: 1rem;
  width: 1.7rem;
  height: 1.7rem;
  display: grid;
  place-items: center;
  background: var(--paper);
  border: 1.5px solid var(--vermillion);
  border-radius: 50%;
  flex-shrink: 0;
}
.pin-card-title {
  font-size: 0.96rem;
  flex: 1 1 auto;
  min-width: 0;
  word-break: break-word;
}
.pin-card-attached {
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-faded);
  flex-shrink: 0;
}
.pin-card-comment {
  margin: 0;
  font-size: 0.84rem;
  color: var(--ink-soft);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pin-card-meta {
  margin: 0;
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  font-size: 0.7rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}
.pin-card-trail { color: var(--swatch, var(--ink-faded)); font-weight: 600; }

/* ───── M4 sheet-density overrides ──────────────────────────────────────────
   Flatten legacy card-style cells (date grid, multi-line place cell, big
   stop-name input) into single-line spreadsheet cells. Targets every selector
   that bumps row height. */
.plan-table tbody td.c-place,
.plan-table tbody td.c-sleep,
.plan-table tbody td.c-notes,
.plan-table tbody td.c-wx,
.plan-table tbody td.c-leg { vertical-align: middle; }
.date-cell {
  display: inline-block;
  position: relative;
  padding: 0;
  border: none;
  cursor: pointer;
  line-height: 1.2;
}
.date-cell:hover { background: transparent; border: none; }
.place-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  position: relative;
  width: 100%;
  min-width: 0;
}
.cell-name {
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  flex: 1 1 auto;
  min-width: 0;
}
.cell-input { padding: 0.08rem 0.3rem; font-size: 0.78rem; line-height: 1.25; }
.cell-input:focus { box-shadow: none; }
.cell-notes-display {
  padding: 0.08rem 0.3rem;
  font-size: 0.74rem;
  line-height: 1.25;
  text-align: left;
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.loc-btn {
  padding: 0.05rem 0.3rem;
  font-size: 0.6rem;
  letter-spacing: 0.04em;
  border-radius: 3px;
  flex-shrink: 0;
}
.grip { font-size: 0.85rem; color: var(--ink-faded); cursor: grab; }
.iti-icon {
  width: 1.1rem;
  height: 1.1rem;
  font-size: 0.85rem;
  line-height: 1;
  padding: 0;
}
.leg-cell { font-size: 0.7rem; }
.row-insert { width: 1.05rem; height: 1.05rem; font-size: 0.72rem; }

@media (max-width: 720px) {
  .plan { padding: 1rem 0.9rem 4rem; gap: 1.4rem; }
  .plan-table thead { display: none; }
  .plan-table, .plan-table tbody, .plan-table tr, .plan-table td { display: block; width: 100%; }
  .plan-row {
    position: relative;
    border: 1px solid var(--cream-edge);
    border-radius: 4px;
    margin-bottom: 0.45rem;
    padding: 0.5rem 0.7rem;
    display: grid;
    grid-template-columns: 4.4rem 1fr;
    gap: 0.3rem 0.6rem;
    align-items: start;
  }
  .plan-row td { border: none; padding: 0; }
  .plan-row .c-date { grid-column: 1 / 2; grid-row: 1 / span 6; }
  .plan-row .c-day,
  .plan-row .c-place,
  .plan-row .c-sleep,
  .plan-row .c-wx,
  .plan-row .c-notes,
  .plan-row .c-leg,
  .plan-row .c-act { grid-column: 2 / 3; }
  .plan-row .c-day { display: none; } /* day index already implied by date column */
  .plan-week td { background: transparent; border: none; }
  .c-grip, .c-date, .c-day, .c-place, .c-sleep, .c-wx, .c-notes, .c-leg, .c-act { width: auto; max-width: none; }
  /* Hover-insert buttons rely on hover — useless on touch and visually
     cramped inside the mobile card layout. */
  .row-insert { display: none; }
  .c-act { display: flex; justify-content: flex-end; }
  .pins-cell { flex-direction: row; }
  .plan-row .c-grip { display: none; }

  .mobile-expand { display: inline-flex; }
  .mobile-summary { display: block; margin-top: 0.15rem; }
  /* Drive column is redundant on mobile (the inline summary under the name
     covers it) — hide unless the row is expanded. */
  .plan-row .c-leg { display: none; }

  /* Collapsed state: row reads as date · name · drive — everything else
     hidden until the user taps the chevron. Brings a 21-stop trip from
     ~12,000px tall down to ~3,500px scrollable list. */
  .plan-row:not(.is-expanded):not(.plan-ghost) .c-sleep,
  .plan-row:not(.is-expanded):not(.plan-ghost) .c-wx,
  .plan-row:not(.is-expanded):not(.plan-ghost) .c-notes,
  .plan-row:not(.is-expanded):not(.plan-ghost) .c-act,
  .plan-row:not(.is-expanded):not(.plan-ghost) .end-edit,
  .plan-row:not(.is-expanded):not(.plan-ghost) .end-picker,
  .plan-row:not(.is-expanded):not(.plan-ghost) .place-loc,
  .plan-row:not(.is-expanded):not(.plan-ghost) .cell-name {
    display: none;
  }
  .plan-row:not(.is-expanded):not(.plan-ghost) .mobile-name {
    display: block;
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--ink);
    line-height: 1.25;
  }
  .plan-row.is-expanded .mobile-summary { display: none; }
  .plan-row.is-expanded .c-leg { display: block; }

  .plan-row.plan-ghost { padding: 0.35rem 0.6rem; }
  .plan-row.plan-ghost .c-place { display: flex; flex-wrap: wrap; gap: 0.3rem; }
}
</style>
