<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import arrowRightUrl from '../assets/sketch/sketch-arrow-right.svg'
import type { ChangeEvidence, PaperSection, ReviewReport } from '../api/types'
import StageTracker from '../components/StageTracker.vue'
import SuggestionItem from '../components/SuggestionItem.vue'
import { concatSections, locateEvidence, type EvidenceLocation } from '../composables/useOffsetLocator'
import { readReviewFlow } from '../composables/useReviewFlow'

/**
 * 修改建议页（P8 阶段 5/6）。
 *
 * 数据唯一来源是共享状态里的 `report.change_list` **全部**条目。三段顺序就是修改顺序
 * （需求「先改硬伤、再补证据、最后改表述」），后端 `change_list.py` 已排好，页面按
 * `section` 分组、段内按后端顺序渲染，**前端不 sort、不过滤**。某段为空仍渲染该段标题 +
 * 「本段无建议」，不让框架消失。
 *
 * 本页只读共享状态：没有 report 就显示空态（文案不含任何建议字样），不兜底调 getReview。
 * 审查类带偏移的证据点击后复用 useOffsetLocator（拼接正文 + indexOf 校准 + 三段高亮），禁 v-html。
 */
const SECTION_ORDER = ['题目约束与数字冲突', '证据不足', '表述'] as const

const report = ref<ReviewReport | null>(null)
const sections = ref<PaperSection[]>([])

const body = computed(() => concatSections(sections.value))

const grouped = computed(() =>
  SECTION_ORDER.map((section) => ({
    section,
    items: report.value ? report.value.change_list.filter((item) => item.section === section) : [],
  })),
)

const contestId = computed(() => report.value?.contest_id ?? '')
const rubricVersion = computed(() => report.value?.rubric_version ?? null)
const status = computed(() => report.value?.status ?? '')
const source = computed(() => report.value?.source ?? '')

// report 在手 ⇒ 六步确实跑完（否则不会有报告）；无 report 时 idle，不伪造进度。
const stagePhase = computed(() => (report.value ? ('done' as const) : ('idle' as const)))

interface LocatedState extends EvidenceLocation {
  key: string
}
const located = ref<LocatedState | null>(null)
const locatedEl = ref<HTMLElement | null>(null)

onMounted(() => {
  const flow = readReviewFlow()
  sections.value = flow.sections.map((section) => ({ ...section }))
  report.value = flow.report
})

async function handleLocate(payload: { key: string; evidence: ChangeEvidence }): Promise<void> {
  const result = locateEvidence(body.value, payload.evidence)
  if (!result) {
    located.value = null
    return
  }
  located.value = { key: payload.key, ...result }
  await nextTick()
  locatedEl.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <article class="suggestions" data-testid="suggestions-page">
    <header class="suggestions__head">
      <span class="suggestions__num" aria-hidden="true">04</span>
      <h1 class="suggestions__title">修改建议</h1>
    </header>

    <StageTracker :phase="stagePhase" :reached-index="report ? 5 : -1" />

    <template v-if="report">
      <header class="suggestions__bar" data-testid="suggestions-bar">
        <dl class="suggestions__meta">
          <div class="suggestions__meta-item">
            <dt>赛题</dt>
            <dd>{{ contestId || '—' }}</dd>
          </div>
          <div class="suggestions__meta-item">
            <dt>量规版本</dt>
            <dd>{{ rubricVersion ?? '未绑定量规' }}</dd>
          </div>
          <div class="suggestions__meta-item">
            <dt>状态</dt>
            <dd>{{ status }}</dd>
          </div>
          <div class="suggestions__meta-item">
            <dt>来源</dt>
            <dd>{{ source }}</dd>
          </div>
        </dl>
      </header>

      <section
        v-for="(group, index) in grouped"
        :key="group.section"
        class="suggestions__section"
        data-testid="suggestion-section"
        :data-section="group.section"
      >
        <h2 class="suggestions__section-title">
          <span class="suggestions__section-num" aria-hidden="true">
            {{ String(index + 1).padStart(2, '0') }}
          </span>
          <span class="suggestions__section-name">{{ group.section }}</span>
        </h2>
        <div v-if="group.items.length > 0" class="suggestions__list">
          <SuggestionItem
            v-for="item in group.items"
            :key="item.upstream_id"
            :item="item"
            :located-key="located?.key ?? null"
            @locate="handleLocate"
          />
        </div>
        <p v-else class="suggestions__empty-section" data-testid="section-empty">本段无建议</p>
        <img
          v-if="index < grouped.length - 1"
          class="suggestions__section-arrow"
          :src="arrowRightUrl"
          alt=""
          aria-hidden="true"
        />
      </section>

      <section v-if="located" class="suggestions__located" data-testid="located-content">
        <h2 class="suggestions__subtitle">原文定位</h2>
        <!-- 文本节点三段拼接（前段 / mark 命中段 / 后段），禁 v-html：正文是用户可控输入。 -->
        <pre class="suggestions__located-body">{{ body.slice(0, located.start) }}<mark ref="locatedEl" data-testid="located-mark">{{ located.text }}</mark>{{ body.slice(located.start + located.text.length) }}</pre>
        <p v-if="!located.exact" class="suggestions__approx" data-testid="approximate-note">
          {{ located.approximateNote }}
        </p>
      </section>
    </template>

    <template v-else>
      <section class="suggestions__empty" data-testid="suggestions-empty">
        <h2 class="suggestions__empty-title">还没有修改建议</h2>
        <p class="suggestions__empty-link"><RouterLink to="/parse">去论文解析页</RouterLink></p>
      </section>
    </template>
  </article>
</template>

<style scoped>
.suggestions {
  max-width: var(--pr-measure);
}

.suggestions__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  margin: 0 0 var(--pr-space-2);
}

.suggestions__num {
  font-family: var(--pr-font-data);
  font-size: 28px;
  line-height: 1;
  color: var(--pr-ink-faint);
}

.suggestions__title {
  margin: 0;
  font-size: var(--pr-text-title);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.suggestions__bar {
  margin: var(--pr-space-4) 0;
  padding: var(--pr-space-3) var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.suggestions__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-6);
  margin: 0;
}

.suggestions__meta-item {
  display: flex;
  gap: var(--pr-space-2);
}

.suggestions__meta-item dt {
  color: var(--pr-ink-muted);
}

.suggestions__meta-item dd {
  margin: 0;
}

.suggestions__section {
  margin-top: var(--pr-space-6);
}

.suggestions__section-title {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-2);
  margin: 0 0 var(--pr-space-3);
  padding-bottom: var(--pr-space-2);
  border-bottom: 1px solid var(--pr-rule);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.suggestions__section-num {
  font-family: var(--pr-font-data);
  font-size: var(--pr-text-base);
  color: var(--pr-ink-faint);
  letter-spacing: 0.02em;
}

.suggestions__section-arrow {
  display: block;
  width: 40px;
  height: 18px;
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-faint);
}

.suggestions__list {
  display: flex;
  flex-direction: column;
  gap: var(--pr-card-gap);
}

.suggestions__empty-section {
  margin: 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.suggestions__located {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-primary-soft);
}

.suggestions__subtitle {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.suggestions__located-body {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--pr-font-quote);
  line-height: var(--pr-leading-quote);
}

.suggestions__located-body mark {
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
  font-weight: 600;
}

.suggestions__approx {
  margin: var(--pr-space-2) 0 0;
  color: var(--pr-range);
  font-size: var(--pr-text-sm);
}

.suggestions__empty {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-6) var(--pr-space-4);
  border: 1px dashed var(--pr-rule-strong);
  border-radius: var(--pr-radius);
}

.suggestions__empty-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.suggestions__empty-link {
  margin: var(--pr-space-3) 0 0;
}
</style>
