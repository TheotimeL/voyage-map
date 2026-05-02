<template>
  <div class="md-view" v-html="rendered" />
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

// Single shared instance — markdown-it is heavy to construct.
const md = new MarkdownIt({
  html: false,        // refuse raw HTML in user notes (XSS guard)
  linkify: true,
  breaks: true,       // newline → <br>, journal-friendly
})

// Add lazy-loading + max-width to images via custom renderer rule.
const defaultImageRenderer = md.renderer.rules.image || ((tokens, idx, opts, env, self) => self.renderToken(tokens, idx, opts))
md.renderer.rules.image = (tokens, idx, opts, env, self) => {
  const token = tokens[idx]
  token.attrSet('loading', 'lazy')
  const existingClass = token.attrGet('class') || ''
  token.attrSet('class', `${existingClass} md-img`.trim())
  return defaultImageRenderer(tokens, idx, opts, env, self)
}

const props = defineProps({
  source: { type: String, default: '' },
})

const rendered = computed(() => (props.source ? md.render(props.source) : ''))
</script>

<style scoped>
.md-view :deep(p) { margin: 0.4em 0; }
.md-view :deep(h1), .md-view :deep(h2), .md-view :deep(h3) { margin: 0.6em 0 0.3em; }
.md-view :deep(ul), .md-view :deep(ol) { margin: 0.4em 0; padding-left: 1.4em; }
.md-view :deep(blockquote) {
  margin: 0.4em 0;
  padding: 0.2em 0.8em;
  border-left: 3px solid var(--ink, #333);
  opacity: 0.85;
}
.md-view :deep(.md-img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 0.4em 0;
}
.md-view :deep(a) { color: var(--accent, #1864ab); }
.md-view :deep(code) {
  background: rgba(0,0,0,0.06);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.9em;
}
</style>
