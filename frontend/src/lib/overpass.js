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

// Walk Overpass `geometry` shapes (way.geometry = list of {lat, lon}; relation
// has `members[].geometry`) into a flat [[lat, lng], …] polyline plus a rough
// km length. Returns { coords, km } or null when geometry is unusable.
function geomToPolyline(e) {
  const segments = []
  if (Array.isArray(e.geometry) && e.geometry.length > 1) {
    segments.push(e.geometry.map((g) => [g.lat, g.lon]))
  } else if (Array.isArray(e.members)) {
    for (const m of e.members) {
      if (Array.isArray(m.geometry) && m.geometry.length > 1) {
        segments.push(m.geometry.map((g) => [g.lat, g.lon]))
      }
    }
  }
  if (!segments.length) return null
  // Concat in member-order so the polyline reads end-to-end. Routes with gaps
  // are still drawn — the visual jump is informative ("this is a relation").
  const coords = [].concat(...segments)
  let km = 0
  for (let i = 1; i < coords.length; i++) {
    km += haversineKm(coords[i - 1], coords[i])
  }
  return { coords, km }
}

function haversineKm([la1, ln1], [la2, ln2]) {
  const R = 6371
  const toRad = (d) => d * Math.PI / 180
  const dLat = toRad(la2 - la1)
  const dLng = toRad(ln2 - ln1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(la1)) * Math.cos(toRad(la2)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

// Plain-language difficulty from SAC scale. Hiding the OSM jargon helps
// non-mountaineers skim the list.
const SAC_PLAIN = {
  hiking: 'easy',
  mountain_hiking: 'moderate',
  demanding_mountain_hiking: 'hard',
  alpine_hiking: 'alpine',
  demanding_alpine_hiking: 'alpine+',
  difficult_alpine_hiking: 'expert',
}
export function sacPlain(sac) { return sac ? (SAC_PLAIN[sac] || sac) : null }

// Trails near a point: query a bbox roughly `radiusKm` around the centre,
// then filter to results that look like hikeable routes. Includes derived
// length (from geometry) and distance from the search origin so the UI can
// sort + label.
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
    const poly = geomToPolyline(e)
    let lat = e.lat ?? e.center?.lat
    let lng = e.lon ?? e.center?.lon
    if (poly && (lat == null || lng == null)) {
      // Derive a representative coord from the polyline midpoint.
      const mid = poly.coords[Math.floor(poly.coords.length / 2)]
      lat = mid[0]
      lng = mid[1]
    }
    if (lat == null || lng == null) continue
    const distFromOrigin = haversineKm([centerLat, centerLng], [lat, lng])
    // Trail's own length: tags.distance (km) is authoritative when present
    // (curators add it for marked routes); otherwise fall back to summing
    // the geometry, rounded to one decimal.
    const declaredKm = tags.distance ? parseFloat(tags.distance) : null
    const computedKm = poly ? Math.round(poly.km * 10) / 10 : null
    const lengthKm = declaredKm || computedKm
    out.push({
      id: `${e.type}/${e.id}`,
      lat,
      lng,
      name,
      kind: tags.route || (tags.sac_scale ? 'hiking' : 'path'),
      sac: tags.sac_scale || null,
      sacPlain: sacPlain(tags.sac_scale),
      lengthKm,
      distFromOrigin: Math.round(distFromOrigin * 10) / 10,
      ref: tags.ref || null,
      coords: poly?.coords || null,
    })
  }
  // Dedupe by name only — long routes often appear as both relation and way
  // with slightly different centres, so coord rounding wasn't enough. Prefer
  // the entry with richer data (length/sac/geometry/ref) when collapsing.
  const seen = new Map()
  function score(t) {
    return (t.sac ? 2 : 0) + (t.lengthKm ? 1 : 0) + (t.coords ? 1 : 0) + (t.ref ? 0.5 : 0)
  }
  for (const t of out) {
    const k = t.name
    const prev = seen.get(k)
    if (!prev || score(t) > score(prev)) seen.set(k, t)
  }
  // Sort by distance from origin so the closest options are at the top.
  return [...seen.values()]
    .sort((a, b) => a.distFromOrigin - b.distFromOrigin)
    .slice(0, 30)
}
