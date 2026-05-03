// UI-state preferences (separate from `lib/settings.js`, which is units/locale).
// Same reactive + localStorage pattern. Lives here so journal-tree expansion,
// future offline-saving toggle, and other UI prefs share one storage key
// without polluting the unit-formatter contract.

import { reactive, watch } from 'vue'

const STORAGE_KEY = 'voyage-map.uiSettings'

function loadInitial() {
  if (typeof localStorage === 'undefined') return { journalExpanded: {} }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { journalExpanded: {} }
    const parsed = JSON.parse(raw)
    return {
      journalExpanded: parsed.journalExpanded && typeof parsed.journalExpanded === 'object'
        ? parsed.journalExpanded
        : {},
    }
  } catch {
    return { journalExpanded: {} }
  }
}

export const uiSettings = reactive(loadInitial())

watch(
  () => ({ journalExpanded: uiSettings.journalExpanded }),
  (next) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* quota / private mode */ }
  },
  { deep: true },
)

// Per-trip helpers — keyed by slug so two trips' journal layouts don't bleed
// into each other. Node keys are caller-defined strings (e.g. `stop:42`,
// `wishlist`).

export function isJournalExpanded(slug, nodeKey, defaultValue = false) {
  const tripState = uiSettings.journalExpanded[slug]
  if (!tripState || !(nodeKey in tripState)) return defaultValue
  return !!tripState[nodeKey]
}

export function setJournalExpanded(slug, nodeKey, expanded) {
  if (!slug) return
  const next = { ...(uiSettings.journalExpanded[slug] || {}) }
  next[nodeKey] = !!expanded
  uiSettings.journalExpanded = { ...uiSettings.journalExpanded, [slug]: next }
}

export function toggleJournalExpanded(slug, nodeKey, defaultValue = false) {
  setJournalExpanded(slug, nodeKey, !isJournalExpanded(slug, nodeKey, defaultValue))
}
