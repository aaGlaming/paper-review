import { expect, test } from '@playwright/test'

test.use({ storageState: './tests/e2e/.auth/teacher.json' })

test('教师能打开记录总览并看到记录行', async ({ page }) => {
  await page.goto('/records')
  await expect(page.locator('.records-table__grid')).toBeVisible()

  const rows = page.locator('.records-table__grid tbody .el-table__row[data-row-id]')
  await expect(rows.first()).toBeVisible()
  expect(await rows.count()).toBeGreaterThanOrEqual(1)
})

test('点击记录行打开包含维度卡和修改建议区块的抽屉', async ({ page }) => {
  await page.goto('/records')
  const row = page.locator('.records-table__grid tbody .el-table__row[data-row-id]').first()
  await expect(row).toBeVisible()
  await row.click()

  const drawer = page.locator('.el-drawer')
  await expect(drawer).toBeVisible()
  await expect(drawer.locator('[data-testid="dimension-card"]').first()).toBeVisible()
  await expect(drawer.getByRole('heading', { name: '修改建议', exact: true })).toBeVisible()
})
