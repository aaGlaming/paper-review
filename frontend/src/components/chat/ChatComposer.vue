<script setup lang="ts">
import type { ContestSummary } from '../../api/types'

defineProps<{ contests: ContestSummary[]; contestId: string; busy: boolean }>()
const emit = defineEmits<{ 'update:contestId': [id: string]; send: [question: string] }>()
const question = defineModel<string>('question', { required: true })
</script>
<template>
  <section class="composer">
    <el-select :model-value="contestId" placeholder="请选择赛题范围" aria-label="赛题范围" @change="emit('update:contestId', $event)">
      <el-option v-for="contest in contests" :key="contest.contest_id" :label="`${contest.year} · ${contest.problem_code} · ${contest.title}`" :value="contest.contest_id" />
    </el-select>
    <el-input v-model="question" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="输入要问的问题" aria-label="问询内容" @keydown.ctrl.enter="emit('send', question)" />
    <el-button type="primary" :loading="busy" :disabled="!contestId || !question.trim()" @click="emit('send', question)">发送</el-button>
  </section>
</template>
<style scoped>
.composer { display:grid; grid-template-columns:minmax(200px, 1fr) auto; gap:.65rem; align-items:end; padding-top:1rem; border-top:1px solid var(--pr-rule) }
.composer :deep(.el-textarea) { grid-column:1 / -1 }
@media(max-width:600px) { .composer { grid-template-columns:1fr } .composer :deep(.el-textarea) { grid-column:auto } }
</style>
