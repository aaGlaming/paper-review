import { ElMessage } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { AUTH_TOKEN_KEY, resetAuthStateForTest, useAuth } from '../../src/composables/useAuth'
import { createAppRouter } from '../../src/router'

beforeEach(() => {
  resetAuthStateForTest()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('记录总览权限守卫', () => {
  it('学生直连 /records 后回到 /parse 并收到一次提示', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'student-token')
    vi.stubGlobal(
      'fetch',
      async () => new Response(JSON.stringify({
        user_id: 'student-a', username: 'student', role: 'student', permissions: [],
      }), { status: 200 }),
    )
    await useAuth().restore()
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
    const router = createAppRouter(createMemoryHistory())

    await router.push('/records')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/parse')
    expect(warning).toHaveBeenCalledTimes(1)
    expect(warning).toHaveBeenCalledWith('需要教师权限')
  })
})
