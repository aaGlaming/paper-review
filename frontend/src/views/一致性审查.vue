<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import type { ChangeEvidence, ChangeListItem, PaperSection, ReviewReport } from '../api/types'
import ConflictItem from '../components/ConflictItem.vue'
import PageArt from '../components/PageArt.vue'
import artUrl from '../assets/sketch/sketch-bg-consistency.svg'
import spotUrl from '../assets/sketch/sketch-spot-consistency.svg'
import ConsistencyEmptyIllustration from '../components/illustrations/ConsistencyEmptyIllustration.vue'
import StageTracker from '../components/StageTracker.vue'
import { concatSections, locateEvidence, type EvidenceLocation } from '../composables/useOffsetLocator'
import { readReviewFlow } from '../composables/useReviewFlow'

/**
 * 一致性审查页（P8 阶段 4/6）。
 *
 * 数据唯一来源是共享状态里的 `report.change_list`，只取 section === '题目约束与数字冲突' 的条目
 * （判定依据是 finding_kind 存在，不是看 kind 的字面值）。维度类条目（证据不足 / 表述）带
 * dimension_code、证据无字符偏移，留给 v1.8.4 修改建议页，本页跳过。
 *
 * 本页只读共享状态：没有 report 就显示空态（文案不含任何审查字样），不兜底调 getReview、
 * 不在前端重跑一致性检查。定位走 useOffsetLocator：先拼接正文再 indexOf 校准，禁 v-html。
 */
const CONSISTENCY_SECTION = '题目约束与数字冲突'

const report = ref<ReviewReport | null>(null)
const sections = ref<PaperSection[]>([])

const body = computed(() => concatSections(sections.value))

const conflicts = computed<ChangeListItem[]>(() =>
  report.value ? report.value.change_list.filter((item) => item.section === CONSISTENCY_SECTION) : [],
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
  <article class="consistency" data-testid="consistency-page">
    <PageArt :art="artUrl" :spot="spotUrl" layout="right" />
    <header class="ed-head">
      <span class="ed-head__num" aria-hidden="true">03</span>
      <p class="ed-head__kicker">硬伤核对 · 逐条定位</p>
      <h1 class="ed-head__title">一致性审查</h1>
    </header>
    <p v-if="report" class="ed-lede">只看硬伤：数字打架、引用失联、数值越界，一条一条点定位核对。</p>

    <StageTracker :phase="stagePhase" :reached-index="report ? 5 : -1" />

    <template v-if="report">
      <p class="ed-kicker">审查单 · {{ conflicts.length > 0 ? `硬伤 ${conflicts.length} 条` : '无冲突' }}</p>
      <header class="consistency__bar" data-testid="consistency-bar">
        <dl class="consistency__meta">
          <div class="consistency__meta-item">
            <dt>赛题</dt>
            <dd>{{ contestId || '—' }}</dd>
          </div>
          <div class="consistency__meta-item">
            <dt>量规版本</dt>
            <dd>{{ rubricVersion ?? '未绑定量规' }}</dd>
          </div>
          <div class="consistency__meta-item">
            <dt>状态</dt>
            <dd>{{ status }}</dd>
          </div>
          <div class="consistency__meta-item">
            <dt>来源</dt>
            <dd>{{ source }}</dd>
          </div>
        </dl>
      </header>

      <section v-if="conflicts.length > 0" class="consistency__list" data-testid="conflict-list">
        <ConflictItem
          v-for="(item, index) in conflicts"
          :key="item.upstream_id || index"
          :item="item"
          :located-key="located?.key ?? null"
          :class="index % 2 === 1 ? 'consistency__item--shift' : null"
          @locate="handleLocate"
        />
      </section>
      <p v-else class="consistency__none">本次审查没有冲突条目。</p>

      <hr v-if="located" class="ed-rule" />
      <section v-if="located" class="consistency__located" data-testid="located-content">
        <p class="ed-kicker">原文定位 · 三段对照</p>
        <h2 class="consistency__subtitle">命中处前后文</h2>
        <!-- 文本节点三段拼接（前段 / mark 命中段 / 后段），禁 v-html：正文是用户可控输入。 -->
        <pre class="consistency__located-body">{{ body.slice(0, located.start) }}<mark ref="locatedEl" data-testid="located-mark">{{ located.text }}</mark>{{ body.slice(located.start + located.text.length) }}</pre>
        <p v-if="!located.exact" class="consistency__approx" data-testid="approximate-note">
          {{ located.approximateNote }}
        </p>
      </section>
    </template>

    <template v-else>
      <section class="consistency__empty" data-testid="consistency-empty">
        <ConsistencyEmptyIllustration class="consistency__empty-illo" />
        <h2 class="consistency__empty-title">还没有审查结果</h2>
        <p class="consistency__empty-link"><RouterLink class="ed-action-link" to="/parse">去论文解析页</RouterLink></p>
      </section>
    </template>
  </article>
</template>

<style scoped>
.consistency {
  max-width: var(--pr-measure);
}

.consistency__bar {
  margin: var(--pr-space-3) 0 var(--pr-space-6);
  padding: 0 0 var(--pr-space-3);
  border-bottom: 1px solid var(--pr-rule);
}

.consistency__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-6);
  margin: 0;
}

.consistency__meta-item {
  display: flex;
  gap: var(--pr-space-2);
}

.consistency__meta-item dt {
  color: var(--pr-ink-muted);
}

.consistency__meta-item dd {
  margin: 0;
}

.consistency__list {
  display: flex;
  flex-direction: column;
  gap: var(--pr-card-gap);
  max-width: 880px;
}

/* 偶数条轻微右错：长串冲突条的阅读节奏不断，又不破坏对齐。 */
.consistency__item--shift {
  margin-left: var(--pr-space-6);
}

@media (max-width: 900px) {
  .consistency__item--shift {
    margin-left: 0;
  }
}

.consistency__none {
  margin: 0;
  color: var(--pr-ink-muted);
}

.consistency__located {
  padding: var(--pr-space-4) 0 0;
  border-top: 2px solid var(--pr-primary);
}

.consistency__subtitle {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.consistency__located-body {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  padding-left: var(--pr-space-3);
  border-left: 2px solid var(--pr-rule-strong);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--pr-font-quote);
  line-height: var(--pr-leading-quote);
}

.consistency__located-body mark {
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
  font-weight: 600;
}

.consistency__approx {
  margin: var(--pr-space-2) 0 0;
  color: var(--pr-range);
  font-size: var(--pr-text-sm);
}

.consistency__empty {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-6) var(--pr-space-4);
  border: 1px dashed var(--pr-rule-strong);
  border-radius: var(--pr-radius);
}

.consistency__empty-illo {
  margin-bottom: var(--pr-space-4);
}

.consistency__empty-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.consistency__empty-link {
  margin: var(--pr-space-3) 0 0;
}
</style>
