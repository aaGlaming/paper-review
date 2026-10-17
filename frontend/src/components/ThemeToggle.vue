<script setup lang="ts">
import { computed } from 'vue'

import moonUrl from '../assets/sketch/sketch-moon.svg'
import sunUrl from '../assets/sketch/sketch-sun.svg'
import { useTheme } from '../composables/useTheme'

/**
 * 白天 / 黑夜切换按钮。固定在导航栏右端，白天显示太阳、黑夜显示月亮，点击切换。
 *
 * 切换只改根节点的 `data-theme`，不改页面结构、不走路由、不发请求；
 * 偏好持久化在 useTheme 里，刷新后仍在。
 */
const { theme, toggle } = useTheme()

const iconUrl = computed(() => (theme.value === 'dark' ? moonUrl : sunUrl))
const label = computed(() => (theme.value === 'dark' ? '切换到白天模式' : '切换到黑夜模式'))
const iconAlt = computed(() => (theme.value === 'dark' ? '月亮' : '太阳'))
</script>

<template>
  <button
    type="button"
    class="theme-toggle"
    data-testid="theme-toggle"
    :data-theme-state="theme"
    :aria-label="label"
    :title="label"
    @click="toggle"
  >
    <img class="theme-toggle__icon" :src="iconUrl" :alt="iconAlt" aria-hidden="true" />
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: none;
  padding: 0;
  border: 1px solid var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-ink-muted);
  cursor: pointer;
  box-shadow: var(--pr-shadow-paper);
}

.theme-toggle:hover {
  background: var(--pr-row-hover);
  color: var(--pr-ink);
}

.theme-toggle__icon {
  width: 24px;
  height: 24px;
  pointer-events: none;
}
</style>
