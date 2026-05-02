<template>
  <div class="more-menu">
    <section class="more-block">
      <h4 class="more-title">Daylight</h4>
      <SunPanel :fallback-lat="fallbackLat" :fallback-lng="fallbackLng" :place-name="placeName" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Find nearby</h4>
      <SurvivalLayer :get-bounds="getBounds" @render="(v) => emit('render-survival', v)" @clear="emit('clear-survival')" />
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Offline tiles</h4>
        <PrecacheButton :theme="theme" :next-leg-bbox="nextLegBbox" />
      </div>
    </section>
  </div>
</template>

<script setup>
import SunPanel from './SunPanel.vue'
import SurvivalLayer from './SurvivalLayer.vue'
import PrecacheButton from './PrecacheButton.vue'

defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
  getBounds: { type: Function, required: true },
  theme: { type: String, required: true },
  placeName: { type: String, default: '' },
  // Bbox for the next leg (today→next stop). Null when there's no upcoming
  // leg; PrecacheButton disables the "Next leg" segment in that case.
  nextLegBbox: { type: Object, default: null },
})
const emit = defineEmits(['render-survival', 'clear-survival'])
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
</style>
