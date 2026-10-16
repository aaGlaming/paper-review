// 一致性审查页（P8 阶段 4/6）。桩掉 api，用 sessionStorage 里的共享状态构造场景。
// 数据源只有 report.change_list 里 section === '题目约束与数字冲突' 的条目（判定依据是 finding_kind 存在）。

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ChangeListItem, PaperSection, ReviewReport } from '../../src/api/types'
import { REVIEW_FLOW_STORAGE_KEY } from '../../src/composables/useReviewFlow'
import { createAppRouter } from '../../src/router'
import ConsistencyView from '../../src/views/一致性审查.vue'
import { CONTEST_ID_TOKEN } from './forbidden-words'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, getReview: vi.fn(), createReview: vi.fn(), resumeReview: vi.fn() }
})

const SECTIONS: PaperSection[] = [
  { title: '摘要', section_type: '未分类', level: 1, content: '摘要里写盘入终止时刻为 412 s。' },
  { title: '四、结果分析', section_type: '结果', level: 2, content: '结果表里写盘入终止时刻为 386 s。' },
]

// 数字冲突一条有两处取值（412 s / 386 s），各自可点击定位。
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

// kind 是「题目约束」，但徽标要显示 finding_kind 的「越界」。
const OUT_OF_RANGE: ChangeListItem = {
  section: '题目约束与数字冲突',
  kind: '题目约束',
  finding_kind: '越界',
  upstream_id: 'finding:越界:速度范围',
  target: '无人机速度',
  evidence: [{ char_start: 0, char_end: 7, text: '160 m/s' }],
  action: '把速度改到约束范围内',
}

// 未提到条件：evidence 为空数组，没有可定位的偏移。
const NOT_MENTIONED: ChangeListItem = {
  section: '题目约束与数字冲突',
  kind: '题目约束',
  finding_kind: '未提到条件',
  upstream_id: 'finding:未提到条件:某条件',
  target: '某条件',
  evidence: [],
  action: '补上这条条件',
}

// 维度类条目：带 dimension_code、证据无字符偏移，本页跳过。
const DIMENSION_ITEM: ChangeListItem = {
  section: '表述',
  kind: '表述',
  upstream_id: 'dimension:presentation',
  dimension_code: 'presentation',
  target: '表述与结构',
  evidence: [{ text: '| 指标 | 数值 |', band: '基本', status: '基本', chunk_ids: [] }],
  action: '按问题顺序重排结果',
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
  change_list: [NUMBER_CONFLICT, OUT_OF_RANGE, NOT_MENTIONED, DIMENSION_ITEM],
  note: '各维结果来自确定性结构回退',
}

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
  const wrapper = mount(ConsistencyView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('一致性审查页', () => {
  it('1. 无 report：渲染空态，文本不含审查字样，conflict-item 数量为 0', async () => {
    writeFlow({})
    const wrapper = await mountView()

    expect(wrapper.find('[data-testid="consistency-empty"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="conflict-item"]')).toHaveLength(0)
    for (const word of ['数字冲突', '越界', '未提到', '引用缺失']) {
      expect(wrapper.text(), word).not.toContain(word)
    }
  })

  it('2. 2 条审查类 + 1 条维度类：冲突列表恰好渲染 2 条（维度类被跳过）', async () => {
    const report = makeReport({ change_list: [NUMBER_CONFLICT, OUT_OF_RANGE, DIMENSION_ITEM] })
    writeFlow({ report, sections: SECTIONS })
    const wrapper = await mountView()

    expect(wrapper.findAll('[data-testid="conflict-item"]')).toHaveLength(2)
  })

  it('3. 数字冲突条目有两条 evidence：渲染出两个 evidence-hit，各自显示 text', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    const first = wrapper.findAll('[data-testid="conflict-item"]')[0]
    const hits = first.findAll('[data-testid="evidence-hit"]')
    expect(hits).toHaveLength(2)
    expect(hits.map((hit) => hit.text())).toEqual(['412 s', '386 s'])
  })

  it('4. 点击 evidence-hit：调用 scrollIntoView，并把该 evidence 标 data-located=true', async () => {
    const scrollSpy = vi.fn()
    ;(Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = scrollSpy

    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.findAll('[data-testid="evidence-hit"]')[0].trigger('click')
    await flushPromises()

    const hits = wrapper.findAll('[data-testid="evidence-hit"]')
    expect(scrollSpy).toHaveBeenCalled()
    expect(hits[0].attributes('data-located')).toBe('true')
    expect(hits[1].attributes('data-located')).toBeUndefined()
  })

  it('5. evidence.text 能在拼接正文里精确找到：mark 命中 text 原文（走 indexOf，不落 char_start）', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.findAll('[data-testid="evidence-hit"]')[0].trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="located-mark"]').text()).toBe('412 s')
  })

  it('6. evidence.text 找不到：落到 char_start 大致位置并标注「按偏移定位，未精确匹配」，仍调用 scrollIntoView', async () => {
    const scrollSpy = vi.fn()
    ;(Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = scrollSpy

    const ghost: ChangeListItem = {
      section: '题目约束与数字冲突',
      kind: '数字冲突',
      finding_kind: '数字冲突',
      upstream_id: 'finding:数字冲突:不存在',
      target: '不存在',
      evidence: [{ char_start: 3, char_end: 8, text: '999 s' }],
      action: '改',
    }
    writeFlow({ report: makeReport({ change_list: [ghost] }), sections: SECTIONS })
    const wrapper = await mountView()

    await wrapper.get('[data-testid="evidence-hit"]').trigger('click')
    await flushPromises()

    expect(scrollSpy).toHaveBeenCalled()
    expect(wrapper.text()).toContain('按偏移定位，未精确匹配')
  })

  it('7. evidence 为空数组：只显示 target 与 action，没有 evidence-hit', async () => {
    writeFlow({ report: makeReport({ change_list: [NOT_MENTIONED] }), sections: SECTIONS })
    const wrapper = await mountView()

    const item = wrapper.get('[data-testid="conflict-item"]')
    expect(item.text()).toContain('某条件')
    expect(item.text()).toContain('补上这条条件')
    expect(item.find('[data-testid="evidence-hit"]').exists()).toBe(false)
  })

  it('8. kind=题目约束 且 finding_kind=越界：徽标显示「越界」，不是「题目约束」', async () => {
    writeFlow({ report: makeReport({ change_list: [OUT_OF_RANGE] }), sections: SECTIONS })
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="conflict-kind"]').text()).toBe('越界')
    expect(wrapper.get('[data-testid="conflict-kind"]').text()).not.toBe('题目约束')
  })

  it('9. 恰好一个 h1，文案「一致性审查」；空态 / 有报告两种状态都成立', async () => {
    const empty = await mountView()
    expect(empty.findAll('h1')).toHaveLength(1)
    expect(empty.get('h1').text()).toBe('一致性审查')

    writeFlow({ report: REPORT, sections: SECTIONS })
    const withReport = await mountView()
    expect(withReport.findAll('h1')).toHaveLength(1)
    expect(withReport.get('h1').text()).toBe('一致性审查')
  })

  it('10. 本页只读共享状态：不调用 resumeReview / createReview / getReview', async () => {
    writeFlow({ report: REPORT, sections: SECTIONS })
    await mountView()

    expect(api.resumeReview).not.toHaveBeenCalled()
    expect(api.createReview).not.toHaveBeenCalled()
    expect(api.getReview).not.toHaveBeenCalled()
  })

  it('11. 源码扫描：一致性审查.vue 与新增组件/模块里不出现题号字面量', () => {
    const HERE = path.dirname(fileURLToPath(import.meta.url))
    const files = [
      path.resolve(HERE, '../../src/views/一致性审查.vue'),
      path.resolve(HERE, '../../src/components/ConflictItem.vue'),
      path.resolve(HERE, '../../src/composables/useOffsetLocator.ts'),
    ]
    for (const file of files) {
      const text = readFileSync(file, 'utf8')
      expect(text.includes(CONTEST_ID_TOKEN), `${file} 出现题号字面量`).toBe(false)
    }
  })
})
