<script setup lang="ts">
import { RouterLink } from 'vue-router'

import ThemeToggle from './ThemeToggle.vue'

// 五个页面入口。顺序即评审流程的顺序：先解析、再评分、再审查、再改、最后对照评测。
const items = [
  { label: '论文解析', to: '/parse' },
  { label: '分项评分', to: '/scoring' },
  { label: '一致性审查', to: '/consistency' },
  { label: '修改建议', to: '/suggestions' },
  { label: '评测对照', to: '/eval' },
] as const
</script>

<template>
  <header class="nav">
    <div class="nav__brand">
      <span class="nav__flow" aria-hidden="true">01–05</span>
      <span class="nav__name">竞赛论文预审工作台</span>
    </div>
    <nav class="nav__links">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="nav__link"
        data-nav-item
      >
        {{ item.label }}
      </RouterLink>
    </nav>
    <div class="nav__spacer" aria-hidden="true"></div>
    <ThemeToggle />
  </header>
</template>

<style scoped>
.nav {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-6);
  padding: var(--pr-space-3) var(--pr-space-4);
  border-bottom: 1px solid var(--pr-rule);
  background: var(--pr-surface);
}

.nav__brand {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  flex: none;
}

.nav__flow {
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-lg);
  color: var(--pr-ink-faint);
  letter-spacing: 0.02em;
}

.nav__name {
  font-size: var(--pr-text-lg);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.nav__links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-4);
}

.nav__spacer {
  flex: 1;
}

.nav__link {
  position: relative;
  padding-bottom: var(--pr-space-1);
  color: var(--pr-ink-muted);
  text-decoration: none;
}

.nav__link:hover {
  color: var(--pr-ink);
}

.nav__link.router-link-active {
  color: var(--pr-ink);
}

/* 激活态：手绘下划线（sketch-underline.svg），替代 CSS 下划线 */
.nav__link.router-link-active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 10px;
  background-image: url('../assets/sketch/sketch-underline.svg');
  background-size: 100% 100%;
  background-repeat: no-repeat;
  pointer-events: none;
}
</style>
