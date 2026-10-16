/**
 * 路由表：五个页面 + 一条带参数的评测单篇（与评测页共用同一个组件）。
 *
 * 路径是冻结的，不在这里自创别名；页面文件名保持中文原名。
 */

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw, Router, RouterHistory } from 'vue-router'

import ConsistencyView from '../views/一致性审查.vue'
import EvalCompareView from '../views/评测对照.vue'
import ParseView from '../views/论文解析.vue'
import ScoringView from '../views/分项评分.vue'
import SuggestionView from '../views/修改建议.vue'

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
    path: '/eval/:paperId',
    name: 'eval-paper',
    component: EvalCompareView,
    meta: { title: '评测对照' },
  },
]

export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  return createRouter({ history, routes })
}

export default createAppRouter()
