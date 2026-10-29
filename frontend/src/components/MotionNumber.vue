<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'

const props = withDefaults(defineProps<{
  value: number
  decimals?: number
  duration?: number
  suffix?: string
}>(), { decimals: 0, duration: 420, suffix: '' })

const displayed = shallowRef(0)
let frame = 0
let mounted = false

function format(value: number): string {
  return `${value.toFixed(props.decimals)}${props.suffix}`
}

function cancel(): void {
  if (frame) cancelAnimationFrame(frame)
  frame = 0
}

function settle(value: number): void {
  cancel()
  displayed.value = value
}

function animate(value: number, from = displayed.value): void {
  cancel()
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || props.duration <= 0) {
    settle(value)
    return
  }

  const startedAt = performance.now()
  const duration = props.duration
  const tick = (now: number) => {
    const progress = Math.min(1, (now - startedAt) / duration)
    const eased = 1 - (1 - progress) ** 3
    displayed.value = from + (value - from) * eased
    if (progress < 1) frame = requestAnimationFrame(tick)
    else frame = 0
  }
  frame = requestAnimationFrame(tick)
}

onMounted(() => {
  mounted = true
  animate(props.value, 0)
})

watch(() => props.value, (value) => {
  if (mounted) animate(value)
})

onBeforeUnmount(cancel)
</script>

<template>
  <span class="motion-number">
    <span aria-hidden="true">{{ format(displayed) }}</span>
    <span class="motion-number__accessible">{{ format(value) }}</span>
  </span>
</template>

<style scoped>
.motion-number__accessible {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
