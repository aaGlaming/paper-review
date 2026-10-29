<script setup lang="ts">
import { onMounted, onUnmounted, useTemplateRef } from 'vue'

import introSvg from '../../../docs/design/sketch-svg/sketch-review-desk-intro.svg?raw'

const emit = defineEmits<{ continue: [] }>()
const action = useTemplateRef<HTMLButtonElement>('action')
let finished = false

function finish(): void {
  if (finished) return
  finished = true
  emit('continue')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    finish()
  }
}

onMounted(() => action.value?.focus({ preventScroll: true }))
onUnmounted(() => {
  finished = true
})
</script>

<template>
  <button
    ref="action"
    class="post-login-intro"
    type="button"
    aria-label="开场动画。点击任意位置，或按 Enter、Space、Escape 进入工作台"
    @click="finish"
    @keydown="onKeydown"
  >
    <span class="post-login-intro__scene">
      <span class="post-login-intro__art" aria-hidden="true" v-html="introSvg"></span>
      <span class="post-login-intro__copy">
        <span class="post-login-intro__eyebrow">校样已就位</span>
        <span class="post-login-intro__title">竞赛论文预审工作台</span>
        <span class="post-login-intro__prompt">点击任意位置，或按 Enter / Space / Esc 进入</span>
      </span>
    </span>
  </button>
</template>

<style scoped>
.post-login-intro {
  position: fixed;
  z-index: 10000;
  inset: 0;
  display: grid;
  place-items: center;
  width: 100%;
  min-height: 100vh;
  padding: clamp(20px, 5vw, 64px);
  overflow: auto;
  border: 0;
  background: var(--pr-paper);
  color: var(--pr-ink);
  font: inherit;
  text-align: center;
  cursor: pointer;
}

.post-login-intro__scene {
  display: grid;
  justify-items: center;
  width: min(100%, 820px);
  gap: clamp(12px, 2.5vh, 24px);
}

.post-login-intro__art {
  display: block;
  width: min(100%, 720px);
}

.post-login-intro__art :deep(svg) {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.post-login-intro__copy {
  display: grid;
  justify-items: center;
  gap: 6px;
}

.post-login-intro__eyebrow {
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.post-login-intro__title {
  font-size: clamp(22px, 4vw, 32px);
  font-weight: 650;
  letter-spacing: 0.04em;
}

.post-login-intro__prompt {
  margin-top: 8px;
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-base);
}

.post-login-intro:hover .post-login-intro__prompt {
  color: var(--pr-primary);
}

.post-login-intro:focus-visible {
  outline: none;
  box-shadow: inset var(--pr-focus-ring);
}

@media (max-width: 560px) {
  .post-login-intro {
    padding: 20px 16px;
  }

  .post-login-intro__art {
    width: min(100%, 480px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .post-login-intro__art :deep(svg) * {
    animation: none !important;
    transition: none !important;
  }
}
</style>
