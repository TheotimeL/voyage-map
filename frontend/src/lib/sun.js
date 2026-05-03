import SunCalc from 'suncalc'
import { formatTime as formatTimeSetting, zoneFor as zoneForSetting } from './settings.js'

export function sunInfo(lat, lng, when = new Date()) {
  const t = SunCalc.getTimes(when, lat, lng)
  return {
    sunrise: t.sunrise,
    sunset: t.sunset,
    civilStart: t.dawn,
    civilEnd: t.dusk,
    night: t.night,
    nightEnd: t.nightEnd,
    now: when,
  }
}

// IANA timezone for a coordinate. Falls back to the browser's zone if the
// lookup fails. Re-exported from settings.js so existing callers keep working.
export const zoneFor = zoneForSetting

// Delegates to the locale-aware formatter in lib/settings.js — one source of
// truth so the user's 12h/24h preference applies everywhere.
export function formatTime(d, lat, lng) {
  return formatTimeSetting(d, lat, lng)
}

export function formatCountdown(ms) {
  const sign = ms < 0 ? '−' : ''
  const abs = Math.abs(ms)
  const minutes = Math.round(abs / 60_000)
  if (minutes === 0) return 'now'
  if (minutes < 60) return `${sign}${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${sign}${h}h ${m}m`
}

// Drive-arrival check: given a leaving wall-time (HH:MM in the destination's
// timezone, on the destination's date), drive minutes, and a destination
// sunset Date, returns { arrive: 'HH:MM', marginMin: 47 }. Negative margin
// means the driver lands after dusk. Returns null if any input is missing.
export function arrivalSafety({ destDate, destLat, destLng, departHHMM, driveMinutes }) {
  if (!destDate || destLat == null || destLng == null || driveMinutes == null) return null
  const zone = zoneFor(destLat, destLng)
  const [hh, mm] = (departHHMM || '10:00').split(':').map(Number)
  // Build the depart Date by interpreting HH:MM as wall time on `destDate` in
  // the destination's IANA zone. `Intl.DateTimeFormat` works the other way,
  // so we approximate via two passes: build a UTC-wall guess, measure its
  // zone offset, then correct.
  const guess = new Date(`${destDate}T${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:00Z`)
  const offsetMin = zoneOffsetMinutes(guess, zone)
  const depart = new Date(guess.getTime() - offsetMin * 60_000)
  const arrive = new Date(depart.getTime() + driveMinutes * 60_000)
  const sunset = SunCalc.getTimes(new Date(`${destDate}T12:00:00Z`), destLat, destLng).sunset
  if (!sunset || isNaN(sunset)) return null
  const marginMin = Math.round((sunset - arrive) / 60_000)
  return { arrive: formatTime(arrive, destLat, destLng), sunset: formatTime(sunset, destLat, destLng), marginMin }
}

// Minutes east of UTC for a given Date in a given IANA zone, e.g.
// (May 15, "America/Los_Angeles") → -420 (PDT). Approximate, sufficient for
// arrival-margin math.
function zoneOffsetMinutes(date, zone) {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone: zone,
    hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
  const parts = Object.fromEntries(dtf.formatToParts(date).filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  const asUTC = Date.UTC(
    Number(parts.year), Number(parts.month) - 1, Number(parts.day),
    Number(parts.hour) % 24, Number(parts.minute), Number(parts.second),
  )
  return Math.round((asUTC - date.getTime()) / 60_000)
}
