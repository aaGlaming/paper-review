// 修改建议页（P8 阶段 5/6）。桩掉 api，用 sessionStorage 里的共享状态构造场景。
// 数据源是 report.change_list 的**全部**条目，按三段分组（题目约束与数字冲突 → 证据不足 → 表述），前端不重排。

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ChangeListItem, PaperSection, ReviewReport } from '../../src/api/types'
import { REVIEW_FLOW_STORAGE_KEY } from '../../src/composables/useReviewFlow'
import { createAppRouter } from '../../src/router'
import SuggestionView from '../../src/views/修改建议.vue'
import { CONTEST_ID_TOKEN } from './forbidden-words'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, getReview: vi.fn(), createReview: vi.fn(), resumeReview: vi.fn() }
})

const SECTIONS: PaperSection[] = [
  { title: '摘要', section_type: '未分类', level: 1, content: '摘要里写盘入终止时刻为 412 s。' },
  { title: '四、结果分析', section_type: '结果', level: 2, content: '结果表里写盘入终止时刻为 386 s。' },
]

// 审查类（数字冲突）：带 finding_kind，evidence 有字符偏移，可点击定位。
const NUMBER_CONFLICT: ChangeListItem = {
  section: '题目约束与数字冲突',
  kind: '数字冲突',
  finding_kind: '数字冲突',
  upstream_id: 'finding:数字冲突:盘入终止时刻',
  target: '盘入终止时刻',
  evidence: [
    { char_start: 0, char_end: 5, text: '412 s' },
    { char_start: 999, char_end: 1004, text: '386 s' },
  ],
  action: '把两处数值改成同一口径，并在正文说明取值来源',
}

// 审查类（越界）：kind 是「题目约束」，徽标要显示 finding_kind 的「越界」。
const OUT_OF_RANGE: ChangeListItem = {
  section: '题目约束与数字冲突',
  kind: '题目约束',
  finding_kind: '越界',
  upstream_id: 'finding:越界:速度范围',
  target: '无人机速度',
  evidence: [{ char_start: 0, char_end: 7, text: '160 m/s' }],
  action: '把速度改到约束范围内',
}

// 维度类（证据不足）：带 dimension_code、无 finding_kind，evidence 无字符偏移。
const INSUFFICIENT: ChangeListItem = {
  section: '证据不足',
  kind: '证据不足',
  dimension_code: 'constraint_check',
  upstream_id: 'dimension:constraint_check',
  target: '检验与题目约束',
  evidence: [{ text: '| 指标 | 数值 |', band: '证据不足', status: '证据不足', chunk_ids: [] }],
  action: '补充调头圆弧两段相切且半径 2 倍的讨论',
}

// 维度类（表述）。
const PRESENTATION: ChangeListItem = {
  section: '表述',
  kind: '表述',
  dimension_code: 'presentation',
  upstream_id: 'dimension:presentation',
  target: '表述与结构',
  evidence: [{ text: '| 指标 | 数值 |', band: '基本', status: '基本', chunk_ids: [] }],
  action: '按问题顺序重排结果，补齐单位与图表编号',
}

const REPORT: ReviewReport = {
  review_id: 'review-1',
  status: '完成',
  contest_id: 'contest-demo-a',
  rubric_id: 'contest-demo-a-v1',
  rubric_version: 1,
  model_name: 'deterministic',
  source: 'deterministic',
  dimensions: [],
  score: { total: 0, weighted: 0, excluded: [], weight_sum: 0 },
  change_list: [NUMBER_CONFLICT, INSUFFICIENT, PRESENTATION],
  note: '各维结果来自确定性结构回退',
}

const SECTION_ORDER = ['题目约束与数字冲突', '证据不足', '表述']

function makeReport(overrides: Partial<ReviewReport>): ReviewReport {
  return { ...REPORT, ...overrides }
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
  const wrapper = mount(SuggestionView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('修改建议页', () => {
  it('1. 无 report：渲染空态，文本不含建议字样，suggestion-item 数量为 0', async () => {
    writeFlow({})
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="suggestions-empty"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="suggestion-item"]')).toHaveLength(0)
    for (const word of ['数字冲突', '证据不足', '表述', '先改', '再补', '最后改']) {
      expect(wrapper.text(), word).not.toContain(word)
    }
  })

  it('2. 含审查类 + 证据不足 + 表述三类：渲染三段 section 标题，顺序固定', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const sections = wrapper.findAll('[data-testid="suggestion-section"]')
    expect(sections).toHaveLength(3)
    expect(sections.map((s) => s.attributes('data-section'))).toEqual(SECTION_ORDER)
    // 段标题取 section 值原样（等宽编号是旁注，另在 .suggestions__section-name 里）
    expect(sections.map((s) => s.get('.suggestions__section-name').text())).toEqual(SECTION_ORDER)
  })

  it('3. 三段齐全时条目总数 = change_list.length，无增无减、顺序一致', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    expect(wrapper.findAll('[data-testid="suggestion-item"]')).toHaveLength(REPORT.change_list.length)
    const upstreams = wrapper.findAll('[data-testid="upstream-id"]').map((el) => el.text())
    expect(upstreams).toEqual(REPORT.change_list.map((item) => item.upstream_id))
  })

  it('分组可由用户收起和展开，状态跟随按钮而不改变条目顺序', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()
    const firstSection = wrapper.findAll('[data-testid="suggestion-section"]')[0]!
    const toggle = firstSection.get('button[aria-expanded]')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(firstSection.findAll('[data-testid="suggestion-item"]')).toHaveLength(1)

    await toggle.trigger('click')
    expect(firstSection.get('button[aria-expanded]').attributes('aria-expanded')).toBe('false')
    expect(firstSection.findAll('[data-testid="suggestion-item"]')).toHaveLength(0)

    await firstSection.get('button[aria-expanded]').trigger('click')
    expect(firstSection.findAll('[data-testid="suggestion-item"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="upstream-id"]').map((item) => item.text())).toEqual(REPORT.change_list.map((item) => item.upstream_id))
  })

  it('4. 某段为空：仍显示该段标题 + 「本段无建议」，段落框架不消失', async () => {
    writeFlow({ report: makeReport({ change_list: [NUMBER_CONFLICT] }), sections: SECTIONS })
    const wrapper = await mountView()

    const sections = wrapper.findAll('[data-testid="suggestion-section"]')
    expect(sections).toHaveLength(3)
    expect(wrapper.findAll('[data-testid="suggestion-item"]')).toHaveLength(1)

    const insufficient = sections[1]
    expect(insufficient.attributes('data-section')).toBe('证据不足')
    expect(insufficient.text()).toContain('本段无建议')
  })

  it('5. 审查类条目（带 finding_kind）：徽标显示 finding_kind，evidence 显示 text', async () => {
    writeFlow({ report: makeReport({ change_list: [OUT_OF_RANGE] }), sections: SECTIONS })
    const wrapper = await mountView()

    const badge = wrapper.get('[data-testid="suggestion-kind"]')
    expect(badge.text()).toBe('越界')
    expect(badge.text()).not.toBe('题目约束')
    expect(wrapper.text()).toContain('160 m/s')
  })

  it('6. 维度类条目（带 dimension_code、无 finding_kind）：徽标显示 kind，不给定位按钮', async () => {
    writeFlow({ report: makeReport({ change_list: [INSUFFICIENT, PRESENTATION] }), sections: SECTIONS })
    const wrapper = await mountView()

    const badges = wrapper.findAll('[data-testid="suggestion-kind"]').map((b) => b.text())
    expect(badges).toEqual(['证据不足', '表述'])
    expect(wrapper.findAll('[data-testid="evidence-hit"]')).toHaveLength(0)
  })

  it('7. 审查类带 char_start 的 evidence 可点击：调用 scrollIntoView 并标 data-located=true', async () => {
    const scrollSpy = vi.fn()
    ;(Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = scrollSpy

    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.findAll('[data-testid="evidence-hit"]')[0].trigger('click')
    await flushPromises()

    const hits = wrapper.findAll('[data-testid="evidence-hit"]')
    expect(scrollSpy).toHaveBeenCalled()
    expect(hits[0].attributes('data-located')).toBe('true')
  })

  it('8. 每条建议都显示 upstream_id', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const upstreams = wrapper.findAll('[data-testid="upstream-id"]').map((el) => el.text())
    expect(upstreams).toEqual([
      'finding:数字冲突:盘入终止时刻',
      'dimension:constraint_check',
      'dimension:presentation',
    ])
  })

  it('9. 恰好一个 h1，文案「修改建议」；空态 / 有报告两种状态都成立', async () => {
    const empty = await mountView()
    expect(empty.findAll('h1')).toHaveLength(1)
    expect(empty.get('h1').text()).toBe('修改建议')

    writeFlow({ report: REPORT, sections: SECTIONS })
    const withReport = await mountView()
    expect(withReport.findAll('h1')).toHaveLength(1)
    expect(withReport.get('h1').text()).toBe('修改建议')
  })

  it('10. 本页只读共享状态：不调用 resumeReview / createReview / getReview', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    await mountView()

    expect(api.resumeReview).not.toHaveBeenCalled()
    expect(api.createReview).not.toHaveBeenCalled()
    expect(api.getReview).not.toHaveBeenCalled()
  })

  it('11. 源码扫描：修改建议.vue 与新增组件里不出现题号字面量', () => {
    const HERE = path.dirname(fileURLToPath(import.meta.url))
    const files = [
      path.resolve(HERE, '../../src/views/修改建议.vue'),
      path.resolve(HERE, '../../src/components/SuggestionItem.vue'),
    ]
    for (const file of files) {
      const text = readFileSync(file, 'utf8')
      expect(text.includes(CONTEST_ID_TOKEN), `${file} 出现题号字面量`).toBe(false)
    }
  })
})
