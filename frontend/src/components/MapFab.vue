<template>
  <button class="map-fab" type="button" :title="title" @click="$emit('click')">
    <span class="fab-glyph">{{ glyph }}</span>
  </button>
</template>

<script setup>
defineProps({
  glyph: { type: String, default: '+' },
  title: { type: String, default: 'Drop a pin' },
})
defineEmits(['click'])
</script>

<style scoped>
.map-fab {
  position: absolute;
  right: 16px;
  bottom: 16px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--vermillion);
  color: var(--paper);
  border: none;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  z-index: 850;
  transition: transform 90ms ease;
}
.map-fab:hover { transform: scale(1.05); }
.fab-glyph { font-size: 1.6rem; line-height: 1; font-weight: 600; }

@media (max-width: 720px) {
  .map-fab { bottom: 80px; }
}
</style>
