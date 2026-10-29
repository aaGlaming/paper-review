<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import type { PaperSection, ReviewArtifact } from '../api/types'
import quoteUrl from '../../../docs/design/sketch-svg/sketch-quote.svg'
import { locateSectionArtifact } from '../composables/useOffsetLocator'
import ArtifactPanel from './ArtifactPanel.vue'

/** 正文保留原文；产物面板只解析表格展示结构，不使用 v-html 注入用户内容。 */
const props = withDefaults(defineProps<{
  section: PaperSection | null
  sections?: PaperSection[]
  paperText?: string
  sectionsRanged?: boolean
  reviewId?: string
  artifacts?: ReviewArtifact[]
  canExtract?: boolean
  extracting?: boolean
  extractError?: string
}>(), {
  sections: () => [],
  paperText: '',
  sectionsRanged: false,
  reviewId: '',
  artifacts: () => [],
  canExtract: false,
  extracting: false,
  extractError: '',
})

const emit = defineEmits<{ extract: [] }>()
const locatedSection = ref<PaperSection | null>(null)
const located = ref<{ start: number; text: string; exact: boolean; note?: string } | null>(null)
const locatedMark = ref<HTMLElement | null>(null)
const displayedSection = computed(() => locatedSection.value ?? props.section)
const displayBody = computed(() => {
  const section = displayedSection.value
  if (!section) return ''
  if (props.sectionsRanged && props.paperText && typeof section.char_start === 'number' && typeof section.char_end === 'number') {
    return props.paperText.slice(section.char_start, section.char_end)
  }
  return section.content
})

async function locate(artifact: ReviewArtifact): Promise<void> {
  const owner = props.sections.find((section) =>
    typeof section.char_start === 'number' && typeof section.char_end === 'number' &&
    section.char_start <= artifact.char_start && artifact.char_start < section.char_end,
  ) ?? props.section
  if (!owner) return
  locatedSection.value = owner
  const source = props.sectionsRanged && props.paperText && typeof owner.char_start === 'number' && typeof owner.char_end === 'number'
    ? props.paperText.slice(owner.char_start, owner.char_end)
    : owner.content
  const result = locateSectionArtifact(owner, source, artifact)
  if (!result) return
  located.value = {
    start: result.start,
    text: result.text,
    exact: result.exact,
    note: result.approximateNote,
  }
  await nextTick()
  locatedMark.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <section class="reader" data-testid="section-reader">
    <template v-if="section">
      <h2 class="reader__title" data-testid="section-content-title">{{ displayedSection?.title ?? section.title }}</h2>

      <div class="reader__reserved" data-testid="reserved-artifacts">
        <ArtifactPanel
          v-if="reviewId"
          :artifacts="artifacts"
          :sections="sections.length ? sections : (section ? [section] : [])"
          :can-extract="canExtract"
          :extracting="extracting"
          :error-message="extractError"
          @locate="locate"
          @extract="emit('extract')"
        />
        <template v-else>
          <span class="reader__slot" data-reserved="claims">主张</span>
          <span class="reader__slot" data-reserved="tables">表格</span>
          <span class="reader__slot" data-reserved="citations">引用</span>
          <p class="reader__note" data-testid="reserved-note">
            产物会在评审确认后显示。
          </p>
        </template>
      </div>

      <div class="reader__quote">
        <img class="reader__quote-mark" :src="quoteUrl" alt="" aria-hidden="true" />
        <pre class="reader__body" data-testid="section-content">{{ located ? displayBody.slice(0, located.start) : displayBody }}<mark v-if="located" ref="locatedMark" data-testid="artifact-mark">{{ located.text }}</mark>{{ located ? displayBody.slice(located.start + located.text.length) : '' }}</pre>
      </div>
      <p v-if="located && !located.exact" class="reader__approx" data-testid="approximate-note">{{ located.note || '按偏移定位，未精确匹配' }}</p>
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

.reader__body mark {
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
  font-weight: 600;
}

.reader__approx {
  margin: var(--pr-space-2) 0 0;
  color: var(--pr-range);
  font-size: var(--pr-text-sm);
}

.reader__empty {
  margin: 0;
  color: var(--pr-ink-faint);
}
</style>
