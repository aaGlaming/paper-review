/**
 * 路由表：五个页面 + 一条带参数的评测单篇（与评测页共用同一个组件）+ 登录 / 注册。
 *
 * 路径是冻结的，不在这里自创别名；页面文件名保持中文原名。
 * 守卫只走 useAuth（可 stub），不直接读 localStorage。
 */

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw, Router, RouterHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuth } from '../composables/useAuth'
import ConsistencyView from '../views/一致性审查.vue'
import EvalCompareView from '../views/评测对照.vue'
import LoginView from '../views/登录.vue'
import ParseView from '../views/论文解析.vue'
import RegisterView from '../views/注册.vue'
import ScoringView from '../views/分项评分.vue'
import SuggestionView from '../views/修改建议.vue'
import RecordsView from '../views/记录总览.vue'
import ChatView from '../views/AI问询.vue'

export const APP_TITLE_SUFFIX = '竞赛论文预审工作台'

/**
 * 登录后跳转：只接受站内相对路径（以 `/` 开头且不以 `//` 开头），
 * 其余一律回 `/parse`（防开放重定向）。登录页与单测共用。
 */
export function resolveRedirect(raw: unknown): string {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//')) {
    return '/parse'
  }
  return raw
}

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/parse' },
  { path: '/parse', name: 'parse', component: ParseView, meta: { title: '论文解析' } },
  { path: '/scoring', name: 'scoring', component: ScoringView, meta: { title: '分项评分' } },
  {
    path: '/consistency',
    name: 'consistency',
    component: ConsistencyView,
    meta: { title: '一致性审查' },
  },
  { path: '/suggestions', name: 'suggestions', component: SuggestionView, meta: { title: '修改建议' } },
  { path: '/eval', name: 'eval', component: EvalCompareView, meta: { title: '评测对照' } },
  {
    path: '/records', name: 'records', component: RecordsView,
    meta: { title: '记录总览', permission: 'review:read:all' },
  },
  { path: '/chat', name: 'chat', component: ChatView, meta: { title: 'AI 问询', permission: 'chat:use' } },
  {
    path: '/dashboard', name: 'dashboard', component: () => import('../views/数据大屏.vue'),
    meta: { title: '数据大屏', permission: 'dashboard:view' },
  },
  {
    path: '/eval/:paperId',
    name: 'eval-paper',
    component: EvalCompareView,
    meta: { title: '评测对照' },
  },
  { path: '/login', name: 'login', component: LoginView, meta: { title: '登录', public: true } },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
    meta: { title: '注册', public: true },
  },
]

export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({ history, routes })

  router.beforeEach(async (to) => {
    const auth = useAuth()
    if (to.meta.public) {
      if ((to.path === '/login' || to.path === '/register') && auth.token.value) {
        return '/parse'
      }
      return true
    }
    if (!auth.token.value) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (!auth.ready.value) {
      try {
        await auth.restore()
      } catch {
        // 401（过期/伪造）时 restore 已清 token → 跳登录；其它失败（后端不可达等）
        // token 还在 → 放行，各页自行降级显示，不把用户踢到同样调不通的登录页。
        if (!auth.token.value) {
          return { path: '/login', query: { redirect: to.fullPath } }
        }
      }
      if (!auth.token.value) {
        return { path: '/login', query: { redirect: to.fullPath } }
      }
    }
    const required = to.meta.permission
    if (typeof required === 'string' && !auth.hasPermission(required)) {
      ElMessage.warning('需要教师权限')
      return '/parse'
    }
    return true
  })

  router.afterEach((to) => {
    const title = typeof to.meta.title === 'string' ? to.meta.title : ''
    try {
      document.title = title ? `${title} · ${APP_TITLE_SUFFIX}` : APP_TITLE_SUFFIX
    } catch {
      // 没有 document（如单测）时跳过
    }
  })

  return router
}

export default createAppRouter()
