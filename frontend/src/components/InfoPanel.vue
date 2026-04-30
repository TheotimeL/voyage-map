<template>
  <DesktopDock v-model:collapsed="collapsed">
    <header class="dock-head">
      <slot name="header" />
    </header>
    <TabBar :tabs="tabs" :active="active" @update:active="(k) => emit('update:active', k)" />
    <div class="tab-content">
      <slot :name="active" />
    </div>
    <template #rail>
      <button
        v-for="t in tabs"
        :key="t.key"
        type="button"
        class="rail-icon"
        :class="{ active: t.key === active }"
        :title="t.label"
        @click="rail(t.key)"
      >{{ t.icon }}</button>
    </template>
  </DesktopDock>
</template>

<script setup>
import { ref } from 'vue'
import DesktopDock from './DesktopDock.vue'
import TabBar from './TabBar.vue'

const props = defineProps({
  tabs: { type: Array, required: true },
  active: { type: String, required: true },
})
const emit = defineEmits(['update:active'])

const collapsed = ref(false)
function rail(key) {
  emit('update:active', key)
  collapsed.value = false
}
</script>

<style scoped>
.dock-head {
  padding: 0.9rem 1rem 0.7rem;
  border-bottom: 1px solid var(--cream-edge);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.tab-content { flex: 1; overflow-y: auto; padding: 0.9rem 1rem 1rem; }
.rail-icon {
  background: transparent;
  border: 1px solid transparent;
  font-size: 1.2rem;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 3px;
}
.rail-icon:hover { background: var(--cream); border-color: var(--cream-edge); }
.rail-icon.active { background: var(--cream); border-color: var(--vermillion); }
</style>
