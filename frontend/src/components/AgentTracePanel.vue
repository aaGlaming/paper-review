<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { fetchAgentSteps } from '../api'
import type { AgentStep } from '../api/types'

const props = defineProps<{ reviewId: string; terminatedBy?: string | null }>()
const steps = ref<AgentStep[]>([])
const open = ref(false)
const loading = ref(false)
const error = ref('')
const reasonText = computed(() => ({ budget_exhausted: '棰勭畻鑰楀敖', no_progress: '连续无新证据' }[props.terminatedBy || ''] || ''))
const lastStep = computed(() => [...steps.value].sort((a, b) => a.idx - b.idx).at(-1))

async function load(): Promise<void> {
  if (!props.reviewId) return
  loading.value = true
  error.value = ''
  try {
    const response = await fetchAgentSteps(props.reviewId)
    steps.value = [...response.steps].sort((a, b) => a.idx - b.idx)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : String(reason)
  } finally {
    loading.value = false
  }
}

onMounted(() => void load())
watch(() => props.reviewId, () => void load())
</script>

<template>
  <section class="trace">
    <button class="trace__toggle" type="button" :aria-expanded="open" @click="open = !open">
      Agent 轨迹（{{ steps.length }} 步）
    </button>
    <div v-if="open" class="trace__body">
      <p v-if="reasonText && lastStep" class="trace__termination">
        本次在第 {{ lastStep.idx }} 步停止：{{ lastStep.action }}（原因：{{ reasonText }}）</p>
      <p v-if="loading" class="trace__muted">正在读取轨迹…</p>
      <div v-else-if="error" class="trace__error">
        <span>{{ error }}</span>
        <button type="button" @click="load">重试</button>
      </div>
      <p v-else-if="steps.length === 0" class="trace__muted">本次评审未产生 Agent 轨迹</p>
      <ol v-else class="trace__rows">
        <li v-for="step in steps" :key="step.idx" class="trace__row" :class="{ 'trace__row--error': !step.ok }">
          <span>#{{ step.idx }}</span><strong>{{ step.action }}</strong><span>{{ step.result_note }}</span>
          <span>{{ step.ok ? 'ok' : `错误码：${step.error_code || 'unknown'}` }}</span><span>{{ step.elapsed_ms }} ms</span>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.trace { margin-top: var(--pr-space-4); border-top: 1px solid var(--pr-rule); }
.trace__toggle { width: 100%; padding: var(--pr-space-3) 0; border: 0; background: transparent; color: var(--pr-ink); text-align: left; cursor: pointer; }
.trace__body { padding-bottom: var(--pr-space-3); }
.trace__rows { display: grid; gap: var(--pr-space-1); margin: 0; padding: 0; list-style: none; }
.trace__row { display: grid; grid-template-columns: 3rem 10rem 1fr 8rem 5rem; gap: var(--pr-space-2); padding: var(--pr-space-2); border-bottom: 1px solid var(--pr-rule); }
.trace__row--error { color: var(--pr-danger); background: var(--pr-conflict-soft); }
.trace__muted { color: var(--pr-ink-muted); }
.trace__error { display: flex; gap: var(--pr-space-3); color: var(--pr-danger); }
.trace__termination { color: var(--pr-warning); }
</style>



