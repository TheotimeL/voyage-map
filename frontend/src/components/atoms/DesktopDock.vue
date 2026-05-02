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
  z-index: 800;
  overflow: hidden;
  transition: width 120ms ease;
}
.desktop-dock.collapsed {
  width: 44px;
  bottom: auto;
  border-color: var(--cream-edge);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}
.dock-collapse {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}
.desktop-dock.collapsed .dock-collapse {
  position: static;
  margin: 0.35rem auto 0.15rem;
}
.dock-body { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.dock-rail {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0 0.25rem 0.4rem;
  align-items: stretch;
}
</style>
