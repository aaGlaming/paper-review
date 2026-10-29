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

describe('数据大屏权限守卫', () => {
  it('学生直连 /dashboard 后回到 /parse 并提示无权限', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'student-token')
    vi.stubGlobal('fetch', async () => new Response(JSON.stringify({
      user_id: 'student-a', username: 'student', role: 'student', permissions: [],
    }), { status: 200 }))
    await useAuth().restore()
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
    const router = createAppRouter(createMemoryHistory())

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/parse')
    expect(warning).toHaveBeenCalledWith('需要教师权限')
  })
})
