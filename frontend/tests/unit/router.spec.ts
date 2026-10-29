import { createMemoryHistory } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import { AUTH_TOKEN_KEY, resetAuthStateForTest, useAuth } from '../../src/composables/useAuth'
import { createAppRouter, routes } from '../../src/router'

describe('路由表', () => {
  it('五个页面路径都能匹配到组件，/ 重定向到 /parse', async () => {
    // 守卫下先取登录态（只 stub fetch，不打后端），再跑原匹配表——原断言逐条保留。
    resetAuthStateForTest()
    localStorage.setItem(AUTH_TOKEN_KEY, 'table-token')
    vi.stubGlobal(
      'fetch',
      async () =>
        new Response(
          JSON.stringify({ user_id: 'u1', username: 'stu', role: 'student', permissions: [] }),
          { status: 200 },
        ),
    )
    try {
      await useAuth().restore()

      const router = createAppRouter(createMemoryHistory())
      await router.push('/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/parse')
      expect(router.currentRoute.value.name).toBe('parse')

      const table: Array<[string, string]> = [
        ['/parse', 'parse'],
        ['/scoring', 'scoring'],
        ['/consistency', 'consistency'],
        ['/suggestions', 'suggestions'],
        ['/eval', 'eval'],
        ['/records', 'records'],
        ['/dashboard', 'dashboard'],
        ['/chat', 'chat'],
        ['/login', 'login'],
        ['/register', 'register'],
      ]
      for (const [routePath, name] of table) {
        const resolved = router.resolve(routePath)
        expect(resolved.name, routePath).toBe(name)
        expect(resolved.matched.length, routePath).toBe(1)
        expect(resolved.matched[0]?.components?.default, routePath).toBeTruthy()
      }

      // 一条重定向 + 五条页面 + 一条带参数的评测单篇 + 登录 + 注册
      expect(routes).toHaveLength(12)
    } finally {
      vi.unstubAllGlobals()
      resetAuthStateForTest()
      localStorage.clear()
    }
  })

  it('/eval/:paperId 带参数时匹配到与 /eval 同一个组件', () => {
    const router = createAppRouter()

    const withParam = router.resolve('/eval/demo-01')
    expect(withParam.name).toBe('eval-paper')
    expect(withParam.params.paperId).toBe('demo-01')

    const plain = router.resolve('/eval')
    expect(withParam.matched[0]?.components?.default).toBe(plain.matched[0]?.components?.default)
  })

  it('未登录时 push(/parse) 落到 /login，且 redirect 查询串是 /parse', async () => {
    resetAuthStateForTest()
    localStorage.clear()

    const router = createAppRouter(createMemoryHistory())
    await router.push('/parse')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/parse')
    resetAuthStateForTest()
  })

  it('已登录时 push(/login) 落到 /parse', async () => {
    resetAuthStateForTest()
    localStorage.setItem(AUTH_TOKEN_KEY, 'test-token')

    const stubFetch = async (input: RequestInfo | URL) =>
      new Response(
        String(input).includes('/api/auth/login')
          ? JSON.stringify({
              token: 'test-token',
              user_id: 'u1',
              role: 'student',
              permissions: [],
            })
          : JSON.stringify({ user_id: 'u1', username: 'stu', role: 'student', permissions: [] }),
        { status: 200 },
      )
    vi.stubGlobal('fetch', stubFetch)
    try {
      // 经 login 把模块级 token 置上（只 stub fetch，不打后端）
      await useAuth().login('stu', 'password123')
    } finally {
      vi.unstubAllGlobals()
    }

    const router = createAppRouter(createMemoryHistory())
    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/parse')
    resetAuthStateForTest()
    localStorage.clear()
  })

  it('token 尚未验证且后端不可达时允许打开登录页', async () => {
    resetAuthStateForTest()
    localStorage.setItem(AUTH_TOKEN_KEY, 'unverified-token')
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    await expect(useAuth().restore()).rejects.toThrow('Failed to fetch')

    const router = createAppRouter(createMemoryHistory())
    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    resetAuthStateForTest()
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('token 尚未验证时保留权限页面路由，等待恢复权限后由接口鉴权', async () => {
    resetAuthStateForTest()
    localStorage.setItem(AUTH_TOKEN_KEY, 'unverified-token')
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    await expect(useAuth().restore()).rejects.toThrow('Failed to fetch')

    const router = createAppRouter(createMemoryHistory())
    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
    resetAuthStateForTest()
    localStorage.clear()
    vi.unstubAllGlobals()
  }, 10_000)
})
