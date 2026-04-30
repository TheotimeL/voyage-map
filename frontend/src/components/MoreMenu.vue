<template>
  <div class="more-menu">
    <section v-if="stats" class="more-block stats-block">
      <h4 class="more-title">Trip stats</h4>
      <ul class="stats">
        <li><span class="stat-num">{{ stats.points }}</span><span class="stat-lbl">pins</span></li>
        <li><span class="stat-num">{{ stats.trails }}</span><span class="stat-lbl">trails</span></li>
        <li v-if="stats.trailKm > 0"><span class="stat-num">{{ stats.trailKm }}</span><span class="stat-lbl">trail km</span></li>
        <li v-if="stats.trailDPlus > 0"><span class="stat-num">{{ stats.trailDPlus.toLocaleString() }}</span><span class="stat-lbl">D+ m</span></li>
        <li><span class="stat-num">{{ stats.days }}</span><span class="stat-lbl">days</span></li>
        <li v-if="stats.driveKm > 0"><span class="stat-num">≈{{ stats.driveKm.toLocaleString() }}</span><span class="stat-lbl">trip km</span></li>
      </ul>
    </section>

    <section class="more-block">
      <h4 class="more-title">Daylight</h4>
      <SunPanel :fallback-lat="fallbackLat" :fallback-lng="fallbackLng" />
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Water · WC · Trash</h4>
        <SurvivalLayer :get-bounds="getBounds" @render="(v) => emit('render-survival', v)" @clear="emit('clear-survival')" />
      </div>
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Offline tiles</h4>
        <PrecacheButton :theme="theme" />
      </div>
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Share link</h4>
        <button class="btn btn-tiny" type="button" @click="emit('copy-url')">
          {{ copied ? 'Copied ✓' : 'Copy link' }}
        </button>
      </div>
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Theme</h4>
        <ThemeToggle />
      </div>
    </section>
  </div>
</template>

<script setup>
import SunPanel from './SunPanel.vue'
import SurvivalLayer from './SurvivalLayer.vue'
import PrecacheButton from './PrecacheButton.vue'
import ThemeToggle from './ThemeToggle.vue'

defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
  getBounds: { type: Function, required: true },
  theme: { type: String, required: true },
  copied: { type: Boolean, default: false },
  stats: { type: Object, default: null },
})
const emit = defineEmits(['render-survival', 'clear-survival', 'copy-url'])
</script>

<style scoped>
.more-menu { display: flex; flex-direction: column; gap: 1rem; }
.more-block { padding-bottom: 0.6rem; border-bottom: 1px dashed var(--cream-edge); }
.more-block:last-child { border-bottom: none; padding-bottom: 0; }
.more-title {
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0 0 0.5rem;
}
.more-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.more-row .more-title { margin: 0; flex-shrink: 0; }
/* Normalize the action buttons across More rows so they line up. */
.more-row :deep(.btn-tiny) {
  min-width: 9rem;
  padding-block: 0.5rem;
}

/* Stats grid */
.stats {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(74px, 1fr));
  gap: 0.5rem 0.7rem;
}
.stats li {
  display: grid;
  gap: 0.05rem;
  padding: 0.35rem 0;
  border-bottom: 1px dotted var(--cream-edge);
}
.stat-num {
  font-family: var(--display);
  font-size: 1.15rem;
  letter-spacing: 0.02em;
  color: var(--ink);
}
.stat-lbl {
  font-family: var(--mono);
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
</style>
