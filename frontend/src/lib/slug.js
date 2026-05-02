// URL slug helpers. The canonical id is the 8-char base58 string the
// backend mints (no dashes — see services/slug.py). For nicer-looking
// links we prefix that id with a slugified trip name:
//
//   /m/vegas-sf-van-adventure-S25TjoW5
//
// The backend never sees the prefix — we strip it client-side before any
// API call. Routes still resolve when the URL is just the id (older
// bookmarks, copy-pasted shares from before this change).

const ID_RE = /^[A-Za-z0-9]+$/

// Slugify a free-form title for use in URLs. ASCII-only: anything outside
// [a-z0-9] becomes '-', repeats collapse, and the result is trimmed and
// capped so the final URL stays readable. We keep the cap loose (60 chars);
// the canonical id at the end is what guarantees uniqueness.
export function slugifyName(name) {
  if (!name) return ''
  return String(name)
    .normalize('NFKD')
    // Strip combining marks (accents) so "Café" → "cafe".
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/, '')
}

// Extract the canonical backend id from a route :slug param. Backend slugs
// have no dashes, so the segment after the last '-' is always the id; if
// there's no dash, the param IS the id (legacy /m/S25TjoW5 links).
export function extractId(routeSlug) {
  if (!routeSlug) return ''
  const s = String(routeSlug)
  const idx = s.lastIndexOf('-')
  if (idx < 0) return s
  const tail = s.slice(idx + 1)
  // Defensive: if the tail looks malformed (empty, has invalid chars), fall
  // back to the full string so we don't fabricate a 404.
  return tail && ID_RE.test(tail) ? tail : s
}

// Build the display slug for a map: "{name-slug}-{id}", or just "{id}" when
// the trip is untitled. Accepts either a full map record or { title, slug }.
export function buildMapSlug(map) {
  if (!map) return ''
  const id = map.slug || map.id || ''
  const namePart = slugifyName(map.title)
  if (!namePart || !id) return id
  return `${namePart}-${id}`
}
