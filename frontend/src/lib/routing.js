// OSRM public demo routing — driving distance + duration between two points.
//
// The demo server is rate-limited and best-effort, so we cache aggressively
// in-memory and fall back to the great-circle distance with a 75 km/h
// estimate when the network call fails.

const OSRM = 'https://router.project-osrm.org/route/v1/driving'
const cache = new Map()

function key(a, b) {
  // Round to ~10m to keep the cache hit-rate high while still accurate.
  const r = (n) => n.toFixed(4)
  return `${r(a.lat)},${r(a.lng)}|${r(b.lat)},${r(b.lng)}`
}

function haversineKm(a, b) {
  const R = 6371, toRad = (x) => x * Math.PI / 180
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat), lat2 = toRad(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export async function routeLeg(a, b) {
  if (a?.lat == null || b?.lat == null) return null
  const k = key(a, b)
  if (cache.has(k)) return cache.get(k)
  // Optimistic fallback in case the network is slow / blocked.
  const km = haversineKm(a, b)
  const fallback = {
    km: Math.round(km),
    minutes: Math.round((km / 75) * 60),
    source: 'estimate',
    geometry: null,
  }

  let result = fallback
  try {
    // overview=simplified keeps the geometry tractable for trip-scale views;
    // geometries=geojson is easiest to feed straight into Leaflet.
    const url = `${OSRM}/${a.lng},${a.lat};${b.lng},${b.lat}?overview=simplified&geometries=geojson&steps=false`
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
    if (res.ok) {
      const data = await res.json()
      const r = data?.routes?.[0]
      if (r && Number.isFinite(r.distance) && Number.isFinite(r.duration)) {
        const coords = r.geometry?.coordinates
        result = {
          km: Math.round(r.distance / 1000),
          minutes: Math.round(r.duration / 60),
          source: 'osrm',
          // OSRM returns [lng, lat]; Leaflet expects [lat, lng].
          geometry: Array.isArray(coords) ? coords.map(([lng, lat]) => [lat, lng]) : null,
        }
      }
    }
  } catch { /* keep fallback */ }
  cache.set(k, result)
  return result
}

// Format minutes as "4h 30" / "45min".
export function fmtMinutes(min) {
  if (!Number.isFinite(min)) return ''
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m === 0 ? `${h}h` : `${h}h ${String(m).padStart(2, '0')}`
}
