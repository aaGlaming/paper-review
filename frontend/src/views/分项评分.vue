<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getContestRubric, getReview } from '../api'
import type { ArchivedReview, DimensionResult, PaperSection, PublishedRubricText, ReviewReport } from '../api/types'
import DimensionCard from '../components/DimensionCard.vue'
import PageArt from '../components/PageArt.vue'
import artUrl from '../../../docs/design/sketch-svg/sketch-bg-scoring.svg'
import spotUrl from '../../../docs/design/sketch-svg/sketch-spot-scoring.svg'
import ScoringEmptyIllustration from '../components/illustrations/ScoringEmptyIllustration.vue'
import StageTracker from '../components/StageTracker.vue'
import RequestActivity from '../components/RequestActivity.vue'
import AgentTracePanel from '../components/AgentTracePanel.vue'
import { isArchivedReview } from '../composables/reviewShape'
import { readReviewFlow } from '../composables/useReviewFlow'

/**
 * 分项评分页（P8 阶段 3/6）。
 *
 * 数据的唯一来源是共享状态里的 `report`（resume 的响应）。`report` 为 null 时，若 `reviewId` 非空，
 * 兜底调一次 `getReview` 拿存档（只有 dimensions），但**明确标注「加权与修改清单未随存档返回」**，
 * 不自算加权、不凭 dimensions 造总分（任务文档 §14 明令禁止）。
 */

const report = ref<ReviewReport | null>(null)
const archive = ref<ArchivedReview | null>(null)
const sections = ref<PaperSection[]>([])
const loading = ref(false)
const loadError = ref('')
const rubric = ref<PublishedRubricText | null>(null)

const located = ref<{ sectionIndex: number; dimensionCode: string; start: number; quote: string } | null>(null)
const locateError = ref('')
const locatedEl = ref<HTMLElement | null>(null)

const dimensions = computed<DimensionResult[]>(() => {
  if (report.value) {
    return report.value.dimensions
  }
  if (archive.value) {
    return archive.value.dimensions
  }
  return []
})

const fromArchive = computed(() => report.value === null && archive.value !== null)
const contestId = computed(() => report.value?.contest_id ?? archive.value?.contest_id ?? '')
const rubricVersion = computed(() => report.value?.rubric_version ?? archive.value?.rubric_version ?? null)
const status = computed(() => report.value?.status ?? '')
const source = computed(() => report.value?.source ?? '')
const modelName = computed(() => report.value?.model_name ?? archive.value?.model_name ?? '')
const score = computed(() => report.value?.score ?? null)
const reviewId = computed(() => readReviewFlow().reviewId || report.value?.review_id || '')
const terminatedBy = computed(() => report.value?.agent_terminated_by ?? null)

// 加权是否真的产生过：只有非确定性回退、且 weight_sum 非 0 才算。页面不自算。
const weightProduced = computed(
  () => report.value !== null && report.value.source !== 'deterministic' && report.value.score.weight_sum > 0,
)

// report 在手 ⇒ 六步确实跑完了（否则不会有报告）；无 report 时 idle，不伪造进度。
const stagePhase = computed(() => (report.value ? ('done' as const) : ('idle' as const)))

onMounted(() => {
  void load()
})

async function load(): Promise<void> {
  const flow = readReviewFlow()
  sections.value = flow.sections.map((section) => ({ ...section }))
  if (flow.report) {
    report.value = flow.report
    await loadRubric(flow.report.contest_id)
    return
  }
  if (!flow.reviewId) {
    return
  }
  loading.value = true
  try {
    const fetched = await getReview(flow.reviewId)
    if (isArchivedReview(fetched)) {
      archive.value = fetched
      await loadRubric(fetched.contest_id)
    }
    // 未确认的快照（ReviewPending）→ 保持空态
  } catch (reason) {
    loadError.value = reason instanceof Error ? reason.message : String(reason)
  } finally {
    loading.value = false
  }
}

async function loadRubric(contest: string): Promise<void> {
  rubric.value = null
  if (!contest) return
  try {
    rubric.value = await getContestRubric(contest)
  } catch {
    rubric.value = null
  }
}

async function locateQuote(dimension: DimensionResult): Promise<void> {
  locateError.value = ''
  const quote = dimension.quote
  if (!quote) {
    locateError.value = '未给原句：证据不足不产生引用，无法定位'
    return
  }
  for (let index = 0; index < sections.value.length; index++) {
    const content = sections.value[index]?.content ?? ''
    const start = content.indexOf(quote)
    if (start !== -1) {
      located.value = { sectionIndex: index, dimensionCode: dimension.dimension_code, start, quote }
      await nextTick()
      locatedEl.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
      return
    }
  }
  located.value = null
  locateError.value = '原句不在当前章节正文里，无法定位'
}
</script>

<template>
  <article class="scoring" :class="{ 'scoring--has-rubric': rubric !== null }" data-testid="scoring-page">
    <PageArt :art="artUrl" :spot="spotUrl" layout="left" />
    <header class="ed-head">
      <span class="ed-head__num" aria-hidden="true">02</span>
      <p class="ed-head__kicker">逐维取证 · 原句定位</p>
      <h1 class="ed-head__title">分项评分</h1>
    </header>
    <p class="ed-lede">五个维度各自取证、各自选档；原句点一下就能回到论文里核对。</p>

    <StageTracker :phase="stagePhase" :reached-index="report ? 5 : -1" />

    <template v-if="report || archive">
      <p class="ed-kicker">评审单 · {{ contestId || '未绑定赛题' }}</p>
      <header class="scoring__bar" data-testid="scoring-bar">
        <dl class="scoring__meta">
          <div class="scoring__meta-item">
            <dt>赛题</dt>
            <dd>{{ contestId || '—' }}</dd>
          </div>
          <div class="scoring__meta-item">
            <dt>量规版本</dt>
            <dd>{{ rubricVersion ?? '未绑定量规' }}</dd>
          </div>
          <template v-if="report">
            <div class="scoring__meta-item">
              <dt>状态</dt>
              <dd>{{ status }}</dd>
            </div>
            <div class="scoring__meta-item">
              <dt>来源</dt>
              <dd>{{ source }}</dd>
            </div>
          </template>
          <div class="scoring__meta-item">
            <dt>模型</dt>
            <dd>{{ modelName || '—' }}</dd>
          </div>
        </dl>
        <p v-if="fromArchive && archive?.change_list_note" class="scoring__archive-note" data-testid="archive-note">
          {{ archive.change_list_note }}；加权未随存档保存。
        </p>
      </header>

      <section v-if="dimensions.length > 0" class="scoring__cards" data-testid="dimensions">
        <p class="ed-kicker scoring__cards-kicker">五维结果 · 按后端顺序</p>
        <TransitionGroup name="proof-list" tag="div" class="scoring__card-list">
          <DimensionCard
            v-for="(dimension, index) in dimensions"
            :key="dimension.dimension_code"
            :dimension="dimension"
            :data-located="located?.dimensionCode === dimension.dimension_code ? 'true' : null"
            :class="index === 0 ? 'scoring__card--lead' : null"
            @locate="locateQuote"
          />
        </TransitionGroup>
      </section>
      <RequestActivity v-else :active="loading" label="正在读取评审存档" />

      <section v-if="rubric" class="scoring__rubric-details">
        <h2 class="scoring__subtitle">量规条文 · {{ rubric.rubric_id }} v{{ rubric.version }}</h2>
        <article v-for="item in rubric.dimensions" :key="item.dimension_code" class="scoring__rubric-item">
          <h3>{{ item.name }}（{{ item.dimension_code }}）· 权重 {{ item.weight }}</h3>
          <ul>
            <li v-for="band in item.bands" :key="band.band">
              {{ band.band }}<template v-if="band.score !== null"> · {{ band.score }}</template> · {{ band.description }}
            </li>
          </ul>
        </article>
      </section>

      <section v-if="fromArchive && archive?.change_list?.length" class="scoring__archive-changes">
        <h2 class="scoring__subtitle">历史审查清单</h2>
        <ol>
          <li v-for="item in archive.change_list" :key="item.upstream_id">
            <strong>{{ item.section }} · {{ item.kind }}</strong>
            <p>{{ item.action }}</p>
            <small>上游编号：{{ item.upstream_id }}</small>
          </li>
        </ol>
      </section>

      <hr class="ed-rule" />
      <section v-if="score" class="scoring__score" data-testid="score">
        <p class="ed-kicker">加权收尾 · 只转写后端原始值</p>
        <p v-if="weightProduced" class="scoring__weighted">
          加权 <strong data-testid="weighted">{{ score.weighted }}</strong>
        </p>
        <p v-else class="scoring__noweight" data-testid="no-weight">
          加权未产生（本次来源 deterministic，未接模型）
        </p>
        <p class="scoring__raw" data-testid="raw-score">
          后端原始值：total {{ score.total }} · weighted {{ score.weighted }} · weight_sum
          {{ score.weight_sum }}
        </p>

        <template v-if="score.excluded.length > 0">
          <h2 class="scoring__subtitle">未进入加权的维度</h2>
          <table class="scoring__excluded" data-testid="excluded-table">
            <thead>
              <tr>
                <th>维度</th>
                <th>档位</th>
                <th>权重</th>
                <th>计入</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in score.excluded" :key="row.dimension_code" data-testid="excluded-row">
                <td>{{ row.dimension_code }}</td>
                <td>{{ row.band ?? '未选档' }}</td>
                <td>{{ row.weight }}</td>
                <td>{{ row.contribution }}</td>
                <td>{{ row.reason }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <p v-else class="scoring__noexcluded">本次没有被排除在加权之外的维度</p>
      </section>

      <section v-if="located" class="scoring__located" data-testid="located-content">
        <p class="ed-kicker">原文定位 · 三段对照</p>
        <h2 class="scoring__subtitle">命中处前后文</h2>
        <pre class="scoring__located-body">{{ sections[located.sectionIndex]?.content.slice(0, located.start) }}<mark ref="locatedEl" data-testid="located-mark">{{ located.quote }}</mark>{{ sections[located.sectionIndex]?.content.slice(located.start + located.quote.length) }}</pre>
      </section>
      <AgentTracePanel v-if="reviewId" :review-id="reviewId" :terminated-by="terminatedBy" />
      <p v-if="locateError" class="scoring__locate-error" data-testid="locate-error">{{ locateError }}</p>
    </template>

    <template v-else>
      <section class="scoring__empty" data-testid="scoring-empty">
        <ScoringEmptyIllustration class="scoring__empty-illo" />
        <h2 class="scoring__empty-title">还没有分项结果</h2>
        <p class="scoring__empty-note">
          需要先在论文解析页选定赛题并确认章节树，这里才会逐维给出结果。
        </p>
        <RequestActivity :active="loading" label="正在读取评审存档" />
        <p v-if="loadError" class="scoring__load-error" data-testid="load-error">{{ loadError }}</p>
        <p class="scoring__empty-link"><RouterLink class="ed-action-link" to="/parse">去论文解析页</RouterLink></p>
      </section>
    </template>
  </article>
</template>

<style scoped>
.scoring {
  max-width: var(--pr-measure);
}

.scoring__bar {
  margin: var(--pr-space-3) 0 var(--pr-space-6);
  padding: 0 0 var(--pr-space-3);
  border-bottom: 1px solid var(--pr-rule);
}

.scoring__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-6);
  margin: 0;
}

.scoring__meta-item {
  display: flex;
  gap: var(--pr-space-2);
}

.scoring__meta-item dt {
  color: var(--pr-ink-muted);
}

.scoring__meta-item dd {
  margin: 0;
}

.scoring__archive-note {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.scoring__cards {
  display: block;
}

.scoring__card-list { display:grid; grid-template-columns:7fr 5fr; gap:var(--pr-card-gap); align-items:start; }
.proof-list-enter-active,.proof-list-leave-active { transition:opacity var(--pr-motion-list) var(--pr-motion-ease), transform var(--pr-motion-list) var(--pr-motion-ease); }
.proof-list-enter-from,.proof-list-leave-to { opacity:0; transform:translateY(5px); }
.proof-list-move { transition:transform var(--pr-motion-list) var(--pr-motion-ease); }

/* 首张维度卡跨整行做视觉焦点：它是读者进入五维的第一眼。 */
.scoring__cards-kicker,
.scoring__card--lead {
  grid-column: 1 / -1;
}

.scoring__score {
  padding: var(--pr-space-4) 0 0;
}

@media (max-width: 900px) {
  .scoring__cards {
    grid-template-columns: 1fr;
  }
  .scoring__card-list { grid-template-columns:1fr; }
}

@media (prefers-reduced-motion: reduce) { .proof-list-enter-active,.proof-list-leave-active,.proof-list-move { transition:none; } }

.scoring__weighted,
.scoring__noweight,
.scoring__raw {
  margin: 0 0 var(--pr-space-2);
}

.scoring__archive-changes li {
  margin-top: var(--pr-space-3);
}

.scoring__archive-changes li p {
  margin: var(--pr-space-1) 0;
}

.scoring__rubric-item {
  margin-top: var(--pr-space-3);
}

.scoring__rubric-item h3 {
  margin: 0 0 var(--pr-space-1);
  font-size: var(--pr-text-sm);
}

.scoring__rubric-item ul {
  display: grid;
  gap: var(--pr-space-1);
  margin: 0;
  padding-left: var(--pr-space-4);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.scoring--has-rubric :deep([data-testid='rubric-reserved']) {
  display: none;
}

.scoring__subtitle {
  margin: var(--pr-space-4) 0 var(--pr-space-2);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.scoring__excluded {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--pr-text-sm);
}

.scoring__excluded th,
.scoring__excluded td {
  padding: var(--pr-space-1) var(--pr-space-2);
  border-bottom: 1px solid var(--pr-rule);
  text-align: left;
}

.scoring__excluded th {
  color: var(--pr-ink-muted);
  font-weight: 600;
}

.scoring__noexcluded {
  margin: 0;
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

.scoring__located {
  padding: var(--pr-space-4) 0 0;
  border-top: 2px solid var(--pr-primary);
}

.scoring__located-body {
  margin: 0;
  padding-left: var(--pr-space-3);
  border-left: 2px solid var(--pr-rule-strong);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--pr-font-quote);
  line-height: var(--pr-leading-quote);
}

.scoring__located-body mark {
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
  font-weight: 600;
}

.scoring__locate-error {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-conflict);
  font-size: var(--pr-text-sm);
}

.scoring__empty {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-6) var(--pr-space-4);
  border: 1px dashed var(--pr-rule-strong);
  border-radius: var(--pr-radius);
}

.scoring__empty-illo {
  margin-bottom: var(--pr-space-4);
}

.scoring__empty-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.scoring__empty-note,
.scoring__loading,
.scoring__load-error {
  margin: 0 0 var(--pr-space-2);
  color: var(--pr-ink-muted);
}

.scoring__load-error {
  color: var(--pr-conflict);
}

.scoring__empty-link {
  margin: var(--pr-space-3) 0 0;
}
</style>
