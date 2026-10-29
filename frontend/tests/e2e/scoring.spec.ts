// 分项评分页的冒烟：走 5173 吃 Vite 代理，后端与真库都在。
// 第一条会真写库（创建 + 确认），接口没有删除路径——这是已知且已记档的污染。

import { expect, test } from '@playwright/test'
import { waitForConfirmed } from './timeouts'

const BAND_WORDS = ['充分', '基本', '不足', '证据不足']

test.beforeEach(async ({ page }) => {
  await page.route('**/api/reviews/*/agent-steps', route =>
    route.fulfill({ json: { review_id: 'x', steps: [] } }),
  )
})

test('解析 → 确认 → 评分页：维度卡、原句定位、刷新仍在', async ({ page }) => {
  // 先在解析页走完整链路
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.locator('[data-testid="demo-item"][data-sample-id="bench-dragon"]').click()
  await page.getByTestId('submit-sample').click()
  await expect(page.getByTestId('confirm-sections')).toBeVisible()
  const confirmStartedAt = Date.now()
  await page.getByTestId('confirm-sections').click()
  await waitForConfirmed(page)
  console.log(`[p26] scoring-confirm-wall-ms=${Date.now() - confirmStartedAt}`)

  // 进评分页
  await page.goto('/scoring')
  const pageRoot = page.getByTestId('scoring-page')

  await expect(page.getByTestId('dimension-card')).toHaveCount(5)

  // 需求 §12.2 点名的事实：assumption 维的原句含「忽略板凳宽度」
  const assumption = page.getByTestId('dimension-card').filter({ hasText: /assumption/ })
  await expect(assumption).toContainText('忽略板凳宽度')

  // 页面不出现「总分 0」「0 分」这类假分数
  await expect(pageRoot).not.toContainText('总分 0')
  await expect(pageRoot).not.toContainText('0 分')

  // 点「定位原句」：该卡进入已定位态，且高亮区里是那段原句（证明 quote 在章节正文里原样找到）
  await assumption.getByTestId('locate-quote').click()
  await expect(page.getByTestId('located-content')).toBeVisible()
  await expect(assumption).toHaveAttribute('data-located', 'true')
  await expect(page.getByTestId('located-mark')).toContainText('忽略板凳宽度')

  // 刷新后维度卡仍在（共享状态没丢）
  await page.reload()
  await expect(page.getByTestId('dimension-card')).toHaveCount(5)
})

test('直接进评分页（无共享状态）：空态，没有任何档位结果', async ({ page }) => {
  await page.goto('/scoring')

  await expect(page.getByTestId('scoring-empty')).toBeVisible()
  await expect(page.getByTestId('dimension-card')).toHaveCount(0)

  const pageRoot = page.getByTestId('scoring-page')
  for (const word of BAND_WORDS) {
    await expect(pageRoot).not.toContainText(word)
  }
})
