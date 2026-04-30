<template>
  <aside class="desktop-dock paper" :class="{ collapsed }">
    <button
      class="dock-collapse btn-icon"
      type="button"
      :aria-label="collapsed ? 'Expand' : 'Collapse'"
      @click="$emit('update:collapsed', !collapsed)"
    >{{ collapsed ? '⟩' : '⟨' }}</button>
    <div v-if="!collapsed" class="dock-body">
      <slot />
    </div>
    <div v-else class="dock-rail">
      <slot name="rail" />
    </div>
  </aside>
</template>

<script setup>
defineProps({
  collapsed: { type: Boolean, default: false },
})
defineEmits(['update:collapsed'])
</script>

<style scoped>
.desktop-dock {
  position: absolute;
  top: 16px;
  left: 16px;
  bottom: 16px;
  width: 360px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--vermillion);
  border-radius: 4px;
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.06);
  z-index: 400;
  overflow: hidden;
}
.desktop-dock.collapsed { width: 56px; }
.dock-collapse {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}
.dock-body { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.dock-rail { flex: 1; padding: 2.5rem 0.5rem 0.5rem; display: flex; flex-direction: column; gap: 0.4rem; }
</style>
