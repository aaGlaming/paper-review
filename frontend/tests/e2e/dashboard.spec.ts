import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

test.use({ storageState: './tests/e2e/.auth/teacher.json' })

test('教师能查看八个大屏模块，学生访问时被权限守卫拦截', async ({ browser, page }) => {
  await page.goto('/dashboard')
  await expect(page.locator('[data-dashboard-module]')).toHaveCount(8)
  await expect(page.getByRole('heading', { name: '提交总量趋势' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '关键指标' })).toBeVisible()
  const screenshotsDir = path.resolve(process.cwd(), '../docs/plan/acceptance/screenshots')
  fs.mkdirSync(screenshotsDir, { recursive: true })
  await page.screenshot({ path: path.join(screenshotsDir, 'v3.4.1-dashboard.png'), fullPage: true })

  const student = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', storageState: './tests/e2e/.auth/user.json' })
  await student.goto('/dashboard')
  await expect(student).toHaveURL(/\/parse$/)
  await expect(student.getByText('需要教师权限')).toBeVisible()
  await student.close()

  const empty = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', storageState: './tests/e2e/.auth/teacher.json' })
  await empty.route('**/api/dashboard/summary', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      cached: false,
      cards: { total_submissions: 0, weekly_new: 0, parse_only: 0, pending_conflicts: 0, gold_agreement: null },
      contests: [], bands: [], insufficient_top: [], conflicts: [], hotspots: [],
      citation: { failure_count: 0, total_dimensions: 0, citation_rate: 0 }, gold: null,
    }),
  }))
  await empty.route('**/api/dashboard/trend?days=30', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ cached: false, days: 30, series: [] }),
  }))
  await empty.goto('/dashboard')
  await expect(empty.locator('[data-dashboard-module]')).toHaveCount(8)
  await expect(empty.locator('[data-chart]')).toHaveCount(0)
  await expect(empty.getByText('暂无数据').first()).toBeVisible()
  await expect(empty.getByText('暂无 gold 数据')).toBeVisible()
  await empty.screenshot({ path: path.join(screenshotsDir, 'v3.4.1-dashboard-empty.png'), fullPage: true })
  await empty.close()
})
