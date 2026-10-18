<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { getEvalPaper, getEvalSummary, listSamples } from '../api'
import type { EvalPaperResult, EvalSummary, SampleItem } from '../api/types'
import MetricCard from '../components/MetricCard.vue'
import PageArt from '../components/PageArt.vue'
import artUrl from '../assets/sketch/sketch-bg-eval.svg'
import spotUrl from '../assets/sketch/sketch-spot-eval.svg'
import EvalSingleIllustration from '../components/illustrations/EvalSingleIllustration.vue'

/**
 * 评测对照页（P8 阶段 6/6，最后一页）。
 *
 * 数据唯一来源是 getEvalSummary()：三项指标、口径（caliber）、来源（source）、note 全部来自它，
 * 页面不自己算任何百分比、不自己凑分母。可选地列 listSamples() 的 15 篇。
 *
 * - `rate` 为 null 时显示「—（无样本）」；`no_samples` 为 true 时整页给说明；
 * - `source='deterministic'` 时额外标注「非模型评测结果」，不把百分比当成果放大；
 * - `/eval/:paperId` 从后端读取单篇 gold 与系统结果；
 * - 取数失败捕获降级，h1 无条件渲染。本页不参与单次评审流程，不放 StageTracker。
 */

const route = useRoute()

const summary = ref<EvalSummary | null>(null)
const samples = ref<SampleItem[]>([])
const loadError = ref('')
const loading = ref(false)
const singlePaper = ref<EvalPaperResult | null>(null)
const singleError = ref('')
const singleLoading = ref(false)

const isSinglePaper = computed(
  () => typeof route.params.paperId === 'string' && route.params.paperId !== '',
)

const metricCards = computed(() => {
  if (!summary.value) {
    return []
  }
  const s = summary.value
  return [
    { code: 'band_agreement', name: '档位一致率', metric: s.band_agreement },
    { code: 'quote_exact_match', name: '引用精确匹配率', metric: s.quote_exact_match },
    { code: 'insufficient_evidence_hit', name: '证据不足命中情况', metric: s.insufficient_evidence_hit },
  ]
})

watch(() => route.params.paperId, (paperId) => {
  if (typeof paperId === 'string' && paperId) {
    void loadPaper(paperId)
  } else {
    singlePaper.value = null
    void load()
  }
}, { immediate: true })

async function loadPaper(paperId: string): Promise<void> {
  singleLoading.value = true
  singleError.value = ''
  singlePaper.value = null
  try {
    singlePaper.value = await getEvalPaper(paperId)
  } catch (reason) {
    singleError.value = reason instanceof Error ? reason.message : String(reason)
  } finally {
    singleLoading.value = false
  }
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    summary.value = await getEvalSummary()
  } catch (reason) {
    loadError.value = reason instanceof Error ? reason.message : String(reason)
    loading.value = false
    return
  }
  try {
    const resp = await listSamples()
    samples.value = resp.samples
  } catch {
    samples.value = [] // 样例列表是可选的，失败不影响三项指标
  }
  loading.value = false
}
</script>

<template>
  <article class="eval" data-testid="eval-page">
    <PageArt :art="artUrl" :spot="spotUrl" layout="right" />
    <header class="ed-head">
      <span class="ed-head__num" aria-hidden="true">05</span>
      <p class="ed-head__kicker">三项指标 · 口径与来源</p>
      <h1 class="ed-head__title">评测对照</h1>
    </header>
    <p class="ed-lede">三项指标各自独立成卡：先看走势，再读口径；数字是脚本自检，不是成果。</p>

    <template v-if="isSinglePaper">
      <section class="eval__single" data-testid="single-paper-placeholder">
        <EvalSingleIllustration class="eval__single-illo" />
        <h2 class="eval__single-title">单篇评测</h2>
        <p v-if="singleLoading" class="eval__single-note">正在读取单篇评测…</p>
        <p v-else-if="singleError" class="eval__single-note">{{ singleError }}</p>
        <template v-else-if="singlePaper">
          <p class="eval__single-note">{{ singlePaper.title }} · 系统来源：{{ singlePaper.source }}</p>
          <p v-if="!singlePaper.gold_available" class="eval__single-note">{{ singlePaper.explanation }}</p>
          <table v-else class="eval__difference">
            <thead><tr><th>维度</th><th>gold</th><th>系统</th><th>对照</th></tr></thead>
            <tbody>
              <tr v-for="row in singlePaper.differences" :key="row.dimension_code">
                <th scope="row">{{ row.dimension_code }}</th>
                <td>gold：{{ row.gold_band ?? '未提供' }}</td>
                <td>系统：{{ row.system_band ?? '未出档' }}</td>
                <td>{{ row.matches ? '一致' : '不一致' }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <p class="eval__single-link"><RouterLink class="ed-action-link" to="/eval">回汇总页</RouterLink></p>
      </section>
    </template>

    <template v-else-if="loadError">
      <section class="eval__error" data-testid="eval-error">
        <h2 class="eval__error-title">评测汇总暂时不可用</h2>
        <p class="eval__error-note">{{ loadError }}</p>
      </section>
    </template>

    <template v-else-if="summary">
      <p class="ed-kicker">语料 · {{ summary.corpus_papers }} 篇 / 可算 {{ summary.gradable_papers }} 篇</p>
      <header class="eval__bar" data-testid="eval-bar">
        <dl class="eval__meta">
          <div class="eval__meta-item">
            <dt>语料片数</dt>
            <dd>{{ summary.corpus_papers }}</dd>
          </div>
          <div class="eval__meta-item">
            <dt>可算样本</dt>
            <dd>{{ summary.gradable_papers }}</dd>
          </div>
          <div class="eval__meta-item">
            <dt>可算维度</dt>
            <dd>{{ summary.gradable_dimensions }}</dd>
          </div>
          <div class="eval__meta-item">
            <dt>来源</dt>
            <dd>{{ summary.source }}</dd>
          </div>
          <div class="eval__meta-item">
            <dt>无样本</dt>
            <dd>{{ summary.no_samples ? '是' : '否' }}</dd>
          </div>
        </dl>
      </header>

      <p v-if="summary.no_samples" class="eval__nosamples" data-testid="no-samples">
        当前没有可评测的样本，三项指标无数据。
      </p>

      <section class="eval__metrics" data-testid="metrics">
        <p class="ed-kicker eval__metrics-kicker">三项指标 · 走势由本卡数据实时生成</p>
        <MetricCard
          v-for="(card, index) in metricCards"
          :key="card.code"
          :code="card.code"
          :name="card.name"
          :metric="card.metric"
          :class="index === 1 ? 'eval__metric--shift' : null"
        />
      </section>

      <hr class="ed-rule" />
      <section class="eval__source" data-testid="source-note">
        <p class="ed-kicker">口径 · 非模型评测结果时明确标注</p>
        <h2 class="eval__subtitle">指标口径与来源</h2>
        <p class="eval__note" data-testid="eval-note">{{ summary.note }}</p>
        <p v-if="summary.source === 'deterministic'" class="eval__deterministic" data-testid="deterministic-note">
          本次为确定性结构回退，非模型评测结果。
        </p>
      </section>

      <section v-if="samples.length > 0" class="eval__samples">
        <h2 class="eval__subtitle">样例列表</h2>
        <p class="eval__samples-note">点一篇查看 gold 与系统档位的逐维对照。</p>
        <ul class="eval__sample-list">
          <li v-for="sample in samples" :key="sample.sample_id" class="eval__sample-row" data-testid="sample-row">
            <RouterLink :to="`/eval/${sample.sample_id}`" class="eval__sample-link">
              <span class="eval__sample-title">{{ sample.title }}</span>
              <span v-if="sample.is_demo" class="eval__sample-tag">演示稿</span>
              <span v-if="sample.has_gold" class="eval__sample-tag">有 gold</span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </template>

    <template v-else>
      <p v-if="loading" class="eval__loading">正在读取评测汇总…</p>
    </template>
  </article>
</template>

<style scoped>
.eval {
  max-width: var(--pr-measure);
}

.eval__bar {
  margin: var(--pr-space-3) 0 var(--pr-space-4);
  padding: 0 0 var(--pr-space-3);
  border-bottom: 1px solid var(--pr-rule);
}

.eval__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2) var(--pr-space-6);
  margin: 0;
}

.eval__meta-item {
  display: flex;
  gap: var(--pr-space-2);
}

.eval__meta-item dt {
  color: var(--pr-ink-muted);
}

.eval__meta-item dd {
  margin: 0;
}

.eval__nosamples {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-range);
  font-size: var(--pr-text-sm);
}

.eval__metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--pr-card-gap);
  align-items: start;
  margin-top: var(--pr-space-6);
}

.eval__metrics-kicker {
  grid-column: 1 / -1;
}

/* 中间卡下沉半格：三卡不再是机械三等分，走势各自独立可读。 */
.eval__metric--shift {
  margin-top: var(--pr-space-6);
}

.eval__source {
  max-width: 720px;
  padding: var(--pr-space-4) 0 0;
}

.eval__single-illo {
  margin-bottom: var(--pr-space-4);
}

.eval__difference {
  width: 100%;
  margin-top: var(--pr-space-4);
  border-collapse: collapse;
  text-align: left;
}

.eval__difference th,
.eval__difference td {
  padding: var(--pr-space-2);
  border-bottom: 1px solid var(--pr-rule);
}

.eval__samples-note {
  margin: 0 0 var(--pr-space-3);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-sm);
}

@media (max-width: 900px) {
  .eval__metrics {
    grid-template-columns: 1fr;
  }

  .eval__metric--shift {
    margin-top: 0;
  }
}

.eval__subtitle {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-base);
  font-weight: 600;
}

.eval__note {
  margin: 0 0 var(--pr-space-2);
  color: var(--pr-ink-muted);
  line-height: var(--pr-leading-base);
}

.eval__deterministic {
  margin: 0;
  color: var(--pr-range);
  font-size: var(--pr-text-sm);
}

.eval__samples {
  margin-top: var(--pr-space-6);
}

.eval__sample-list {
  display: flex;
  flex-direction: column;
  gap: var(--pr-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.eval__sample-row {
  border-bottom: 1px solid var(--pr-rule);
}

.eval__sample-link {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  padding: var(--pr-space-2) var(--pr-space-1);
  color: var(--pr-ink);
  text-decoration: none;
}

.eval__sample-link:hover {
  background: var(--pr-row-hover);
}

.eval__sample-title {
  font-size: var(--pr-text-base);
}

.eval__sample-tag {
  padding: 0 var(--pr-space-2);
  border: 1px solid var(--pr-rule-strong);
  border-radius: var(--pr-radius);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-xs);
}

.eval__error,
.eval__single {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-6) var(--pr-space-4);
  border: 1px dashed var(--pr-rule-strong);
  border-radius: var(--pr-radius);
}

.eval__error-title,
.eval__single-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-lg);
  font-weight: 600;
}

.eval__error-note,
.eval__single-note {
  margin: 0;
  color: var(--pr-ink-muted);
}

.eval__single-link {
  margin: var(--pr-space-3) 0 0;
}

.eval__loading {
  margin-top: var(--pr-space-6);
  color: var(--pr-ink-muted);
}
</style>
