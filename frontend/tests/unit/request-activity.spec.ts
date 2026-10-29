import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RequestActivity from '../../src/components/RequestActivity.vue'

describe('RequestActivity', () => {
  it('只在真实请求进行时显示活动提示', () => {
    const wrapper = mount(RequestActivity, { props: { active: true, label: '正在分析记录' } })
    expect(wrapper.get('[data-testid="request-activity"]').attributes('role')).toBe('status')
    expect(wrapper.text()).toContain('正在分析记录')
    wrapper.unmount()

    const inactive = mount(RequestActivity, { props: { active: false, label: '正在分析记录' } })
    expect(inactive.find('[data-testid="request-activity"]').exists()).toBe(false)
  })
})
