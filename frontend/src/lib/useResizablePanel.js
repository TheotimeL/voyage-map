import { ref } from 'vue'

const STORAGE_KEY = 'detail_panel_width'
const MIN = 320
const MAX = 720
const DEFAULT = 460

// Drag handle width controller for the desktop DetailPanel. Mobile bypasses
// this entirely (the panel goes fullscreen). Width persists to localStorage so
// the user only resizes once.
export function useResizablePanel() {
  const width = ref(readStored() ?? DEFAULT)
  const dragging = ref(false)

  function onPointerDown(e) {
    dragging.value = true
    e.target.setPointerCapture?.(e.pointerId)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'ew-resize'
  }

  function onPointerMove(e) {
    if (!dragging.value) return
    width.value = Math.max(MIN, Math.min(MAX, e.clientX))
  }

  function onPointerUp(e) {
    if (!dragging.value) return
    dragging.value = false
    e.target.releasePointerCapture?.(e.pointerId)
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
    try { localStorage.setItem(STORAGE_KEY, String(width.value)) } catch { /* ignore */ }
  }

  return { width, dragging, onPointerDown, onPointerMove, onPointerUp }
}

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const n = parseInt(raw, 10)
    return Number.isFinite(n) && n >= MIN && n <= MAX ? n : null
  } catch { return null }
}
