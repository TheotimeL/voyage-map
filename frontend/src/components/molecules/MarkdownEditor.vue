<template>
  <div class="md-editor" :class="{ 'is-empty': !modelValue }">
    <div v-if="editor" class="md-toolbar">
      <button type="button" :class="{ active: editor.isActive('bold') }" @click="editor.chain().focus().toggleBold().run()" title="Bold"><b>B</b></button>
      <button type="button" :class="{ active: editor.isActive('italic') }" @click="editor.chain().focus().toggleItalic().run()" title="Italic"><i>I</i></button>
      <button type="button" :class="{ active: editor.isActive('heading', { level: 2 }) }" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()" title="Heading">H</button>
      <button type="button" :class="{ active: editor.isActive('bulletList') }" @click="editor.chain().focus().toggleBulletList().run()" title="Bullet list">•</button>
      <button type="button" @click="editor.chain().focus().setHorizontalRule().run()" title="Horizontal rule">—</button>
      <button type="button" @click="onLink" title="Link">🔗</button>
      <label class="img-btn" :class="{ 'is-uploading': uploading }" :title="uploading ? 'Uploading…' : 'Insert image'">
        <span v-if="uploading" class="img-spinner" aria-hidden="true">⟳</span>
        <span v-else>📷</span>
        <input type="file" accept="image/*" class="hidden" :disabled="uploading" @change="onPickImage" />
      </label>
    </div>
    <editor-content :editor="editor" class="md-surface" />
    <p v-if="uploading" class="md-hint">Uploading image — keep the form open until it's done.</p>
    <p v-if="uploadError" class="md-error">{{ uploadError }}</p>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import Dropcursor from '@tiptap/extension-dropcursor'
import { Markdown } from 'tiptap-markdown'
import { uploadImage } from '@/api.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Notes…' },
})
// `update:uploading` lets the parent form disable Save while a file is in
// flight. Without it, the user could click Save before the upload finishes,
// the form would persist a comment that doesn't reference the new image, and
// the post-modal-close insertion would silently no-op into a destroyed editor.
const emit = defineEmits(['update:modelValue', 'update:uploading'])

const uploadError = ref('')
const uploading = ref(false)

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Image.configure({
      // Native node-drag inside ProseMirror — gives us reorder for free.
      inline: false,
      allowBase64: false,
    }),
    Link.configure({ openOnClick: false, autolink: true }),
    Placeholder.configure({ placeholder: () => props.placeholder }),
    Dropcursor.configure({ class: 'md-dropcursor' }),
    Markdown.configure({
      transformPastedText: true,
      transformCopiedText: true,
    }),
  ],
  editorProps: {
    handlePaste: (view, event) => handleImagePaste(event),
    handleDrop: (view, event) => handleImageDrop(event),
  },
  onUpdate: ({ editor }) => {
    // Tiptap-markdown exposes `.storage.markdown.getMarkdown()` for serialize.
    const md = editor.storage.markdown.getMarkdown()
    emit('update:modelValue', md)
  },
})

// Keep external model changes in sync without echoing our own emits.
watch(() => props.modelValue, (next) => {
  if (!editor.value) return
  const current = editor.value.storage.markdown.getMarkdown()
  if (next !== current) editor.value.commands.setContent(next || '', false)
})

onBeforeUnmount(() => editor.value?.destroy())

async function onPickImage(e) {
  const file = (e.target.files || [])[0]
  e.target.value = ''
  if (file) await uploadAndInsert(file)
}

async function uploadAndInsert(file) {
  if (!file || !file.type.startsWith('image/')) return
  uploadError.value = ''
  uploading.value = true
  emit('update:uploading', true)
  try {
    const { url } = await uploadImage(file)
    editor.value?.chain().focus().setImage({ src: url, alt: file.name || '' }).run()
  } catch (err) {
    uploadError.value = err.message || 'Upload failed.'
  } finally {
    uploading.value = false
    emit('update:uploading', false)
  }
}

function handleImagePaste(event) {
  const items = event.clipboardData?.items || []
  for (const item of items) {
    if (item.type?.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) { uploadAndInsert(file); return true }
    }
  }
  return false
}

function handleImageDrop(event) {
  const file = event.dataTransfer?.files?.[0]
  if (file && file.type?.startsWith('image/')) {
    event.preventDefault()
    uploadAndInsert(file)
    return true
  }
  return false
}

function onLink() {
  const prev = editor.value?.getAttributes('link').href || ''
  const url = window.prompt('Link URL', prev)
  if (url === null) return
  if (url === '') {
    editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
    return
  }
  editor.value?.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
}
</script>

<style scoped>
.md-editor {
  border: 1px solid var(--rule, #d8d2c3);
  border-radius: 8px;
  background: var(--paper, #fdfaf2);
  font-family: inherit;
}
.md-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.4rem;
  border-bottom: 1px solid var(--rule, #d8d2c3);
  position: sticky;
  top: 0;
  background: inherit;
  z-index: 1;
}
.md-toolbar button, .md-toolbar .img-btn {
  border: 1px solid transparent;
  background: transparent;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.95em;
}
.md-toolbar button.active { background: rgba(0,0,0,0.08); }
.md-toolbar button:hover, .md-toolbar .img-btn:hover { background: rgba(0,0,0,0.04); }
.img-btn { display: inline-flex; align-items: center; }
.hidden { display: none; }
.md-surface { padding: 0.6rem 0.8rem; min-height: 6em; }
.md-surface :deep(.ProseMirror) { outline: none; min-height: 5em; }
.md-surface :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  color: var(--muted, #968b76);
  pointer-events: none;
  height: 0;
}
.md-surface :deep(img) { max-width: 100%; border-radius: 6px; cursor: grab; }
.md-error { color: #b53127; font-size: 0.85em; padding: 0 0.8rem 0.4rem; }
.md-hint { color: var(--ink-faded, #968b76); font-size: 0.8em; padding: 0 0.8rem 0.4rem; margin: 0; font-style: italic; }
.img-btn.is-uploading { opacity: 0.7; pointer-events: none; }
.img-spinner { display: inline-block; animation: md-spin 0.9s linear infinite; }
@keyframes md-spin { to { transform: rotate(360deg); } }
</style>
