<script setup lang="ts">
import { computed } from 'vue'

import arrowDownUrl from '../assets/sketch/sketch-arrow-down.svg'
import circleUrl from '../assets/sketch/sketch-circle.svg'
import type { ChangeEvidence, ChangeListItem } from '../api/types'
import { isLocatable } from '../composables/useOffsetLocator'

/**
 * 冲突条：呈现 report.change_list 里 section === '题目约束与数字冲突' 的一条。
 *
 * - 徽标原样显示 `finding_kind`（数字冲突 / 越界 / 未提到条件 / 缺少情形 / 引用缺失），
 *   不显示 `kind` 的字面值（「数字冲突」与「题目约束」都属于这一段）；
 * - 标题用 `target`，为空时退回 `upstream_id`；
 * - `evidence[]` 逐条显示 text；带 char_start/char_end 的才是可点击的「证据定位」按钮；
 *   evidence 为空数组（未提到条件 / 缺少情形）只显示 target 与 action，不渲染任何定位按钮。
 */
const props = defineProps<{
  item: ChangeListItem
  /** 当前命中定位的证据键；命中才给对应按钮标 data-located。 */
  locatedKey: string | null
}>()

const emit = defineEmits<{
  (event: 'locate', payload: { key: string; evidence: ChangeEvidence }): void
}>()

const title = computed(() => {
  const target = props.item.target
  return target && target.trim() ? target : props.item.upstream_id
})

const badge = computed(() => props.item.finding_kind ?? props.item.kind)

function evidenceKey(evidenceIndex: number): string {
  // 上游 id + evidence 序号：一条冲突里的两处取值各自独立可定位。
  return `${props.item.upstream_id}:${evidenceIndex}`
}
</script>

<template>
  <article class="conflict sk-card-frame" data-testid="conflict-item">
    <header class="conflict__head">
      <span class="conflict__badge" data-testid="conflict-kind">{{ badge }}</span>
      <h2 class="conflict__title">{{ title }}</h2>
    </header>

    <p class="conflict__action" data-testid="conflict-action">
      <img class="conflict__action-arrow" :src="arrowDownUrl" alt="" aria-hidden="true" />
      {{ item.action }}
    </p>

    <section v-if="item.evidence.length > 0" class="conflict__evidence">
      <h3 class="conflict__label">证据</h3>
      <ul class="conflict__evidence-list">
        <li
          v-for="(evidence, evidenceIndex) in item.evidence"
          :key="evidenceIndex"
          class="conflict__evidence-item"
        >
          <button
            v-if="isLocatable(evidence)"
            type="button"
            class="conflict__hit"
            data-testid="evidence-hit"
            :data-located="evidenceKey(evidenceIndex) === locatedKey ? 'true' : null"
            @click="emit('locate', { key: evidenceKey(evidenceIndex), evidence })"
          >
            <span class="conflict__hit-label">
              <img class="conflict__hit-circle" :src="circleUrl" alt="" aria-hidden="true" />
              {{ evidence.text ?? '' }}
            </span>
          </button>
          <span v-else class="conflict__evidence-text">{{ evidence.text ?? '' }}</span>
        </li>
      </ul>
    </section>
  </article>
</template>

<style scoped>
.conflict {
  padding: var(--pr-card-pad);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.conflict__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
}

.conflict__badge {
  padding: 0 var(--pr-space-2);
  border: 1px solid var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.conflict__title {
  margin: 0;
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.conflict__action {
  display: flex;
  align-items: flex-start;
  gap: var(--pr-space-2);
  margin: var(--pr-space-2) 0 0;
}

.conflict__action-arrow {
  width: 18px;
  height: 24px;
  flex: none;
  margin-top: 2px;
}

.conflict__evidence {
  margin-top: var(--pr-space-3);
}

.conflict__label {
  margin: 0 0 var(--pr-space-1);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-xs);
  font-weight: 600;
}

.conflict__evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.conflict__hit {
  padding: var(--pr-space-1) var(--pr-space-3);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-primary);
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
  cursor: pointer;
}

/* 固定比例容器：与 sketch-circle.svg 的 140:90 一致，圈 inset 撑满时 SVG 正好填满 */
.conflict__hit-label {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 28px;
  aspect-ratio: 140 / 90;
}

.conflict__hit:hover {
  background: var(--pr-primary-soft);
}

.conflict__hit-circle {
  position: absolute;
  inset: -6px -8px;
  pointer-events: none;
}

.conflict__hit[data-located='true'] {
  border-color: var(--pr-primary-strong);
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
}

.conflict__evidence-text {
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
}
</style>
