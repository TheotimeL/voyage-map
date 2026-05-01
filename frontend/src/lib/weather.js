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
  // Pull both daily aggregates and hourly so we can build start-of-day picks
  // (best run window, dawn temp, etc.) without a second request.
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}` +
    '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code' +
    '&hourly=temperature_2m,precipitation_probability,weather_code' +
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
    const hourlyByDate = {}
    const h = data.hourly
    if (h?.time) {
      h.time.forEach((iso, i) => {
        const day = iso.slice(0, 10)
        const hour = parseInt(iso.slice(11, 13), 10)
        if (!hourlyByDate[day]) hourlyByDate[day] = []
        hourlyByDate[day].push({
          hour,
          temp: Math.round(h.temperature_2m[i]),
          rainPct: h.precipitation_probability?.[i] ?? null,
          code: h.weather_code?.[i] ?? null,
        })
      })
    }
    const entry = { byDate, hourlyByDate }
    cache.set(k, entry)
    return entry
  } catch {
    cache.set(k, { byDate: {}, hourlyByDate: {} })
    return cache.get(k)
  }
}

export async function dailyForecast(lat, lng, dateISO) {
  if (lat == null || lng == null) return null
  const entry = await fetchForLocation(lat, lng)
  return entry.byDate[dateISO] || null
}

// Hourly forecast for one day, sorted by hour. Returns [] if the day is
// outside the forecast window or fetch failed. Keep tight: just enough to
// pick a run-start window.
export async function hourlyForecast(lat, lng, dateISO) {
  if (lat == null || lng == null) return []
  const entry = await fetchForLocation(lat, lng)
  return entry.hourlyByDate?.[dateISO] || []
}

// Best 3-hour window for a "morning effort" (run, hike). Picks the contiguous
// 3-hour slot between 5am and 11am with the lowest mean temp + rain
// probability — what a trail-runner wants for an early start. Returns null
// when the day's hourly data isn't loaded.
export async function bestMorningWindow(lat, lng, dateISO) {
  const hours = await hourlyForecast(lat, lng, dateISO)
  if (!hours.length) return null
  const morning = hours.filter((h) => h.hour >= 5 && h.hour <= 11)
  if (morning.length < 3) return null
  let best = null
  for (let i = 0; i <= morning.length - 3; i++) {
    const slot = morning.slice(i, i + 3)
    const meanTemp = slot.reduce((s, h) => s + h.temp, 0) / 3
    const meanRain = slot.reduce((s, h) => s + (h.rainPct || 0), 0) / 3
    // Lower is better; cap rain weight so sub-30% doesn't drown out temp.
    const score = Math.abs(meanTemp - 14) + Math.min(meanRain, 60) * 0.5
    if (!best || score < best.score) {
      best = { startHour: slot[0].hour, endHour: slot[2].hour + 1, meanTemp: Math.round(meanTemp), meanRain: Math.round(meanRain), score }
    }
  }
  return best
}

export function glyphFor(code) {
  if (code == null) return ''
  return CODE_GLYPH[code] || '·'
}
