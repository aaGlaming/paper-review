// 视觉重设计的冒烟：两个视口下五页无横向滚动；完整链路后评分页定位仍可用。
// 本文件第一条是纯布局断言（jsdom 验不了横向滚动），必须走 Playwright。

import { expect, test } from '@playwright/test'

const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1920, height: 1080 },
] as const

const PAGES = ['/parse', '/scoring', '/consistency', '/suggestions', '/eval']

for (const viewport of VIEWPORTS) {
  test(`视口 ${viewport.width}×${viewport.height}：五页无横向滚动`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    for (const path of PAGES) {
      await page.goto(path)
      await expect(page.locator('h1')).toHaveCount(1)
      const scrollWidth = await page.evaluate(() => document.scrollingElement?.scrollWidth ?? 0)
      const innerWidth = await page.evaluate(() => window.innerWidth)
      expect(scrollWidth, `${path} 出现横向滚动`).toBeLessThanOrEqual(innerWidth + 1)
    }
  })
}

test('完整链路 → /scoring：维度卡可见、点击定位仍高亮', async ({ page }) => {
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('demo-item').first().click()
  await page.getByTestId('submit-sample').click()
  await expect(page.getByTestId('confirm-sections')).toBeVisible({ timeout: 20_000 })
  await page.getByTestId('confirm-sections').click()
  await expect(page.getByTestId('confirmed-card')).toBeVisible()

  await page.goto('/scoring')
  await expect(page.getByTestId('dimension-card')).toHaveCount(5)

  // 点击「定位原句」仍能滚动并高亮（本版只改表现，不改 indexOf 定位语义）
  await page.locator('[data-testid="dimension-card"]').first().getByTestId('locate-quote').click()
  await expect(page.getByTestId('located-mark')).toBeVisible()
})
