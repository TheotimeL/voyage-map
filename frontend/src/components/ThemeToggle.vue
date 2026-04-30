<template>
  <button
    class="theme-toggle"
    type="button"
    :title="theme === 'dark' ? 'Switch to light' : 'Switch to dark'"
    @click="toggleTheme"
  >
    {{ theme === 'dark' ? '☀' : '☾' }}
  </button>
</template>

<script setup>
import { theme, toggleTheme } from '@/lib/theme.js'
</script>

<style scoped>
.theme-toggle {
  background: transparent;
  border: 1px solid var(--ink-faded);
  border-radius: 2px;
  width: 2rem; height: 2rem;
  display: grid; place-items: center;
  color: var(--ink-soft);
  cursor: pointer;
  font-size: 1rem;
}
.theme-toggle:hover { color: var(--vermillion); border-color: var(--vermillion); }
</style>
