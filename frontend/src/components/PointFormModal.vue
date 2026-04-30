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
import { reactive, onMounted, useTemplateRef } from 'vue'
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
  width: min(440px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 0.75rem;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin-top: 0.4rem;
}
.cat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.4rem;
}
.cat {
  background: rgba(255, 252, 240, 0.6);
  border: 1px solid var(--ink-faded);
  border-radius: 2px;
  padding: 0.5rem 0.2rem;
  cursor: pointer;
  display: grid;
  gap: 0.2rem;
  font-family: var(--serif-body);
  color: var(--ink-soft);
  transition: all 90ms ease;
}
.cat:hover { border-color: var(--oxblood); color: var(--ink); }
.cat.active {
  background: var(--oxblood);
  border-color: var(--oxblood-deep);
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
