// 一致性审查页的冒烟：走 5173 吃 Vite 代理，后端与真库都在。
// 第一条会真写库（创建 + 确认），接口没有删除路径——这是已知且已记档的污染。

import { expect, test } from '@playwright/test'
import { waitForConfirmed } from './timeouts'

test('解析 → 确认 → 一致性审查：冲突列表、412/386、点击定位、刷新仍在', async ({ page }) => {
  // 先在解析页走完整链路
  await page.goto('/parse')
  await page.getByTestId('contest-select').selectOption({ index: 1 })
  await page.locator('[data-testid="demo-item"][data-sample-id="bench-dragon"]').click()
  await page.getByTestId('submit-sample').click()
  // 后端冷启动下首个 createReview 会导入图/审查/报告模块，实测约 7s，放宽默认 5s 的超时。
  await expect(page.getByTestId('confirm-sections')).toBeVisible({ timeout: 20_000 })
  await page.getByTestId('confirm-sections').click()
  await waitForConfirmed(page)

  // 进一致性审查页
  await page.goto('/consistency')
  const pageRoot = page.getByTestId('consistency-page')

  // 冲突列表条数 ≥ 1
  await expect(page.getByTestId('conflict-item').first()).toBeVisible()
  expect(await page.getByTestId('conflict-item').count()).toBeGreaterThanOrEqual(1)

  // 需求 §12.2 点名：板凳龙样例同时看得到「412 s」与「386 s」两条 evidence
  await expect(pageRoot).toContainText('412 s')
  await expect(pageRoot).toContainText('386 s')

  // 页面不出现「总分 0」「0 分」这类假分数
  await expect(pageRoot).not.toContainText('总分 0')
  await expect(pageRoot).not.toContainText('0 分')

  // 点击一条 evidence 后该条进入 data-located="true"
  await page.getByTestId('evidence-hit').first().click()
  await expect(page.getByTestId('evidence-hit').first()).toHaveAttribute('data-located', 'true')
  await expect(page.getByTestId('located-content')).toBeVisible()

  // 刷新后冲突列表仍在（共享状态没丢）
  await page.reload()
  await expect(page.getByTestId('conflict-item').first()).toBeVisible()
  expect(await page.getByTestId('conflict-item').count()).toBeGreaterThanOrEqual(1)
})

test('直接进一致性审查（无共享状态）：空态，冲突列表为空', async ({ page }) => {
  await page.goto('/consistency')

  await expect(page.getByTestId('consistency-empty')).toBeVisible()
  await expect(page.getByTestId('conflict-item')).toHaveCount(0)
})
