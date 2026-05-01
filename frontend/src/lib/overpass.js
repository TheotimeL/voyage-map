export const SURVIVAL_KINDS = [
  { key: 'water',  label: 'Water',  icon: '💧' },
  { key: 'dump',   label: 'Dump',   icon: '🚐' },
  { key: 'toilet', label: 'Toilet', icon: '🚻' },
  { key: 'trash',  label: 'Trash',  icon: '🗑' },
  { key: 'shower', label: 'Shower', icon: '🚿' },
]
const ICONS = Object.fromEntries(SURVIVAL_KINDS.map((k) => [k.key, k.icon]))

export function classifyKind(tags = {}) {
  if (tags.amenity === 'drinking_water') return 'water'
  if (tags.amenity === 'waste_disposal' || tags.amenity === 'recycling') return 'trash'
  if (tags.sanitary_dump_station === 'yes' || tags.amenity === 'sanitary_dump_station') return 'dump'
  if (tags.amenity === 'toilets') return 'toilet'
  if (tags.amenity === 'shower' || tags.shower === 'yes') return 'shower'
  return null
}

export function mapElement(e) {
  const kind = classifyKind(e.tags)
  if (!kind || e.lat == null) return null
  return {
    id: `${e.type}/${e.id}`,
    lat: e.lat,
    lng: e.lon,
    kind,
    icon: ICONS[kind],
    label: e.tags?.name || `${kind}`,
  }
}

export async function fetchSurvival(bounds, kinds = null) {
  const { _southWest: sw, _northEast: ne } = bounds
  const params = new URLSearchParams({
    south: sw.lat, west: sw.lng, north: ne.lat, east: ne.lng, kind: 'survival',
  })
  if (kinds && kinds.length) params.set('kinds', kinds.join(','))
  const res = await fetch(`/api/overpass?${params}`)
  if (!res.ok) throw new Error('Overpass query failed.')
  const data = await res.json()
  return (data.elements || []).map(mapElement).filter(Boolean)
}

// Trails near a point: query a bbox roughly `radiusKm` around the centre,
// then filter to results that look like hikeable routes.
export async function fetchTrails(centerLat, centerLng, radiusKm = 12) {
  const dLat = radiusKm / 111
  const dLng = radiusKm / (111 * Math.max(0.2, Math.cos(centerLat * Math.PI / 180)))
  const params = new URLSearchParams({
    south: centerLat - dLat,
    west: centerLng - dLng,
    north: centerLat + dLat,
    east: centerLng + dLng,
    kind: 'trails',
  })
  const res = await fetch(`/api/overpass?${params}`)
  if (!res.ok) throw new Error('Could not fetch trails.')
  const data = await res.json()
  const out = []
  for (const e of data.elements || []) {
    const tags = e.tags || {}
    const name = tags.name || tags['name:en'] || tags['name:fr']
    if (!name) continue
    const lat = e.lat ?? e.center?.lat
    const lng = e.lon ?? e.center?.lon
    if (lat == null || lng == null) continue
    out.push({
      id: `${e.type}/${e.id}`,
      lat,
      lng,
      name,
      kind: tags.route || (tags.sac_scale ? 'hiking' : 'path'),
      sac: tags.sac_scale || null,
      distance: tags.distance ? parseFloat(tags.distance) : null,
      ref: tags.ref || null,
    })
  }
  // Dedupe by name only — long routes often appear as both relation and way
  // with slightly different centres, so coord rounding wasn't enough. Prefer
  // the entry with richer tags (sac/distance/ref) when collapsing.
  const seen = new Map()
  function score(t) {
    return (t.sac ? 2 : 0) + (t.distance ? 1 : 0) + (t.ref ? 0.5 : 0)
  }
  for (const t of out) {
    const k = t.name
    const prev = seen.get(k)
    if (!prev || score(t) > score(prev)) seen.set(k, t)
  }
  return [...seen.values()].slice(0, 30)
}
