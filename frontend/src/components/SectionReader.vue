<script setup lang="ts">
import type { PaperSection } from '../api/types'
import quoteUrl from '../assets/sketch/sketch-quote.svg'

/**
 * 正文（右栏）：原样呈现选中章节的 `content`，**不做 Markdown 解析**（本版不引 Markdown 库）。
 *
 * 正文上方给「主张 / 表格 / 引用」三块留了位置：这三样是需求点名要的解析产物，
 * 但后端从未产出（创建评审的响应里只有章节树与正文），所以这里只显示一行说明，
 * **不放占位假数据**。
 */
defineProps<{ section: PaperSection | null }>()
</script>

<template>
  <section class="reader" data-testid="section-reader">
    <template v-if="section">
      <h2 class="reader__title" data-testid="section-content-title">{{ section.title }}</h2>

      <div class="reader__reserved" data-testid="reserved-artifacts">
        <span class="reader__slot" data-reserved="claims">主张</span>
        <span class="reader__slot" data-reserved="tables">表格</span>
        <span class="reader__slot" data-reserved="citations">引用</span>
        <p class="reader__note" data-testid="reserved-note">
          上面三块由后端解析产出；创建评审的响应里只有章节树与正文，还没有它们。
        </p>
      </div>

      <div class="reader__quote">
        <img class="reader__quote-mark" :src="quoteUrl" alt="" aria-hidden="true" />
        <pre class="reader__body" data-testid="section-content">{{ section.content }}</pre>
      </div>
    </template>

    <p v-else class="reader__empty" data-testid="section-content-empty">
      点左栏的任一章节，这里显示它的正文原文。
    </p>
  </section>
</template>

<style scoped>
.reader {
  min-width: 0;
}

.reader__quote {
  display: flex;
  gap: var(--pr-space-2);
}

.reader__quote-mark {
  width: 20px;
  height: 20px;
  flex: none;
  margin-top: 3px;
  color: var(--pr-ink-faint);
}

.reader__title {
  margin: 0 0 var(--pr-space-3);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.reader__reserved {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--pr-space-2);
  margin-bottom: var(--pr-space-3);
  padding: var(--pr-space-2) var(--pr-space-3);
  border: 1px dashed var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-slot-bg);
}

.reader__slot {
  padding: 0 var(--pr-space-2);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-xs);
}

.reader__note {
  flex-basis: 100%;
  margin: 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-xs);
}

.reader__body {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--pr-font-quote);
  font-size: var(--pr-text-base);
  line-height: var(--pr-leading-quote);
}

.reader__empty {
  margin: 0;
  color: var(--pr-ink-faint);
}
</style>
