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

export function formatTime(d) {
  if (!(d instanceof Date) || Number.isNaN(d.valueOf())) return '—'
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
