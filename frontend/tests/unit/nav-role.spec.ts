import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import AppNav from '../../src/components/AppNav.vue'
import { AUTH_TOKEN_KEY, resetAuthStateForTest } from '../../src/composables/useAuth'
import { createAppRouter } from '../../src/router'

function loginAs(role: 'student' | 'teacher', username: string): void {
  resetAuthStateForTest()
  localStorage.clear()
  localStorage.setItem(AUTH_TOKEN_KEY, `token-${role}`)
  vi.stubGlobal(
    'fetch',
    async () =>
      new Response(
        JSON.stringify({
          user_id: 'u1', username, role,
          permissions: role === 'teacher' ? ['review:read:all', 'chat:use', 'dashboard:view'] : [],
        }),
        { status: 200 },
      ),
  )
}

beforeEach(() => {
  resetAuthStateForTest()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('导航角色菜单', () => {
  it('学生看不到记录总览或 AI 问询，也看不到任何 pending 项', async () => {
    loginAs('student', 'stu001')
    const { useAuth } = await import('../../src/composables/useAuth')
    await useAuth().restore()

    const router = createAppRouter(createMemoryHistory())
    await router.push('/parse')
    await router.isReady()
    const wrapper = mount(AppNav, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[data-nav-pending]')).toHaveLength(0)
    expect(wrapper.find('a[href="/records"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/chat"]').exists()).toBe(false)
  })

  it('教师看到记录、问询和数据大屏三个可点的权限入口', async () => {
    loginAs('teacher', 'tea001')
    const { useAuth } = await import('../../src/composables/useAuth')
    await useAuth().restore()

    const router = createAppRouter(createMemoryHistory())
    await router.push('/parse')
    await router.isReady()
    const wrapper = mount(AppNav, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('[data-nav-pending]')).toHaveLength(0)
    const recordsLink = wrapper.get('a[href="/records"]')
    expect(recordsLink.attributes('data-nav-item')).toBeDefined()
    expect(recordsLink.attributes('data-nav-pending')).toBeUndefined()
    expect(wrapper.get('a[href="/chat"]').attributes('data-nav-item')).toBeDefined()
    expect(wrapper.get('a[href="/dashboard"]').attributes('data-nav-item')).toBeDefined()
  })

  it('登录态无法验证时显示重试和退出入口，恢复后显示教师页面', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'recover-token')
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        user_id: 'u-recovered',
        username: 'teacher',
        role: 'teacher',
        permissions: ['review:read:all', 'chat:use', 'dashboard:view'],
      }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const { useAuth } = await import('../../src/composables/useAuth')
    await expect(useAuth().restore()).rejects.toThrow('Failed to fetch')

    const router = createAppRouter(createMemoryHistory())
    const wrapper = mount(AppNav, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-testid="session-recovery"]').text()).toContain('无法验证登录状态')
    expect(wrapper.find('a[href="/dashboard"]').exists()).toBe(false)
    await wrapper.get('[data-testid="session-retry"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('a[href="/dashboard"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="session-recovery"]').exists()).toBe(false)
  })
})
