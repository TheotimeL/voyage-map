// Shared category list and coord formatters.

export const CATEGORIES = [
  { key: 'camp',    emoji: '🚐', label: 'Camp' },
  { key: 'trail',   emoji: '🥾', label: 'Trail' },
  { key: 'view',    emoji: '🏔️', label: 'View' },
  { key: 'sight',   emoji: '🏛️', label: 'Sight' },
  { key: 'food',    emoji: '🍴', label: 'Food' },
  { key: 'drink',   emoji: '☕', label: 'Drink' },
  { key: 'stay',    emoji: '🛏️', label: 'Stay' },
  { key: 'transit', emoji: '⛽', label: 'Fuel' },
  { key: 'shop',    emoji: '🛒', label: 'Shop' },
  { key: 'note',    emoji: '📍', label: 'Note' },
]

export function parseGPX(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, 'application/xml')
  if (doc.querySelector('parsererror')) throw new Error('Could not parse GPX file.')

  const collect = (sel) => {
    const out = { coords: [], elevations: [] }
    for (const pt of doc.querySelectorAll(sel)) {
      const lat = parseFloat(pt.getAttribute('lat'))
      const lng = parseFloat(pt.getAttribute('lon'))
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue
      out.coords.push([lat, lng])
      const ele = parseFloat(pt.querySelector('ele')?.textContent ?? '')
      out.elevations.push(Number.isFinite(ele) ? ele : null)
    }
    return out
  }

  let parsed = collect('trkpt')
  if (!parsed.coords.length) parsed = collect('rtept')
  if (!parsed.coords.length) parsed = collect('wpt')
  if (!parsed.coords.length) throw new Error('No track or route points found in GPX.')

  const name =
    doc.querySelector('trk > name')?.textContent?.trim() ||
    doc.querySelector('rte > name')?.textContent?.trim() ||
    doc.querySelector('metadata > name')?.textContent?.trim() ||
    null

  return { coords: parsed.coords, elevations: parsed.elevations, name }
}

// Build a minimal GPX <trk> from a coords list so OSM-derived trails (which
// have no elevation, just a polyline) flow through the same renderTrack /
// elevation pipeline as imported GPX files. Keep it tight: one segment, no
// metadata beyond the optional name.
export function coordsToGPX(coords, name) {
  const trkpts = coords
    .map(([lat, lng]) => `<trkpt lat="${lat}" lon="${lng}"/>`)
    .join('')
  const safeName = name ? String(name).replace(/[<>&]/g, '') : ''
  return `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="voyage-map"><trk>${safeName ? `<name>${safeName}</name>` : ''}<trkseg>${trkpts}</trkseg></trk></gpx>`
}

export const TRACK_PALETTE = ['#0a4d5b', '#5e6b3b', '#6b3a5a', '#1f3851', '#a85a2b', '#3b6b8a']

export function trackColor(index) {
  return TRACK_PALETTE[index % TRACK_PALETTE.length]
}

function _toIso(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function todayISO() {
  const d = new Date()
  return _toIso(d.getFullYear(), d.getMonth(), d.getDate())
}

export function openInMaps(lat, lng, label) {
  const dest = `${lat},${lng}`
  const q = label ? `${dest}(${encodeURIComponent(label)})` : dest
  // Universal URL: Web/Android open Google Maps, iOS offers to open native maps via the app banner.
  const url = `https://www.google.com/maps/dir/?api=1&destination=${q}`
  window.open(url, '_blank', 'noopener,noreferrer')
}

export function formatLat(lat) {
  const v = Number(lat)
  if (!Number.isFinite(v)) return ''
  const hemi = v >= 0 ? 'N' : 'S'
  return `${Math.abs(v).toFixed(4)}° ${hemi}`
}

export function formatLng(lng) {
  const v = Number(lng)
  if (!Number.isFinite(v)) return ''
  const hemi = v >= 0 ? 'E' : 'W'
  return `${Math.abs(v).toFixed(4)}° ${hemi}`
}

export function getMyLocation(opts = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by this browser.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) => {
        const msg =
          err.code === 1
            ? 'Location permission denied.'
            : err.code === 2
              ? 'Could not pinpoint your location.'
              : 'Locating timed out.'
        reject(new Error(msg))
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000, ...opts },
    )
  })
}

// First /uploads/ image inline in a markdown note. The thumb URL follows the
// `<name>_thumb.<ext>` convention created by services/storage.py — derived
// instead of stored so we have one source of truth (the markdown).
export function extractMarkerThumb(markdown) {
  if (!markdown) return null
  const m = markdown.match(/!\[[^\]]*\]\((\/uploads\/[^)\s]+)\)/)
  if (!m) return null
  const fullUrl = m[1]
  const thumbUrl = fullUrl.replace(/(\.[^.]+)$/, '_thumb$1')
  return { full_url: fullUrl, thumb_url: thumbUrl }
}

// One-line plain-text preview for compact UI (the today-banner). Strips
// markdown formatting *crudely* — we don't need a real parser for a banner
// snippet, and pulling markdown-it into util.js would bloat early bundles.
export function markdownExcerpt(markdown, maxLen = 120) {
  if (!markdown) return ''
  const stripped = markdown
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')        // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')     // links → keep label
    .replace(/[*_`#>~]+/g, '')                    // emphasis / headings / code
    .replace(/\n+/g, ' ')                         // collapse newlines
    .replace(/[ \t]{3,}/g, '  ')                  // collapse 3+ spaces to two
    .trim()
  return stripped.length > maxLen ? stripped.slice(0, maxLen).trimEnd() + '…' : stripped
}
