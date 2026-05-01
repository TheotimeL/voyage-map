// Driving distance + duration + road geometry between two points.
//
// Goes through our backend `/api/route` proxy: it speaks OSRM upstream but
// caches results in SQLite, so road geometry survives restarts (the previous
// in-memory-only cache evaporated on every reload, which is why "we don't
// show roads anymore" used to creep back in mid-trip). Falls back to the
// great-circle distance with a 75 km/h estimate when the network call fails,
// so the itinerary is still informative when fully offline.

const cache = new Map()
const LS_KEY = 'voyage.routes.v1'
const LS_MAX = 500

function key(a, b) {
  // Round to ~10m to keep the cache hit-rate high while still accurate.
  // Endpoints sorted so A→B and B→A share a row, mirroring the backend.
  const r = (n) => n.toFixed(4)
  const p1 = `${r(a.lat)},${r(a.lng)}`
  const p2 = `${r(b.lat)},${r(b.lng)}`
  return p1 < p2 ? `${p1}|${p2}` : `${p2}|${p1}`
}

function haversineKm(a, b) {
  const R = 6371, toRad = (x) => x * Math.PI / 180
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat), lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

// Hydrate the in-memory cache from localStorage so the very first render
// after a reload shows real roads instantly (the SQLite cache on the server
// is the source of truth, but going through a network round-trip would still
// flash the dashed fallback). We persist OSRM hits only — estimates are
// cheap to recompute and shouldn't lock us out of trying the real call.
let lsLoaded = false
function loadFromLocalStorage() {
  if (lsLoaded || typeof localStorage === 'undefined') return
  lsLoaded = true
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return
    const obj = JSON.parse(raw)
    if (obj && typeof obj === 'object') {
      for (const [k, v] of Object.entries(obj)) cache.set(k, v)
    }
  } catch { /* corrupted entry — ignore */ }
}

function saveToLocalStorage() {
  if (typeof localStorage === 'undefined') return
  try {
    // Only persist real OSRM hits (with geometry). Trim to LS_MAX entries
    // by keeping the most recently inserted ones — Map iteration order is
    // insertion order, so slicing the tail does the right thing.
    const entries = []
    for (const [k, v] of cache.entries()) {
      if (v?.source === 'osrm' && v.geometry) entries.push([k, v])
    }
    const trimmed = entries.slice(-LS_MAX)
    localStorage.setItem(LS_KEY, JSON.stringify(Object.fromEntries(trimmed)))
  } catch { /* quota exceeded etc. — drop silently */ }
}

export async function routeLeg(a, b) {
  if (a?.lat == null || b?.lat == null) return null
  loadFromLocalStorage()
  const k = key(a, b)
  if (cache.has(k)) return cache.get(k)

  const km = haversineKm(a, b)
  const fallback = {
    km: Math.round(km),
    minutes: Math.round((km / 75) * 60),
    source: 'estimate',
    geometry: null,
  }

  let result = fallback
  try {
    const params = new URLSearchParams({
      a_lat: String(a.lat),
      a_lng: String(a.lng),
      b_lat: String(b.lat),
      b_lng: String(b.lng),
    })
    const res = await fetch(`/api/route?${params}`, { signal: AbortSignal.timeout(12000) })
    if (res.ok) {
      const data = await res.json()
      if (Number.isFinite(data?.km) && Number.isFinite(data?.minutes)) {
        result = {
          km: data.km,
          minutes: data.minutes,
          source: data.source || 'osrm',
          geometry: Array.isArray(data.geometry) ? data.geometry : null,
        }
      }
    }
  } catch { /* keep fallback */ }

  // Estimates are cheap to recompute and shouldn't lock us out of trying the
  // real OSRM call once the network comes back. Cache only confirmed routes.
  if (result.source === 'osrm') {
    cache.set(k, result)
    saveToLocalStorage()
  }
  return result
}

// Format minutes as "4h 30m" / "45 min".
export function fmtMinutes(min) {
  if (!Number.isFinite(min)) return ''
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m === 0 ? `${h}h` : `${h}h ${String(m).padStart(2, '0')}m`
}
