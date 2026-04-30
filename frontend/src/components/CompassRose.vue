<template>
  <svg
    class="compass"
    :width="size"
    :height="size"
    viewBox="0 0 120 120"
    aria-hidden="true"
  >
    <defs>
      <radialGradient id="cr-fill" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(244, 236, 216, 0.6)" />
        <stop offset="100%" stop-color="rgba(244, 236, 216, 0)" />
      </radialGradient>
    </defs>
    <circle cx="60" cy="60" r="56" fill="url(#cr-fill)" stroke="currentColor" stroke-width="0.7" opacity="0.55" />
    <circle cx="60" cy="60" r="44" fill="none" stroke="currentColor" stroke-width="0.5" opacity="0.5" />
    <!-- Cardinal points -->
    <g stroke="currentColor" stroke-width="0.8" fill="currentColor" opacity="0.85">
      <polygon points="60,8 64,60 60,56 56,60" />
      <polygon points="60,112 64,60 60,64 56,60" opacity="0.5" />
      <polygon points="8,60 60,56 56,60 60,64" opacity="0.5" />
      <polygon points="112,60 60,56 64,60 60,64" opacity="0.5" />
    </g>
    <!-- Diagonal -->
    <g stroke="currentColor" stroke-width="0.4" opacity="0.4">
      <line x1="22" y1="22" x2="98" y2="98" />
      <line x1="98" y1="22" x2="22" y2="98" />
    </g>
    <!-- Labels -->
    <g font-family="IM Fell English, Georgia, serif" font-size="11" fill="currentColor" text-anchor="middle">
      <text x="60" y="22">N</text>
      <text x="60" y="106" opacity="0.6">S</text>
      <text x="14" y="63" opacity="0.6">W</text>
      <text x="106" y="63" opacity="0.6">E</text>
    </g>
    <circle cx="60" cy="60" r="2" fill="currentColor" />
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 120 },
})
</script>

<style scoped>
.compass { color: var(--ink-soft); }
</style>
