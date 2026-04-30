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
