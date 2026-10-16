import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import App from '../../src/App.vue'
import { createAppRouter } from '../../src/router'

describe('应用外壳', () => {
  it('挂载后渲染出导航，且导航里有五个页面入口', async () => {
    const router = createAppRouter()
    await router.push('/parse')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    const links = wrapper.findAll('[data-nav-item]')
    expect(links).toHaveLength(5)
    expect(links.map((link) => link.text())).toEqual([
      '论文解析',
      '分项评分',
      '一致性审查',
      '修改建议',
      '评测对照',
    ])

    // 导航之外要有内容区，路由出口渲染出当前页面标题。
    // 注意：解析页此时会真的去取数，而 jsdom 里没有后端 —— 它必须捕获失败并降级显示，
    // 所以下面这两条断言在任何取数结果下都成立。
    expect(wrapper.find('main').exists()).toBe(true)
    expect(wrapper.get('main').text()).toContain('论文解析')
    expect(wrapper.get('main').findAll('h1')).toHaveLength(1)
  })
})
