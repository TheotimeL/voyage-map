// App-wide locale / units settings — reactive, persisted to localStorage so
// the user's choice survives reloads. Defaults are auto-detected from the
// browser locale: en-US gets imperial / 12h / "May 9", everyone else gets
// metric / 24h / "9 May".
//
// Keep this small. The four formatter helpers (`formatDistance`, `formatTemp`,
// `formatTime`, `formatDate`) read the reactive `settings` object, so changing
// any setting re-renders every formatted value across the app.

import { reactive, watch } from 'vue'
import tzLookup from 'tz-lookup'

const STORAGE_KEY = 'voyage-map.settings'

function detectDefaults() {
  const lang = (typeof navigator !== 'undefined' && navigator.language) || ''
  if (lang.toLowerCase().startsWith('en-us')) {
    return { units: 'imperial', dateFmt: 'us', timeFmt: '12h' }
  }
  return { units: 'metric', dateFmt: 'eu', timeFmt: '24h' }
}

function loadInitial() {
  const fallback = detectDefaults()
  if (typeof localStorage === 'undefined') return fallback
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return {
      units: parsed.units === 'imperial' || parsed.units === 'metric' ? parsed.units : fallback.units,
      dateFmt: ['iso', 'us', 'eu'].includes(parsed.dateFmt) ? parsed.dateFmt : fallback.dateFmt,
      timeFmt: parsed.timeFmt === '12h' || parsed.timeFmt === '24h' ? parsed.timeFmt : fallback.timeFmt,
    }
  } catch {
    return fallback
  }
}

export const settings = reactive(loadInitial())

watch(
  () => ({ units: settings.units, dateFmt: settings.dateFmt, timeFmt: settings.timeFmt }),
  (next) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* ignore quota errors */ }
  },
)

// --- Number helper ----------------------------------------------------------

// Format with locale-aware grouping. Drops decimals for ≥10, keeps one decimal
// for <10 — so a 4.2-mile run doesn't read as "4 mi".
function fmtNumber(v) {
  if (!Number.isFinite(v)) return String(v)
  const abs = Math.abs(v)
  if (abs >= 10) return Math.round(v).toLocaleString()
  return (Math.round(v * 10) / 10).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

// --- Distance ---------------------------------------------------------------

const KM_TO_MI = 0.621371

export function formatDistance(km) {
  if (km == null || !Number.isFinite(Number(km))) return ''
  const k = Number(km)
  return settings.units === 'imperial' ? `${fmtNumber(k * KM_TO_MI)} mi` : `${fmtNumber(k)} km`
}

// Distance number only, no unit — for places that already render the unit
// label as a separate span. Returns a string with locale grouping.
export function formatDistanceValue(km) {
  if (km == null || !Number.isFinite(Number(km))) return ''
  const k = Number(km)
  return fmtNumber(settings.units === 'imperial' ? k * KM_TO_MI : k)
}

export function distanceUnit() {
  return settings.units === 'imperial' ? 'mi' : 'km'
}

// --- Temperature ------------------------------------------------------------

export function formatTemp(c) {
  if (c == null || !Number.isFinite(Number(c))) return ''
  const cv = Number(c)
  return settings.units === 'imperial' ? `${Math.round(cv * 9 / 5 + 32)}°F` : `${Math.round(cv)}°C`
}

// Just the rounded number, no unit — for places that render the degree glyph
// as a separate span (e.g. "73° / 51°").
export function formatTempValue(c) {
  if (c == null || !Number.isFinite(Number(c))) return ''
  const cv = Number(c)
  return settings.units === 'imperial' ? Math.round(cv * 9 / 5 + 32) : Math.round(cv)
}

// --- Time -------------------------------------------------------------------

// IANA timezone for a coordinate. Falls back to the browser's zone if the
// lookup fails (out-of-range coords, etc.).
export function zoneFor(lat, lng) {
  try { return tzLookup(lat, lng) }
  catch {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone } catch { return undefined }
  }
}

// Accepts a Date, an ISO string, or a "HH:mm" wall-time string. Returns
// "20:25" / "8:25 PM". When `lat`+`lng` are passed (Date inputs only) the
// time is rendered in that location's IANA zone; otherwise browser-local.
export function formatTime(input, lat, lng) {
  if (input == null || input === '') return '—'
  if (typeof input === 'string' && /^\d{1,2}:\d{2}(?::\d{2})?$/.test(input)) {
    const [hh, mm] = input.split(':').map(Number)
    return formatTimeFromHM(hh, mm)
  }
  let date
  if (input instanceof Date) date = input
  else if (typeof input === 'string') date = new Date(input)
  else return '—'
  if (!(date instanceof Date) || Number.isNaN(date.valueOf())) return '—'
  const opts = { hour: 'numeric', minute: '2-digit', hour12: settings.timeFmt === '12h' }
  if (lat != null && lng != null) {
    const tz = zoneFor(lat, lng)
    if (tz) opts.timeZone = tz
  }
  // Force a locale to keep the rendered separator/format stable across browsers.
  const locale = settings.timeFmt === '12h' ? 'en-US' : 'en-GB'
  return new Intl.DateTimeFormat(locale, opts).format(date)
}

function formatTimeFromHM(hh, mm) {
  const mmStr = String(mm).padStart(2, '0')
  if (settings.timeFmt === '12h') {
    const period = hh >= 12 ? 'PM' : 'AM'
    const h12 = ((hh + 11) % 12) + 1
    return `${h12}:${mmStr} ${period}`
  }
  return `${String(hh).padStart(2, '0')}:${mmStr}`
}

// --- Date -------------------------------------------------------------------

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "9 May" (eu) / "May 9" (us) / "2026-05-09" (iso). Accepts a Date or an
// ISO "YYYY-MM-DD" string. Parses ISO via fixed digits so the rendered
// day doesn't drift in negative-offset zones.
export function formatDate(input) {
  if (input == null || input === '') return ''
  let y, m, d
  if (input instanceof Date) {
    if (Number.isNaN(input.valueOf())) return ''
    y = input.getFullYear(); m = input.getMonth() + 1; d = input.getDate()
  } else if (typeof input === 'string') {
    const iso = input.slice(0, 10)
    const parts = iso.split('-').map(Number)
    if (parts.length === 3 && parts.every(Number.isFinite)) {
      [y, m, d] = parts
    } else {
      const dt = new Date(input)
      if (Number.isNaN(dt.valueOf())) return ''
      y = dt.getFullYear(); m = dt.getMonth() + 1; d = dt.getDate()
    }
  } else {
    return ''
  }
  const month = MONTHS_SHORT[m - 1] || ''
  if (settings.dateFmt === 'iso') return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  if (settings.dateFmt === 'us') return `${month} ${d}`
  return `${d} ${month}`
}
