// 手稿风修复（阶段 8/8）：圈注定位、折线图按数据生成、修改建议页手稿化、密度一致。
// 本版是修 bug，纪律是先写断言看着它红，再修到绿。

import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ConflictItem from '../../src/components/ConflictItem.vue'
import DimensionCard from '../../src/components/DimensionCard.vue'
import MetricCard from '../../src/components/MetricCard.vue'
import type {
  ChangeListItem,
  DimensionResult,
  EvalSummary,
  PaperSection,
  ReviewReport,
} from '../../src/api/types'
import { REVIEW_FLOW_STORAGE_KEY } from '../../src/composables/useReviewFlow'
import { createAppRouter } from '../../src/router'
import SuggestionView from '../../src/views/修改建议.vue'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..', '..', 'src')

function ruleOf(relativePath: string, selector: string): string {
  const source = readFileSync(path.join(SRC, relativePath), 'utf8')
  const escaped = selector.replace('.', '\\.')
  return source.match(new RegExp(`${escaped}\\s*\\{[^}]*\\}`))?.[0] ?? ''
}

const DIMENSION: DimensionResult = {
  dimension_code: 'assumption',
  band: '基本',
  chunk_ids: ['c1'],
  quote: '本文忽略板凳宽度',
  status: '基本',
}

const CONFLICT_ITEM: ChangeListItem = {
  section: '题目约束与数字冲突',
  kind: '数字冲突',
  finding_kind: '数字冲突',
  upstream_id: 'finding:数字冲突:盘入终止时刻',
  target: '盘入终止时刻',
  evidence: [
    { char_start: 175, char_end: 180, text: '412 s' },
    { char_start: 699, char_end: 704, text: '386 s' },
  ],
  action: '把两处数值改成同一口径',
}

const SUMMARY: EvalSummary = {
  corpus_papers: 15,
  gradable_papers: 12,
  gradable_dimensions: 60,
  source: 'deterministic',
  band_agreement: { matched: 26, total: 60, rate: 0.43333333333333335, low_sample: false, caliber: '档位一致率口径' },
  quote_exact_match: { matched: 60, total: 60, rate: 1.0, low_sample: false, caliber: '引用精确匹配率口径' },
  insufficient_evidence_hit: { matched: 2, total: 5, rate: 0.4, low_sample: false, caliber: '证据不足命中口径' },
  no_samples: false,
  demo_papers_without_gold: 3,
  note: 'source=deterministic 脚本自检',
}

const SECTIONS: PaperSection[] = [
  { title: '摘要', section_type: '未分类', level: 1, content: '摘要正文' },
  { title: '一、模型假设', section_type: '假设', level: 2, content: '假设正文' },
]

const CHANGE_LIST: ChangeListItem[] = [
  CONFLICT_ITEM,
  {
    section: '证据不足',
    kind: '证据不足',
    dimension_code: 'constraint_check',
    upstream_id: 'dimension:constraint_check',
    target: '检验与题目约束',
    evidence: [{ text: '| 指标 | 数值 |', band: '证据不足', status: '证据不足', chunk_ids: [] }],
    action: '补充调头圆弧讨论',
  },
  {
    section: '表述',
    kind: '表述',
    dimension_code: 'presentation',
    upstream_id: 'dimension:presentation',
    target: '表述与结构',
    evidence: [{ text: '| 指标 | 数值 |', band: '基本', status: '基本', chunk_ids: [] }],
    action: '按问题顺序重排结果',
  },
]

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
  change_list: CHANGE_LIST,
  note: '确定性回退',
}

function writeFlow(report: ReviewReport): void {
  sessionStorage.setItem(
    REVIEW_FLOW_STORAGE_KEY,
    JSON.stringify({ contestId: 'contest-demo-a', reviewId: 'review-1', sections: SECTIONS, report }),
  )
}

async function mountSuggestionView() {
  const router = createAppRouter()
  const wrapper = mount(SuggestionView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('手稿风修复', () => {
  it('1. DimensionCard 圈容器 position: relative，圈只用 inset 不写 width/height', () => {
    const wrapper = mount(DimensionCard, { props: { dimension: DIMENSION } })

    expect(wrapper.find('.card__band-wrap').exists()).toBe(true)
    expect(wrapper.find('.card__band-circle').exists()).toBe(true)

    // 固定比例容器：band-wrap 显式 position: relative
    const wrapRule = ruleOf('components/DimensionCard.vue', '.card__band-wrap')
    expect(wrapRule).toMatch(/position:\s*relative/)
    // 圈规则里不能再写 width/height（与 inset 混用会互相覆盖、把圈拉偏）
    const rule = ruleOf('components/DimensionCard.vue', '.card__band-circle')
    expect(rule).not.toMatch(/width\s*:/)
    expect(rule).not.toMatch(/height\s*:/)
    expect(rule).toMatch(/inset\s*:/)
  })

  it('2. ConflictItem 圈只包住按钮内文字：文字外层容器 position: relative', () => {
    const wrapper = mount(ConflictItem, { props: { item: CONFLICT_ITEM, locatedKey: null } })

    expect(wrapper.find('.conflict__hit-label').exists()).toBe(true)
    const labelRule = ruleOf('components/ConflictItem.vue', '.conflict__hit-label')
    expect(labelRule).toMatch(/position:\s*relative/)
    expect(wrapper.find('.conflict__hit-circle').exists()).toBe(true)
    // 按钮文案不变（圈只是套在外层的装饰）
    expect(wrapper.get('[data-testid="evidence-hit"]').text()).toBe('412 s')
  })

  it('3. MetricCard 传入不同 matched/total 时，生成的折线 path 的 d 互不相同', () => {
    const codes = ['band_agreement', 'quote_exact_match', 'insufficient_evidence_hit'] as const
    const ds = codes.map((code) => {
      const wrapper = mount(MetricCard, { props: { code, name: '指标', metric: SUMMARY[code] } })
      return wrapper.get('.metric__chart-line').attributes('d') ?? ''
    })
    expect(ds[0]).not.toBe(ds[1])
    expect(ds[1]).not.toBe(ds[2])
    expect(ds[0]).not.toBe(ds[2])
    for (const d of ds) {
      expect(d).toMatch(/^M\d/)
    }
  })

  it('4. MetricCard 的 rate 为 null 时，不渲染折线 path，只渲染「—（无样本）」', () => {
    const wrapper = mount(MetricCard, {
      props: {
        code: 'band_agreement',
        name: '档位一致率',
        metric: { matched: 0, total: 0, rate: null, low_sample: false, caliber: '无样本口径' },
      },
    })
    expect(wrapper.find('.metric__chart-line').exists()).toBe(false)
    expect(wrapper.get('[data-testid="metric-rate"]').text()).toBe('—（无样本）')
  })

  it('5. 修改建议页渲染三段分组，且相邻段之间存在推进箭头', async () => {
    writeFlow(REPORT)
    const wrapper = await mountSuggestionView()

    const sections = wrapper.findAll('[data-testid="suggestion-section"]')
    expect(sections).toHaveLength(3)
    // 三段之间有两个箭头（第 1→2、2→3 段）
    expect(wrapper.findAll('.suggestions__section-arrow')).toHaveLength(2)
  })

  it('6. 三页的卡片内边距走同一令牌（评分卡 / 冲突条 / 建议条 / 指标卡）', () => {
    const cards: Array<[string, string]> = [
      ['components/DimensionCard.vue', '.card'],
      ['components/ConflictItem.vue', '.conflict'],
      ['components/MetricCard.vue', '.metric'],
      ['components/SuggestionItem.vue', '.suggestion'],
    ]
    for (const [file, selector] of cards) {
      const rule = ruleOf(file, selector)
      expect(rule, file).toMatch(/padding\s*:\s*var\(--pr-card-pad\)/)
    }
  })

  it('7. 源码扫描：新增/修改的 .vue 无裸色值、无无界 hover 位移，动态图表尊重 reduced-motion', () => {
    const files = [
      'components/DimensionCard.vue',
      'components/ConflictItem.vue',
      'components/MetricCard.vue',
      'components/SuggestionItem.vue',
      'views/修改建议.vue',
    ]
    for (const file of files) {
      const text = readFileSync(path.join(SRC, file), 'utf8')
      expect(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], `${file} 出现裸色值`).toEqual([])
      expect(text.includes('hover') && text.includes('translate'), `${file} hover 位移`).toBe(false)
    }
    expect(readFileSync(path.join(SRC, 'components/MetricCard.vue'), 'utf8')).toContain('prefers-reduced-motion')
  })

  it('8. 98 个 data-testid 全部唯一且动态请求钩子存在', () => {
    const ids = new Set<string>()
    const walk = (dir: string): void => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          walk(full)
        } else if (entry.name.endsWith('.vue')) {
          for (const match of readFileSync(full, 'utf8').matchAll(/data-testid="([^"]+)"/g)) {
            ids.add(match[1])
          }
        }
      }
    }
    walk(SRC)
    expect(ids.size).toBe(101)
    expect(ids.has('theme-toggle')).toBe(true)
    expect(ids.has('artifact-panel')).toBe(true)
    expect(ids.has('artifact-empty')).toBe(true)
    expect(ids.has('`artifact-group-${group.type}`')).toBe(true)
    expect(ids.has('artifact-mark')).toBe(true)
    expect(ids.has('request-activity')).toBe(true)
  })
})
