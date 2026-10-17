// 昼夜主题的 E2E：右上角按钮真实点击，白天太阳 ↔ 黑夜月亮来回切，偏好刷新不丢。
// 布局回归仍由 visual.spec.ts 守，这里只验切换行为与图标。

import { expect, test } from '@playwright/test'

test('右上角切换按钮：点击在太阳/月亮间切换，刷新后偏好仍在', async ({ page }) => {
  await page.goto('/parse')
  await expect(page.locator('h1')).toHaveText('论文解析')

  const toggle = page.getByTestId('theme-toggle')
  await expect(toggle).toBeVisible()

  // 首访默认白天（除非跑 E2E 的机器偏好黑夜：以 data-theme-state 为准不断言死值，
  // 先归一到白天再走切换流程）。
  if ((await toggle.getAttribute('data-theme-state')) === 'dark') {
    await toggle.click()
  }
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(toggle).toHaveAttribute('data-theme-state', 'light')
  // 图标 img 带 aria-hidden，不进无障碍树：用类选择器断言 alt。
  await expect(toggle.locator('.theme-toggle__icon')).toHaveAttribute('alt', '太阳')

  // 切黑夜
  await toggle.click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(toggle).toHaveAttribute('data-theme-state', 'dark')
  await expect(toggle.locator('.theme-toggle__icon')).toHaveAttribute('alt', '月亮')

  // 黑夜下五页标题仍在（主题只换色，不换结构）
  for (const path of ['/scoring', '/consistency', '/suggestions', '/eval']) {
    await page.goto(path)
    await expect(page.locator('h1')).toHaveCount(1)
  }

  // 回解析页再切回白天，刷新后仍是白天（localStorage 持久化）
  await page.goto('/parse')
  await page.getByTestId('theme-toggle').click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.getByTestId('theme-toggle')).toHaveAttribute('data-theme-state', 'light')
})
