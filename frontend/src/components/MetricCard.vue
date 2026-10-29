<script setup lang="ts">
import { computed } from 'vue'

import type { EvalMetric } from '../api/types'

/**
 * 指标卡：呈现 getEvalSummary() 返回的一项指标。
 *
 * - `rate` 可能为 null（分母为 0 时后端给 null），显示「—（无样本）」而不是 0 或 NaN；
 * - `rate` 显示为百分比，但不放大加粗当成果——它旁边一定有 caliber 与来源说明（在页面层）；
 * - `matched / total` 原样显示，`caliber` 原文显示；
 * - **折线图按本卡自己的 matched/total 实时生成**（方案第 10 条：数据必须精确，只有视觉表现可以是手绘的）：
 *   保持手绘语言（微弯折线、数据点小圈、手绘坐标轴、虚线连到横轴），但走势由 rate 决定；
 *   rate 为 null 或 total 为 0 时不画线，只显示「—（无样本）」。
 */
const props = defineProps<{
  /** 指标代码：band_agreement / quote_exact_match / insufficient_evidence_hit。 */
  code: string
  /** 指标中文名：页面自有的标签，映射固定，不是来自后端。 */
  name: string
  metric: EvalMetric
}>()

function formatRate(rate: number | null): string {
  if (rate === null) {
    return '—（无样本）'
  }
  // 去掉尾随 0：1.0 → 100%，0.4333… → 43.3%，0.0 → 0%
  return `${Number((rate * 100).toFixed(1))}%`
}

const rateText = computed(() => props.metric.low_sample ? '样本过少' : formatRate(props.metric.rate))

function round(n: number): number {
  return Math.round(n * 10) / 10
}

// 折线几何：viewBox 200×84，横轴 y=72、顶部 y=10，末点高度由 rate 决定。
const chart = computed(() => {
  const total = props.metric.total
  const rate = props.metric.rate
  if (props.metric.low_sample || rate === null || total <= 0) {
    return null
  }
  const x0 = 16
  const x1 = 190
  const yBase = 72
  const yTop = 10
  const endY = round(yBase - (yBase - yTop) * rate)
  const midX = (x0 + x1) / 2
  const midY = round(yBase - (yBase - yTop) * rate * 0.82)
  return {
    line: `M${x0} ${yBase} C ${midX - 22} ${round(midY + 7)} ${midX + 26} ${round(midY - 5)} ${x1} ${endY}`,
    pointX: x1,
    pointY: endY,
    dash: `M${x1} ${endY} L${x1} ${yBase}`,
  }
})
</script>

<template>
  <article class="metric sk-card-frame" data-testid="metric-card" :data-metric="code">
    <span class="sk-tape" aria-hidden="true"></span>
    <h2 class="metric__name">{{ name }}</h2>
    <p class="metric__rate" data-testid="metric-rate">{{ rateText }}</p>
    <p class="metric__fraction" data-testid="metric-fraction">{{ metric.matched }} / {{ metric.total }}</p>
    <p v-if="metric.low_sample" class="metric__low-sample-note" data-testid="metric-low-sample-note">
      本指标分母仅 {{ metric.total }} 个维度，不足以支撑结论
    </p>
    <svg v-if="chart" class="metric__chart" viewBox="0 0 200 84" aria-hidden="true">
      <path d="M6 5 C5 28 5.5 58 7 78" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
      <path d="M4 76 C54 77 120 76.5 196 75.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
      <path class="metric__chart-line" :d="chart.line" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <circle :cx="chart.pointX" :cy="chart.pointY" r="3.4" fill="none" stroke="currentColor" stroke-width="1.3" />
      <path :d="chart.dash" fill="none" stroke="currentColor" stroke-width="0.9" stroke-linecap="round" opacity="0.35" stroke-dasharray="4 5" />
    </svg>
    <p class="metric__caliber" data-testid="metric-caliber">{{ metric.caliber }}</p>
  </article>
</template>

<style scoped>
.metric {
  padding: var(--pr-card-pad);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  transform: rotate(-0.4deg);
}

.metric__chart {
  display: block;
  width: 100%;
  height: 68px;
  margin: var(--pr-card-title-gap) 0;
}

.metric__chart-line { stroke-dasharray: 240; stroke-dashoffset: 240; animation: metric-line-draw var(--pr-motion-number) var(--pr-motion-ease) forwards; }
@keyframes metric-line-draw { to { stroke-dashoffset:0; } }
@media (prefers-reduced-motion:reduce) { .metric__chart-line { animation:none; stroke-dashoffset:0; } }

.metric__name {
  margin: 0 0 var(--pr-card-title-gap);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.metric__rate {
  margin: 0 0 var(--pr-space-1);
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-lg);
  /* 不放大加粗：这是脚本自检数字，不是成果 */
  font-weight: 400;
}

.metric__fraction {
  margin: 0 0 var(--pr-card-title-gap);
  color: var(--pr-ink-muted);
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
}

.metric__low-sample-note {
  margin: 0 0 var(--pr-card-title-gap);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-xs);
  line-height: var(--pr-leading-base);
}

.metric__caliber {
  margin: 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-xs);
  line-height: var(--pr-leading-base);
}
</style>
