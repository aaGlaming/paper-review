<script setup lang="ts">
import type { ChatSessionItem } from '../../api/types'

defineProps<{ sessions: ChatSessionItem[]; activeId: string | null; loading: boolean }>()
const emit = defineEmits<{ create: []; select: [id: string]; remove: [id: string] }>()
</script>
<template>
  <aside class="sessions" aria-label="问询会话">
    <el-button type="primary" :loading="loading" @click="emit('create')">新建会话</el-button>
    <div class="sessions__list">
      <div v-for="item in sessions" :key="item.session_id" class="sessions__row" :class="{ active: activeId === item.session_id }">
        <button class="sessions__select" type="button" @click="emit('select', item.session_id)">{{ item.title }}</button>
        <el-button text type="danger" aria-label="删除会话" @click="emit('remove', item.session_id)">删除</el-button>
      </div>
      <p v-if="!sessions.length" class="muted">还没有会话</p>
    </div>
  </aside>
</template>
<style scoped>
.sessions { display:flex; flex-direction:column; gap:1rem; min-height:0 }
.sessions__list { overflow:auto }
.sessions__row { display:flex; align-items:center; border-bottom:1px solid var(--pr-rule); gap:.25rem }
.sessions__row.active { background:var(--pr-primary-soft) }
.sessions__select { flex:1; min-width:0; text-align:left; border:0; background:transparent; padding:.75rem .4rem; color:var(--pr-ink); cursor:pointer; overflow:hidden; text-overflow:ellipsis }
.muted { color:var(--pr-ink-muted) }
</style>
