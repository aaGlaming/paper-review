import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { resetAuthStateForTest } from '../../src/composables/useAuth'
import { resolveRedirect } from '../../src/router'
import LoginView from '../../src/views/登录.vue'

function mountLogin(redirect?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/parse', component: { template: '<div>parse</div>' } },
      { path: '/register', component: { template: '<div>register</div>' } },
    ],
  })
  if (redirect !== undefined) {
    void router.replace({ path: '/login', query: { redirect } })
  }
  return mount(LoginView, { global: { plugins: [router] } })
}

beforeEach(() => {
  resetAuthStateForTest()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('登录页', () => {
  it('背景容器引用了压小的背景图', () => {
    const wrapper = mountLogin()
    expect(wrapper.attributes('style')).toContain('login_background')
  })

  it('密码错误时显示后端返回的 message，不翻译', async () => {
    vi.stubGlobal(
      'fetch',
      async () => new Response(JSON.stringify({ detail: '用户名或密码错误' }), { status: 401 }),
    )
    const wrapper = mountLogin()
    await wrapper.find('input[name="username"]').setValue('stu')
    await wrapper.find('input[name="password"]').setValue('wrongpass')
    await wrapper.find('form').trigger('submit.prevent')
    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(wrapper.find('[role="alert"]').text()).toBe('用户名或密码错误')
    expect(wrapper.find('.post-login-intro').exists()).toBe(false)
  })

  it('redirect=/parse 跳转生效，站外 redirect 被忽略', () => {
    expect(resolveRedirect('/parse')).toBe('/parse')
    expect(resolveRedirect('https://evil.example')).toBe('/parse')
    expect(resolveRedirect('//evil.example/x')).toBe('/parse')
    expect(resolveRedirect(undefined)).toBe('/parse')
  })

  it('登录成功先播放开场，点击后才进入安全重定向目标', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: LoginView },
        { path: '/records', component: { template: '<div>records</div>' } },
        { path: '/parse', component: { template: '<div>parse</div>' } },
        { path: '/register', component: { template: '<div>register</div>' } },
      ],
    })
    await router.push({ path: '/login', query: { redirect: '/records' } })
    await router.isReady()
    vi.stubGlobal(
      'fetch',
      async () => new Response(
        JSON.stringify({ token: 'intro-token', user_id: 'u-intro', role: 'student', permissions: [] }),
        { status: 200 },
      ),
    )
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    await wrapper.find('input[name="username"]').setValue('stu')
    await wrapper.find('input[name="password"]').setValue('password123')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(wrapper.find('.post-login-intro').exists()).toBe(true)
    await wrapper.get('.post-login-intro').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/records')
  })
})
