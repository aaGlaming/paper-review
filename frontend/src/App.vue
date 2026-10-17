<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppNav from './components/AppNav.vue'
import './styles/sketch.css'
</script>

<template>
  <div class="shell">
    <div class="photo-bg" aria-hidden="true"></div>
    <AppNav />
    <main class="shell__body">
      <RouterView />
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
}
</style>
