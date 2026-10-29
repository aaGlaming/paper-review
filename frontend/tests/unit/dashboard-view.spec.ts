import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import { echarts } from '../../src/lib/echarts'
import DashboardView from '../../src/views/数据大屏.vue'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, getDashboardSummary: vi.fn(), getDashboardTrend: vi.fn() }
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(echarts, 'init').mockReturnValue({
    setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(),
  } as never)
  vi.mocked(api.getDashboardSummary).mockResolvedValue({
    cached: false,
    cards: { total_submissions: 0, weekly_new: 0, parse_only: 2, pending_conflicts: 0, gold_agreement: null },
    contests: [], bands: [], insufficient_top: [], conflicts: [], hotspots: [],
    citation: { failure_count: 0, total_dimensions: 0, citation_rate: 0 }, gold: null,
  })
  vi.mocked(api.getDashboardTrend).mockResolvedValue({
    cached: false, days: 30, series: [],
  })
})

describe('数据大屏', () => {
  it('两接口并行取数，空数据提示暂无数据且不创建图表容器', async () => {
    const wrapper = mount(DashboardView)
    await flushPromises()
    expect(api.getDashboardSummary).toHaveBeenCalledOnce()
    expect(api.getDashboardTrend).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('暂无数据')
    expect(wrapper.get('[data-testid="parse-only-count"]').text()).toBe('另有 2 篇仅解析未评分')
    expect(wrapper.findAll('[data-chart]')).toHaveLength(0)
    expect(echarts.init).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('路由销毁时 dispose 所有 ECharts 实例', async () => {
    const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    vi.mocked(echarts.init).mockReturnValue(chart as never)
    vi.mocked(api.getDashboardSummary).mockResolvedValue({
      cached: false,
      cards: { total_submissions: 1, weekly_new: 1, parse_only: 0, pending_conflicts: 1, gold_agreement: null },
      contests: [{ contest_id: 'c1', review_count: 1 }],
      bands: [{ dimension_code: 'd1', counts: { '充分': 1, '基本': 0, '不足': 0, '证据不足': 0 }, insufficient_total: 0 }],
      insufficient_top: [{ dimension_code: 'd1', counts: { '充分': 1, '基本': 0, '不足': 0, '证据不足': 0 }, insufficient_total: 0 }],
      conflicts: [{ kind: '数字冲突', count: 1 }], hotspots: [{ target: '关键参数', count: 1 }],
      citation: { failure_count: 0, total_dimensions: 1, citation_rate: 0 }, gold: null,
    })
    vi.mocked(api.getDashboardTrend).mockResolvedValue({
      cached: false, days: 30, series: [{ date: '2026-10-20', total: 1, ownerless: 0 }],
    })
    const wrapper = mount(DashboardView)
    await flushPromises()
    expect(echarts.init).toHaveBeenCalled()
    wrapper.unmount()
    expect(chart.dispose).toHaveBeenCalledTimes(vi.mocked(echarts.init).mock.calls.length)
  })

  it('图表动画服从系统减少动态效果偏好', async () => {
    const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    vi.mocked(echarts.init).mockReturnValue(chart as never)
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('prefers-reduced-motion'), media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }))
    vi.mocked(api.getDashboardSummary).mockResolvedValue({
      cached: false,
      cards: { total_submissions: 1, weekly_new: 1, parse_only: 0, pending_conflicts: 1, gold_agreement: null },
      contests: [{ contest_id: 'c1', review_count: 1 }], bands: [], insufficient_top: [], conflicts: [], hotspots: [],
      citation: { failure_count: 0, total_dimensions: 0, citation_rate: 0 }, gold: null,
    })
    const wrapper = mount(DashboardView)
    await flushPromises()
    expect(chart.setOption).toHaveBeenCalledWith(expect.objectContaining({ animation: false, animationDuration: 0, animationDurationUpdate: 0 }))
    wrapper.unmount()
    vi.unstubAllGlobals()
  })
})
