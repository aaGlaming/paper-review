// 修改建议页的冒烟：走 5173 吃 Vite 代理，后端与真库都在。
// 第一条会真写库（创建 + 确认），接口没有删除路径——这是已知且已记档的污染。

import { expect, test } from '@playwright/test'

test('解析 → 确认 → 修改建议：三段分组、上游指针、刷新仍在', async ({ page }) => {
  // 先在解析页走完整链路
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.getByTestId('demo-item').first().click()
  await page.getByTestId('submit-sample').click()
  await expect(page.getByTestId('confirm-sections')).toBeVisible()
  await page.getByTestId('confirm-sections').click()
  await expect(page.getByTestId('confirmed-card')).toBeVisible()

  // 进修改建议页
  await page.goto('/suggestions')

  // 三段框架都渲染，顺序固定（就是修改顺序）
  await expect(page.getByTestId('suggestion-section')).toHaveCount(3)
  const sections = page.getByTestId('suggestion-section')
  await expect(sections.nth(0)).toHaveAttribute('data-section', '题目约束与数字冲突')
  await expect(sections.nth(1)).toHaveAttribute('data-section', '证据不足')
  await expect(sections.nth(2)).toHaveAttribute('data-section', '表述')

  // 至少一条建议，且每条建议都显示上游 id（需求 §12.3 的可见化）
  await expect(page.getByTestId('suggestion-item').first()).toBeVisible()
  const itemCount = await page.getByTestId('suggestion-item').count()
  expect(itemCount).toBeGreaterThanOrEqual(1)
  const upstreamCount = await page.getByTestId('upstream-id').count()
  expect(upstreamCount).toBe(itemCount)

  // 刷新后建议列表仍在（共享状态没丢）
  await page.reload()
  await expect(page.getByTestId('suggestion-item').first()).toBeVisible()
  expect(await page.getByTestId('suggestion-item').count()).toBe(itemCount)
})

test('直接进修改建议（无共享状态）：空态，suggestion-item 数量为 0', async ({ page }) => {
  await page.goto('/suggestions')

  await expect(page.getByTestId('suggestions-empty')).toBeVisible()
  await expect(page.getByTestId('suggestion-item')).toHaveCount(0)
})
