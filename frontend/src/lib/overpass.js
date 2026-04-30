export function classifyKind(tags = {}) {
  if (tags.amenity === 'drinking_water') return 'water'
  if (tags.amenity === 'waste_disposal') return 'trash'
  if (tags.sanitary_dump_station === 'yes') return 'dump'
  if (tags.amenity === 'toilets') return 'toilet'
  return null
}

const ICONS = {
  water: '💧',
  trash: '🗑',
  dump: '🚐',
  toilet: '🚻',
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

export async function fetchSurvival(bounds) {
  const { _southWest: sw, _northEast: ne } = bounds
  const params = new URLSearchParams({
    south: sw.lat, west: sw.lng, north: ne.lat, east: ne.lng, kind: 'survival',
  })
  const res = await fetch(`/api/overpass?${params}`)
  if (!res.ok) throw new Error('Overpass query failed.')
  const data = await res.json()
  return (data.elements || []).map(mapElement).filter(Boolean)
}
