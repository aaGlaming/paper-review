<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError, createReview, listContests, listSamples, resumeReview } from '../api'
import type { ContestSummary, PaperSection, ReviewReport, SampleItem } from '../api/types'
import SectionReader from '../components/SectionReader.vue'
import SectionTree from '../components/SectionTree.vue'
import StageTracker from '../components/StageTracker.vue'
import { REVIEW_STAGES, type StagePhase } from '../composables/reviewVocabulary'
import { readReviewFlow, setConfirmedReport, setReviewCreated } from '../composables/useReviewFlow'

/**
 * 论文解析页（P8 阶段 2/6）。
 *
 * 三条纪律：
 * 1. **只渲染接口真给的东西**。创建评审的响应里只有章节树与正文，没有档位、分数、加权，
 *    也没有主张 / 表格 / 引用——所以这一页一个档位都不显示，也不在前端重解析论文。
 * 2. **不自己拼 URL**：所有请求都走 `src/api`，这里只调函数。
 * 3. **不假装进度**：步骤指示器只按真实观测到的时点点亮（见 StageTracker）。
 */

const contests = ref<ContestSummary[]>([])
const samples = ref<SampleItem[]>([])
const loading = ref(true)

const contestId = ref('')
const selectedSampleId = ref('')
const paperText = ref('')

const reviewId = ref('')
const sections = ref<PaperSection[]>([])
const selectedIndex = ref(0)
const report = ref<ReviewReport | null>(null)

const phase = ref<StagePhase>('idle')
const reachedIndex = ref(-1)
const busy = ref(false)
const error = ref('')

const hasContest = computed(() => contestId.value !== '')
const hasSample = computed(() => selectedSampleId.value !== '')
const hasText = computed(() => paperText.value.trim().length > 0)

// paper_text 与 sample_id 互斥：两条路都填时先让用户清掉一个，而不是悄悄丢掉一份输入
const conflict = computed(() => hasSample.value && hasText.value)

const submitHint = computed(() => {
  if (!hasContest.value) {
    return '先选赛题：没有绑定赛题就没有量规，确认之后也拿不到任何维度。'
  }
  if (conflict.value) {
    return '演示样例与粘贴正文只能选一条：请清空其中一个再提交。'
  }
  if (!hasSample.value && !hasText.value) {
    return '先选一篇演示样例，或在下面粘贴正文。'
  }
  if (busy.value) {
    return '处理中，请稍候。'
  }
  return ''
})

const canSubmitSample = computed(
  () => hasContest.value && hasSample.value && !conflict.value && !busy.value,
)
const canSubmitText = computed(
  () => hasContest.value && hasText.value && !conflict.value && !busy.value,
)

const selectedSection = computed(() => sections.value[selectedIndex.value] ?? null)
const contestSummary = computed(() =>
  loading.value ? '正在读取赛题…' : `共 ${contests.value.length} 道可预审赛题`,
)

function describeError(reason: unknown): string {
  if (reason instanceof ApiError) {
    const parts = [reason.message]
    if (reason.filename) {
      parts.push(`文件：${reason.filename}`)
    }
    if (reason.field) {
      parts.push(`字段：${reason.field}`)
    }
    return parts.join('；')
  }
  return reason instanceof Error ? reason.message : String(reason)
}

function hydrateFromFlow(): void {
  const flow = readReviewFlow()
  contestId.value = flow.contestId
  reviewId.value = flow.reviewId
  sections.value = flow.sections.map((section) => ({ ...section }))
  report.value = flow.report
  if (flow.report) {
    phase.value = 'done'
    reachedIndex.value = REVIEW_STAGES.length - 1
  } else if (flow.reviewId && flow.sections.length > 0) {
    phase.value = 'parsed'
    reachedIndex.value = 0
  }
}

async function loadInputs(): Promise<void> {
  loading.value = true
  try {
    const [contestList, sampleList] = await Promise.all([listContests(), listSamples(true)])
    contests.value = contestList.contests
    samples.value = sampleList.samples
  } catch (reason) {
    // 取不到赛题与样例也要把页面渲染出来：标题与说明照常，只是暂时没得选
    error.value = describeError(reason)
  } finally {
    loading.value = false
  }
}

function pickSample(sampleId: string): void {
  selectedSampleId.value = sampleId
}

function selectSection(index: number): void {
  selectedIndex.value = index
}

function changeSectionType(index: number, value: string): void {
  const target = sections.value[index]
  if (!target) {
    return
  }
  sections.value[index] = { ...target, section_type: value }
  selectedIndex.value = index
}

async function createFromInputs(source: 'sample' | 'text'): Promise<void> {
  if (busy.value) {
    return
  }
  if (source === 'sample' && !canSubmitSample.value) {
    return
  }
  if (source === 'text' && !canSubmitText.value) {
    return
  }

  busy.value = true
  error.value = ''
  phase.value = 'running'
  try {
    const created = await createReview(
      source === 'sample'
        ? { sample_id: selectedSampleId.value, contest_id: contestId.value }
        : { paper_text: paperText.value, contest_id: contestId.value },
    )
    reviewId.value = created.review_id
    sections.value = created.sections.map((section) => ({ ...section }))
    selectedIndex.value = 0
    report.value = null
    // 真正观测到的只有这一个时点：创建成功、章节树已产出
    reachedIndex.value = 0
    phase.value = 'parsed'
    setReviewCreated(created.review_id, contestId.value, sections.value)
  } catch (reason) {
    // 创建失败：没有有效评审单，不留下任何章节树
    reviewId.value = ''
    sections.value = []
    selectedIndex.value = 0
    reachedIndex.value = -1
    error.value = describeError(reason)
    phase.value = 'failed'
  } finally {
    busy.value = false
  }
}

async function confirmSections(): Promise<void> {
  if (busy.value || !reviewId.value || sections.value.length === 0) {
    return
  }
  busy.value = true
  error.value = ''
  phase.value = 'running'
  try {
    const confirmed = await resumeReview(
      reviewId.value,
      sections.value.map((section) => ({ ...section })),
    )
    report.value = confirmed
    // 报告到手，六步链路才算跑完；此前不点亮任何中间步
    reachedIndex.value = REVIEW_STAGES.length - 1
    phase.value = 'done'
    setConfirmedReport(confirmed, sections.value)
  } catch (reason) {
    // 确认失败：保留已提交的章节树（用户改过的类型不能丢），只报错
    error.value = describeError(reason)
    phase.value = 'failed'
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  hydrateFromFlow()
  void loadInputs()
})
</script>

<template>
  <article class="parse" data-testid="parse-page">
    <header class="parse__head">
      <span class="parse__num" aria-hidden="true">01</span>
      <h1 class="parse__title">论文解析</h1>
    </header>
    <p class="parse__lead">
      选一道已发布赛题，再填一篇稿子：解析出章节树，确认之后才进入分项评分。
    </p>

    <section class="inputs" data-testid="inputs">
      <div class="inputs__row">
        <label class="inputs__label" for="parse-contest">赛题</label>
        <select
          id="parse-contest"
          v-model="contestId"
          class="inputs__select"
          data-testid="contest-select"
        >
          <option value="">未选择</option>
          <option v-for="contest in contests" :key="contest.contest_id" :value="contest.contest_id">
            {{ contest.title }}
          </option>
        </select>
        <span class="inputs__meta" data-testid="contest-count">{{ contestSummary }}</span>
      </div>

      <div class="inputs__pair">
        <div class="inputs__block" data-testid="sample-block">
          <h2 class="inputs__block-title">用演示样例</h2>
          <div class="inputs__demos">
            <button
              v-for="sample in samples"
              :key="sample.sample_id"
              type="button"
              class="inputs__demo"
              data-testid="demo-item"
              :data-selected="selectedSampleId === sample.sample_id ? 'true' : 'false'"
              @click="pickSample(sample.sample_id)"
            >
              {{ sample.title }}
            </button>
          </div>
          <button
            type="button"
            class="inputs__submit"
            data-testid="submit-sample"
            :disabled="!canSubmitSample"
            @click="createFromInputs('sample')"
          >
            解析这篇演示
          </button>
        </div>

        <div class="inputs__block" data-testid="text-block">
          <h2 class="inputs__block-title">或粘贴正文</h2>
          <textarea
            v-model="paperText"
            class="inputs__text"
            data-testid="paper-text"
            rows="6"
            placeholder="把 Markdown 正文粘到这里，用 # 标题分段"
          />
          <button
            type="button"
            class="inputs__submit"
            data-testid="submit-text"
            :disabled="!canSubmitText"
            @click="createFromInputs('text')"
          >
            用这段正文解析
          </button>
        </div>
      </div>

      <p v-if="submitHint" class="inputs__hint" data-testid="submit-hint">{{ submitHint }}</p>
      <p v-if="error" class="inputs__error" data-testid="input-error">{{ error }}</p>
    </section>

    <StageTracker :phase="phase" :reached-index="reachedIndex" />

    <section v-if="sections.length > 0" class="workspace" data-testid="workspace">
      <SectionTree
        :sections="sections"
        :selected-index="selectedIndex"
        @select="selectSection"
        @change-type="changeSectionType"
      />
      <SectionReader :section="selectedSection" />
    </section>

    <div v-if="sections.length > 0" class="actions">
      <button
        type="button"
        class="actions__confirm"
        data-testid="confirm-sections"
        :disabled="busy"
        @click="confirmSections"
      >
        确认章节树，进入分项评分
      </button>
      <span class="actions__note">确认之后才会按量规逐维取证；这一页不显示档位。</span>
    </div>

    <section v-if="report" class="confirmed" data-testid="confirmed-card">
      <h2 class="confirmed__title">已确认</h2>
      <dl class="confirmed__list">
        <dt class="confirmed__term">状态</dt>
        <dd class="confirmed__value" data-testid="confirmed-status">{{ report.status }}</dd>
        <dt class="confirmed__term">维度数</dt>
        <dd class="confirmed__value" data-testid="confirmed-dimension-count">
          {{ report.dimensions.length }}
        </dd>
        <dt class="confirmed__term">量规版本</dt>
        <dd class="confirmed__value">{{ report.rubric_version ?? '未绑定' }}</dd>
        <dt class="confirmed__term">来源</dt>
        <dd class="confirmed__value" data-testid="confirmed-source">{{ report.source }}</dd>
      </dl>
      <p class="confirmed__next">
        <RouterLink to="/scoring">去分项评分页</RouterLink>（该页在下一版实现）
      </p>
    </section>
  </article>
</template>

<style scoped>
.parse {
  max-width: var(--pr-measure);
}

.parse__head {
  display: flex;
  align-items: baseline;
  gap: var(--pr-space-3);
  margin: 0 0 var(--pr-space-2);
}

.parse__num {
  font-family: var(--pr-font-data);
  font-size: 28px;
  line-height: 1;
  color: var(--pr-ink-faint);
}

.parse__title {
  margin: 0;
  font-size: var(--pr-text-title);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.parse__lead {
  margin: 0 0 var(--pr-space-6);
  color: var(--pr-ink-muted);
}

.inputs {
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.inputs__row {
  display: flex;
  align-items: center;
  gap: var(--pr-space-3);
}

.inputs__label {
  flex: none;
  color: var(--pr-ink-muted);
}

.inputs__select,
.inputs__text {
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-ink);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-base);
}

.inputs__select {
  min-width: 240px;
  padding: var(--pr-space-1) var(--pr-space-2);
}

/* focus 用批注色下划线式描边，不用浏览器默认蓝描边 */
.inputs__select:focus,
.inputs__text:focus {
  outline: none;
  border-color: var(--pr-primary);
}

.inputs__meta {
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.inputs__pair {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-6);
  margin-top: var(--pr-space-4);
}

.inputs__block {
  flex: 1 1 320px;
  min-height: 200px;
  padding: var(--pr-space-3);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-slot-bg);
}

.inputs__block-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-sm);
  font-weight: 600;
  color: var(--pr-ink-muted);
}

.inputs__demos {
  display: flex;
  flex-wrap: wrap;
  gap: var(--pr-space-2);
  margin-bottom: var(--pr-space-3);
}

.inputs__demo {
  padding: var(--pr-space-1) var(--pr-space-3);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
  color: var(--pr-ink);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-sm);
  cursor: pointer;
}

.inputs__demo[data-selected='true'] {
  border-color: var(--pr-primary);
  background: var(--pr-primary-soft);
  color: var(--pr-primary-strong);
}

.inputs__text {
  display: block;
  width: 100%;
  margin-bottom: var(--pr-space-3);
  padding: var(--pr-space-2);
  resize: vertical;
}

.inputs__submit {
  padding: var(--pr-space-1) var(--pr-space-3);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-primary);
  color: var(--pr-surface);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-sm);
  cursor: pointer;
}

.inputs__submit:disabled {
  border-color: var(--pr-rule);
  background: var(--pr-surface-sunken);
  color: var(--pr-ink-faint);
  cursor: not-allowed;
}

.inputs__hint {
  margin: var(--pr-space-3) 0 0;
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.inputs__error {
  margin: var(--pr-space-2) 0 0;
  padding: var(--pr-space-2) var(--pr-space-3);
  border-radius: var(--pr-radius);
  background: var(--pr-conflict-soft);
  color: var(--pr-conflict);
  font-size: var(--pr-text-sm);
}

.workspace {
  display: flex;
  gap: var(--pr-space-6);
  margin-top: var(--pr-space-6);
  padding-top: var(--pr-space-4);
  border-top: 1px solid var(--pr-rule);
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--pr-space-3);
  margin-top: var(--pr-space-4);
}

.actions__confirm {
  padding: var(--pr-space-2) var(--pr-space-4);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-primary);
  color: var(--pr-surface);
  font-family: var(--pr-font-ui);
  font-size: var(--pr-text-base);
  cursor: pointer;
}

.actions__confirm:disabled {
  border-color: var(--pr-rule);
  background: var(--pr-surface-sunken);
  color: var(--pr-ink-faint);
  cursor: not-allowed;
}

.actions__note {
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.confirmed {
  margin-top: var(--pr-space-6);
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-primary);
  border-radius: var(--pr-radius);
  background: var(--pr-primary-soft);
}

.confirmed__title {
  margin: 0 0 var(--pr-space-3);
  font-size: var(--pr-text-lg);
  font-weight: 600;
  color: var(--pr-primary-strong);
}

.confirmed__list {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--pr-space-1) var(--pr-space-4);
  margin: 0;
}

.confirmed__term {
  color: var(--pr-ink-muted);
}

.confirmed__value {
  margin: 0;
}

.confirmed__next {
  margin: var(--pr-space-3) 0 0;
  font-size: var(--pr-text-sm);
}
</style>
