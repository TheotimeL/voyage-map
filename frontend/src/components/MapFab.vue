<template>
  <div class="map-fab-wrap">
    <Transition name="fab-pop">
      <div v-if="open && !armed" class="fab-menu paper" role="menu">
        <p class="fab-menu-eyebrow mono">Add to trip</p>
        <button type="button" class="fab-menu-item" @click="pick('stop')">
          <span class="fab-menu-icon" aria-hidden="true">▣</span>
          <span class="fab-menu-text">
            <strong>Add a stop</strong>
            <em>A place you'll sleep or hang out</em>
          </span>
        </button>
        <button type="button" class="fab-menu-item" @click="pick('pin')">
          <span class="fab-menu-icon" aria-hidden="true">⌖</span>
          <span class="fab-menu-text">
            <strong>Drop a pin</strong>
            <em>Click anywhere on the map</em>
          </span>
        </button>
        <button type="button" class="fab-menu-item" @click="pick('search')">
          <span class="fab-menu-icon" aria-hidden="true">⚲</span>
          <span class="fab-menu-text">
            <strong>Search a place</strong>
            <em>Find by name</em>
          </span>
        </button>
      </div>
    </Transition>
    <button class="map-fab" type="button" :title="armedTitle" :class="{ armed }" @click="onClick">
      <span class="fab-glyph">{{ armed ? '×' : (open ? '×' : '+') }}</span>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  // armed === true while drop-mode is engaged (next map click drops a pin).
  // The popover hides itself in that case so the × on the FAB is unambiguous.
  armed: { type: Boolean, default: false },
})
const emit = defineEmits(['drop', 'search', 'add-stop'])

const open = ref(false)
const armedTitle = computed(() =>
  props.armed ? 'Cancel — click × to exit drop-mode' : 'Add a pin, place, stop, or trail',
)

function onClick() {
  if (props.armed) {
    // Cancel drop-mode without re-opening the menu.
    emit('drop', { cancel: true })
    return
  }
  open.value = !open.value
}

function pick(kind) {
  open.value = false
  if (kind === 'pin') emit('drop', { cancel: false })
  else if (kind === 'search') emit('search')
  else if (kind === 'stop') emit('add-stop')
}

// Click-outside to close the menu.
function onDocClick(e) {
  if (!open.value) return
  const root = e.target.closest?.('.map-fab-wrap')
  if (!root) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))
</script>

<style scoped>
.map-fab-wrap {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 850;
}
.map-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--vermillion);
  color: var(--paper);
  border: none;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  transition: transform 90ms ease, background 120ms ease;
}
.map-fab:hover { transform: scale(1.05); }
.map-fab.armed { background: var(--ink); box-shadow: 0 0 0 4px var(--vermillion), 0 2px 8px rgba(0,0,0,0.3); }
.fab-glyph { font-size: 1.6rem; line-height: 1; font-weight: 600; }

.fab-menu {
  position: absolute;
  bottom: 70px;
  right: 0;
  width: 260px;
  padding: 0.6rem 0.5rem 0.5rem;
  display: grid;
  gap: 0.2rem;
  border-radius: 6px;
  box-shadow: 0 12px 24px rgba(0,0,0,0.18);
}
.fab-menu-eyebrow {
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0 0.4rem 0.2rem;
}
.fab-menu-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.6rem;
  align-items: center;
  background: transparent;
  border: none;
  padding: 0.5rem 0.55rem;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--ink);
}
.fab-menu-item:hover { background: var(--cream); }
.fab-menu-icon { font-size: 1.3rem; }
.fab-menu-text { display: grid; gap: 0.05rem; }
.fab-menu-text strong { font-size: 0.95rem; font-weight: 600; }
.fab-menu-text em {
  font-style: normal;
  font-size: 0.74rem;
  color: var(--ink-faded);
  letter-spacing: 0.02em;
}

.fab-pop-enter-active, .fab-pop-leave-active { transition: opacity 140ms ease, transform 140ms ease; }
.fab-pop-enter-from, .fab-pop-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 720px) {
  .map-fab-wrap { bottom: 80px; }
  .fab-menu { width: 260px; padding: 0.7rem 0.55rem 0.6rem; }
  /* Each menu row hits at least a 56-px tap area. The display strong is
     bumped to 1.05rem; em descriptions stay smaller so the row reads as
     "label · explanation" instead of two equal lines. */
  .fab-menu-item { padding: 0.7rem 0.6rem; min-height: 56px; }
  .fab-menu-icon { font-size: 1.45rem; }
  .fab-menu-text strong { font-size: 1.05rem; }
  .fab-menu-text em { font-size: 0.78rem; }
}
</style>
