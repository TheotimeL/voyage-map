<template>
  <!-- "Passport stamp" decorative element. Circular outline, vermillion ink. -->
  <svg
    class="stamp"
    :width="size"
    :height="size"
    viewBox="0 0 200 200"
    aria-hidden="true"
  >
    <defs>
      <path
        id="stamp-arc"
        d="M 100,100 m -78,0 a 78,78 0 1,1 156,0 a 78,78 0 1,1 -156,0"
      />
    </defs>
    <!-- Outer dashed ring -->
    <circle cx="100" cy="100" r="92" fill="none" stroke="currentColor" stroke-width="2.5" stroke-dasharray="6 4" />
    <!-- Inner solid ring -->
    <circle cx="100" cy="100" r="78" fill="none" stroke="currentColor" stroke-width="2" />
    <!-- Curved text along arc -->
    <text font-family="Anton, Impact, sans-serif" font-size="16" fill="currentColor" letter-spacing="3">
      <textPath href="#stamp-arc" startOffset="0">{{ topText }}</textPath>
    </text>
    <!-- Center mark: route arrow -->
    <g transform="translate(100,100)">
      <line x1="-26" y1="0" x2="22" y2="0" stroke="currentColor" stroke-width="3" stroke-linecap="square" />
      <polyline points="14,-8 22,0 14,8" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="miter" stroke-linecap="square" />
      <circle cx="-26" cy="0" r="4" fill="currentColor" />
    </g>
    <!-- Center label -->
    <text x="100" y="138" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10" letter-spacing="2" fill="currentColor">
      {{ bottomText }}
    </text>
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 160 },
  topText: { type: String, default: '· VOYAGE MAP · FIELD GUIDE · EST 2026 · ' },
  bottomText: { type: String, default: 'PLOT YOUR COURSE' },
})
</script>

<style scoped>
.stamp {
  color: var(--vermillion);
  transform: rotate(-8deg);
  opacity: 0.95;
}
</style>
