// Thin fetch wrapper. All endpoints are scoped under /api.

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

export const api = {
  createMap: (payload) => request('POST', '/maps', payload),
  getMap: (slug) => request('GET', `/maps/${slug}`),
  patchMap: (slug, payload) => request('PATCH', `/maps/${slug}`, payload),

  addPoint: (slug, payload) => request('POST', `/maps/${slug}/points`, payload),
  patchPoint: (slug, id, payload) => request('PATCH', `/maps/${slug}/points/${id}`, payload),
  deletePoint: (slug, id) => request('DELETE', `/maps/${slug}/points/${id}`),

  addItineraryDay: (slug, payload) => request('POST', `/maps/${slug}/itinerary`, payload),
  patchItineraryDay: (slug, id, payload) => request('PATCH', `/maps/${slug}/itinerary/${id}`, payload),
  deleteItineraryDay: (slug, id) => request('DELETE', `/maps/${slug}/itinerary/${id}`),
  clearItinerary: (slug) => request('DELETE', `/maps/${slug}/itinerary`),
}

// Nominatim geocoding (free OSM service). Throttle to be polite.
let lastGeocode = 0
export async function geocode(query) {
  if (!query || query.trim().length < 2) return []
  const now = Date.now()
  const wait = Math.max(0, 800 - (now - lastGeocode))
  if (wait > 0) await new Promise((r) => setTimeout(r, wait))
  lastGeocode = Date.now()
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=8&dedupe=1&q=${encodeURIComponent(query)}`
  const res = await fetch(url, { headers: { 'Accept-Language': navigator.language || 'en' } })
  if (!res.ok) return []
  const data = await res.json()
  return data
    .map((d) => ({
      label: d.display_name,
      lat: parseFloat(d.lat),
      lng: parseFloat(d.lon),
      importance: parseFloat(d.importance) || 0,
    }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 6)
}
