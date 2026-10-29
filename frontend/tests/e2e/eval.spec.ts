// 评测对照页的冒烟：走 5173 吃 Vite 代理，后端与真库都在。
// 本页只读评测与样例接口，不写库、无污染。

import { expect, test } from '@playwright/test'

test('进 /eval：三张指标卡、43.3%、确定性回退标注、100%', async ({ page }) => {
  await page.goto('/eval')

  // 三张指标卡都在
  await expect(page.getByTestId('metric-card')).toHaveCount(3)

  // band_agreement 的 rate 与后端 0.4333… 一致（约 43.3%）
  await expect(page.locator('[data-metric="band_agreement"] [data-testid="metric-rate"]')).toHaveText(
    '43.3%',
  )

  // quote_exact_match 显示 100%（确定性回退下引用精确匹配率 = 1.0）
  await expect(page.locator('[data-metric="quote_exact_match"] [data-testid="metric-rate"]')).toHaveText(
    '100%',
  )

  // note 原文里出现「确定性结构回退」与「不是模型准确率」
  await expect(page.getByTestId('eval-note')).toContainText('确定性结构回退')
  await expect(page.getByTestId('eval-note')).toContainText('不是模型准确率')

  // 确定性回退被额外标注为非模型评测结果
  await expect(page.getByTestId('deterministic-note')).toContainText('非模型评测结果')
})

test('点一行样例 → /eval/:paperId：无 gold 演示稿明确说明不能计算差异', async ({ page }) => {
  await page.goto('/eval')
  await expect(page.getByTestId('sample-row').first()).toBeVisible()

  // 点第一行样例，跳到 /eval/:paperId
  await page.getByTestId('sample-row').first().getByRole('link').click()
  await expect(page).toHaveURL(/\/eval\/[^/]+$/)

  // 该演示稿没有 gold；说明不可计算差异，不将空表伪装成无差异。
  await expect(page.getByTestId('single-paper-placeholder')).toBeVisible()
  await expect(page.getByTestId('single-paper-placeholder')).toContainText('没有 gold 档位')

  // 不含 gold 假数据（没有指标卡）
  await expect(page.getByTestId('metric-card')).toHaveCount(0)
})
