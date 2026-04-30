// Daily weather forecast from Open-Meteo (free, no key required).
// Caches by lat/lng so each location is fetched at most once per session;
// returns null for dates outside Open-Meteo's 16-day forecast window.

const cache = new Map()  // key "lat,lng" → { byDate: { iso: { tMax, tMin, precip, code } } }

const CODE_GLYPH = {
  0: '☀',  1: '🌤', 2: '⛅', 3: '☁',
  45: '🌫', 48: '🌫',
  51: '🌦', 53: '🌦', 55: '🌧',
  56: '🌧', 57: '🌧',
  61: '🌧', 63: '🌧', 65: '🌧',
  66: '🌧', 67: '🌧',
  71: '🌨', 73: '🌨', 75: '❄',
  77: '🌨',
  80: '🌦', 81: '🌧', 82: '🌧',
  85: '🌨', 86: '🌨',
  95: '⛈', 96: '⛈', 99: '⛈',
}

function key(lat, lng) {
  // Round to ~10km grid so nearby days share the same fetch.
  return `${lat.toFixed(1)},${lng.toFixed(1)}`
}

async function fetchForLocation(lat, lng) {
  const k = key(lat, lng)
  if (cache.has(k)) return cache.get(k)
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}` +
    '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code' +
    '&forecast_days=16&timezone=auto'
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error('open-meteo ' + res.status)
    const data = await res.json()
    const byDate = {}
    const d = data.daily
    if (d?.time) {
      d.time.forEach((iso, i) => {
        byDate[iso] = {
          tMax: Math.round(d.temperature_2m_max[i]),
          tMin: Math.round(d.temperature_2m_min[i]),
          precip: d.precipitation_sum[i] ?? 0,
          code: d.weather_code[i] ?? null,
        }
      })
    }
    const entry = { byDate }
    cache.set(k, entry)
    return entry
  } catch {
    cache.set(k, { byDate: {} })
    return cache.get(k)
  }
}

export async function dailyForecast(lat, lng, dateISO) {
  if (lat == null || lng == null) return null
  const entry = await fetchForLocation(lat, lng)
  return entry.byDate[dateISO] || null
}

export function glyphFor(code) {
  if (code == null) return ''
  return CODE_GLYPH[code] || '·'
}
