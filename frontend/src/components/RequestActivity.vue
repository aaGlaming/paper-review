<script setup lang="ts">
withDefaults(defineProps<{
  active: boolean
  label: string
}>(), { active: false })
</script>

<template>
  <p v-if="active" class="request-activity" data-testid="request-activity" role="status" aria-live="polite">
    <span class="request-activity__mark" aria-hidden="true"><i></i><i></i><i></i></span>
    <span>{{ label }}</span>
  </p>
</template>

<style scoped>
.request-activity {
  display: inline-flex;
  align-items: center;
  gap: var(--pr-space-2);
  margin: var(--pr-space-2) 0;
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.request-activity__mark {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 12px;
}

.request-activity__mark i {
  width: 3px;
  height: 5px;
  background: currentColor;
  transform-origin: center bottom;
  animation: request-mark 700ms ease-in-out infinite alternate;
}

.request-activity__mark i:nth-child(2) { animation-delay: 120ms; }
.request-activity__mark i:nth-child(3) { animation-delay: 240ms; }

@keyframes request-mark {
  to { transform: scaleY(1.65); }
}

@media (prefers-reduced-motion: reduce) {
  .request-activity__mark i { animation: none; }
}
</style>
