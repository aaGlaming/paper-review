import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import AgentTracePanel from '../../src/components/AgentTracePanel.vue'
import { fetchAgentSteps } from '../../src/api'

vi.mock('../../src/api', () => ({ fetchAgentSteps: vi.fn() }))
const mockedFetch = vi.mocked(fetchAgentSteps)

describe('AgentTracePanel', () => {
  it('renders sorted rows and warning style', async () => {
    mockedFetch.mockResolvedValue({ review_id: 'r1', steps: [
      { idx: 2, node: 'tools', action: 'search_evidence', args_digest: 'x', result_note: '错误码', ok: false, error_code: 'not_found', elapsed_ms: 3, created_at: '' },
      { idx: 1, node: 'model', action: 'list_dimensions', args_digest: 'x', result_note: 'ok', ok: true, error_code: null, elapsed_ms: 1, created_at: '' },
    ] })
    const wrapper = mount(AgentTracePanel, { props: { reviewId: 'r1' } })
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('#1')
    expect(wrapper.find('.trace__row--error').exists()).toBe(true)
  })

  it('shows empty and error states distinctly', async () => {
    mockedFetch.mockResolvedValueOnce({ review_id: 'r1', steps: [] })
    const wrapper = mount(AgentTracePanel, { props: { reviewId: 'r1' } })
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('未产生 Agent 轨迹')
    mockedFetch.mockRejectedValueOnce(new Error('接口失败'))
    await wrapper.setProps({ reviewId: 'r2' })
    await flushPromises()
    expect(wrapper.text()).toContain('接口失败')
    expect(wrapper.text()).not.toContain('未产生 Agent 轨迹')
  })

  it('shows no-progress termination reason', async () => {
    mockedFetch.mockResolvedValue({ review_id: 'r1', steps: [{ idx: 1, node: 'tools', action: 'search_evidence', args_digest: 'x', result_note: 'x', ok: true, error_code: null, elapsed_ms: 1, created_at: '' }] })
    const wrapper = mount(AgentTracePanel, { props: { reviewId: 'r1', terminatedBy: 'no_progress' } })
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('连续无新证据')
  })
})
