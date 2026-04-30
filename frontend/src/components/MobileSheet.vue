<template>
  <div
    ref="sheetEl"
    class="mobile-sheet paper"
    :class="['state-' + state]"
    :style="{ '--sheet-h': heightPct + '%' }"
  >
    <div
      class="sheet-handle"
      @pointerdown="onDragStart"
      @pointermove="onDragMove"
      @pointerup="onDragEnd"
      @pointercancel="onDragEnd"
    >
      <span class="handle-bar" />
    </div>
    <slot name="tabs" />
    <div class="sheet-content"><slot /></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const STATES = { peek: 8, half: 50, full: 92 } // % of viewport height
const order = ['peek', 'half', 'full']

const state = ref('peek')
const sheetEl = ref(null)
const heightPct = computed(() => STATES[state.value])

let dragStartY = null
let dragStartPct = null
let dragLivePct = null

function onDragStart(e) {
  dragStartY = e.clientY
  dragStartPct = STATES[state.value]
  dragLivePct = dragStartPct
  e.target.setPointerCapture(e.pointerId)
}
function onDragMove(e) {
  if (dragStartY == null) return
  const dy = dragStartY - e.clientY  // up = positive
  const pct = dragStartPct + (dy / window.innerHeight) * 100
  dragLivePct = Math.max(STATES.peek, Math.min(STATES.full, pct))
  if (sheetEl.value) sheetEl.value.style.setProperty('--sheet-h', `${dragLivePct}%`)
}
function onDragEnd(e) {
  if (dragStartY == null) return
  const target = order
    .map((k) => ({ k, d: Math.abs(STATES[k] - dragLivePct) }))
    .sort((a, b) => a.d - b.d)[0].k
  state.value = target
  dragStartY = null
  if (sheetEl.value) sheetEl.value.style.removeProperty('--sheet-h')
  e.target.releasePointerCapture?.(e.pointerId)
}

defineExpose({ setState: (s) => { if (STATES[s]) state.value = s } })
</script>

<style scoped>
.mobile-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: var(--sheet-h, 8%);
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--vermillion);
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.08);
  z-index: 800;
  transition: height 220ms ease;
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.mobile-sheet.state-peek { transition-duration: 180ms; }
.sheet-handle {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
}
.sheet-handle:active { cursor: grabbing; }
.handle-bar {
  width: 44px;
  height: 4px;
  border-radius: 2px;
  background: var(--ink-faded);
}
.sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem 1rem 1rem;
}
</style>
