<template>
  <div class="more-menu">
    <section class="more-block">
      <h4 class="more-title">Daylight</h4>
      <SunPanel :fallback-lat="fallbackLat" :fallback-lng="fallbackLng" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Survival POIs</h4>
      <SurvivalLayer :get-bounds="getBounds" @render="(v) => emit('render-survival', v)" @clear="emit('clear-survival')" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Offline</h4>
      <PrecacheButton :theme="theme" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Share</h4>
      <button class="btn btn-ghost btn-share" @click="emit('copy-url')">
        {{ copied ? 'Copied ✓' : 'Copy link' }}
      </button>
    </section>

    <section class="more-block">
      <h4 class="more-title">Theme</h4>
      <ThemeToggle />
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
})
const emit = defineEmits(['render-survival', 'clear-survival', 'copy-url'])
</script>

<style scoped>
.more-menu { display: flex; flex-direction: column; gap: 1.2rem; }
.more-block { padding-bottom: 0.4rem; border-bottom: 1px dashed var(--cream-edge); }
.more-block:last-child { border-bottom: none; }
.more-title {
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin: 0 0 0.5rem;
}
</style>
