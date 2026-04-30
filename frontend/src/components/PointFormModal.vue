<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">{{ isNew ? 'Mark a place' : 'Edit place' }}</p>
      <p class="coord">
        {{ formatLat(modelValue.lat) }} · {{ formatLng(modelValue.lng) }}
      </p>

      <label class="lbl">Title</label>
      <input
        ref="titleInput"
        v-model="form.title"
        class="field"
        maxlength="120"
        placeholder="e.g. Café A Brasileira"
      />

      <label class="lbl">Notes</label>
      <textarea
        v-model="form.comment"
        class="field"
        maxlength="2000"
        placeholder="What's here? Why does it matter?"
      />

      <label class="lbl">Category</label>
      <div class="cat-grid">
        <button
          v-for="c in categories"
          :key="c.key"
          type="button"
          class="cat"
          :class="{ active: form.category === c.key }"
          @click="form.category = c.key"
        >
          <span class="cat-emoji">{{ c.emoji }}</span>
          <span class="cat-label">{{ c.label }}</span>
        </button>
      </div>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">{{ isNew ? 'Drop pin' : 'Save' }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, onMounted, onBeforeUnmount, useTemplateRef } from 'vue'
import { CATEGORIES, formatLat, formatLng } from '@/util.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
  isNew: { type: Boolean, default: true },
})
const emit = defineEmits(['save', 'close'])

const categories = CATEGORIES

const form = reactive({
  title: props.modelValue.title || '',
  comment: props.modelValue.comment || '',
  category: props.modelValue.category || 'note',
})

const titleInput = useTemplateRef('titleInput')
onMounted(() => titleInput.value?.focus())

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

function submit() {
  emit('save', {
    title: form.title.trim() || null,
    comment: form.comment.trim() || null,
    category: form.category,
  })
}
</script>

<style scoped>
.modal {
  width: min(540px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 1rem;
  padding: 1.4rem 1.5rem;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin-top: 0.2rem;
}
.cat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
}
.cat {
  background: var(--cream);
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  padding: 0.6rem 0.3rem;
  cursor: pointer;
  display: grid;
  gap: 0.25rem;
  font-family: var(--body);
  color: var(--ink-soft);
  transition: all 90ms ease;
}
.cat:hover { border-color: var(--vermillion); color: var(--ink); }
.cat.active {
  background: var(--vermillion);
  border-color: var(--vermillion-deep);
  color: var(--paper);
}
.cat-emoji { font-size: 1.2rem; }
.cat-label { font-size: 0.78rem; letter-spacing: 0.04em; }
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.6rem;
  flex-wrap: wrap;
}
</style>
