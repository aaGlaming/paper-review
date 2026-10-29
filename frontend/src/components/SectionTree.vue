<script setup lang="ts">
import type { PaperSection } from '../api/types'
import { SECTION_TYPE_OPTIONS } from '../composables/reviewVocabulary'
import docTreeUrl from '../../../docs/design/sketch-svg/sketch-doc-tree.svg'

/**
 * 章节树（左栏）。层级用**缩进**表达：`level` 映射成 `--pr-depth`，缩进量在 CSS 里算。
 * 不用 01 / 02 / 03 这类装饰性编号——这不是序列，是层级。
 */
defineProps<{ sections: PaperSection[]; selectedIndex: number }>()

const emit = defineEmits<{
  (event: 'select', index: number): void
  (event: 'change-type', index: number, value: string): void
}>()

function depthOf(section: PaperSection): number {
  return Math.max(section.level - 1, 0)
}

function onChange(index: number, event: Event): void {
  emit('change-type', index, (event.target as HTMLSelectElement).value)
}
</script>

<template>
  <nav class="tree" data-testid="section-tree" aria-label="章节树">
    <h2 class="tree__title">
      <img class="tree__icon" :src="docTreeUrl" alt="" aria-hidden="true" />
      章节树
    </h2>
    <ul class="tree__list">
      <li
        v-for="(section, index) in sections"
        :key="`${index}-${section.title}`"
        class="tree__row"
        data-testid="section-item"
        :data-depth="String(depthOf(section))"
        :data-selected="index === selectedIndex ? 'true' : 'false'"
        :style="{ '--pr-depth': String(depthOf(section)) }"
        @click="emit('select', index)"
      >
        <span class="tree__name">{{ section.title }}</span>
        <select
          class="tree__type"
          data-testid="section-type"
          :value="section.section_type"
          aria-label="章节类型"
          @click.stop
          @change="onChange(index, $event)"
        >
          <option v-for="option in SECTION_TYPE_OPTIONS" :key="option" :value="option">
            {{ option }}
          </option>
        </select>
      </li>
    </ul>
    <p class="tree__hint">点一条看它的正文；类型可以改，确认时才提交。</p>
  </nav>
</template>

<style scoped>
.tree {
  min-width: 0;
  border-right: 1px solid var(--pr-rule);
  padding-right: var(--pr-space-4);
}

@media (max-width: 900px) {
  .tree {
    border-right: 0;
    border-bottom: 1px solid var(--pr-rule);
    padding-right: 0;
    padding-bottom: var(--pr-space-4);
  }
}

.tree__title {
  display: flex;
  align-items: center;
  gap: var(--pr-space-2);
  margin: 0 0 var(--pr-space-3);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.tree__icon {
  width: 20px;
  height: 20px;
  flex: none;
}

.tree__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.tree__row {
  display: flex;
  align-items: center;
  gap: var(--pr-space-2);
  padding-top: var(--pr-space-1);
  padding-bottom: var(--pr-space-1);
  /* 层级缩进：depth 由行内的 --pr-depth 给出，量在令牌里 */
  padding-left: calc(var(--pr-indent) * var(--pr-depth, 0));
  border-radius: var(--pr-radius);
  cursor: pointer;
}

.tree__row:hover {
  background: var(--pr-row-hover);
}

.tree__row[data-selected='true'] {
  background: var(--pr-row-selected);
}

.tree__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree__type {
  flex: none;
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-ink-muted);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-sm);
}

.tree__hint {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-xs);
}
</style>
