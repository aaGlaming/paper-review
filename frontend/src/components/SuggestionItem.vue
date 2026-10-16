<script setup lang="ts">
import { computed } from 'vue'

import type { ChangeEvidence, ChangeListItem } from '../api/types'
import { isLocatable } from '../composables/useOffsetLocator'

/**
 * 建议条：呈现 report.change_list 的一条，覆盖审查类与维度类两种形状。
 *
 * - **先判形状**：带 `finding_kind` 的是审查类（徽标显示 finding_kind），
 *   带 `dimension_code` 的是维度类（徽标显示 kind）。`finding_kind ?? kind` 一次覆盖两种，
 *   不会静默取到 undefined；
 * - 标题用 `target`，为空时退回 `upstream_id`；
 * - `evidence[]` 逐条显示 text；带 char_start/char_end 的（审查类）才是可点击的定位按钮，
 *   维度类证据无偏移、纯展示，不给定位按钮；
 * - 上游指针显示 `upstream_id`（需求 §12.3「每条建议指回上游」的可见化）。
 */
const props = defineProps<{
  item: ChangeListItem
  /** 当前命中定位的证据键；命中才给对应按钮标 data-located。 */
  locatedKey: string | null
}>()

const emit = defineEmits<{
  (event: 'locate', payload: { key: string; evidence: ChangeEvidence }): void
}>()

const badge = computed(() => props.item.finding_kind ?? props.item.kind)

const title = computed(() => {
  const target = props.item.target
  return target && target.trim() ? target : props.item.upstream_id
})

function evidenceKey(evidenceIndex: number): string {
  return `${props.item.upstream_id}:${evidenceIndex}`
}
</script>

<template>
  <article class="suggestion sk-card-frame" data-testid="suggestion-item">
    <header class="suggestion__head">
      <span class="suggestion__badge" data-testid="suggestion-kind">{{ badge }}</span>
      <h3 class="suggestion__title">{{ title }}</h3>
    </header>

    <p class="suggestion__action" data-testid="suggestion-action">{{ item.action }}</p>

    <section v-if="item.evidence.length > 0" class="suggestion__evidence">
      <h4 class="suggestion__label">当前证据</h4>
      <ul class="suggestion__evidence-list">
        <li
          v-for="(evidence, evidenceIndex) in item.evidence"
          :key="evidenceIndex"
          class="suggestion__evidence-item"
        >
          <button
            v-if="isLocatable(evidence)"
            type="button"
            class="suggestion__hit"
            data-testid="evidence-hit"
            :data-located="evidenceKey(evidenceIndex) === locatedKey ? 'true' : null"
            @click="emit('locate', { key: evidenceKey(evidenceIndex), evidence })"
          >
            {{ evidence.text ?? '' }}
          </button>
          <span v-else class="suggestion__evidence-text">{{ evidence.text ?? '' }}</span>
        </li>
      </ul>
    </section>

    <p class="suggestion__upstream" data-testid="upstream-id">{{ item.upstream_id }}</p>
  </article>
</template>

<style scoped>
.suggestion {
  padding: var(--pr-card-pad);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.suggestion__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
}

.suggestion__badge {
  padding: 0 var(--pr-space-2);
  border: 1px solid var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.suggestion__title {
  margin: 0;
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.suggestion__action {
  margin: var(--pr-space-2) 0 0;
}

.suggestion__evidence {
  margin-top: var(--pr-space-3);
}

.suggestion__label {
  margin: 0 0 var(--pr-space-1);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-xs);
  font-weight: 600;
}

.suggestion__evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.suggestion__hit {
  padding: var(--pr-space-1) var(--pr-space-3);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-primary);
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
  cursor: pointer;
}

.suggestion__hit[data-located='true'] {
  border-color: var(--pr-primary-strong);
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
}

.suggestion__evidence-text {
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-sm);
}

.suggestion__upstream {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-faint);
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-xs);
}
</style>
