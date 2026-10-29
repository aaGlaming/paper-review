/**
 * 登录态单例：token + 当前用户 + me 是否拉取过（ready）。
 *
 * 不用 Pinia（项目不装状态管理库），模块级 ref 即单例。
 * 存储键 `pr.auth.token` 用 localStorage：跨标签页与刷新都要在；
 * 代价是 XSS 可读，所以**任何地方都不许把 token 拼进 URL、日志、`console.log`**。
 * 读写一律 try/catch（隐私模式会抛），照 useTheme 的写法。
 */

import { ref } from 'vue'

import { authLogin, authLogout, authMe, setAuthToken } from '../api'
import type { AuthUser } from '../api/types'

export const AUTH_TOKEN_KEY = 'pr.auth.token'

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

function readToken(): string | null {
  try {
    const raw = storage()?.getItem(AUTH_TOKEN_KEY)
    return raw ? raw : null
  } catch {
    return null
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) {
      storage()?.setItem(AUTH_TOKEN_KEY, token)
    } else {
      storage()?.removeItem(AUTH_TOKEN_KEY)
    }
  } catch {
    // 存储不可用时只做内存切换，不抛错
  }
}

const token = ref<string | null>(readToken())
const user = ref<AuthUser | null>(null)
const ready = ref(false)
const restoreError = ref('')

if (token.value) {
  setAuthToken(token.value)
}

function applyToken(next: string | null): void {
  token.value = next
  writeToken(next)
  setAuthToken(next)
}

export function useAuth(): {
  token: typeof token
  user: typeof user
  ready: typeof ready
  restoreError: typeof restoreError
  login: (username: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  restore: () => Promise<void>
  hasPermission: (code: string) => boolean
  isTeacher: () => boolean
} {
  async function login(username: string, password: string): Promise<AuthUser> {
    const result = await authLogin({ username, password })
    applyToken(result.token)
    const me: AuthUser = {
      user_id: result.user_id,
      username,
      role: result.role,
      permissions: result.permissions,
    }
    user.value = me
    ready.value = true
    restoreError.value = ''
    return me
  }

  async function logout(): Promise<void> {
    try {
      await authLogout()
    } catch {
      // 登出失败也清本地态：服务端本就不撤销 token（见 findings 登出口径）
    }
    user.value = null
    ready.value = false
    restoreError.value = ''
    applyToken(null)
  }

  async function restore(): Promise<void> {
    // 模块加载后才写入 localStorage 的 token（如单测预置、另一标签页登录）在这里同步。
    if (!token.value) {
      const stored = readToken()
      if (stored) {
        token.value = stored
        setAuthToken(stored)
      }
    }
    if (!token.value) {
      user.value = null
      ready.value = true
      restoreError.value = ''
      return
    }
    restoreError.value = ''
    try {
      user.value = await authMe()
      ready.value = true
      restoreError.value = ''
    } catch (error) {
      if (error instanceof Error && 'status' in error && (error as { status: number }).status === 401) {
        user.value = null
        applyToken(null)
        ready.value = true
        restoreError.value = ''
      } else {
        // 未知错误不是“无权限”：保留 token，但允许守卫和用户稍后重试认证恢复。
        user.value = null
        ready.value = false
        restoreError.value = '无法验证登录状态，请检查服务连接后重试。'
      }
      throw error
    }
  }

  function hasPermission(code: string): boolean {
    return (user.value?.permissions ?? []).includes(code)
  }

  function isTeacher(): boolean {
    return user.value?.role === 'teacher'
  }

  return { token, user, ready, restoreError, login, logout, restore, hasPermission, isTeacher }
}

/** 仅供单测：清掉模块状态，下一个用例重新读盘。 */
export function resetAuthStateForTest(): void {
  user.value = null
  ready.value = false
  restoreError.value = ''
  applyToken(null)
}
