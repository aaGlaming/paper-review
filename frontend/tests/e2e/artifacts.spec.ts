import fs from 'node:fs'
import path from 'node:path'

import { expect, test } from '@playwright/test'

test.use({ storageState: './tests/e2e/.auth/teacher.json' })

// These two review ids are the retained v3.5.5 demo records created from samples.
const DEMOS = [
  { name: 'smoke', reviewId: '2446e390294542efbe3afddf637065a1', locate: 'claim' },
  { name: 'planting', reviewId: '833f43f990284c19834ae1742d8425cb', locate: 'table' },
] as const

test('教师查看两篇带产物评审、显示三组并能点击原文定位', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1200 })
  const screenshotDir = path.resolve(process.cwd(), '../docs/plan/acceptance/screenshots')
  fs.mkdirSync(screenshotDir, { recursive: true })

  for (const demo of DEMOS) {
    await page.goto(`/records?review=${encodeURIComponent(demo.reviewId)}`)
    const drawer = page.locator('.el-drawer')
    await expect(drawer).toBeVisible()
    await expect(drawer.getByTestId('artifact-group-claim')).toBeVisible()
    await expect(drawer.getByTestId('artifact-group-table')).toBeVisible()
    await expect(drawer.getByTestId('artifact-group-citation')).toBeVisible()
    await expect(drawer.getByTestId('artifact-panel')).not.toContainText('本篇未抽取到产物')

    if (demo.locate === 'claim') {
      await drawer.getByTestId('artifact-group-claim').locator('button').first().click()
    } else {
      await drawer.getByTestId('artifact-group-table').locator('button').first().click()
    }
    await expect(drawer.getByTestId('artifact-mark')).toBeVisible()
    await drawer.screenshot({ path: path.join(screenshotDir, `v3.5.5-artifacts-${demo.name}.png`) })
  }
})
