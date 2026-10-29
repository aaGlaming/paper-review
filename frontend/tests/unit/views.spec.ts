import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import ConsistencyView from '../../src/views/一致性审查.vue'
import EvalCompareView from '../../src/views/评测对照.vue'
import ParseView from '../../src/views/论文解析.vue'
import ScoringView from '../../src/views/分项评分.vue'
import SuggestionView from '../../src/views/修改建议.vue'
import { createAppRouter } from '../../src/router'

// 五个页面（解析 / 评分 / 一致性审查 / 修改建议 / 评测对照）都已是真页面，不再有占位页。
// 原 PLACEHOLDERS 名单已清空：不留空数组让循环断言变成无意义通过。

describe('页面组件', () => {
  it('论文解析页能挂载，且恰好一个 h1 文案为论文解析', async () => {
    // 这里不桩 api：jsdom 里没有后端，页面的取数会失败。
    // 失败必须被页面捕获并降级显示，h1 无条件渲染——这正是它能在这条用例里站住的原因。
    const router = createAppRouter()
    const wrapper = mount(ParseView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('论文解析')
  })

  it('分项评分页能挂载（空态），且恰好一个 h1 文案为分项评分', async () => {
    // 共享状态为空 → 空态。这里的 sessionStorage 是干净的，不会触发兜底取档。
    const router = createAppRouter()
    const wrapper = mount(ScoringView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('分项评分')
  })

  it('一致性审查页能挂载（空态），且恰好一个 h1 文案为一致性审查', async () => {
    // 本页只读共享状态：空态下不兜底取档，h1 无条件渲染。
    const router = createAppRouter()
    const wrapper = mount(ConsistencyView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('一致性审查')
  })

  it('修改建议页能挂载（空态），且恰好一个 h1 文案为修改建议', async () => {
    // 本页只读共享状态：空态下不兜底取档，h1 无条件渲染。
    const router = createAppRouter()
    const wrapper = mount(SuggestionView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('修改建议')
  })

  it('评测对照页能挂载（取数失败降级），且恰好一个 h1 文案为评测对照', async () => {
    // 这里不桩 api：jsdom 里没有后端，getEvalSummary 会失败。
    // 页面必须捕获并降级显示错误态，h1 无条件渲染。
    const router = createAppRouter(createMemoryHistory())
    await router.push('/eval')
    await router.isReady()
    const wrapper = mount(EvalCompareView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('h1').text()).toBe('评测对照')
  })
})
