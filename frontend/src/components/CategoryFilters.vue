<template>
  <div v-if="cats.length > 0" class="chips">
    <button
      v-for="c in cats"
      :key="c.key"
      type="button"
      class="chip"
      :class="{ off: hidden.has(c.key) }"
      :title="hidden.has(c.key) ? `Show ${c.label}` : `Hide ${c.label}`"
      @click="toggle(c.key)"
    >
      <span class="ch-emoji">{{ c.emoji }}</span>
      <span class="ch-count">{{ c.count }}</span>
    </button>
    <button v-if="hidden.size > 0" type="button" class="reset" @click="$emit('reset')">All</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CATEGORIES } from '@/util.js'

const props = defineProps({
  points: { type: Array, default: () => [] },
  hidden: { type: Set, default: () => new Set() },
})
const emit = defineEmits(['toggle', 'reset'])

const cats = computed(() => {
  const counts = new Map()
  for (const p of props.points) {
    counts.set(p.category, (counts.get(p.category) || 0) + 1)
  }
  return CATEGORIES.filter((c) => counts.has(c.key)).map((c) => ({
    ...c,
    count: counts.get(c.key),
  }))
})

function toggle(key) { emit('toggle', key) }
</script>

<style scoped>
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding-bottom: 0.6rem;
  margin-bottom: 0.4rem;
  border-bottom: 1px dotted var(--cream-edge);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.55rem;
  font-family: var(--mono);
  font-size: 0.78rem;
  background: var(--paper);
  color: var(--ink);
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  cursor: pointer;
  transition: all 90ms ease;
}
.chip:hover { background: var(--cream); }
.chip.off {
  background: transparent;
  color: var(--ink-faded);
  border-color: var(--ink-faded);
}
.chip.off .ch-emoji { filter: grayscale(1) opacity(0.55); }
.ch-emoji { font-size: 0.95rem; line-height: 1; }
.ch-count { font-weight: 600; }
.reset {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--ink);
  color: var(--paper);
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  padding: 0.25rem 0.7rem;
  cursor: pointer;
}
.reset:hover { background: var(--vermillion); border-color: var(--vermillion); }
</style>
