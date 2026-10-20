import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { resetAuthStateForTest } from '../../src/composables/useAuth'
import RegisterView from '../../src/views/注册.vue'

function mountRegister() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/register', component: RegisterView },
      { path: '/parse', component: { template: '<div>parse</div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
    ],
  })
  return mount(RegisterView, { global: { plugins: [router] } })
}

beforeEach(() => {
  resetAuthStateForTest()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('注册页', () => {
  it('两次密码不一致时不发请求', async () => {
    const spy = vi.fn(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', spy)

    const wrapper = mountRegister()
    await wrapper.find('input[name="password"]').setValue('password123')
    await wrapper.find('input[name="confirm"]').setValue('password456')
    await wrapper.find('form').trigger('submit.prevent')
    await wrapper.vm.$nextTick()

    expect(spy).not.toHaveBeenCalled()
    expect(wrapper.find('[role="alert"]').text()).toContain('不一致')
  })

  it('409 显示统一文案，不猜是用户名还是邮箱', async () => {
    vi.stubGlobal(
      'fetch',
      async () => new Response(JSON.stringify({ detail: '该注册信息不可用' }), { status: 409 }),
    )
    const wrapper = mountRegister()
    await wrapper.find('input[name="username"]').setValue('stu')
    await wrapper.find('input[name="email"]').setValue('stu@example.com')
    await wrapper.find('input[name="password"]').setValue('password123')
    await wrapper.find('input[name="confirm"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(wrapper.find('[role="alert"]').text()).toBe('该注册信息不可用')
  })
})
