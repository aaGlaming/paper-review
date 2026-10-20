import { beforeEach, describe, expect, it, vi } from 'vitest'

import { setAuthToken } from '../../src/api'
import { AUTH_TOKEN_KEY, resetAuthStateForTest, useAuth } from '../../src/composables/useAuth'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

beforeEach(() => {
  resetAuthStateForTest()
  localStorage.clear()
  setAuthToken(null)
  vi.unstubAllGlobals()
})

describe('useAuth', () => {
  it('login 成功后 token 落 localStorage，且后续 request 带 Authorization 头', async () => {
    const authorizations: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const headers = new Headers(init?.headers)
        authorizations.push(headers.get('Authorization') ?? '')
        if (String(input).includes('/api/auth/login')) {
          return jsonResponse({
            token: 'tok-123',
            user_id: 'u1',
            role: 'student',
            permissions: ['review:create'],
          })
        }
        return jsonResponse({ contests: [] })
      }),
    )

    const me = await useAuth().login('stu', 'password123')

    expect(me.username).toBe('stu')
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('tok-123')

    // 后续请求自动带头（api 层模块变量已同步）
    const { listContests } = await import('../../src/api')
    await listContests()
    expect(authorizations).toContain('Bearer tok-123')
  })

  it('logout 清 token 与用户态（登出接口 204 无 body 不抛错）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).includes('/api/auth/logout')
          ? new Response(null, { status: 204 })
          : jsonResponse({ token: 'tok-123', user_id: 'u1', role: 'student', permissions: [] }),
      ),
    )

    await useAuth().login('stu', 'password123')
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).not.toBeNull()

    await useAuth().logout()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(useAuth().user.value).toBeNull()
  })

  it('restore 遇 401 自动清 token', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'stale-token')
    setAuthToken('stale-token')
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: '未登录' }, 401)))

    await expect(useAuth().restore()).rejects.toThrow()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(useAuth().user.value).toBeNull()
  })
})
