<template>
  <article class="detail paper">
    <button class="close" type="button" aria-label="Close" @click="$emit('close')">×</button>

    <div class="head">
      <span class="badge"><span>{{ emoji }}</span></span>
      <div>
        <p class="eyebrow">{{ catLabel }}</p>
        <h3 class="title">{{ point.title || `Untitled ${catLabel.toLowerCase()}` }}</h3>
      </div>
    </div>

    <p v-if="point.comment" class="comment">{{ point.comment }}</p>
    <p v-else class="comment muted"><em>No notes yet.</em></p>

    <p class="coord meta">
      {{ formatLat(point.lat) }} · {{ formatLng(point.lng) }}
    </p>

    <div class="actions">
      <button class="btn btn-ghost" @click="$emit('edit')">Edit</button>
      <button class="btn btn-ghost danger" @click="$emit('delete')">Delete</button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { CATEGORIES, formatLat, formatLng } from '@/util.js'

const props = defineProps({
  point: { type: Object, required: true },
})
defineEmits(['edit', 'delete', 'close'])

const cat = computed(() => CATEGORIES.find((c) => c.key === props.point.category) || CATEGORIES[7])
const emoji = computed(() => cat.value.emoji)
const catLabel = computed(() => cat.value.label)
</script>

<style scoped>
.detail {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: min(320px, calc(100% - 2rem));
  z-index: 800;
  padding: 1rem 1.1rem 0.9rem;
  display: grid;
  gap: 0.55rem;
}
.close {
  position: absolute;
  top: 0.4rem;
  right: 0.6rem;
  background: transparent;
  border: none;
  font-family: var(--body);
  font-size: 1.4rem;
  line-height: 1;
  color: var(--ink-faded);
  cursor: pointer;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
}
.close:hover { color: var(--ink); background: var(--cream); }

.head { display: flex; gap: 0.7rem; align-items: center; }
.badge {
  width: 2.4rem;
  height: 2.4rem;
  display: grid;
  place-items: center;
  font-size: 1.15rem;
  background: var(--paper);
  border: 2.5px solid var(--vermillion);
  border-radius: 50%;
  flex-shrink: 0;
}

.title {
  margin: 0.1rem 0 0;
  font-size: 1.35rem;
  line-height: 1.05;
  text-transform: uppercase;
}

.comment {
  font-size: 0.96rem;
  color: var(--ink-soft);
  margin: 0;
  white-space: pre-wrap;
}
.comment.muted { color: var(--ink-faded); }

.meta { margin: 0; font-size: 0.78rem; }

.actions {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
  margin-top: 0.3rem;
}
.danger { color: var(--vermillion); border-color: var(--vermillion); }
.danger:hover { background: var(--vermillion); color: var(--paper); border-color: var(--vermillion); }

@media (max-width: 720px) {
  .detail { top: auto; bottom: 1rem; right: 1rem; left: 1rem; width: auto; }
}
</style>
