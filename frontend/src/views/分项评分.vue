<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getReview } from '../api'
import type { ArchivedReview, DimensionResult, PaperSection, ReviewReport } from '../api/types'
import DimensionCard from '../components/DimensionCard.vue'
import StageTracker from '../components/StageTracker.vue'
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
    }
    // 未确认的快照（ReviewPending）→ 保持空态
  } catch (reason) {
    loadError.value = reason instanceof Error ? reason.message : String(reason)
  } finally {
    loading.value = false
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
  <article class="scoring" data-testid="scoring-page">
    <header class="scoring__head">
      <span class="scoring__num" aria-hidden="true">02</span>
      <h1 class="scoring__title">分项评分</h1>
    </header>

    <StageTracker :phase="stagePhase" :reached-index="report ? 5 : -1" />

    <template v-if="report || archive">
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
        <p v-if="fromArchive" class="scoring__archive-note" data-testid="archive-note">
          加权与修改清单未随存档返回，下面只是存档里的维度档位；可在论文解析页重跑一次以拿全量报告。
        </p>
      </header>

      <section v-if="dimensions.length > 0" class="scoring__cards" data-testid="dimensions">
        <DimensionCard
          v-for="dimension in dimensions"
          :key="dimension.dimension_code"
          :dimension="dimension"
          :data-located="located?.dimensionCode === dimension.dimension_code ? 'true' : null"
          @locate="locateQuote"
        />
      </section>

      <section v-if="score" class="scoring__score" data-testid="score">
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
        <h2 class="scoring__subtitle">原文定位：{{ sections[located.sectionIndex]?.title }}</h2>
        <pre class="scoring__located-body">{{ sections[located.sectionIndex]?.content.slice(0, located.start) }}<mark ref="locatedEl" data-testid="located-mark">{{ located.quote }}</mark>{{ sections[located.sectionIndex]?.content.slice(located.start + located.quote.length) }}</pre>
      </section>
      <p v-if="locateError" class="scoring__locate-error" data-testid="locate-error">{{ locateError }}</p>
    </template>

    <template v-else>
      <section class="scoring__empty" data-testid="scoring-empty">
        <h2 class="scoring__empty-title">还没有分项结果</h2>
        <p class="scoring__empty-note">
          需要先在论文解析页选定赛题并确认章节树，这里才会逐维给出结果。
        </p>
        <p v-if="loading" class="scoring__loading">正在读取评审存档…</p>
        <p v-if="loadError" class="scoring__load-error" data-testid="load-error">{{ loadError }}</p>
        <p class="scoring__empty-link"><RouterLink to="/parse">去论文解析页</RouterLink></p>
      </section>
    </template>
  </article>
</template>

<style scoped>
.scoring {
  max-width: var(--pr-measure);
}

.scoring__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  margin: 0 0 var(--pr-space-2);
}

.scoring__num {
  font-family: var(--pr-font-data);
  font-size: 28px;
  line-height: 1;
  color: var(--pr-ink-faint);
}

.scoring__title {
  margin: 0;
  font-size: var(--pr-text-title);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.scoring__bar {
  margin: var(--pr-space-4) 0;
  padding: var(--pr-space-3) var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
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
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.scoring__cards {
  display: flex;
  flex-direction: column;
  gap: var(--pr-card-gap);
}

.scoring__score {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.scoring__weighted,
.scoring__noweight,
.scoring__raw {
  margin: 0 0 var(--pr-space-2);
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
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.scoring__located {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-primary-soft);
}

.scoring__located-body {
  margin: 0;
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
