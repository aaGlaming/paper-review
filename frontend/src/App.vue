<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppNav from './components/AppNav.vue'
import './styles/sketch.css'
</script>

<template>
  <div class="shell">
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

.shell__body {
  flex: 1;
  width: 100%;
  max-width: var(--pr-measure);
  margin: 0 auto;
  padding: var(--pr-space-6) var(--pr-space-4);
}
</style>
