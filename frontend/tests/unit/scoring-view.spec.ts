// 分项评分页（P8 阶段 3/6）。桩掉 api，用 sessionStorage 里的共享状态构造场景。
// 档位词只作为「数据」出现在维度里；空态文案里绝不能有这四个词。

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ArchivedReview, PaperSection, ReviewReport } from '../../src/api/types'
import { REVIEW_FLOW_STORAGE_KEY } from '../../src/composables/useReviewFlow'
import { isArchivedReview, isReviewPending, isReviewReport } from '../../src/composables/reviewShape'
import { createAppRouter } from '../../src/router'
import ScoringView from '../../src/views/分项评分.vue'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, getReview: vi.fn(), getContestRubric: vi.fn(), createReview: vi.fn(), resumeReview: vi.fn() }
})

const QUOTE_IN_SECTION = '本文忽略板凳宽度'
const QUOTE_NOT_FOUND = '这段原句不在任何章节里'

const SECTIONS: PaperSection[] = [
  { title: '摘要', section_type: '未分类', level: 1, content: '这是摘要，与下面各章节无关。' },
  { title: '一、模型假设', section_type: '假设', level: 2, content: `1. 为简化计算，${QUOTE_IN_SECTION}，把每节板凳视为刚体连杆。` },
  { title: '二、模型求解', section_type: '求解', level: 2, content: '采用迭代法求解。' },
]

const DIMENSIONS = [
  { dimension_code: 'assumption', band: '基本', chunk_ids: ['c1'], quote: QUOTE_IN_SECTION, status: '基本' },
  { dimension_code: 'modeling', band: '基本', chunk_ids: [], quote: '这是摘要，与下面各章节无关。', status: '基本' },
  { dimension_code: 'constraint_check', band: '证据不足', chunk_ids: [], quote: null, status: '证据不足' },
  { dimension_code: 'solution', band: null, chunk_ids: [], quote: null, status: null },
  { dimension_code: 'presentation', band: '基本', chunk_ids: ['c2'], quote: '采用迭代法求解。', status: '基本' },
]

const REPORT: ReviewReport = {
  review_id: 'review-1',
  status: '完成',
  contest_id: 'contest-demo-a',
  rubric_id: 'contest-demo-a-v1',
  rubric_version: 1,
  model_name: 'deterministic',
  source: 'deterministic',
  dimensions: DIMENSIONS,
  score: { total: 0, weighted: 0, excluded: [], weight_sum: 0 },
  change_list: [],
  note: '各维结果来自确定性结构回退',
}

const ARCHIVED: ArchivedReview = {
  review_id: 'review-1',
  contest_id: 'contest-demo-a',
  rubric_id: 'contest-demo-a-v1',
  rubric_version: 1,
  model_name: 'deterministic',
  created_at: '2026-10-16T00:00:00',
  dimensions: DIMENSIONS,
  change_list: [],
  change_list_note: '该记录为旧数据，未保存审查清单',
}

const RUBRIC = {
  contest_id: 'contest-demo-a', rubric_id: 'contest-demo-a-v1', version: 1,
  dimensions: [{
    dimension_code: 'assumption', name: '假设合理性', weight: 20,
    bands: [
      { band: '充分', score: 4, description: '依据完整' },
      { band: '基本', score: 3, description: '基本合理' },
      { band: '不足', score: 2, description: '论证较弱' },
      { band: '证据不足', score: null, description: '没有可核对证据' },
    ],
  }],
}

function makeReport(overrides: Partial<ReviewReport>): ReviewReport {
  return { ...REPORT, ...overrides, score: { ...REPORT.score, ...overrides.score } }
}

function writeFlow(partial: {
  contestId?: string
  reviewId?: string
  sections?: PaperSection[]
  report?: ReviewReport | null
}): void {
  sessionStorage.setItem(
    REVIEW_FLOW_STORAGE_KEY,
    JSON.stringify({ contestId: '', reviewId: '', sections: [], report: null, ...partial }),
  )
}

async function mountView() {
  const router = createAppRouter()
  const wrapper = mount(ScoringView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  vi.mocked(api.getReview).mockResolvedValue(ARCHIVED)
  vi.mocked(api.getContestRubric).mockRejectedValue(new Error('not found'))
})

describe('分项评分页', () => {
  it('1. 没有 report 且没有 reviewId：渲染空态，不含四个档位词，也没有维度卡', async () => {
    writeFlow({})
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="scoring-empty"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-dimension]')).toHaveLength(0)
    for (const word of ['充分', '基本', '不足', '证据不足']) {
      expect(wrapper.text(), word).not.toContain(word)
    }
  })

  it('2. 有 report：维度卡条数等于 dimensions.length，顺序与后端一致', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS, reviewId: 'review-1', contestId: 'contest-demo-a' })
    const wrapper = await mountView()

    const codes = wrapper.findAll('[data-testid="dimension-card"]').map((card) => card.attributes('data-dimension'))
    expect(codes).toEqual(DIMENSIONS.map((d) => d.dimension_code))
  })

  it('3. 每张卡显示 dimension_code 与 band；band 为 null 时显示「未选档」', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const solution = wrapper.get('[data-dimension="solution"]')
    expect(solution.text()).toContain('未选档')
    expect(solution.text()).not.toContain('null')
    const assumption = wrapper.get('[data-dimension="assumption"]')
    expect(assumption.get('[data-testid="band"]').text()).toBe('基本')
  })

  it('4. band 为证据不足的卡带 data-insufficient=true，其余不带，且卡内没有数字分数', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const insufficient = wrapper.get('[data-dimension="constraint_check"]')
    expect(insufficient.attributes('data-insufficient')).toBe('true')
    expect(/\d/.test(insufficient.text())).toBe(false)

    const normal = wrapper.get('[data-dimension="assumption"]')
    expect(normal.attributes('data-insufficient')).toBeUndefined()
  })

  it('5. quote 为 null：显示「未给原句」，没有原句文本，定位按钮 disabled 并给原因', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const card = wrapper.get('[data-dimension="constraint_check"]')
    expect(card.text()).toContain('未给原句')
    expect(card.find('[data-testid="quote-text"]').exists()).toBe(false)
    const locate = card.get('[data-testid="locate-quote"]')
    expect(locate.attributes('disabled')).toBeDefined()
    expect(card.text()).toContain('无法定位')
  })

  it('6. 点「定位原句」：在 sections 里找到含 quote 的章节，调用 scrollIntoView 并把该处高亮', async () => {
    const scrollSpy = vi.fn()
    ;(Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = scrollSpy

    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.get('[data-dimension="assumption"] [data-testid="locate-quote"]').trigger('click')
    await flushPromises()

    expect(scrollSpy).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="located-content"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="located-mark"]').text()).toBe(QUOTE_IN_SECTION)
    expect(wrapper.get('[data-dimension="assumption"]').attributes('data-located')).toBe('true')
  })

  it('7. quote 非空但不在任何 section 里：显示无法定位，不调用 scrollIntoView', async () => {
    const scrollSpy = vi.fn()
    ;(Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = scrollSpy

    const report = makeReport({
      dimensions: [{ dimension_code: 'assumption', band: '基本', chunk_ids: [], quote: QUOTE_NOT_FOUND, status: '基本' }],
    })
    writeFlow({ report, sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.get('[data-dimension="assumption"] [data-testid="locate-quote"]').trigger('click')
    await flushPromises()

    expect(scrollSpy).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="locate-error"]').text()).toContain('无法定位')
    expect(wrapper.find('[data-testid="located-content"]').exists()).toBe(false)
  })

  it('8. score 全 0 且 source=deterministic：显示「加权未产生」，无「总分 0 / 0 分 / 得分 0」，三个原始值都在', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const text = wrapper.text()
    expect(text).toContain('加权未产生')
    expect(text).not.toContain('总分 0')
    expect(text).not.toContain('0 分')
    expect(text).not.toContain('得分 0')
    for (const key of ['total', 'weighted', 'weight_sum']) {
      expect(text).toContain(key)
    }
  })

  it('9. 后端返回非零加权：页面显示 76.5', async () => {
    const report = makeReport({ source: 'model', score: { total: 88, weighted: 76.5, excluded: [], weight_sum: 100 } })
    writeFlow({ report, sections: SECTIONS })
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="weighted"]').text()).toBe('76.5')
    expect(wrapper.text()).not.toContain('加权未产生')
  })

  it('10. excluded 有两条：原生表格恰好两行，且 reason 原文出现', async () => {
    const report = makeReport({
      source: 'model',
      score: {
        total: 88,
        weighted: 76.5,
        weight_sum: 100,
        excluded: [
          { dimension_code: 'constraint_check', band: '证据不足', status: '证据不足', weight: 20, contribution: 0, reason: '证据不足不参与加权' },
          { dimension_code: 'solution', band: null, status: '选档失败', weight: 20, contribution: 0, reason: '选档失败不参与加权' },
        ],
      },
    })
    writeFlow({ report, sections: SECTIONS })
    const wrapper = await mountView()

    expect(wrapper.findAll('[data-testid="excluded-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('证据不足不参与加权')
    expect(wrapper.text()).toContain('选档失败不参与加权')
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('11. 恰好一个 h1，文案「分项评分」；空态 / 有报告 / 定位中三种状态都成立', async () => {
    const empty = await mountView()
    expect(empty.findAll('h1')).toHaveLength(1)
    expect(empty.get('h1').text()).toBe('分项评分')

    writeFlow({ report: REPORT, sections: SECTIONS })
    const withReport = await mountView()
    expect(withReport.findAll('h1')).toHaveLength(1)
    expect(withReport.get('h1').text()).toBe('分项评分')

    const located = await mountView()
    await located.get('[data-dimension="assumption"] [data-testid="locate-quote"]').trigger('click')
    await flushPromises()
    expect(located.findAll('h1')).toHaveLength(1)
    expect(located.get('h1').text()).toBe('分项评分')
  })

  it('12. 类型判别：七字段存档不被判成 ReviewReport，完整报告才判成 ReviewReport', () => {
    expect(isReviewReport(ARCHIVED)).toBe(false)
    expect(isArchivedReview(ARCHIVED)).toBe(true)
    expect(isReviewPending(ARCHIVED)).toBe(false)

    expect(isReviewReport(REPORT)).toBe(true)
    expect(isArchivedReview(REPORT)).toBe(false)
  })

  it('13. 本页只读：不调用 createReview / resumeReview', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    await mountView()

    expect(api.createReview).not.toHaveBeenCalled()
    expect(api.resumeReview).not.toHaveBeenCalled()
  })

  it('14. 只有 reviewId 没有 report：兜底取档，渲染维度并标注旧存档未保存审查清单', async () => {
    writeFlow({ reviewId: 'review-1', sections: SECTIONS, report: null })
    const wrapper = await mountView()

    expect(api.getReview).toHaveBeenCalledWith('review-1')
    expect(wrapper.findAll('[data-testid="dimension-card"]')).toHaveLength(DIMENSIONS.length)
    expect(wrapper.text()).toContain('该记录为旧数据，未保存审查清单')
    expect(wrapper.find('[data-testid="score"]').exists()).toBe(false)
  })

  it('15. 兜底取档拿到的是未确认快照：保持空态', async () => {
    vi.mocked(api.getReview).mockResolvedValue({
      review_id: 'review-1',
      status: '待确认',
      sections: SECTIONS,
      confirmed: false,
    })
    writeFlow({ reviewId: 'review-1', sections: SECTIONS, report: null })
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="scoring-empty"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="dimension-card"]')).toHaveLength(0)
  })

  it('16. 读取到量规时显示维度中文名、权重和四档说明', async () => {
    vi.mocked(api.getContestRubric).mockResolvedValue(RUBRIC)
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    expect(api.getContestRubric).toHaveBeenCalledWith('contest-demo-a')
    expect(wrapper.text()).toContain('假设合理性')
    expect(wrapper.text()).toContain('权重 20')
    expect(wrapper.text()).toContain('充分 · 4 · 依据完整')
    expect(wrapper.text()).toContain('证据不足 · 没有可核对证据')
  })

  it('17. 量规接口不可用时保留诚实占位；旧存档显示清单缺失说明', async () => {
    writeFlow({ reviewId: 'review-1', sections: SECTIONS, report: null })
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('当前接口未给出')
    expect(wrapper.text()).toContain('该记录为旧数据，未保存审查清单')
  })

  it('18. 历史存档有审查清单时展示条目与上游编号', async () => {
    vi.mocked(api.getReview).mockResolvedValue({
      ...ARCHIVED,
      change_list: [{ section: '证据不足', kind: '证据不足', upstream_id: 'dimension:assumption', evidence: [], action: '补充论证材料' }],
      change_list_note: null,
    })
    writeFlow({ reviewId: 'review-1', sections: SECTIONS, report: null })
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('补充论证材料')
    expect(wrapper.text()).toContain('dimension:assumption')
  })
})
