<template>
  <ul class="point-list">
    <li v-if="points.length === 0" class="empty">
      <em>No marks yet. Click the map to drop one.</em>
    </li>
    <li
      v-for="p in points"
      :key="p.id"
      class="point"
      :class="{ active: p.id === activeId }"
      @click="$emit('select', p)"
    >
      <span class="pin-mini">{{ emojiFor(p.category) }}</span>
      <div class="text">
        <div class="title">{{ p.title || untitled(p) }}</div>
        <div v-if="p.comment" class="comment">{{ p.comment }}</div>
        <div class="coord">
          {{ formatLat(p.lat) }} · {{ formatLng(p.lng) }}
        </div>
      </div>
    </li>
  </ul>
</template>

<script setup>
import { CATEGORIES, formatLat, formatLng } from '@/util.js'

defineProps({
  points: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
})
defineEmits(['select'])

const emojiMap = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.emoji]))
function emojiFor(key) {
  return emojiMap[key] || '📍'
}
function untitled(p) {
  const cat = CATEGORIES.find((c) => c.key === p.category)
  return cat ? cat.label : 'Untitled'
}
</script>

<style scoped>
.point-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
}
.empty {
  font-family: var(--serif-body);
  color: var(--ink-faded);
  padding: 1rem 0.2rem;
}
.point {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.7rem;
  align-items: start;
  padding: 0.55rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 2px;
  cursor: pointer;
  transition: background 90ms ease, border-color 90ms ease;
}
.point:hover { background: rgba(184, 138, 74, 0.12); border-color: var(--paper-edge); }
.point.active { background: rgba(139, 58, 58, 0.13); border-color: var(--oxblood); }
.pin-mini {
  font-size: 1.1rem;
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  background: var(--paper);
  border: 1.5px solid var(--oxblood);
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
}
.pin-mini > * { transform: rotate(45deg); }
.title {
  font-family: var(--serif-display);
  font-size: 1.05rem;
  color: var(--ink);
  line-height: 1.2;
}
.comment {
  font-size: 0.92rem;
  color: var(--ink-soft);
  margin-top: 0.15rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.coord { margin-top: 0.2rem; font-size: 0.78rem; }
</style>
