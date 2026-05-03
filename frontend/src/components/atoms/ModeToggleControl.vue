<template>
  <div class="mode-toggle mono" role="tablist" :aria-label="`View mode`">
    <button
      type="button"
      class="mode-btn"
      :class="{ on: mode === 'plan' }"
      :aria-pressed="mode === 'plan'"
      title="Plan mode — table of stops + wishlist of pins"
      @click="$emit('change', 'plan')"
    >
      <span class="mode-glyph" aria-hidden="true">▤</span>
      <span class="mode-label">Plan</span>
    </button>
    <button
      type="button"
      class="mode-btn"
      :class="{ on: mode === 'map' }"
      :aria-pressed="mode === 'map'"
      title="Map mode — full-bleed map, edit pins via dialog"
      @click="$emit('change', 'map')"
    >
      <span class="mode-glyph" aria-hidden="true">◵</span>
      <span class="mode-label">Map</span>
    </button>
    <button
      type="button"
      class="mode-btn"
      :class="{ on: mode === 'journal' }"
      :aria-pressed="mode === 'journal'"
      title="Journal mode — notebook of stops and pins for long-form notes"
      @click="$emit('change', 'journal')"
    >
      <span class="mode-glyph" aria-hidden="true">❧</span>
      <span class="mode-label">Journal</span>
    </button>
  </div>
</template>

<script setup>
defineProps({ mode: { type: String, required: true } })
defineEmits(['change'])
</script>

<style scoped>
.mode-toggle {
  display: inline-flex;
  background: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  overflow: hidden;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  box-shadow: 0 2px 0 var(--ink);
}
.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: transparent;
  border: none;
  padding: 0.32rem 0.8rem;
  cursor: pointer;
  color: var(--ink);
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
}
.mode-btn:hover { background: var(--cream); }
.mode-btn.on {
  background: var(--ink);
  color: var(--paper);
}
.mode-btn.on:hover { background: var(--ink); }
.mode-glyph {
  font-size: 0.95rem;
  line-height: 1;
}
.mode-label { font-weight: 600; }

@media (max-width: 720px) {
  .mode-btn { padding: 0.32rem 0.6rem; }
  .mode-label { display: none; }
  .mode-glyph { font-size: 1.05rem; }
}
</style>
