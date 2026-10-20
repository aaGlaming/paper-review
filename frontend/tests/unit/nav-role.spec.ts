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
          permissions: role === 'teacher' ? ['review:read:all'] : [],
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
  it('学生看不到记录总览，也看不到任何 pending 项', async () => {
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
  })

  it('教师看到两个 pending 项和可点的记录总览', async () => {
    loginAs('teacher', 'tea001')
    const { useAuth } = await import('../../src/composables/useAuth')
    await useAuth().restore()

    const router = createAppRouter(createMemoryHistory())
    await router.push('/parse')
    await router.isReady()
    const wrapper = mount(AppNav, { global: { plugins: [router] } })
    await wrapper.vm.$nextTick()

    const pending = wrapper.findAll('[data-nav-pending]')
    expect(pending).toHaveLength(2)
    for (const item of pending) {
      expect(item.attributes('aria-disabled')).toBe('true')
      expect(item.attributes('title')).toContain('上线')
      expect(item.element.tagName).not.toBe('A')
    }
    const recordsLink = wrapper.get('a[href="/records"]')
    expect(recordsLink.attributes('data-nav-item')).toBeDefined()
    expect(recordsLink.attributes('data-nav-pending')).toBeUndefined()
  })
})
