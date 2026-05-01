// IndexedDB snapshot of /api/maps/{slug} responses.
//
// The PWA already cached the bare HTTP response in Workbox (StaleWhileRevalidate
// on `/api/maps/...`), but that cache lives inside the service worker — it
// can't be inspected from JS, doesn't survive cache cleanups, and it's a dumb
// blob (no fast lookup, no per-field updates). IndexedDB gives us a
// guaranteed local mirror keyed by slug, so the trip opens instantly from
// disk on every load and stays usable when the van is in a dead zone.
//
// Scope: read-only offline. Writes go through the API as before; if a write
// fails, the user gets the existing toast / error UI. A real write-back queue
// is out of scope for this iteration — most "I want to add a pin offline"
// flows are rare on the road relative to "I want to look at the map I
// already planned".

const DB_NAME = 'voyage-snapshot'
const STORE = 'maps'
const VERSION = 1

let _dbPromise = null

function openDB() {
  if (_dbPromise) return _dbPromise
  if (typeof indexedDB === 'undefined') return Promise.resolve(null)
  _dbPromise = new Promise((resolve) => {
    const req = indexedDB.open(DB_NAME, VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'slug' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    // Private browsing / disabled storage / quota — fail soft so the rest of
    // the app still works against the network.
    req.onerror = () => {
      console.warn('voyage-snapshot: indexedDB.open failed', req.error)
      resolve(null)
    }
  })
  return _dbPromise
}

async function withStore(mode, fn) {
  const db = await openDB()
  if (!db) return null
  return new Promise((resolve) => {
    const tx = db.transaction(STORE, mode)
    const store = tx.objectStore(STORE)
    const result = fn(store)
    tx.oncomplete = () => resolve(result?.value ?? result ?? null)
    tx.onerror = () => {
      console.warn('voyage-snapshot: tx error', tx.error)
      resolve(null)
    }
    tx.onabort = () => {
      console.warn('voyage-snapshot: tx aborted', tx.error)
      resolve(null)
    }
  })
}

// Read the cached payload for `slug`. Returns null when there's no snapshot
// or IndexedDB is unavailable (private mode, etc.).
export async function readSnapshot(slug) {
  if (!slug) return null
  const db = await openDB()
  if (!db) return null
  return new Promise((resolve) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(slug)
    req.onsuccess = () => {
      const row = req.result
      resolve(row?.payload || null)
    }
    req.onerror = () => {
      console.warn('voyage-snapshot: read failed', req.error)
      resolve(null)
    }
  })
}

// Persist the latest server response. Writes happen in the background — we
// never await them in the hot path so the UI never stalls on storage.
// Callers may pass a Vue reactive proxy (the live `mapData.value` from
// MapView's deep watcher); IndexedDB's structured-clone refuses proxies, so
// we round-trip through JSON to land on a plain object.
export async function writeSnapshot(slug, payload) {
  if (!slug || !payload) return
  let plain
  try { plain = JSON.parse(JSON.stringify(payload)) }
  catch (e) {
    console.warn('voyage-snapshot: payload not serialisable', e)
    return
  }
  await withStore('readwrite', (store) => {
    store.put({ slug, payload: plain, savedAt: Date.now() })
  })
}

// True if the device probably can't reach the API. Used to decide whether to
// surface the "offline (showing saved copy)" badge. `navigator.onLine` is a
// hint, not a guarantee — the actual loader still tries the network.
export function isLikelyOffline() {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}
