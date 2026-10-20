import { expect, test } from '@playwright/test'

test('学生导航不显示记录总览，直接访问也回到论文解析页', async ({ page }) => {
  await page.goto('/parse')
  await expect(page.getByRole('link', { name: '记录总览' })).toHaveCount(0)

  await page.goto('/records')
  await expect(page).toHaveURL(/\/parse$/)
})
