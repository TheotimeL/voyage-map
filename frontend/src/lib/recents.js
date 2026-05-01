// Track recently-visited maps in localStorage so the home view can list them.
// Each entry: { slug, title, visitedAt, stats?, lastCenter? }.
// Most-recent first, capped at 12.

const KEY = 'voyage:recent-maps'
const CAP = 12

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') }
  catch { return [] }
}
function write(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)) } catch { /* private mode */ }
}

export function rememberMap(slug, title, stats = null, extras = null) {
  if (!slug) return
  const list = read().filter((m) => m.slug !== slug)
  list.unshift({
    slug,
    title: title || null,
    visitedAt: new Date().toISOString(),
    stats: stats || null,
    ...(extras || {}),
  })
  write(list.slice(0, CAP))
}

// Refresh just the stats / extras of an existing entry without touching
// `visitedAt` — used when adding/removing pins on a map already at the top.
export function updateRecentStats(slug, stats, extras = null) {
  if (!slug) return
  const list = read()
  const idx = list.findIndex((m) => m.slug === slug)
  if (idx < 0) return
  list[idx] = { ...list[idx], stats: stats || list[idx].stats, ...(extras || {}) }
  write(list)
}

export function forgetMap(slug) {
  write(read().filter((m) => m.slug !== slug))
}

export function recentMaps() {
  return read()
}
