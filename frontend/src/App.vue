<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppNav from './components/AppNav.vue'
import './styles/sketch.css'

const route = useRoute()
const isPublicRoute = computed(() => route.meta.public === true)
</script>

<template>
  <div class="shell">
    <div class="photo-bg" aria-hidden="true"></div>
    <AppNav v-if="!isPublicRoute" />
    <main class="shell__body" :class="{ 'shell__body--auth': isPublicRoute }" tabindex="-1">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="page" mode="out-in">
          <component :is="Component" :key="viewRoute.path" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

/* 全局照片底图：fixed 铺满视口，z-index:-1 落在 shell 层叠上下文底部——
   在内容之下、在 body 纸底之上；纱罩用主题变量保证双主题可读。
   fixed 不占布局、不产滚动；pointer-events 穿透。 */
.photo-bg {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image:
    linear-gradient(var(--pr-photo-veil), var(--pr-photo-veil)),
    url('./assets/sketch/photo-background.jpg');
  background-size: cover, cover;
  background-position: center, center;
  background-repeat: no-repeat, no-repeat;
}

.shell__body {
  flex: 1;
  width: 100%;
  max-width: var(--pr-measure);
  margin: 0 auto;
  padding: var(--pr-space-6) var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-top: 0;
  background: var(--pr-surface);
  box-shadow: var(--pr-shadow-sheet);
}

.shell__body--auth {
  display: grid;
  place-items: center;
  width: 100%;
  max-width: none;
  min-height: 100vh;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.page-enter-active,
.page-leave-active {
  transition: opacity var(--pr-motion-page) var(--pr-motion-ease), transform var(--pr-motion-page) var(--pr-motion-ease);
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
  transform: translateY(5px);
}

@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
}
</style>
