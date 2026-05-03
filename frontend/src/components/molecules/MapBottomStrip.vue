<template>
  <div
    v-if="banner && !dismissed"
    class="bottom-strip"
    :class="{ 'is-live': banner.live, 'is-future': !banner.live }"
  >
    <button
      class="strip-main"
      type="button"
      :title="`Center on ${banner.day.label || 'this day'}`"
      @click="$emit('go-day', banner.day)"
    >
      <span class="strip-tag mono">{{ banner.tag }}</span>
      <span class="strip-text">{{ banner.text }}</span>
    </button>

    <div v-if="visibleWx.length" class="strip-meta strip-wx mono">
      <span
        v-for="wx in visibleWx"
        :key="wx.date"
        class="strip-wx-cell"
        :class="{ 'is-active': wx.isActive, 'is-faded': !wx.forecast }"
        :title="`Forecast for ${wx.date}`"
      >
        <span v-if="visibleWx.length > 1" class="strip-wx-tag">{{ wx.tag }}</span>
        <template v-if="wx.forecast">
          {{ wxGlyph(wx.forecast.code) }} {{ formatTempValue(wx.forecast.tMax) }}°/{{ formatTempValue(wx.forecast.tMin) }}°
        </template>
        <template v-else>—</template>
      </span>
    </div>

    <span v-if="banner.sun" class="strip-meta strip-sun mono">
      ☀ {{ banner.sun.rise }} → {{ banner.sun.set }}
      <template v-if="banner.live && sunsetCountdown"> · sunset {{ sunsetCountdown }}</template>
    </span>

    <div class="strip-meta strip-survival" :title="error || 'Toggle nearby spots'">
      <button
        v-for="k in survivalKindsVisible"
        :key="k.key"
        type="button"
        class="strip-survival-chip"
        :class="{ on: selected.has(k.key) }"
        :disabled="loading && !selected.has(k.key)"
        :title="`${selected.has(k.key) ? 'Hide' : 'Show'} ${k.label.toLowerCase()} on the map`"
        :aria-pressed="selected.has(k.key)"
        @click="toggleKind(k.key)"
      >{{ k.icon }}</button>
    </div>

    <span v-if="banner.live && nextLegInfo" class="strip-meta strip-next mono">↳ {{ nextLegInfo }}</span>

    <div class="strip-actions">
      <button
        v-if="banner.live && nextStop"
        class="strip-advance mono"
        type="button"
        :title="`Mark ${banner.day.label || 'this stop'} as completed and jump to next`"
        @click="$emit('advance')"
      ><span class="strip-advance-tick" aria-hidden="true">✓</span> Made it →</button>
      <button class="strip-action" type="button" title="Edit this day" @click="$emit('edit-day', banner.day)">✎</button>
      <button class="strip-close" type="button" title="Hide for this session" @click="$emit('dismiss')">×</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { fetchSurvival, SURVIVAL_KINDS } from '@/lib/overpass.js'
import { glyphFor as wxGlyph } from '@/lib/weather.js'
import { formatTempValue } from '@/lib/settings.js'

const props = defineProps({
  // Mirrors `todayBanner` in MapView: { tag, text, day, live, notes?, sun? }.
  banner: { type: Object, default: null },
  // Same shape as MapView's bannerSpanWx (one entry per day in the stop span).
  weatherChips: { type: Array, default: () => [] },
  nextStop: { type: Object, default: null },
  nextLegInfo: { type: String, default: null },
  sunsetCountdown: { type: String, default: null },
  dismissed: { type: Boolean, default: false },
  // Used by the inline survival toggles to query Overpass for the visible bbox.
  getBounds: { type: Function, required: true },
})
const emit = defineEmits(['go-day', 'edit-day', 'advance', 'dismiss', 'render-survival', 'clear-survival'])

// Hide 'shower' from the inline strip — it's the rarest kind and the strip
// already crowds quickly. The four others (water/dump/toilet/trash) are the
// daily van-life concerns.
const survivalKindsVisible = SURVIVAL_KINDS.filter((k) => k.key !== 'shower')

// Weather: cap at 2 days so the strip stays glanceable. For an N-day stop the
// remaining days are visible inside the day card.
const visibleWx = computed(() => props.weatherChips.slice(0, 2))

const selected = ref(new Set())
const loading = ref(false)
const error = ref('')

async function refresh() {
  if (selected.value.size === 0) {
    emit('clear-survival')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const items = await fetchSurvival(props.getBounds(), [...selected.value])
    emit('render-survival', items)
  } catch (e) {
    error.value = e.message || 'Could not load nearby spots.'
    emit('clear-survival')
  } finally {
    loading.value = false
  }
}

function toggleKind(k) {
  const next = new Set(selected.value)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  selected.value = next
  refresh()
}
</script>

<style scoped>
/* Bottom-center strip — replaces the old top "today banner". Same ink/paper
   palette so the visual identity carries over: dark slab in future mode,
   vermillion when the trip is live (today is inside a stop). */
.bottom-strip {
  position: absolute;
  left: 50%;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 1rem);
  transform: translateX(-50%);
  z-index: 700;
  display: inline-flex;
  align-items: stretch;
  background: var(--ink);
  color: var(--paper);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  max-width: calc(100% - 2rem);
  overflow: hidden;
}
.bottom-strip.is-live { background: var(--vermillion-deep); }

.strip-main {
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0.45rem 0.7rem;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}
.strip-main:hover { background: rgba(255, 255, 255, 0.06); }
.strip-tag {
  display: inline-block;
  background: var(--vermillion);
  color: var(--paper);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  padding: 0.15rem 0.45rem;
  border-radius: 2px;
  font-weight: 700;
  flex-shrink: 0;
}
.bottom-strip.is-live .strip-tag {
  background: var(--paper);
  color: var(--vermillion-deep);
}
.strip-text {
  font-family: var(--display);
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}

.strip-meta {
  display: inline-flex;
  align-items: center;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.72);
  padding: 0 0.6rem;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  white-space: nowrap;
}
.strip-wx { gap: 0.5rem; }
.strip-wx-cell.is-active { color: rgba(255, 255, 255, 0.95); font-weight: 600; }
.strip-wx-cell.is-faded { color: rgba(255, 255, 255, 0.4); font-style: italic; }
.strip-wx-tag {
  font-size: 0.56rem;
  letter-spacing: 0.16em;
  color: rgba(255, 255, 255, 0.45);
  margin-right: 0.2rem;
}

.strip-survival { gap: 0.25rem; padding: 0.35rem 0.45rem; }
.strip-survival-chip {
  background: transparent;
  color: inherit;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  padding: 0.18rem 0.5rem;
  cursor: pointer;
  font: inherit;
  font-size: 0.95rem;
  line-height: 1;
}
.strip-survival-chip:hover { border-color: var(--paper); }
.strip-survival-chip.on {
  background: var(--paper);
  color: var(--ink);
  border-color: var(--paper);
}
.strip-survival-chip:disabled { opacity: 0.55; cursor: wait; }

.strip-next { color: rgba(255, 255, 255, 0.85); }

.strip-actions { display: inline-flex; }
.strip-action,
.strip-close,
.strip-advance {
  background: transparent;
  border: none;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--cream);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}
.strip-action,
.strip-close { width: 2.2rem; }
.strip-advance {
  padding: 0 0.75rem;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  background: var(--vermillion);
  color: var(--paper);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.strip-advance:hover { background: var(--vermillion-deep); }
.strip-advance-tick { font-size: 0.85rem; line-height: 1; letter-spacing: 0; }
.strip-action:hover { background: var(--vermillion-deep); color: var(--paper); }
.strip-close:hover { background: rgba(255, 255, 255, 0.12); color: var(--paper); }

@media (max-width: 720px) {
  /* On phones the bottom-right cluster (FAB / locate / recenter) eats the
     right column, so stop centering and inset the strip from both edges
     with extra room on the right for the FAB stack. Wraps to two lines
     when content overflows. */
  .bottom-strip {
    left: 0.5rem;
    right: 88px;
    transform: none;
    max-width: none;
    flex-wrap: wrap;
  }
  .strip-text { max-width: 14ch; font-size: 0.85rem; }
  .strip-meta { padding: 0 0.45rem; font-size: 0.66rem; }
  .strip-survival { padding: 0.3rem 0.4rem; }
  .strip-survival-chip { font-size: 0.85rem; padding: 0.15rem 0.4rem; }
  .strip-action, .strip-close { width: 2rem; }
  .strip-advance { padding: 0 0.55rem; font-size: 0.62rem; }
}
@media (max-width: 480px) {
  /* Tightest phones: drop the upcoming-leg label so the survival chips and
     stop name stay readable. The full info is one tap away on the day card. */
  .strip-next { display: none; }
}
</style>
