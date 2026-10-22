<script setup lang="ts">
import { computed } from 'vue'

import { REVIEW_STAGES, type StagePhase } from '../composables/reviewVocabulary'

/**
 * 预审步骤指示器。**只按真实观测到的时点点亮，不补中间态。**
 *
 * `resume` 是同步接口，后端一次跑完六步，中间态拿不到。所以：
 * - 只有 `reachedIndex` 之内的步骤是「已完成」——那是页面真的收到过的证据；
 * - 请求在飞时只显示「处理中」这个不确定态，不逐条点亮；elapsed 只报告真实经过时间，不伪造步骤进度；
 * - 失败或超时显示「停在：等待服务返回」，绝不补一句评语。
 */
const props = defineProps<{
  phase: StagePhase
  /** 最后一个**真实观测到**已完成的步骤下标；-1 表示一个都没观测到。 */
  reachedIndex?: number
  elapsedSeconds?: number
  elapsedActive?: boolean
  slowHintMs?: number
}>()

const BADGE: Record<StagePhase, string> = {
  idle: '未开始',
  running: '处理中',
  parsed: '待确认',
  done: '已完成',
  failed: '停在：等待服务返回',
}

const NOTE: Record<StagePhase, string> = {
  idle: '尚未提交。',
  running: '等待服务返回：后端一次跑完这六步，中间态看不见，所以这里不逐条点亮。',
  parsed: '章节树已产出、赛题已绑定；确认之后才进入检索与选档。',
  done: '报告已收到，整条链路已跑完。',
  failed: '请求失败或超时，停在：等待服务返回；不补写任何评语。',
}

const badgeText = computed(() => BADGE[props.phase])
const elapsedSeconds = computed(() => props.elapsedSeconds ?? 0)
const showElapsed = computed(() => props.phase === 'running' && Boolean(props.elapsedActive))
const showSlowHint = computed(
  () => showElapsed.value && elapsedSeconds.value * 1_000 > (props.slowHintMs ?? 20_000),
)
const note = computed(() => {
  if (props.phase === 'failed') {
    return `请求失败或超时，停在：等待服务返回；已等待 ${elapsedSeconds.value} 秒后结束；不补写任何评语。`
  }
  return NOTE[props.phase]
})

const steps = computed(() =>
  REVIEW_STAGES.map((name, index) => ({
    name,
    done: index <= (props.reachedIndex ?? -1),
  })),
)
</script>

<template>
  <section class="tracker" data-testid="stage-tracker" :data-phase="phase">
    <header class="tracker__head">
      <h2 class="tracker__title">预审步骤</h2>
      <span class="tracker__badge" data-testid="stage-badge" :data-state="phase">{{ badgeText }}</span>
    </header>
    <ol class="tracker__steps">
      <li
        v-for="step in steps"
        :key="step.name"
        class="tracker__step"
        data-stage-step
        :data-state="step.done ? 'done' : 'pending'"
      >
        <span class="tracker__step-name">{{ step.name }}</span>
        <span class="tracker__step-mark">{{ step.done ? '已完成' : '未开始' }}</span>
      </li>
    </ol>
    <p v-if="showElapsed" class="tracker__elapsed" data-testid="stage-elapsed">
      已等待 {{ elapsedSeconds }} 秒
    </p>
    <p v-if="showSlowHint" class="tracker__slow-hint" data-testid="stage-slow-hint">
      已等待 {{ elapsedSeconds }} 秒，仍在处理；本流程正常需数十秒，可继续等待或稍后回来查看
    </p>
    <p class="tracker__note" data-testid="stage-note">{{ note }}</p>
  </section>
</template>

<style scoped>
.tracker {
  margin: var(--pr-space-6) 0;
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.tracker__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
}

.tracker__title {
  margin: 0;
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.tracker__badge {
  padding: 0 var(--pr-space-2);
  border-radius: var(--pr-radius);
  font-size: var(--pr-text-sm);
  transition: color var(--pr-motion-interaction) ease, background-color var(--pr-motion-interaction) ease;
}

.tracker__badge[data-state='idle'] {
  background: var(--pr-badge-idle-bg);
  color: var(--pr-badge-idle-ink);
}

.tracker__badge[data-state='running'] {
  background: var(--pr-badge-running-bg);
  color: var(--pr-badge-running-ink);
}

.tracker__badge[data-state='parsed'],
.tracker__badge[data-state='done'] {
  background: var(--pr-badge-done-bg);
  color: var(--pr-badge-done-ink);
}

.tracker__badge[data-state='failed'] {
  background: var(--pr-badge-stopped-bg);
  color: var(--pr-badge-stopped-ink);
}

.tracker__steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-4);
  margin: var(--pr-space-3) 0 0;
  padding: 0;
  list-style: none;
}

.tracker__step {
  display: flex;
  gap: var(--pr-space-1);
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.tracker__step[data-state='done'] {
  color: var(--pr-ink);
}

.tracker__step-mark {
  font-size: var(--pr-text-xs);
}

.tracker__elapsed,
.tracker__slow-hint {
  margin: var(--pr-space-3) 0 0;
  font-size: var(--pr-text-sm);
}

.tracker__elapsed {
  color: var(--pr-ink);
  font-variant-numeric: tabular-nums;
}

.tracker__slow-hint {
  color: var(--pr-ink-muted);
}

.tracker__note {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

@media (prefers-reduced-motion:reduce) { .tracker__badge { transition:none; } }
</style>
