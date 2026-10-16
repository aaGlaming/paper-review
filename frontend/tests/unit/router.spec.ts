import { describe, expect, it } from 'vitest'

import { createAppRouter, routes } from '../../src/router'

describe('路由表', () => {
  it('五个页面路径都能匹配到组件，/ 重定向到 /parse', async () => {
    const router = createAppRouter()
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
    ]
    for (const [routePath, name] of table) {
      const resolved = router.resolve(routePath)
      expect(resolved.name, routePath).toBe(name)
      expect(resolved.matched.length, routePath).toBe(1)
      expect(resolved.matched[0]?.components?.default, routePath).toBeTruthy()
    }

    // 一条重定向 + 五条页面 + 一条带参数的评测单篇
    expect(routes).toHaveLength(7)
  })

  it('/eval/:paperId 带参数时匹配到与 /eval 同一个组件', () => {
    const router = createAppRouter()

    const withParam = router.resolve('/eval/demo-01')
    expect(withParam.name).toBe('eval-paper')
    expect(withParam.params.paperId).toBe('demo-01')

    const plain = router.resolve('/eval')
    expect(withParam.matched[0]?.components?.default).toBe(plain.matched[0]?.components?.default)
  })
})
