import SunCalc from 'suncalc'

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

// Format an absolute Date as HH:MM. When `lng` is provided, the time is shown
// in the mean solar time at that longitude — useful when the user is browsing
// from a different timezone (e.g., planning a US trip from Europe).
export function formatTime(d, lng) {
  if (!(d instanceof Date) || Number.isNaN(d.valueOf())) return '—'
  if (lng == null) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const utcMin = d.getUTCHours() * 60 + d.getUTCMinutes()
  const offsetMin = Math.round(lng / 15) * 60
  const total = ((utcMin + offsetMin) % 1440 + 1440) % 1440
  const h = Math.floor(total / 60)
  const m = total % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
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
