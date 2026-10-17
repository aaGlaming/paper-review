/**
 * 白天 / 黑夜主题状态：`light` | `dark`。
 *
 * 切换只改根节点的 `data-theme` 属性与配色，不改布局、字体、组件结构与手绘风格
 * （sketch.md §2.5）。颜色全部来自 `tokens.css` 的语义 Token，本文件不写任何色值。
 *
 * 持久化用 `localStorage`（跨会话记住偏好），与评审流程的 `sessionStorage` 分开；
 * 不引入任何状态管理依赖。无定时器、无网络请求。
 */

import { ref } from 'vue'

export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'paper-review:theme'

const LIGHT: Theme = 'light'
const DARK: Theme = 'dark'

function isTheme(value: unknown): value is Theme {
  return value === LIGHT || value === DARK
}

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

/** 读存档：没有或被改坏都返回 null，由调用方决定回退。 */
export function getStoredTheme(): Theme | null {
  const raw = storage()?.getItem(THEME_STORAGE_KEY)
  return isTheme(raw) ? raw : null
}

/** 系统偏好：只在无存档时用一次；读不到（jsdom、隐私模式）就回白天。 */
export function getPreferredTheme(): Theme {
  try {
    if (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
    ) {
      return DARK
    }
  } catch {
    // 读不到偏好就当白天，不抛错
  }
  return LIGHT
}

/** 生效：根节点属性 + 持久化。两步各自 try，坏一步不影响另一步。 */
export function applyTheme(theme: Theme): void {
  try {
    document.documentElement.setAttribute('data-theme', theme)
  } catch {
    // 没有 document（如 SSR）时只做持久化
  }
  try {
    storage()?.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // 存储不可用时只做内存切换，不抛错
  }
}

const current = ref<Theme>(LIGHT)
let initialized = false

/** 共享状态：全应用共用同一个 theme，多次调用不重复读盘。 */
export function useTheme(): {
  theme: typeof current
  set: (theme: Theme) => void
  toggle: () => void
} {
  if (!initialized) {
    current.value = getStoredTheme() ?? getPreferredTheme()
    applyTheme(current.value)
    initialized = true
  }

  function set(theme: Theme): void {
    current.value = theme
    applyTheme(theme)
  }

  function toggle(): void {
    set(current.value === DARK ? LIGHT : DARK)
  }

  return { theme: current, set, toggle }
}

/** 仅供单测：把模块状态退回未初始化，下一个 useTheme() 重新读盘。 */
export function resetThemeStateForTest(): void {
  initialized = false
  current.value = LIGHT
}
