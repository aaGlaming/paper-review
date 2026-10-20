import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '../../src/App.vue'
import { AUTH_TOKEN_KEY, resetAuthStateForTest, useAuth } from '../../src/composables/useAuth'
import { createAppRouter } from '../../src/router'

describe('应用外壳', () => {
  it('挂载后渲染出导航，且导航里有五个页面入口', async () => {
    resetAuthStateForTest()
    localStorage.clear()
    localStorage.setItem(AUTH_TOKEN_KEY, 'shell-token')
    const stubFetch = async (input: RequestInfo | URL) => {
      if (String(input).includes('/api/auth/me')) {
        return new Response(
          JSON.stringify({
            user_id: 'u-shell',
            username: 'shell_student',
            role: 'student',
            permissions: [],
          }),
          { status: 200 },
        )
      }
      if (String(input).includes('/api/auth/logout')) {
        return new Response(null, { status: 204 })
      }
      // 解析页取数：给带字段的空结果，保持 contests 为数组，不触发降级外的异常
      return new Response(JSON.stringify({ contests: [], samples: [] }), { status: 200 })
    }
    vi.stubGlobal('fetch', stubFetch)
    // restore 经守卫拉 me：只 stub fetch，不打后端
    await useAuth().restore()

    const router = createAppRouter(createMemoryHistory())
    await router.push('/parse')
    await router.isReady()

    try {
      const wrapper = mount(App, { global: { plugins: [router] } })
      await wrapper.vm.$nextTick()

      const links = wrapper.findAll('[data-nav-item]:not([data-nav-pending])')
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

      // 登录态下用户区显示用户名与角色标签；退出后 token 被清空。
      expect(wrapper.find('[data-nav-user]').exists()).toBe(true)
      expect(wrapper.get('[data-nav-user]').text()).toContain('shell_student')
      expect(wrapper.get('[data-nav-role]').text()).toBe('学生')
      await wrapper.get('[data-nav-logout]').trigger('click')
      await flushPromises()
      expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    } finally {
      vi.unstubAllGlobals()
      resetAuthStateForTest()
      localStorage.clear()
    }
  })
})
