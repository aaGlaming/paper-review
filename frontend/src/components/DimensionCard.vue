<script setup lang="ts">
import { computed } from 'vue'

import circleUrl from '../assets/sketch/sketch-circle.svg'
import magnifierUrl from '../assets/sketch/sketch-magnifier.svg'
import type { DimensionResult } from '../api/types'

/**
 * 维度卡：逐条呈现 report.dimensions 的一项，顺序与后端一致，本组件不排序、不过滤。
 *
 * - 维度标识用 `dimension_code` 原样显示，**不翻译、不臆造中文名**；
 * - 「量规条文」预留一块：维度中文名、权重、四档说明没有任何接口能拿到，只显示说明；
 * - `quote` 为 null 时显示「未给原句」，定位按钮置灰并说明原因。
 */
const props = defineProps<{ dimension: DimensionResult }>()

const emit = defineEmits<{ (event: 'locate', dimension: DimensionResult): void }>()

const insufficient = computed(() => props.dimension.band === '证据不足')
</script>

<template>
  <article
    class="card sk-card-frame"
    data-testid="dimension-card"
    :data-dimension="dimension.dimension_code"
    :data-band="dimension.band ?? ''"
    :data-insufficient="insufficient ? 'true' : null"
  >
    <span class="sk-tape" aria-hidden="true"></span>
    <header class="card__head">
      <h2 class="card__code">{{ dimension.dimension_code }}</h2>
      <span class="card__band-wrap">
        <img class="card__band-circle" :src="circleUrl" alt="" aria-hidden="true" />
        <span class="card__band" data-testid="band">{{ dimension.band ?? '未选档' }}</span>
      </span>
      <span class="card__status" data-testid="status">{{ dimension.status ?? '—' }}</span>
    </header>

    <section class="card__section" data-testid="rubric-reserved">
      <h3 class="card__label">量规条文</h3>
      <p class="card__reserved-note">
        维度名、权重与四档说明由后端量规提供，当前接口未给出（赛题接口只有 rubric_id 与 version）。
      </p>
    </section>

    <section class="card__section" data-testid="quote-section">
      <h3 class="card__label">论文原句</h3>
      <p v-if="dimension.quote" class="card__quote" data-testid="quote-text">{{ dimension.quote }}</p>
      <p v-else class="card__noquote" data-testid="no-quote">未给原句：证据不足不产生引用</p>
    </section>

    <section class="card__section">
      <h3 class="card__label">切片编号</h3>
      <p class="card__chunks" data-testid="chunk-ids">
        {{ dimension.chunk_ids.length > 0 ? dimension.chunk_ids.join('、') : '无切片' }}
      </p>
    </section>

    <div class="card__foot">
      <button
        type="button"
        class="card__locate"
        data-testid="locate-quote"
        :disabled="!dimension.quote"
        @click="emit('locate', dimension)"
      >
        <img class="card__locate-icon" :src="magnifierUrl" alt="" aria-hidden="true" />
        定位原句
      </button>
      <span v-if="!dimension.quote" class="card__locate-hint">未给原句，无法定位</span>
    </div>
  </article>
</template>

<style scoped>
.card {
  padding: var(--pr-card-pad);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.card[data-insufficient='true'] {
  background: var(--pr-insufficient-soft);
}

/* 固定比例容器：与 sketch-circle.svg 的 140:90 一致，圈 inset 撑满时 SVG 正好填满、
   不触发"inset + auto + 内旋比"的边缘情况，圈心稳居文字心。 */
.card__band-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 28px;
  aspect-ratio: 140 / 90;
}

/* 圈只用 inset（不写 width/height）：与 inset 混用会互相覆盖、把圈拉偏。 */
.card__band-circle {
  position: absolute;
  inset: -6px -8px;
  pointer-events: none;
}

.card__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
}

.card__code {
  margin: 0;
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.card__band {
  padding: 0 var(--pr-space-2);
  border: 1px solid var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  font-size: var(--pr-text-sm);
}

.card[data-insufficient='true'] .card__band {
  border-color: var(--pr-insufficient);
  color: var(--pr-insufficient);
}

.card__status {
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.card__section {
  margin-top: var(--pr-space-3);
}

.card__label {
  margin: 0 0 var(--pr-space-1);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-xs);
  font-weight: 600;
}

.card__reserved-note,
.card__noquote {
  margin: 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.card__quote {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--pr-font-quote);
  line-height: var(--pr-leading-quote);
}

.card__chunks {
  margin: 0;
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
}

.card__foot {
  display: flex;
  align-items: center;
  gap: var(--pr-space-3);
  margin-top: var(--pr-space-3);
}

.card__locate {
  display: inline-flex;
  align-items: center;
  gap: var(--pr-space-1);
  padding: var(--pr-space-1) var(--pr-space-3);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-primary);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-sm);
  cursor: pointer;
  box-shadow: var(--pr-shadow-paper);
}

.card__locate:hover {
  background: var(--pr-primary-soft);
}

.card__locate-icon {
  width: 16px;
  height: 16px;
}

.card__locate:disabled {
  border-color: var(--pr-rule);
  color: var(--pr-ink-faint);
  cursor: not-allowed;
}

.card__locate-hint {
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-xs);
}
</style>
