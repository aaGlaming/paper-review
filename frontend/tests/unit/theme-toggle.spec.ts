// 昼夜主题（sketch.md §2）：切换按钮只改 data-theme，不改结构与功能。
// 白天显示太阳、黑夜显示月亮；偏好落 localStorage，刷新后仍在。

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ThemeToggle from '../../src/components/ThemeToggle.vue'
import { resetThemeStateForTest, THEME_STORAGE_KEY } from '../../src/composables/useTheme'
import { createAppRouter } from '../../src/router'
import App from '../../src/App.vue'
import { resetAuthStateForTest, useAuth } from '../../src/composables/useAuth'

beforeEach(() => {
  localStorage.clear()
  resetAuthStateForTest()
  document.documentElement.removeAttribute('data-theme')
  resetThemeStateForTest()
})

afterEach(() => {
  vi.unstubAllGlobals()
  resetAuthStateForTest()
  localStorage.clear()
})

describe('昼夜主题切换', () => {
  it('1. 默认白天：根节点为 light，按钮显示太阳', () => {
    const wrapper = mount(ThemeToggle)

    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(wrapper.get('[data-testid="theme-toggle"]').attributes('data-theme-state')).toBe('light')
    // vitest 把小 SVG 内联成 data URL，看不到文件名：用 alt 区分太阳 / 月亮。
    expect(wrapper.get('.theme-toggle__icon').attributes('alt')).toBe('太阳')
    expect(wrapper.get('.theme-toggle__icon').attributes('src')).toContain('手绘太阳')
  })

  it('2. 点击一次切黑夜：根节点为 dark，按钮显示月亮并持久化', async () => {
    const wrapper = mount(ThemeToggle)

    await wrapper.get('[data-testid="theme-toggle"]').trigger('click')
    await flushPromises()

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(wrapper.get('[data-testid="theme-toggle"]').attributes('data-theme-state')).toBe('dark')
    expect(wrapper.get('.theme-toggle__icon').attributes('alt')).toBe('月亮')
    expect(wrapper.get('.theme-toggle__icon').attributes('src')).toContain('手绘月亮')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('3. 再点一次切回白天', async () => {
    const wrapper = mount(ThemeToggle)

    await wrapper.get('[data-testid="theme-toggle"]').trigger('click')
    await wrapper.get('[data-testid="theme-toggle"]').trigger('click')
    await flushPromises()

    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('4. 存档为 dark 时首屏即黑夜（刷新不丢偏好）', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')

    const wrapper = mount(ThemeToggle)

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(wrapper.get('[data-testid="theme-toggle"]').attributes('data-theme-state')).toBe('dark')
  })

  it('5. 导航栏右端挂着切换按钮，五个入口一个不少', async () => {
    vi.stubGlobal(
      'fetch',
      async (input: RequestInfo | URL) => {
        if (String(input).includes('/api/auth/login')) {
          return new Response(JSON.stringify({
            token: 'theme-shell-token', user_id: 'u-theme', username: 'theme_student', role: 'student', permissions: [],
          }), { status: 200 })
        }
        return new Response(JSON.stringify({ contests: [], samples: [] }), { status: 200 })
      },
    )
    await useAuth().login('theme_student', 'password')
    const router = createAppRouter()
    await router.push('/parse')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    expect(wrapper.findAll('[data-nav-item]')).toHaveLength(5)
    expect(wrapper.find('[data-testid="theme-toggle"]').exists()).toBe(true)
  })
})
