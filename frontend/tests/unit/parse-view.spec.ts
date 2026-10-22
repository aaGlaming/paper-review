// 论文解析页（P8 阶段 2/6）。api 层整体桩掉：本文件只验页面行为，不发真请求。
// 断言里刻意不出现任何写死的演示稿标题——标题必须来自 listSamples(true) 的返回。

import { flushPromises, mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api'
import * as api from '../../src/api'
import {
  REVIEW_STAGES,
  SECTION_TYPES,
  SECTION_TYPE_OPTIONS,
  UNCLASSIFIED_SECTION_TYPE,
} from '../../src/composables/reviewVocabulary'
import { AWARD_WORDS, CONTEST_ID_TOKEN } from './forbidden-words'
import { REVIEW_FLOW_STORAGE_KEY } from '../../src/composables/useReviewFlow'
import { createAppRouter } from '../../src/router'
import type { PaperSection, ReviewReport } from '../../src/api/types'
import ParseView from '../../src/views/论文解析.vue'
import StageTracker from '../../src/components/StageTracker.vue'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return {
    ...actual,
    listContests: vi.fn(),
    getContestRubric: vi.fn(),
    listSamples: vi.fn(),
    createReview: vi.fn(),
    resumeReview: vi.fn(),
    getReview: vi.fn(),
  }
})

const SRC_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'src')

const CONTEST_A = 'contest-demo-a'
const CONTEST_B = 'contest-demo-b'

const CONTESTS = {
  contests: [
    {
      contest_id: CONTEST_A,
      year: 2024,
      problem_code: 'A',
      title: '演示赛题甲',
      statement: '题面甲',
      status: 'published',
      rubric: { rubric_id: 'contest-demo-a-v1', version: 1, status: 'published' },
      constraints: [],
      pitfall_count: 1,
      exemplar_count: 1,
    },
    {
      contest_id: CONTEST_B,
      year: 2024,
      problem_code: 'C',
      title: '演示赛题乙',
      statement: '题面乙',
      status: 'published',
      rubric: { rubric_id: 'contest-demo-b-v1', version: 1, status: 'published' },
      constraints: [],
      pitfall_count: 1,
      exemplar_count: 1,
    },
  ],
}

const SAMPLES = {
  samples: [
    { sample_id: 'demo-alpha', title: '演示样例甲', is_demo: true, contest_id: CONTEST_A, has_gold: false },
    { sample_id: 'demo-beta', title: '演示样例乙', is_demo: true, contest_id: CONTEST_A, has_gold: false },
  ],
}

const SECTIONS: PaperSection[] = [
  { title: '摘要', section_type: UNCLASSIFIED_SECTION_TYPE, level: 1, content: '摘要正文' },
  { title: '一、模型假设', section_type: '假设', level: 2, content: '假设正文' },
  { title: '二、模型的建立', section_type: '模型', level: 2, content: '建模正文' },
  { title: '三、模型求解', section_type: '求解', level: 2, content: '求解正文' },
  { title: '四、结果分析', section_type: '结果', level: 2, content: '结果正文' },
]

const REPORT: ReviewReport = {
  review_id: 'review-1',
  status: '完成',
  contest_id: CONTEST_A,
  rubric_id: 'contest-demo-a-v1',
  rubric_version: 1,
  model_name: 'deterministic',
  source: 'deterministic',
  dimensions: [
    { dimension_code: 'assumption', band: '基本', chunk_ids: [], quote: '原句一', status: '基本' },
    { dimension_code: 'modeling', band: '基本', chunk_ids: [], quote: '原句二', status: '基本' },
    { dimension_code: 'solution', band: '基本', chunk_ids: [], quote: '原句三', status: '基本' },
    { dimension_code: 'constraint_check', band: '基本', chunk_ids: [], quote: '原句四', status: '基本' },
    { dimension_code: 'presentation', band: '基本', chunk_ids: [], quote: '原句五', status: '基本' },
  ],
  score: { total: 0, weighted: 0, excluded: [], weight_sum: 0 },
  change_list: [],
  note: '各维结果来自确定性结构回退',
}

async function mountView() {
  const router = createAppRouter()
  const wrapper = mount(ParseView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

async function createOne(wrapper: Awaited<ReturnType<typeof mountView>>) {
  await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_A)
  await wrapper.get('[data-testid="demo-item"]').trigger('click')
  await wrapper.get('[data-testid="submit-sample"]').trigger('click')
  await flushPromises()
}

function sourceOf(relative: string): string {
  return readFileSync(path.join(SRC_ROOT, relative), 'utf8')
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  vi.mocked(api.listContests).mockResolvedValue(CONTESTS)
  vi.mocked(api.getContestRubric).mockResolvedValue({
    contest_id: CONTEST_A,
    rubric_id: 'contest-demo-a-v1',
    version: 1,
    dimensions: Array.from({ length: 5 }, (_, index) => ({
      dimension_code: `dimension-${index}`,
      name: `维度 ${index}`,
      weight: 20,
      bands: [],
    })),
  })
  vi.mocked(api.listSamples).mockResolvedValue(SAMPLES)
  vi.mocked(api.createReview).mockResolvedValue({
    review_id: 'review-1',
    status: '待确认',
    sections: SECTIONS,
  })
  vi.mocked(api.resumeReview).mockResolvedValue(REPORT)
  vi.mocked(api.getReview).mockRejectedValue(new ApiError(404, '未使用'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('论文解析页', () => {
  it('running态显示已等待秒数，并随真实经过时间递增', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    vi.mocked(api.resumeReview).mockImplementation(() => new Promise<ReviewReport>(() => {}))

    await wrapper.get('[data-testid="confirm-sections"]').trigger('click')
    expect(wrapper.get('[data-testid="stage-tracker"]').attributes('data-phase')).toBe('running')
    expect(vi.getTimerCount()).toBeGreaterThan(0)
    expect(wrapper.get('[data-testid="stage-elapsed"]').text()).toContain('0')

    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(wrapper.get('[data-testid="stage-elapsed"]').text()).toContain('2')
    wrapper.unmount()
  })

  it('等待超过20秒后显示带实际秒数的慢提示', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    vi.mocked(api.resumeReview).mockImplementation(() => new Promise<ReviewReport>(() => {}))

    await wrapper.get('[data-testid="confirm-sections"]').trigger('click')
    await vi.advanceTimersByTimeAsync(21_000)
    await flushPromises()

    expect(wrapper.get('[data-testid="stage-slow-hint"]').text()).toContain('21')
    expect(wrapper.get('[data-testid="stage-slow-hint"]').text()).toContain(
      '仍在处理；本流程正常需数十秒，可继续等待或稍后回来查看',
    )
    wrapper.unmount()
  })

  it('非running态不显示耗时与慢提示钩子', () => {
    for (const phase of ['idle', 'parsed', 'done', 'failed'] as const) {
      const wrapper = mount(StageTracker, { props: { phase, reachedIndex: -1, elapsedSeconds: 21 } })
      expect(wrapper.find('[data-testid="stage-elapsed"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="stage-slow-hint"]').exists()).toBe(false)
      wrapper.unmount()
    }
  })

  it('1. 空赛题仍可创建解析会话，并明确标记为仅解析', async () => {
    const wrapper = await mountView()

    await wrapper.get('[data-testid="demo-item"]').trigger('click')

    expect(wrapper.get('[data-testid="contest-assessment-meta"]').text()).toBe('未绑定赛题 · 仅解析')
    expect(wrapper.get('[data-testid="submit-sample"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="submit-sample"]').trigger('click')
    await flushPromises()

    expect(api.createReview).toHaveBeenCalledWith({ sample_id: 'demo-alpha', contest_id: '' })
    expect(wrapper.get('[data-testid="confirm-sections"]').attributes('disabled')).toBeDefined()
  })

  it('确认区显示所选赛题、published 量规版本与维度数', async () => {
    const wrapper = await mountView()
    await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_A)
    await flushPromises()

    expect(api.getContestRubric).toHaveBeenCalledWith(CONTEST_A)
    expect(wrapper.get('[data-testid="contest-assessment-meta"]').text()).toBe('演示赛题甲 · 量规 v1 · 5 个维度')
  })

  it('无 published 量规时说明原因并禁用创建入口', async () => {
    vi.mocked(api.getContestRubric).mockRejectedValueOnce(new ApiError(404, 'missing rubric'))
    const wrapper = await mountView()
    await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_B)
    await flushPromises()
    await wrapper.get('[data-testid="demo-item"]').trigger('click')

    expect(wrapper.get('[data-testid="contest-assessment-meta"]').text()).toBe(
      '该赛题没有已发布量规，暂时无法评分',
    )
    expect(wrapper.get('[data-testid="submit-sample"]').attributes('disabled')).toBeDefined()
  })

  it('2. 演示按钮由 listSamples(true) 渲染，点击后用 sample_id 与当前赛题调 createReview', async () => {
    const wrapper = await mountView()

    expect(api.listSamples).toHaveBeenCalledWith(true)
    const buttons = wrapper.findAll('[data-testid="demo-item"]')
    expect(buttons.map((button) => button.text())).toEqual(SAMPLES.samples.map((item) => item.title))

    await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_A)
    await buttons[0]?.trigger('click')
    await wrapper.get('[data-testid="submit-sample"]').trigger('click')
    await flushPromises()

    expect(api.createReview).toHaveBeenCalledTimes(1)
    expect(api.createReview).toHaveBeenCalledWith({ sample_id: 'demo-alpha', contest_id: CONTEST_A })
  })

  it('3. 粘贴正文后用 paper_text 调 createReview，且同一次调用不带 sample_id', async () => {
    const wrapper = await mountView()

    await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_A)
    await wrapper.get('[data-testid="paper-text"]').setValue('# 摘要\n正文一段')
    await wrapper.get('[data-testid="submit-text"]').trigger('click')
    await flushPromises()

    expect(api.createReview).toHaveBeenCalledTimes(1)
    const payload = vi.mocked(api.createReview).mock.calls[0]?.[0]
    expect(payload).toEqual({ paper_text: '# 摘要\n正文一段', contest_id: CONTEST_A })
    expect(payload).not.toHaveProperty('sample_id')
  })

  it('4. 两个输入都填或都空时提交按钮禁用并给出说明', async () => {
    const wrapper = await mountView()
    await wrapper.get('[data-testid="contest-select"]').setValue(CONTEST_A)

    // 都空
    expect(wrapper.get('[data-testid="submit-sample"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="submit-text"]').attributes('disabled')).toBeDefined()
    const emptyHint = wrapper.get('[data-testid="submit-hint"]').text()
    expect(emptyHint).toContain('粘贴正文')

    // 都填
    await wrapper.get('[data-testid="demo-item"]').trigger('click')
    await wrapper.get('[data-testid="paper-text"]').setValue('# 摘要\n正文一段')

    expect(wrapper.get('[data-testid="submit-sample"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="submit-text"]').attributes('disabled')).toBeDefined()
    const conflictHint = wrapper.get('[data-testid="submit-hint"]').text()
    expect(conflictHint).toContain('只能选一条')
    expect(conflictHint).not.toBe(emptyHint)

    await wrapper.get('[data-testid="submit-sample"]').trigger('click')
    await wrapper.get('[data-testid="submit-text"]').trigger('click')
    await flushPromises()
    expect(api.createReview).not.toHaveBeenCalled()
  })

  it('5. 章节树条数与 sections 一致，层级用缩进表达而不是编号', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)

    const rows = wrapper.findAll('[data-testid="section-item"]')
    expect(rows).toHaveLength(SECTIONS.length)

    // 层级用缩进：depth 随 level 递增，且行的 style 不同
    expect(rows[0]?.attributes('data-depth')).toBe('0')
    expect(rows[1]?.attributes('data-depth')).toBe('1')
    expect(rows[1]?.attributes('style')).not.toBe(rows[0]?.attributes('style'))

    // 章节树内不出现 01 / 02 / 03 这类装饰性编号（层级靠缩进，不靠编号）。
    // 页面顶部另有 h1 旁的流程大编号（01 论文解析），那是页面级编号，不在此列。
    const tree = wrapper.get('[data-testid="section-tree"]')
    const numbered = Array.from(tree.element.querySelectorAll('*') as NodeListOf<Element>)
      .map((element) => (element.textContent ?? '').trim())
      .filter((text) => /^\d{2}$/.test(text))
    expect(numbered).toEqual([])
  })

  it('6. 未确认时页面不出现任何档位、分数或加权', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)

    const text = wrapper.text()
    for (const word of ['充分', '基本', '不足', '证据不足']) {
      expect(text, word).not.toContain(word)
    }
    expect(wrapper.find('[data-band]').exists()).toBe(false)
    expect(wrapper.find('[data-dimensions]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="confirmed-card"]').exists()).toBe(false)
  })

  it('7. 改过 section_type 后确认：提交的 sections 用改后的值，其余逐字不变', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)

    const selects = wrapper.findAll('[data-testid="section-type"]')
    expect(selects).toHaveLength(SECTIONS.length)
    await selects[1]?.setValue('结果')
    await wrapper.get('[data-testid="confirm-sections"]').trigger('click')
    await flushPromises()

    expect(api.resumeReview).toHaveBeenCalledTimes(1)
    const called = vi.mocked(api.resumeReview).mock.calls[0]
    expect(called?.[0]).toBe('review-1')
    const sent = called?.[1] ?? []
    expect(sent).toHaveLength(SECTIONS.length)
    expect(sent.map((item) => item.section_type)).toEqual(
      SECTIONS.map((item, index) => (index === 1 ? '结果' : item.section_type)),
    )
    expect(sent[1]?.title).toBe(SECTIONS[1]?.title)
    expect(sent[1]?.content).toBe(SECTIONS[1]?.content)
    expect(sent[0]).toEqual(SECTIONS[0])
    expect(sent[4]).toEqual(SECTIONS[4])
  })

  it('8. 创建失败时显示 detail 文案，且不渲染章节树', async () => {
    vi.mocked(api.createReview).mockRejectedValue(
      new ApiError(400, 'paper_text 与 sample_id 只能给一个', {
        detail: 'paper_text 与 sample_id 只能给一个',
      }),
    )
    const wrapper = await mountView()
    await createOne(wrapper)

    expect(wrapper.get('[data-testid="input-error"]').text()).toContain('paper_text 与 sample_id 只能给一个')
    expect(wrapper.findAll('[data-testid="section-item"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="confirm-sections"]').exists()).toBe(false)
  })

  it('8b. 坏包类错误把 filename 与 field 一并显示', async () => {
    vi.mocked(api.createReview).mockRejectedValue(
      new ApiError(400, '权重合计不为 100', {
        detail: '权重合计不为 100',
        filename: 'rubric.json',
        field: 'dimensions[0].weight',
      }),
    )
    const wrapper = await mountView()
    await createOne(wrapper)

    const error = wrapper.get('[data-testid="input-error"]').text()
    expect(error).toContain('权重合计不为 100')
    expect(error).toContain('rubric.json')
    expect(error).toContain('dimensions[0].weight')
  })

  it('9. 确认成功后把 reviewId 与 report 写进共享状态，并渲染已确认结果卡', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)
    await wrapper.get('[data-testid="confirm-sections"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="confirmed-card"]')
    expect(card.text()).toContain(REPORT.status)
    expect(card.text()).toContain(REPORT.source)
    expect(wrapper.get('[data-testid="confirmed-assessment-meta"]').text()).toBe(
      '演示赛题甲 · 量规 v1 · 5 个维度',
    )
    expect(wrapper.get('[data-testid="confirmed-dimension-count"]').text()).toBe(
      String(REPORT.dimensions.length),
    )

    const stored = JSON.parse(sessionStorage.getItem(REVIEW_FLOW_STORAGE_KEY) ?? '{}')
    expect(stored.reviewId).toBe('review-1')
    expect(stored.contestId).toBe(CONTEST_A)
    expect(stored.report?.review_id).toBe('review-1')
    expect(stored.sections).toHaveLength(SECTIONS.length)
  })

  it('10. 确认失败时显示错误、保留已提交的章节树，步骤指示停在等待服务返回', async () => {
    const wrapper = await mountView()
    await createOne(wrapper)

    const selects = wrapper.findAll('[data-testid="section-type"]')
    await selects[2]?.setValue('参考文献')
    vi.mocked(api.resumeReview).mockRejectedValue(new ApiError(500, '服务内部错误'))

    await wrapper.get('[data-testid="confirm-sections"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="input-error"]').text()).toContain('服务内部错误')
    expect(wrapper.findAll('[data-testid="section-item"]')).toHaveLength(SECTIONS.length)
    const stillChanged = wrapper.findAll('[data-testid="section-type"]')[2]
    expect((stillChanged?.element as HTMLSelectElement).value).toBe('参考文献')
    expect(wrapper.get('[data-testid="stage-badge"]').text()).toBe('停在：等待服务返回')
    expect(wrapper.get('[data-testid="stage-note"]').text()).toContain('已等待 0 秒')
  })

  it('11. 章节类型词表恰好六个类型 + 未分类，顺序一致，且只在一处定义', async () => {
    expect([...SECTION_TYPES]).toEqual(['假设', '模型', '求解', '结果', '检验', '参考文献'])
    expect(UNCLASSIFIED_SECTION_TYPE).toBe('未分类')
    expect([...SECTION_TYPE_OPTIONS]).toEqual([...SECTION_TYPES, '未分类'])
    expect([...REVIEW_STAGES]).toEqual(['赛题对齐', '按维检索', '选档', '规则审查', '原句校验', '生成报告'])

    const wrapper = await mountView()
    await createOne(wrapper)
    const select = wrapper.findAll('[data-testid="section-type"]')[0]
    const options = Array.from((select?.element as HTMLSelectElement).options).map((option) => option.value)
    expect(options).toEqual([...SECTION_TYPE_OPTIONS])

    // 词表只准有一处定义：'未分类' 这个字面量只许出现在词表模块里
    const files = [
      'composables/reviewVocabulary.ts',
      'composables/useReviewFlow.ts',
      'components/StageTracker.vue',
      'components/SectionTree.vue',
      'components/SectionReader.vue',
      'views/论文解析.vue',
    ]
    const holders = files.filter((file) => sourceOf(file).includes(UNCLASSIFIED_SECTION_TYPE))
    expect(holders).toEqual(['composables/reviewVocabulary.ts'])
  })

  it('12. 源码约束：不出现 band / 奖项字样 / 题号、不直接发请求，计时器不伪造步骤', async () => {
    const files = [
      'composables/reviewVocabulary.ts',
      'composables/useReviewFlow.ts',
      'components/StageTracker.vue',
      'components/SectionTree.vue',
      'components/SectionReader.vue',
      'views/论文解析.vue',
    ]

    for (const file of files) {
      const source = sourceOf(file)
      expect(source, `${file} 出现 band`).not.toContain('band')
      expect(source, `${file} 出现题号`).not.toContain(CONTEST_ID_TOKEN)
      for (const word of AWARD_WORDS) {
        expect(source.includes(word), `${file} 出现 ${word}`).toBe(false)
      }
      if (file !== 'views/论文解析.vue') {
        expect(source, `${file} 用定时器伪造进度`).not.toContain('setInterval')
        expect(source, `${file} 用定时器伪造进度`).not.toContain('setTimeout')
      }
      // 页面与组件不得直接发请求：URL 字面量与 fetch 只许待在 src/api 下。
      // 这里认的是**引号紧邻**的 /api/...，免得把 `../api/types` 这种类型导入路径也算进来。
      expect(source, `${file} 直接发请求`).not.toContain('fetch(')
      expect(/['"`]\/api\//.test(source), `${file} 出现 URL 字面量`).toBe(false)
    }
    expect(sourceOf('views/论文解析.vue')).toContain('计时器只显示经过时间，不更新步骤')
    expect(sourceOf('components/StageTracker.vue')).not.toContain('setInterval')
    expect(sourceOf('components/StageTracker.vue')).not.toContain('setTimeout')
  })

  it('12b. 页面在任何状态下都恰好一个 h1，文案为论文解析', async () => {
    const idle = await mountView()
    expect(idle.findAll('h1')).toHaveLength(1)
    expect(idle.get('h1').text()).toBe('论文解析')

    const created = await mountView()
    await createOne(created)
    expect(created.findAll('h1')).toHaveLength(1)
    expect(created.get('h1').text()).toBe('论文解析')

    const failed = await mountView()
    vi.mocked(api.createReview).mockRejectedValue(new ApiError(400, '出错了'))
    await createOne(failed)
    expect(failed.findAll('h1')).toHaveLength(1)
    expect(failed.get('h1').text()).toBe('论文解析')

    // 前面那段把 createReview 改成必失败了，这一段要恢复成能成功
    vi.mocked(api.createReview).mockResolvedValue({
      review_id: 'review-1',
      status: '待确认',
      sections: SECTIONS,
    })
    const confirmed = await mountView()
    await createOne(confirmed)
    await confirmed.get('[data-testid="confirm-sections"]').trigger('click')
    await flushPromises()
    expect(confirmed.findAll('h1')).toHaveLength(1)
    expect(confirmed.get('h1').text()).toBe('论文解析')
  })

  it('12c. 章节树为空时不渲染左栏，但页面仍可用', async () => {
    vi.mocked(api.createReview).mockResolvedValue({
      review_id: 'review-empty',
      status: '待确认',
      sections: [],
    })
    const wrapper = await mountView()
    await createOne(wrapper)

    expect(wrapper.findAll('[data-testid="section-item"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="confirm-sections"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="stage-badge"]').text()).toBe('待确认')
  })
})
