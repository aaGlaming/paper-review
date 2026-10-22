<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError, createReview, getContestRubric, listContests, listSamples, resumeReview } from '../api'
import type { ContestSummary, PaperSection, PublishedRubricText, ReviewReport, SampleItem } from '../api/types'
import artUrl from '../assets/sketch/sketch-bg-parse.svg'
import spotUrl from '../assets/sketch/sketch-spot-parse.svg'
import PageArt from '../components/PageArt.vue'
import SectionReader from '../components/SectionReader.vue'
import SectionTree from '../components/SectionTree.vue'
import StageTracker from '../components/StageTracker.vue'
import ParseEmptyIllustration from '../components/illustrations/ParseEmptyIllustration.vue'
import { REVIEW_STAGES, type StagePhase } from '../composables/reviewVocabulary'
import { readReviewFlow, setConfirmedReport, setReviewCreated } from '../composables/useReviewFlow'

// 历史模型路径最大耗时为 36.6 秒；5 秒过短，20 秒表示明显偏慢但仍在正常范围，属于可调整的工程阈值。
const SLOW_HINT_MS = 20_000

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
const rubric = ref<PublishedRubricText | null>(null)
const rubricState = ref<'idle' | 'loading' | 'available' | 'missing' | 'empty' | 'error'>('idle')
const rubricError = ref('')

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
const elapsedSeconds = ref(0)
const elapsedActive = ref(false)
let elapsedTimer: number | null = null
let confirmationStartedAt = 0

const hasContest = computed(() => contestId.value !== '')
const hasSample = computed(() => selectedSampleId.value !== '')
const hasText = computed(() => paperText.value.trim().length > 0)
const selectedContest = computed(() =>
  contests.value.find((contest) => contest.contest_id === contestId.value) ?? null,
)
const canScore = computed(() => hasContest.value && rubricState.value === 'available')
const assessmentMeta = computed(() => {
  if (!hasContest.value) {
    return '未绑定赛题 · 仅解析'
  }
  if (rubricState.value === 'loading' || rubricState.value === 'idle') {
    return '正在读取赛题与量规…'
  }
  if (rubricState.value === 'missing') {
    return '该赛题没有已发布量规，暂时无法评分'
  }
  if (rubricState.value === 'empty') {
    return '该赛题的已发布量规没有维度，暂时无法评分'
  }
  if (rubricState.value === 'error') {
    return `量规读取失败：${rubricError.value}`
  }
  const title = selectedContest.value?.title ?? '已选赛题'
  return `${title} · 量规 v${rubric.value?.version} · ${rubric.value?.dimensions.length ?? 0} 个维度`
})
const confirmedAssessmentMeta = computed(() => {
  if (!report.value?.contest_id) {
    return '未绑定赛题 · 仅解析'
  }
  const title = contests.value.find((contest) => contest.contest_id === report.value?.contest_id)?.title ?? '已绑定赛题'
  return `${title} · 量规 v${report.value.rubric_version} · ${report.value.dimensions.length} 个维度`
})

// paper_text 与 sample_id 互斥：两条路都填时先让用户清掉一个，而不是悄悄丢掉一份输入
const conflict = computed(() => hasSample.value && hasText.value)

const submitHint = computed(() => {
  if (hasContest.value && rubricState.value === 'loading') {
    return '正在检查该赛题的已发布量规。'
  }
  if (hasContest.value && (rubricState.value === 'missing' || rubricState.value === 'empty')) {
    return assessmentMeta.value
  }
  if (hasContest.value && rubricState.value === 'error') {
    return assessmentMeta.value
  }
  if (!hasContest.value) {
    return '未绑定赛题时只创建解析会话，不进行评分。'
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
  () => hasSample.value && !conflict.value && !busy.value && (!hasContest.value || canScore.value),
)
const canSubmitText = computed(
  () => hasText.value && !conflict.value && !busy.value && (!hasContest.value || canScore.value),
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

watch(contestId, async (selectedId) => {
  rubric.value = null
  rubricError.value = ''
  if (!selectedId) {
    rubricState.value = 'idle'
    return
  }

  rubricState.value = 'loading'
  try {
    const loaded = await getContestRubric(selectedId)
    if (contestId.value !== selectedId) {
      return
    }
    rubric.value = loaded
    rubricState.value = loaded.dimensions.length > 0 ? 'available' : 'empty'
  } catch (reason) {
    if (contestId.value !== selectedId) {
      return
    }
    if (reason instanceof ApiError && reason.status === 404) {
      rubricState.value = 'missing'
    } else {
      rubricError.value = describeError(reason)
      rubricState.value = 'error'
    }
  }
})

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
  elapsedActive.value = false
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

onUnmounted(() => {
  if (elapsedTimer !== null) {
    window.clearInterval(elapsedTimer)
    elapsedTimer = null
  }
})

async function confirmSections(): Promise<void> {
  if (busy.value || !reviewId.value || sections.value.length === 0 || !canScore.value) {
    return
  }
  busy.value = true
  error.value = ''
  phase.value = 'running'
  elapsedSeconds.value = 0
  elapsedActive.value = true
  confirmationStartedAt = Date.now()
  // 计时器只显示经过时间，不更新步骤；StageTracker 的步骤仍只依据真实报告点亮。
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - confirmationStartedAt) / 1000)
  }, 1_000)
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
    if (elapsedTimer !== null) {
      window.clearInterval(elapsedTimer)
      elapsedTimer = null
    }
    elapsedSeconds.value = Math.floor((Date.now() - confirmationStartedAt) / 1000)
    elapsedActive.value = false
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
    <PageArt :art="artUrl" :spot="spotUrl" layout="right" />
    <div class="parse__hero">
      <header class="ed-head parse__hero-head">
        <span class="ed-head__num" aria-hidden="true">01</span>
        <p class="ed-head__kicker">稿源 · 章节树 · 确认</p>
        <h1 class="ed-head__title">论文解析</h1>
      </header>
        <p class="ed-lede parse__hero-lede">
        可选绑定赛题，再填一篇稿子：解析出章节树；只有赛题量规可用时才能进入分项评分。
      </p>
      <ParseEmptyIllustration class="parse__hero-illo" />
    </div>

    <section class="inputs" data-testid="inputs">
      <p class="ed-kicker">第一步 · 绑定赛题与稿源</p>
      <p class="inputs__intro-text">两条路线二选一：演示样例最快，粘贴正文最自由。解析出章节树后，确认才进入评分。</p>
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
      <p class="inputs__assessment" data-testid="contest-assessment-meta">{{ assessmentMeta }}</p>

      <div class="inputs__pair">
        <div class="inputs__block inputs__block--primary ed-focus" data-testid="sample-block">
          <p class="ed-kicker">路线 A · 推荐</p>
          <h2 class="inputs__block-title">用演示样例</h2>
          <div class="inputs__demos">
            <button
              v-for="sample in samples"
              :key="sample.sample_id"
              type="button"
              class="inputs__demo"
              data-testid="demo-item"
              :data-sample-id="sample.sample_id"
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

        <div class="inputs__block inputs__block--secondary" data-testid="text-block">
          <p class="ed-kicker">路线 B</p>
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

    <StageTracker
      :phase="phase"
      :reached-index="reachedIndex"
      :elapsed-seconds="elapsedSeconds"
      :elapsed-active="elapsedActive"
      :slow-hint-ms="SLOW_HINT_MS"
    />

    <section v-if="sections.length > 0" class="workspace" data-testid="workspace">
      <div class="workspace__tree">
        <p class="ed-kicker">第二步 · 章节树（点一条看正文）</p>
        <SectionTree
          :sections="sections"
          :selected-index="selectedIndex"
          @select="selectSection"
          @change-type="changeSectionType"
        />
      </div>
      <div class="workspace__reader">
        <p class="ed-kicker">正文原文</p>
        <SectionReader :section="selectedSection" />
      </div>
    </section>

    <div v-if="sections.length > 0" class="actions">
      <button
        type="button"
        class="actions__confirm"
        data-testid="confirm-sections"
        :disabled="busy || !canScore"
        @click="confirmSections"
      >
        确认章节树，进入分项评分
      </button>
      <span class="actions__note">确认之后才会按量规逐维取证；这一页不显示档位。</span>
    </div>

    <section v-if="report" class="confirmed" data-testid="confirmed-card">
      <h2 class="confirmed__title">已确认</h2>
      <dl class="confirmed__list">
        <dt class="confirmed__term">评审范围</dt>
        <dd class="confirmed__value" data-testid="confirmed-assessment-meta">{{ confirmedAssessmentMeta }}</dd>
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
        <RouterLink class="ed-action-link" to="/scoring">去分项评分页</RouterLink>
        <span class="confirmed__next-note">报告已就绪，后面三页会接着用它。</span>
      </p>
    </section>
  </article>
</template>

<style scoped>
.parse {
  max-width: var(--pr-measure);
}

/* 首页 hero：标题占 7、插画占 5 的非对称组合，插画是"等稿子进来"的叙事，
   不是装饰角标；窄屏时插画退到标题下方，不挤表单。 */
.parse__hero {
  display: grid;
  grid-template-columns: 7fr 5fr;
  grid-template-areas:
    'head illo'
    'lede illo';
  gap: 0 var(--pr-space-6);
  align-items: center;
  margin-bottom: var(--pr-space-6);
}

.parse__hero-head {
  grid-area: head;
  margin-bottom: 0;
}

.parse__hero-lede {
  grid-area: lede;
  margin: var(--pr-space-2) 0 0;
}

.parse__hero-illo {
  grid-area: illo;
  width: 100%;
  max-width: 300px;
  justify-self: end;
}

.inputs {
  padding: var(--pr-space-4);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-surface);
}

.inputs__kicker {
  margin: 0 0 var(--pr-space-3);
}

.inputs__intro-text {
  margin: 0 0 var(--pr-space-4);
  padding-bottom: var(--pr-space-4);
  border-bottom: 1px dashed var(--pr-rule);
  color: var(--pr-ink-muted);
  font-size: var(--pr-text-base);
  line-height: var(--pr-leading-base);
}

@media (max-width: 900px) {
  .parse__hero {
    grid-template-columns: 1fr;
    grid-template-areas: 'head' 'lede' 'illo';
  }

  .parse__hero-illo {
    justify-self: start;
    max-width: 240px;
    margin-top: var(--pr-space-4);
  }
}

.inputs__row {
  display: flex;
  flex-wrap: wrap;
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
  min-width: 0;
  max-width: 100%;
  padding: var(--pr-space-1) var(--pr-space-2);
}

@media (min-width: 901px) {
  .inputs__select {
    min-width: 240px;
  }
}

/* focus 用批注色边框 + 全局 focus 环，不用浏览器默认蓝描边 */
.inputs__select:focus-visible,
.inputs__text:focus-visible {
  outline: none;
  border-color: var(--pr-primary);
  box-shadow: var(--pr-focus-ring);
}

.inputs__meta {
  color: var(--pr-ink-faint);
  font-size: var(--pr-text-sm);
}

.inputs__pair {
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: var(--pr-space-6);
  align-items: start;
  margin-top: var(--pr-space-4);
}

.inputs__block {
  min-height: 200px;
  padding: var(--pr-space-3);
  border: 1px solid var(--pr-rule);
  border-radius: var(--pr-radius);
  background: var(--pr-slot-bg);
}

.inputs__block--primary {
  padding: var(--pr-space-4);
  background: var(--pr-surface);
}

.inputs__block--secondary {
  border-style: dashed;
}

.inputs__block-title {
  margin: 0 0 var(--pr-space-2);
  font-size: var(--pr-text-lg);
  font-weight: 600;
  color: var(--pr-ink);
}

@media (max-width: 900px) {
  .inputs__pair {
    grid-template-columns: 1fr;
  }
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
  color: var(--pr-ink-muted);
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
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: var(--pr-space-6);
  align-items: start;
  margin-top: var(--pr-space-6);
  padding-top: var(--pr-space-4);
  border-top: 1px solid var(--pr-rule);
}

.workspace__tree,
.workspace__reader {
  min-width: 0;
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
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
  color: var(--pr-ink-muted);
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
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--pr-space-3);
  margin: var(--pr-space-3) 0 0;
  font-size: var(--pr-text-sm);
}

.confirmed__next-note {
  color: var(--pr-ink-muted);
}
</style>
