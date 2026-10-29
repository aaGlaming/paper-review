// 评测对照页（P8 阶段 6/6）。桩掉 api，数据源只有 getEvalSummary()（可选 listSamples()）。
// 单篇路由 /eval/:paperId 只渲染缺口说明，不臆造 gold。

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import * as api from '../../src/api'
import type { EvalSummary, SampleItem } from '../../src/api/types'
import { AUTH_TOKEN_KEY, resetAuthStateForTest } from '../../src/composables/useAuth'
import { createAppRouter } from '../../src/router'
import EvalView from '../../src/views/评测对照.vue'
import { AWARD_WORDS, CONTEST_ID_TOKEN } from './forbidden-words'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return {
    ...actual,
    getEvalSummary: vi.fn(),
    getEvalPaper: vi.fn(),
    listSamples: vi.fn(),
    getReview: vi.fn(),
    createReview: vi.fn(),
    resumeReview: vi.fn(),
    authMe: vi.fn(),
  }
})

// 实测响应（v1.8.5 §1.2），字段与后端一字不差。
const SUMMARY: EvalSummary = {
  corpus_papers: 15,
  gradable_papers: 12,
  gradable_dimensions: 60,
  source: 'deterministic',
  band_agreement: {
    matched: 26,
    total: 60,
    rate: 0.43333333333333335,
    low_sample: false,
    caliber: '档位一致率 = 系统档位与 gold 档位一致的维度数 / 有 gold 的维度总数',
  },
  quote_exact_match: {
    matched: 60,
    total: 60,
    rate: 1.0,
    low_sample: false,
    caliber: '引用精确匹配率 = 原句逐字出现在所引父块里的维度数 / 给出原句的维度数',
  },
  insufficient_evidence_hit: {
    matched: 0,
    total: 2,
    rate: 0.0,
    low_sample: true,
    caliber: '证据不足命中情况 = gold 为证据不足且系统也判证据不足的维度数 / gold 为证据不足的维度数',
  },
  no_samples: false,
  demo_papers_without_gold: 3,
  note: '分子分母都按有 gold 的可算样本计算；三篇演示稿没有 gold，不计入分母。source=deterministic 时这些数字是确定性结构回退的脚本自检，不是模型准确率。',
}

// 15 条：3 篇 demo + 12 篇 has_gold。contest_id 用中性值，不写题号字面量。
const SAMPLES: SampleItem[] = [
  { sample_id: 'demo-1', title: '演示稿一', is_demo: true, contest_id: 'contest-a', has_gold: false },
  { sample_id: 'demo-2', title: '演示稿二', is_demo: true, contest_id: 'contest-b', has_gold: false },
  { sample_id: 'demo-3', title: '演示稿三', is_demo: true, contest_id: 'contest-c', has_gold: false },
  ...Array.from({ length: 12 }, (_, i) => ({
    sample_id: `eval-${String(i + 1).padStart(2, '0')}`,
    title: `评测论文 ${i + 1}`,
    is_demo: false,
    contest_id: 'contest-x',
    has_gold: true,
  })),
]

async function mountAt(path: string) {
  // 守卫下 push 受保护路由需先登录（只 mock authMe，不打后端）；页面断言零改动。
  resetAuthStateForTest()
  localStorage.setItem(AUTH_TOKEN_KEY, 'eval-token')
  vi.mocked(api.authMe).mockResolvedValue({
    user_id: 'u1',
    username: 'stu',
    role: 'student',
    permissions: [],
  })
  const { useAuth } = await import('../../src/composables/useAuth')
  await useAuth().restore()
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mount(EvalView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getEvalSummary).mockResolvedValue(SUMMARY)
  vi.mocked(api.listSamples).mockResolvedValue({ samples: SAMPLES })
})

describe('评测对照页', () => {
  it('1. 取数成功：渲染三张指标卡，data-metric 分别为三项', async () => {
    const wrapper = await mountAt('/eval')

    const cards = wrapper.findAll('[data-testid="metric-card"]')
    expect(cards).toHaveLength(3)
    expect(cards.map((card) => card.attributes('data-metric'))).toEqual([
      'band_agreement',
      'quote_exact_match',
      'insufficient_evidence_hit',
    ])
  })

  it('2. 常规指标显示百分比，小样本指标改显示样本量提示', async () => {
    const wrapper = await mountAt('/eval')

    const band = wrapper.get('[data-metric="band_agreement"]')
    expect(band.get('[data-testid="metric-rate"]').text()).toBe('43.3%')
    expect(band.get('[data-testid="metric-fraction"]').text()).toBe('26 / 60')
    expect(band.get('[data-testid="metric-caliber"]').text()).toBe(SUMMARY.band_agreement.caliber)

    const quote = wrapper.get('[data-metric="quote_exact_match"]')
    expect(quote.get('[data-testid="metric-rate"]').text()).toBe('100%')
    expect(quote.get('[data-testid="metric-fraction"]').text()).toBe('60 / 60')

    const insufficient = wrapper.get('[data-metric="insufficient_evidence_hit"]')
    expect(insufficient.get('[data-testid="metric-rate"]').text()).toBe('样本过少')
    expect(insufficient.get('[data-testid="metric-rate"]').text()).not.toContain('%')
    expect(insufficient.get('[data-testid="metric-fraction"]').text()).toBe('0 / 2')
  })

  it('3. rate 为 null（no_samples=true）：显示「—（无样本）」，不显示 NaN 或 0', async () => {
    vi.mocked(api.getEvalSummary).mockResolvedValue({
      ...SUMMARY,
      no_samples: true,
      band_agreement: { matched: 0, total: 0, rate: null, low_sample: false, caliber: '档位一致率口径' },
    })
    const wrapper = await mountAt('/eval')

    const rate = wrapper.get('[data-metric="band_agreement"] [data-testid="metric-rate"]')
    expect(rate.text()).toBe('—（无样本）')
    expect(rate.text()).not.toContain('0')
    expect(wrapper.text()).not.toContain('NaN')
  })

  it('4. source=deterministic：显示 note 原文，且出现「确定性结构回退 / 非模型评测结果」', async () => {
    const wrapper = await mountAt('/eval')

    expect(wrapper.get('[data-testid="eval-note"]').text()).toBe(SUMMARY.note)
    expect(wrapper.get('[data-testid="eval-note"]').text()).toContain('确定性结构回退')
    expect(wrapper.get('[data-testid="deterministic-note"]').text()).toContain('非模型评测结果')
  })

  it('5. 取数失败：降级显示错误态，h1 仍在', async () => {
    vi.mocked(api.getEvalSummary).mockRejectedValue(new Error('网络错误'))
    const wrapper = await mountAt('/eval')

    expect(wrapper.find('[data-testid="eval-error"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="eval-error"]').text()).toContain('评测汇总暂时不可用')
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('评测对照')
  })

  it('6. /eval/:paperId：显示 gold 与系统逐维差异，不渲染汇总指标', async () => {
    vi.mocked(api.getEvalPaper).mockResolvedValue({
      paper_id: 'eval-01', title: '评测论文', source: 'deterministic',
      gold_available: true, explanation: null,
      gold: [{ dimension_code: 'assumption', band: '充分' }],
      system: [{ dimension_code: 'assumption', band: '基本', status: '基本', quote: '原句', chunk_ids: [] }],
      differences: [{ dimension_code: 'assumption', gold_band: '充分', system_band: '基本', matches: false }],
    })
    const wrapper = await mountAt('/eval/eval-01')

    expect(api.getEvalPaper).toHaveBeenCalledWith('eval-01')
    expect(wrapper.text()).toContain('评测论文')
    expect(wrapper.text()).toContain('gold：充分')
    expect(wrapper.text()).toContain('系统：基本')
    expect(wrapper.text()).toContain('不一致')
    expect(wrapper.findAll('[data-testid="metric-card"]')).toHaveLength(0)
    expect(api.getEvalSummary).not.toHaveBeenCalled()
  })

  it('单篇无 gold 时明确说明未提供标准档位', async () => {
    vi.mocked(api.getEvalPaper).mockResolvedValue({
      paper_id: 'demo-paper', title: '演示稿', source: 'deterministic',
      gold_available: false, explanation: '该演示稿没有 gold 档位，无法计算逐维差异。',
      gold: null, system: [], differences: null,
    })
    const wrapper = await mountAt('/eval/demo-paper')
    expect(wrapper.text()).toContain('该演示稿没有 gold 档位')
    expect(wrapper.text()).not.toContain('不一致')
  })

  it('7. listSamples 返回 15 条：渲染 15 行，demo 标「演示稿」、has_gold 标「有 gold」', async () => {
    const wrapper = await mountAt('/eval')

    const rows = wrapper.findAll('[data-testid="sample-row"]')
    expect(rows).toHaveLength(15)
    expect(rows[0]?.text()).toContain('演示稿')
    expect(rows[0]?.text()).not.toContain('有 gold')
    expect(rows[3]?.text()).toContain('有 gold')
    expect(rows[3]?.text()).not.toContain('演示稿')
  })

  it('8. 恰好一个 h1「评测对照」：成功 / 失败 / 单篇三种状态都成立', async () => {
    const success = await mountAt('/eval')
    expect(success.findAll('h1')).toHaveLength(1)
    expect(success.get('h1').text()).toBe('评测对照')

    vi.mocked(api.getEvalSummary).mockRejectedValue(new Error('x'))
    const failed = await mountAt('/eval')
    expect(failed.findAll('h1')).toHaveLength(1)
    expect(failed.get('h1').text()).toBe('评测对照')

    const single = await mountAt('/eval/eval-01')
    expect(single.findAll('h1')).toHaveLength(1)
    expect(single.get('h1').text()).toBe('评测对照')
  })

  it('9. 本页只调 getEvalSummary 与 listSamples，不调 resumeReview / createReview / getReview', async () => {
    await mountAt('/eval')

    expect(api.getEvalSummary).toHaveBeenCalled()
    expect(api.listSamples).toHaveBeenCalled()
    expect(api.resumeReview).not.toHaveBeenCalled()
    expect(api.createReview).not.toHaveBeenCalled()
    expect(api.getReview).not.toHaveBeenCalled()
  })

  it('10. 源码扫描：评测对照.vue 与新增组件不出现题号字面量、不出现奖项字样', () => {
    const HERE = path.dirname(fileURLToPath(import.meta.url))
    const files = [
      path.resolve(HERE, '../../src/views/评测对照.vue'),
      path.resolve(HERE, '../../src/components/MetricCard.vue'),
    ]
    for (const file of files) {
      const text = readFileSync(file, 'utf8')
      expect(text.includes(CONTEST_ID_TOKEN), `${file} 出现题号字面量`).toBe(false)
      for (const word of AWARD_WORDS) {
        expect(text.includes(word), `${file} 出现奖项字样 ${word}`).toBe(false)
      }
    }
  })
})
