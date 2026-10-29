import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PostLoginIntro from '../../src/components/PostLoginIntro.vue'

describe('登录后开场', () => {
  it('展示有明确名称的全屏进入按钮和校样动画', () => {
    const wrapper = mount(PostLoginIntro)
    const button = wrapper.get('.post-login-intro')

    expect(button.attributes('aria-label')).toContain('进入工作台')
    expect(wrapper.text()).toContain('点击任意位置')
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('点击屏幕只发出一次进入事件', async () => {
    const wrapper = mount(PostLoginIntro)
    const button = wrapper.get('.post-login-intro')

    await button.trigger('click')
    await button.trigger('click')

    expect(wrapper.emitted('continue')).toHaveLength(1)
  })

  it.each(['Enter', ' ', 'Escape'])('按 %s 可进入工作台', async (key) => {
    const wrapper = mount(PostLoginIntro)
    await wrapper.get('.post-login-intro').trigger('keydown', { key })
    expect(wrapper.emitted('continue')).toHaveLength(1)
  })
})
