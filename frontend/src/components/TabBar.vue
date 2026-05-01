<template>
  <nav class="tab-bar" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.key"
      type="button"
      role="tab"
      class="tab"
      :class="{ active: t.key === active }"
      :aria-selected="t.key === active"
      @click="$emit('update:active', t.key)"
    >
      <span class="tab-icon" aria-hidden="true">{{ t.icon }}</span>
      <span class="tab-label">{{ t.label }}</span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  tabs: { type: Array, required: true }, // [{key, label, icon}]
  active: { type: String, required: true },
})
defineEmits(['update:active'])
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--cream-edge);
  background: var(--paper);
}
.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.7rem 0.4rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font: inherit;
  font-size: 0.92rem;
  color: var(--ink-faded);
  cursor: pointer;
  min-height: 44px;
  transition: color 90ms ease, border-color 90ms ease;
}
.tab:hover { color: var(--ink); }
.tab.active { color: var(--vermillion); border-bottom-color: var(--vermillion); }
.tab-icon { font-size: 1.05rem; }
.tab-label { font-family: var(--mono); font-size: 0.78rem; letter-spacing: 0.05em; text-transform: uppercase; }
@media (max-width: 720px) {
  /* Mobile sheet: bigger labels and a 48-px tap target make the bottom
     tab bar feel less like a footer and more like the navigation it is. */
  .tab { padding: 0.85rem 0.4rem; min-height: 48px; }
  .tab-icon { font-size: 1.2rem; }
  .tab-label { font-size: 0.88rem; }
}
</style>
