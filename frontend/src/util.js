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

export const TRACK_PALETTE = ['#0a4d5b', '#5e6b3b', '#6b3a5a', '#1f3851', '#a85a2b', '#3b6b8a']

export function trackColor(index) {
  return TRACK_PALETTE[index % TRACK_PALETTE.length]
}

// French / English month parsing for pasted itineraries.
const MONTH_LOOKUP = {
  janvier: 0, jan: 0, january: 0,
  'février': 1, fevrier: 1, fev: 1, 'fév': 1, feb: 1, february: 1,
  mars: 2, mar: 2, march: 2,
  avril: 3, avr: 3, april: 3, apr: 3,
  mai: 4, may: 4,
  juin: 5, june: 5, jun: 5,
  juillet: 6, juil: 6, july: 6, jul: 6,
  'août': 7, aout: 7, august: 7, aug: 7,
  septembre: 8, sept: 8, september: 8, sep: 8,
  octobre: 9, oct: 9, october: 9,
  novembre: 10, nov: 10, november: 10,
  'décembre': 11, decembre: 11, dec: 11, december: 11,
}

function _toIso(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function parseFlexibleDate(text, defaultYear) {
  if (!text) return null
  const s = String(text).trim().toLowerCase()
  // ISO YYYY-MM-DD
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  if (m) return _toIso(+m[1], +m[2] - 1, +m[3])
  // DD/MM/YYYY or DD-MM-YYYY
  m = s.match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$/)
  if (m) {
    const y = m[3].length === 2 ? 2000 + +m[3] : +m[3]
    return _toIso(y, +m[2] - 1, +m[1])
  }
  // "samedi 9 mai" / "9 mai" / "may 9" / "May 9, 2026"
  m = s.match(/(\d{1,2})\s+([a-zàâéèêïô.]+)/i) || s.match(/([a-zàâéèêïô.]+)\s+(\d{1,2})/i)
  if (!m) return null
  const a = m[1], b = m[2]
  const dayPart = /^\d/.test(a) ? a : b
  const monPart = /^\d/.test(a) ? b : a
  const day = parseInt(dayPart, 10)
  const monthKey = monPart.replace(/\.$/, '')
  const month = MONTH_LOOKUP[monthKey]
  if (month == null) return null
  const yearMatch = s.match(/(20\d{2})/)
  const year = yearMatch ? +yearMatch[1] : (defaultYear || new Date().getFullYear())
  return _toIso(year, month, day)
}

export function parseItineraryPaste(text, defaultYear) {
  const lines = String(text).replace(/\r/g, '').trim().split('\n').filter((l) => l.trim())
  if (!lines.length) return []
  const sep = lines[0].includes('\t') ? '\t' : lines[0].includes(';') ? ';' : ','
  const rows = lines.map((l) => l.split(sep).map((c) => c.trim()))
  const first = rows[0].map((c) => c.toLowerCase())
  const hasHeader = first.some((c) => c.includes('date') || c.includes('lieu') || c.includes('jour'))
  let dateIdx = 0, dodoIdx = 1, lieuIdx = 2, planIdx = 3, notesIdx = 4
  if (hasHeader) {
    const findIdx = (test) => first.findIndex(test)
    dateIdx = findIdx((c) => c.includes('date') || c.startsWith('jour'))
    dodoIdx = findIdx((c) => /dodo|hébergement|hebergement|hotel|sleep|stay/.test(c))
    lieuIdx = findIdx((c) => c === 'lieu' || c.startsWith('lieu '))
    planIdx = findIdx((c) => c.includes('prévu') || c.includes('prevu') || c.includes('planned'))
    notesIdx = findIdx((c) => c.includes('note'))
    rows.shift()
  }
  const out = []
  for (const r of rows) {
    const dateText = dateIdx >= 0 ? r[dateIdx] : ''
    if (!dateText) continue
    const date = parseFlexibleDate(dateText, defaultYear)
    if (!date) continue
    const dodo = dodoIdx >= 0 ? (r[dodoIdx] || '') : ''
    const lieu = lieuIdx >= 0 ? (r[lieuIdx] || '') : ''
    const plan = planIdx >= 0 ? (r[planIdx] || '') : ''
    const label = (lieu || plan || dodo || '').trim()
    const noteParts = []
    if (dodo && dodo !== label) noteParts.push(dodo)
    const notesCol = notesIdx >= 0 ? (r[notesIdx] || '') : ''
    if (notesCol) noteParts.push(notesCol)
    out.push({ date, label: label || null, notes: noteParts.join(' · ') || null })
  }
  return out
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
