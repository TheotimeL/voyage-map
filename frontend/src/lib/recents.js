// Track recently-visited maps in localStorage so the home view can list them.
// Each entry: { slug, title, visitedAt (ISO) }. Most-recent first, capped at 12.

const KEY = 'voyage:recent-maps'
const CAP = 12

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') }
  catch { return [] }
}
function write(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)) } catch { /* private mode */ }
}

export function rememberMap(slug, title) {
  if (!slug) return
  const list = read().filter((m) => m.slug !== slug)
  list.unshift({ slug, title: title || null, visitedAt: new Date().toISOString() })
  write(list.slice(0, CAP))
}

export function forgetMap(slug) {
  write(read().filter((m) => m.slug !== slug))
}

export function recentMaps() {
  return read()
}
