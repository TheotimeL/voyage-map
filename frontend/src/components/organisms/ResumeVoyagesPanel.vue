<template>
  <div class="resume-root" :class="{ open }">
    <!-- Always-visible left-edge handle. Click toggles the drawer. -->
    <button
      class="handle paper"
      type="button"
      :aria-expanded="open"
      :title="open ? 'Hide recent voyages' : 'Show recent voyages'"
      @click="open = !open"
    >
      <span class="handle-arrow" aria-hidden="true">{{ open ? '◂' : '▸' }}</span>
      <span class="handle-label mono">Voyages</span>
      <span v-if="recents.length" class="handle-count mono">{{ recents.length }}</span>
    </button>

    <Transition name="drawer">
      <aside v-if="open" class="drawer paper" role="dialog" aria-label="Recent voyages">
        <header class="drawer-head">
          <span class="eyebrow">Resume a voyage</span>
          <button
            class="drawer-close"
            type="button"
            title="Close"
            @click="open = false"
          >×</button>
        </header>

        <ul v-if="recents.length" class="recents-list">
          <li v-for="r in recents" :key="r.slug" class="recent-card">
            <router-link
              :to="{ name: 'map', params: { slug: displaySlug(r) } }"
              class="recent-link"
              :title="`Open /m/${displaySlug(r)}`"
              @click="open = false"
            >
              <span class="recent-title">{{ r.title || 'Untitled voyage' }}</span>
              <span v-if="r.stats" class="recent-stats mono">
                <template v-if="r.stats.days">{{ r.stats.days }} day{{ r.stats.days === 1 ? '' : 's' }} · </template>
                <template v-if="r.stats.trails">{{ r.stats.trails }} trail{{ r.stats.trails === 1 ? '' : 's' }} · </template>
                {{ r.stats.points }} pin{{ r.stats.points === 1 ? '' : 's' }}
              </span>
              <span class="recent-meta mono">{{ relTime(r.visitedAt) }}</span>
            </router-link>
            <button
              class="recent-action"
              type="button"
              :title="`Copy share link for ${r.title || 'voyage'}`"
              @click="copyLink(r)"
            >
              {{ copiedSlug === r.slug ? '✓' : '⧉' }}
            </button>
            <button
              class="recent-forget"
              type="button"
              :title="`Remove ${r.title || 'voyage'} from this list`"
              @click="$emit('forget', r.slug)"
            >×</button>
          </li>
        </ul>
        <p v-else class="empty mono">No voyages yet — your recent maps will appear here.</p>
      </aside>
    </Transition>

    <!-- Backdrop catches outside clicks to dismiss the drawer. -->
    <div v-if="open" class="backdrop" @click="open = false"></div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { buildMapSlug } from '@/lib/slug.js'

defineProps({
  recents: { type: Array, default: () => [] },
})
defineEmits(['forget'])

const open = ref(false)
const copiedSlug = ref(null)

function displaySlug(r) { return buildMapSlug(r) }

async function copyLink(r) {
  try {
    const display = buildMapSlug(r)
    await navigator.clipboard.writeText(`${window.location.origin}/m/${display}`)
    copiedSlug.value = r.slug
    setTimeout(() => { if (copiedSlug.value === r.slug) copiedSlug.value = null }, 1400)
  } catch { /* no clipboard permission */ }
}

function relTime(iso) {
  if (!iso) return ''
  const ms = Date.now() - new Date(iso).getTime()
  const min = Math.floor(ms / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} hr ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d} day${d === 1 ? '' : 's'} ago`
  const w = Math.floor(d / 7)
  if (w < 5) return `${w} wk ago`
  return new Date(iso).toLocaleDateString()
}
</script>

<style scoped>
.resume-root { position: relative; }

/* Handle pinned to the left edge of the viewport ----------------- */
.handle {
  position: fixed;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.7rem 0.4rem;
  border: 1.5px solid var(--ink);
  border-left: none;
  border-radius: 0 6px 6px 0;
  background: var(--paper);
  box-shadow: 3px 3px 0 var(--ink);
  cursor: pointer;
  font-family: var(--mono);
  color: var(--ink);
  transition: transform 220ms ease, box-shadow 120ms ease;
}
.handle:hover { box-shadow: 4px 4px 0 var(--ink); }
/* When the drawer is open, slide the handle out of the way at the drawer edge. */
.resume-root.open .handle {
  transform: translateY(-50%) translateX(320px);
  box-shadow: none;
}
.handle-arrow {
  font-size: 0.9rem;
  line-height: 1;
  color: var(--vermillion);
}
.handle-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-size: 0.66rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}
.handle-count {
  font-size: 0.66rem;
  color: var(--ink-faded);
  letter-spacing: 0.06em;
}

/* Drawer --------------------------------------------------------- */
.drawer {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: min(320px, 88vw);
  z-index: 31;
  border-right: 1.5px solid var(--ink);
  box-shadow: 6px 0 0 var(--ink);
  padding: 1.2rem 1rem 1.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  overflow-y: auto;
}
.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 0.6rem;
}
.drawer-close {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.2rem;
}
.drawer-close:hover { color: var(--vermillion); }

/* Recents list (stacked vertically inside the narrow drawer) ----- */
.recents-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.recent-card {
  display: flex;
  align-items: stretch;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--paper);
  overflow: hidden;
  transition: transform 80ms ease, box-shadow 120ms ease;
}
.recent-card:hover { transform: translate(-2px, -2px); box-shadow: 4px 4px 0 var(--ink); }
.recent-link {
  flex: 1;
  display: grid;
  gap: 0.15rem;
  padding: 0.65rem 0.7rem;
  color: var(--ink);
  text-decoration: none;
  min-width: 0;
}
.recent-title {
  font-family: var(--display);
  font-size: 1rem;
  line-height: 1.15;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.recent-stats { font-size: 0.7rem; color: var(--ink-soft); letter-spacing: 0.04em; }
.recent-meta { font-size: 0.68rem; color: var(--ink-faded); letter-spacing: 0.08em; }
.recent-action,
.recent-forget {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.55rem;
  border-left: 1px dashed var(--cream-edge);
  display: grid;
  place-items: center;
  min-width: 2rem;
}
.recent-action:hover,
.recent-forget:hover { color: var(--vermillion); background: var(--cream); }

.empty {
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  color: var(--ink-faded);
  text-align: center;
  padding: 1.5rem 0.5rem;
}

/* Backdrop ------------------------------------------------------- */
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 29;
  background: rgba(20, 20, 20, 0.18);
  backdrop-filter: blur(1px);
}

/* Slide-in transition ------------------------------------------- */
.drawer-enter-active,
.drawer-leave-active { transition: transform 220ms ease, opacity 220ms ease; }
.drawer-enter-from,
.drawer-leave-to { transform: translateX(-100%); opacity: 0; }
</style>
