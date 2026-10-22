import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ContestSummary, ReviewListItem, ReviewListResponse } from '../../src/api/types'
import RecordsView from '../../src/views/记录总览.vue'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, listContests: vi.fn(), listReviews: vi.fn() }
})

const CONTESTS: ContestSummary[] = [
  {
    contest_id: 'contest-a', year: 2026, problem_code: 'A1', title: '练习题', statement: '',
    status: 'published', rubric: null, constraints: [], pitfall_count: 0, exemplar_count: 0,
  },
  {
    contest_id: 'contest-b', year: 2025, problem_code: 'B2', title: '另一题', statement: '',
    status: 'published', rubric: null, constraints: [], pitfall_count: 0, exemplar_count: 0,
  },
]

const ROWS: ReviewListItem[] = [
  {
    review_id: 'review-a', contest_id: 'contest-a', rubric_id: 'rubric-a', rubric_version: 2,
    model_name: 'model-a', created_at: '2026-10-20T10:00:00', user_id: 'student-a',
    owner_username: 'student-name', bands: { assumption: '基本', evidence: '充分' }, finding_total: 3,
  },
  {
    review_id: 'review-b', contest_id: 'contest-b', rubric_id: 'rubric-b', rubric_version: 1,
    model_name: 'model-b', created_at: '2026-10-19T10:00:00', user_id: null,
    owner_username: null, bands: {}, finding_total: 0,
  },
]

function result(scope: ReviewListResponse['scope'] = 'all', rows = ROWS): ReviewListResponse {
  return { reviews: rows, total: rows.length, page: 1, page_size: 20, scope }
}

async function mountPage() {
  const wrapper = mount(RecordsView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.listContests).mockResolvedValue({ contests: CONTESTS })
  vi.mocked(api.listReviews).mockResolvedValue(result())
})

describe('记录总览页', () => {
  it('渲染七列与返回的行数', async () => {
    const wrapper = await mountPage()
    const headers = wrapper.findAll('th').map((item) => item.text().trim())
    expect(headers).toEqual(['提交时间', '学生', '赛题', '量规版本', '模型', '档位概览', '冲突数'])
    expect(wrapper.findAll('tbody tr.el-table__row')).toHaveLength(2)
    expect(wrapper.text()).toContain('assumption 基本')
    expect(wrapper.text()).toContain('无主')
    expect(wrapper.find('tbody tr[data-row-id="review-a"]').exists()).toBe(true)
  })

  it('范围只由响应 scope 决定：own 隐藏学生列，all 显示', async () => {
    vi.mocked(api.listReviews).mockResolvedValueOnce(result('own'))
    const own = await mountPage()
    expect(own.findAll('th').map((item) => item.text().trim())).not.toContain('学生')
    own.unmount()

    vi.mocked(api.listReviews).mockResolvedValueOnce(result('all'))
    const all = await mountPage()
    expect(all.findAll('th').map((item) => item.text().trim())).toContain('学生')
    expect(all.text()).toContain('全部学生')
  })

  it('切换赛题后带 contest_id 重取当前筛选', async () => {
    const wrapper = await mountPage()
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('change', 'contest-b')
    await flushPromises()
    expect(api.listReviews).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.listReviews).mock.calls[1]?.[0]).toMatchObject({ contestId: 'contest-b' })
  })

  it('筛选重取期间保留已有行并显示真实请求状态', async () => {
    const wrapper = await mountPage()
    let resolve!: (value: ReviewListResponse) => void
    vi.mocked(api.listReviews).mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('change', 'contest-b')
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('tbody tr.el-table__row')).toHaveLength(2)
    expect(wrapper.get('[data-testid="request-activity"]').text()).toContain('正在更新评审记录')

    resolve(result('all', [ROWS[1]!]))
    await flushPromises()
    expect(wrapper.findAll('tbody tr.el-table__row')).toHaveLength(1)
    expect(wrapper.find('[data-testid="request-activity"]').exists()).toBe(false)
  })

  it('开关启用 owner=owned，关闭后不传 owner', async () => {
    const wrapper = await mountPage()
    const toggle = wrapper.findComponent({ name: 'ElSwitch' })
    toggle.vm.$emit('update:modelValue', true)
    toggle.vm.$emit('change', true)
    await flushPromises()
    expect(vi.mocked(api.listReviews).mock.calls[1]?.[0]).toMatchObject({ owner: 'owned' })

    toggle.vm.$emit('update:modelValue', false)
    toggle.vm.$emit('change', false)
    await flushPromises()
    expect(vi.mocked(api.listReviews).mock.calls[2]?.[0]).not.toHaveProperty('owner')
  })

  it('total 为零时显示空态且不渲染表格', async () => {
    vi.mocked(api.listReviews).mockResolvedValueOnce(result('all', []))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('还没有评审记录')
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(false)
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
  })

  it('ApiError 显示 message，标题与筛选仍保留', async () => {
    vi.mocked(api.listReviews).mockRejectedValueOnce(new api.ApiError(503, '列表暂不可用'))
    const wrapper = await mountPage()
    expect(wrapper.get('h1').text()).toBe('记录总览')
    expect(wrapper.text()).toContain('列表暂不可用')
    expect(wrapper.find('.records-filters').exists()).toBe(true)
  })
})
