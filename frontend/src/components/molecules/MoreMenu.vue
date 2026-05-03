<template>
  <div class="more-menu">
    <section class="more-block">
      <h4 class="more-title">Daylight</h4>
      <SunPanel :fallback-lat="fallbackLat" :fallback-lng="fallbackLng" :place-name="placeName" />
    </section>

    <section class="more-block">
      <h4 class="more-title">Find nearby</h4>
      <SurvivalLayer
        :get-bounds="getBounds"
        :selected="survivalSelected"
        :enabled="survivalEnabled"
        @update:selected="(v) => emit('update:survival-selected', v)"
        @update:enabled="(v) => emit('update:survival-enabled', v)"
        @render="(v) => emit('render-survival', v)"
        @clear="emit('clear-survival')"
      />
    </section>

    <section class="more-block">
      <div class="more-row">
        <h4 class="more-title">Offline tiles</h4>
        <PrecacheButton :theme="theme" :next-leg-bbox="nextLegBbox" />
      </div>
    </section>

    <section class="more-block">
      <h4 class="more-title">Units &amp; format</h4>
      <div class="more-units">
        <div class="more-units-row">
          <span class="more-units-label mono">Distance</span>
          <div class="seg mono" role="group" aria-label="Distance units">
            <button type="button" class="seg-btn" :class="{ on: settings.units === 'metric' }" @click="settings.units = 'metric'">km</button>
            <button type="button" class="seg-btn" :class="{ on: settings.units === 'imperial' }" @click="settings.units = 'imperial'">mi</button>
          </div>
        </div>
        <div class="more-units-row">
          <span class="more-units-label mono">Temp</span>
          <div class="seg mono" role="group" aria-label="Temperature units">
            <button type="button" class="seg-btn" :class="{ on: settings.units === 'metric' }" @click="settings.units = 'metric'">°C</button>
            <button type="button" class="seg-btn" :class="{ on: settings.units === 'imperial' }" @click="settings.units = 'imperial'">°F</button>
          </div>
        </div>
        <div class="more-units-row">
          <span class="more-units-label mono">Time</span>
          <div class="seg mono" role="group" aria-label="Clock format">
            <button type="button" class="seg-btn" :class="{ on: settings.timeFmt === '24h' }" @click="settings.timeFmt = '24h'">24h</button>
            <button type="button" class="seg-btn" :class="{ on: settings.timeFmt === '12h' }" @click="settings.timeFmt = '12h'">12h</button>
          </div>
        </div>
        <div class="more-units-row">
          <span class="more-units-label mono">Date</span>
          <div class="seg mono" role="group" aria-label="Date format">
            <button type="button" class="seg-btn" :class="{ on: settings.dateFmt === 'iso' }" @click="settings.dateFmt = 'iso'">ISO</button>
            <button type="button" class="seg-btn" :class="{ on: settings.dateFmt === 'eu' }" @click="settings.dateFmt = 'eu'">EU</button>
            <button type="button" class="seg-btn" :class="{ on: settings.dateFmt === 'us' }" @click="settings.dateFmt = 'us'">US</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import SunPanel from './SunPanel.vue'
import SurvivalLayer from './SurvivalLayer.vue'
import PrecacheButton from './PrecacheButton.vue'
import { settings } from '@/lib/settings.js'

defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
  getBounds: { type: Function, required: true },
  theme: { type: String, required: true },
  placeName: { type: String, default: '' },
  // Bbox for the next leg (today→next stop). Null when there's no upcoming
  // leg; PrecacheButton disables the "Next leg" segment in that case.
  nextLegBbox: { type: Object, default: null },
  // Controlled state for SurvivalLayer — kept in MapView so the persistent
  // Tools chip strip stays in sync with this panel.
  survivalSelected: { type: Set, default: null },
  survivalEnabled: { type: Boolean, default: null },
})
const emit = defineEmits([
  'render-survival',
  'clear-survival',
  'update:survival-selected',
  'update:survival-enabled',
])
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

/* Compact toggle group for Units & format. Mirrors the .seg / .seg-btn
   styling used in PlanView so the visual rhythm stays consistent. */
.more-units { display: grid; gap: 0.35rem; }
.more-units-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.more-units-label {
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.seg {
  display: inline-flex;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  overflow: hidden;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.seg-btn {
  background: transparent;
  border: none;
  padding: 0.2rem 0.6rem;
  cursor: pointer;
  color: var(--ink);
  font-family: inherit;
  font-size: inherit;
  letter-spacing: inherit;
}
.seg-btn.on { background: var(--ink); color: var(--paper); }
</style>
