// Thin fetch wrapper. All endpoints are scoped under /api.

import { readSnapshot, writeSnapshot } from '@/lib/snapshot.js'

async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${text ? ` — ${text}` : ''}`)
  }
  if (res.status === 204) return null
  return res.json()
}

// Fetch a map and shadow-copy the response into IndexedDB. Mutating endpoints
// don't return the full map, so we re-read after writes (see `refreshMap`
// below) to keep the snapshot consistent.
async function fetchAndStash(slug) {
  const data = await request('GET', `/maps/${slug}`)
  // Don't await — storage failures shouldn't block the UI.
  writeSnapshot(slug, data)
  return data
}

export const api = {
  createMap: (payload) => request('POST', '/maps', payload),
  getMap: (slug) => fetchAndStash(slug),
  patchMap: async (slug, payload) => {
    const out = await request('PATCH', `/maps/${slug}`, payload)
    writeSnapshot(slug, out)
    return out
  },

  // Snapshot-first load: returns whatever IndexedDB has now (possibly null),
  // and a `refresh` promise that resolves with the fresh server payload.
  // Lets MapView render instantly from disk on every cold start.
  getMapWithSnapshot: async (slug) => {
    const cached = await readSnapshot(slug)
    const refresh = fetchAndStash(slug)
    return { cached, refresh }
  },

  addPoint: (slug, payload) => request('POST', `/maps/${slug}/points`, payload),
  patchPoint: (slug, id, payload) => request('PATCH', `/maps/${slug}/points/${id}`, payload),
  deletePoint: (slug, id) => request('DELETE', `/maps/${slug}/points/${id}`),

  addItineraryDay: (slug, payload) => request('POST', `/maps/${slug}/itinerary`, payload),
  addItineraryDaysBulk: (slug, rows, { replace = false } = {}) =>
    request('POST', `/maps/${slug}/itinerary/bulk${replace ? '?replace=true' : ''}`, rows),
  patchItineraryDay: (slug, id, payload) => request('PATCH', `/maps/${slug}/itinerary/${id}`, payload),
  deleteItineraryDay: (slug, id) => request('DELETE', `/maps/${slug}/itinerary/${id}`),
  clearItinerary: (slug) => request('DELETE', `/maps/${slug}/itinerary`),

  // Re-pull the full map and update the snapshot. Call after a batch of
  // writes when you want the on-disk mirror to reflect the new state — most
  // single-pin/day mutations don't need this since the in-memory state is
  // already merged and the next page load will refresh anyway.
  refreshSnapshot: (slug) => fetchAndStash(slug),
}

// Geocoding goes through our FastAPI proxy (`/api/geocode`, `/api/reverse`)
// which sets a User-Agent, throttles to ≤1 req/s, and shares a 7-day cache —
// hitting Nominatim direct from the browser leads to 429s surfaced as
// opaque CORS errors.

const reverseCache = new Map()
const reverseLabelCache = new Map()
export async function reverseGeocode(lat, lng) {
  const key = `${lat.toFixed(1)},${lng.toFixed(1)}`
  if (reverseCache.has(key)) return reverseCache.get(key)
  try {
    const params = new URLSearchParams({ lat: String(lat), lng: String(lng) })
    if (navigator.language) params.set('lang', navigator.language)
    const res = await fetch(`/api/reverse?${params}`)
    if (!res.ok) throw new Error('reverse ' + res.status)
    const d = await res.json()
    const a = d.address || {}
    const city = a.city || a.town || a.village || a.hamlet || a.county || a.state || a.country || null
    reverseCache.set(key, city)
    if (d.display_name) reverseLabelCache.set(key, d.display_name)
    return city
  } catch {
    reverseCache.set(key, null)
    return null
  }
}

// Same hit as reverseGeocode but returns the full Nominatim `display_name`
// ("Las Vegas, Clark County, Nevada, United States") rather than the short
// city/county-fallback string. Useful when the caller wants context, not a
// label — the plan view's Location column uses this so a stop near Vegas
// reads "Las Vegas, …" instead of just "Clark County".
export async function reverseGeocodeLabel(lat, lng) {
  const key = `${lat.toFixed(1)},${lng.toFixed(1)}`
  if (reverseLabelCache.has(key)) return reverseLabelCache.get(key)
  try {
    const params = new URLSearchParams({ lat: String(lat), lng: String(lng) })
    if (navigator.language) params.set('lang', navigator.language)
    const res = await fetch(`/api/reverse?${params}`)
    if (!res.ok) throw new Error('reverse ' + res.status)
    const d = await res.json()
    const label = d.display_name || null
    reverseLabelCache.set(key, label)
    return label
  } catch {
    reverseLabelCache.set(key, null)
    return null
  }
}

// Try to read a `lat, lng` (or DMS-ish "11° N 80° W") pair from the input. Lets
// users paste raw coordinates into the search box without round-tripping
// through Nominatim.
const COORD_DECIMAL = /^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*$/
const COORD_HEMI = /^\s*(\d+(?:\.\d+)?)\s*°?\s*([NS])\s*[,\s]+\s*(\d+(?:\.\d+)?)\s*°?\s*([EW])\s*$/i
export function parseCoords(input) {
  if (!input) return null
  const m1 = input.match(COORD_DECIMAL)
  if (m1) {
    const lat = parseFloat(m1[1]); const lng = parseFloat(m1[2])
    if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) return { lat, lng }
  }
  const m2 = input.match(COORD_HEMI)
  if (m2) {
    let lat = parseFloat(m2[1]); let lng = parseFloat(m2[3])
    if (m2[2].toUpperCase() === 'S') lat = -lat
    if (m2[4].toUpperCase() === 'W') lng = -lng
    if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) return { lat, lng }
  }
  return null
}

// Forward geocoding via our backend.
//
// `bias` shapes the result ranking:
//   { bbox: [west, south, east, north] }   — soft viewbox (preferred area, hard
//                                             bound when `bounded` is true)
//   { lat, lng, radiusKm }                  — synthesises a bbox around a point
//   null/undefined                          — global search
//
// Throws on upstream rate-limit (429) so callers can surface a helpful message.
export async function geocode(query, bias = null, { bounded = false } = {}) {
  if (!query || query.trim().length < 2) return []
  const coords = parseCoords(query)
  if (coords) {
    return [{
      label: `${coords.lat.toFixed(5)}, ${coords.lng.toFixed(5)}`,
      lat: coords.lat,
      lng: coords.lng,
      importance: 1,
      osmClass: null,
      osmType: null,
      address: null,
    }]
  }
  const params = new URLSearchParams({ q: query })
  const viewbox = biasToViewbox(bias)
  if (viewbox) {
    params.set('viewbox', viewbox)
    if (bounded) params.set('bounded', '1')
  }
  if (navigator.language) params.set('lang', navigator.language)
  const res = await fetch(`/api/geocode?${params}`)
  if (res.status === 429) {
    const err = new Error('Geocoder rate-limited; try again in a moment')
    err.code = 'rate_limited'
    throw err
  }
  if (!res.ok) return []
  const data = await res.json()
  return data
    .map((d) => ({
      label: d.display_name,
      lat: parseFloat(d.lat),
      lng: parseFloat(d.lon),
      importance: parseFloat(d.importance) || 0,
      osmClass: d.class || null,
      osmType: d.type || null,
      address: d.address || null,
    }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 6)
}

// Translate a flexible `bias` argument to a Nominatim `viewbox` string
// (`west,north,east,south`). Returns null when the input is empty.
function biasToViewbox(bias) {
  if (!bias) return null
  if (Array.isArray(bias.bbox) && bias.bbox.length === 4) {
    const [w, s, e, n] = bias.bbox
    return `${w},${n},${e},${s}`
  }
  if (Number.isFinite(bias.lat) && Number.isFinite(bias.lng)) {
    const r = Number.isFinite(bias.radiusKm) ? bias.radiusKm : 800
    // 1° lat ≈ 111 km. Longitude shrinks toward the poles.
    const dLat = r / 111
    const dLng = r / (111 * Math.max(0.2, Math.cos(bias.lat * Math.PI / 180)))
    const w = bias.lng - dLng, e = bias.lng + dLng
    const s = bias.lat - dLat, n = bias.lat + dLat
    return `${w},${n},${e},${s}`
  }
  return null
}

// Upload an image file to the backend. Returns { url, thumb_url }.
// Uses raw fetch (not `request`) because the body is multipart, not JSON.
export async function uploadImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/api/uploads/image', { method: 'POST', body: fd })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`Upload failed (${res.status})${detail ? `: ${detail}` : ''}`)
  }
  return res.json() // { url, thumb_url }
}

// Map an OSM class/type pair to one of our pin categories. Returns null when
// nothing fits (callers default to 'note').
const OSM_CATEGORY_RULES = [
  { match: ({ c, t }) => c === 'tourism' && /^(hotel|hostel|motel|guest_house|chalet|apartment|caravan_site)$/.test(t), cat: 'stay' },
  { match: ({ c, t }) => c === 'tourism' && /camp/.test(t || ''), cat: 'camp' },
  { match: ({ c, t }) => c === 'tourism' && /^(viewpoint|attraction|artwork|theme_park|museum|gallery)$/.test(t), cat: ({ t }) => t === 'viewpoint' ? 'view' : 'sight' },
  { match: ({ c, t }) => c === 'natural' && /^(peak|volcano|cliff|saddle|cape|water|beach)$/.test(t), cat: 'view' },
  { match: ({ c }) => c === 'historic', cat: 'sight' },
  { match: ({ c, t }) => c === 'amenity' && /^(restaurant|fast_food|food_court|ice_cream|biergarten)$/.test(t), cat: 'food' },
  { match: ({ c, t }) => c === 'amenity' && /^(cafe|bar|pub)$/.test(t), cat: 'drink' },
  { match: ({ c, t }) => c === 'amenity' && t === 'fuel', cat: 'transit' },
  { match: ({ c, t }) => c === 'shop' || (c === 'amenity' && /^(marketplace|pharmacy)$/.test(t)), cat: 'shop' },
  { match: ({ c, t }) => c === 'highway' && /^(footway|path|track)$/.test(t), cat: 'trail' },
  { match: ({ c, t }) => c === 'leisure' && /^(park|nature_reserve)$/.test(t), cat: 'view' },
]

export function categoryFromOSM(osmClass, osmType) {
  if (!osmClass) return null
  const ctx = { c: osmClass, t: osmType }
  for (const rule of OSM_CATEGORY_RULES) {
    if (rule.match(ctx)) return typeof rule.cat === 'function' ? rule.cat(ctx) : rule.cat
  }
  return null
}
