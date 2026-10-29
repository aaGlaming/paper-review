import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'
import type { ReviewArchive } from '../../src/api/types'
import RecordDrawer from '../../src/components/records/RecordDrawer.vue'

vi.mock('../../src/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api')>()
  return { ...actual, getReview: vi.fn(), getReviewArtifacts: vi.fn().mockResolvedValue([]) }
})

const REVIEW: ReviewArchive = {
  review_id: 'review-1',
  contest_id: 'contest-a',
  rubric_id: 'rubric-a',
  rubric_version: 1,
  model_name: 'model-a',
  created_at: '2026-10-20T10:00:00',
  dimensions: [
    { dimension_code: 'assumption', band: '基本', quote: '命中原句', chunk_ids: [], status: '基本' },
    { dimension_code: 'evidence', band: '充分', quote: '找不到的原句', chunk_ids: [], status: '充分' },
  ],
  change_list: [],
  change_list_note: null,
  sections: [{ title: '正文', section_type: 'body', level: 1, content: `正文开头${'前文'.repeat(35)}命中原句${'后文'.repeat(35)}正文结尾` }],
}

function mountDrawer(record: ReviewArchive = REVIEW, failure?: Error) {
  if (failure) vi.mocked(api.getReview).mockRejectedValue(failure)
  else vi.mocked(api.getReview).mockResolvedValue(record)
  return mount(RecordDrawer, {
    props: { reviewId: 'review-1' },
    global: {
      plugins: [ElementPlus],
      stubs: {
        ElDrawer: {
          props: ['modelValue', 'title', 'size', 'direction', 'destroyOnClose'],
          emits: ['update:modelValue'],
          template: '<section v-if="modelValue" class="el-drawer"><button class="test-close" @click="$emit(\'update:modelValue\', false)"></button><slot /></section>',
        },
      },
    },
  })
}

beforeEach(() => vi.clearAllMocks())

describe('记录详情抽屉', () => {
  it('显示原样维度码，并为正文命中显示前后上下文和高亮', async () => {
    const wrapper = mountDrawer()
    await flushPromises()

    expect(wrapper.text()).toContain('assumption')
    expect(wrapper.findAll('mark').some((mark) => mark.text() === '命中原句')).toBe(true)
    expect(wrapper.text()).toContain('前文')
    expect(wrapper.text()).toContain('后文')

    await wrapper.find('[data-dimension="assumption"] [data-testid="locate-quote"]').trigger('click')
    expect(wrapper.find('[data-quote-code="assumption"]').classes()).toContain('record-drawer__quote--active')
  })

  it('没有正文快照时保留引用并说明无法定位', async () => {
    const wrapper = mountDrawer({ ...REVIEW, sections: [] })
    await flushPromises()

    expect(wrapper.text()).toContain('找不到的原句')
    expect(wrapper.text()).toContain('该记录没有正文快照，无法在正文中定位')
    expect(wrapper.find('mark').exists()).toBe(false)
  })

  it('正文无法精确匹配时展示原句与 approximateNote', async () => {
    const review: ReviewArchive = {
      ...REVIEW,
      dimensions: [
        { dimension_code: 'assumption', band: '基本', quote: '不在正文里的引用', chunk_ids: [], status: '基本' },
      ],
    }
    const wrapper = mountDrawer(review)
    await flushPromises()

    expect(wrapper.text()).toContain('不在正文里的引用')
    expect(wrapper.text()).toContain('按偏移定位，未精确匹配')
  })

  it('按条目 kind 分组并区分复用建议组件与审查组件', async () => {
    const review: ReviewArchive = {
      ...REVIEW,
      change_list: [
        { section: '维度', kind: '维度建议', upstream_id: 'd1', dimension_code: 'assumption', evidence: [], action: '修改维度项' },
        { section: '审查', kind: '数字冲突', upstream_id: 'f1', finding_kind: '冲突', evidence: [], action: '复核数字' },
      ],
    }
    const wrapper = mountDrawer(review)
    await flushPromises()

    expect(wrapper.text()).toContain('维度建议（1）')
    expect(wrapper.text()).toContain('审查 findings（1）')
    expect(wrapper.findAll('[data-testid="suggestion-item"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="conflict-item"]')).toHaveLength(1)
  })

  it('ApiError 留在抽屉显示 message', async () => {
    const wrapper = mountDrawer(REVIEW, new api.ApiError(503, '详情暂不可用'))
    await flushPromises()
    expect(wrapper.text()).toContain('详情暂不可用')
  })

  it('用户关闭抽屉时向父级发送 close', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    await wrapper.find('.test-close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
