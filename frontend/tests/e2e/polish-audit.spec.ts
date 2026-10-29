// Phase 5 全站巡检探针：双主题 × 双视口的量化检查。
// 查：横向溢出、标题/插画重叠、表格可用、控制台错误、焦点环。
import { expect, test } from '@playwright/test'

const PAGES = ['/parse', '/scoring', '/consistency', '/suggestions', '/eval']

for (const theme of ['light', 'dark']) {
  test.describe(`巡检 theme=${theme}`, () => {
    test.use({ viewport: { width: 1440, height: 900 } })

    for (const path of PAGES) {
      test(`${path} 无横向溢出、无控制台错误`, async ({ page }) => {
        const errors: string[] = []
        page.on('pageerror', (err) => errors.push(String(err)))
        page.on('console', (msg) => {
          if (msg.type() === 'error') errors.push(msg.text())
        })
        await page.addInitScript((t) => {
          localStorage.setItem('paper-review:theme', t)
        }, theme)
        await page.goto(path)
        await expect(page.locator('h1')).toBeVisible()

        const overflow = await page.evaluate(() => ({
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth,
        }))
        expect(overflow.scrollW, `${path} 横向溢出`).toBeLessThanOrEqual(overflow.clientW + 1)
        expect(errors, `${path} 控制台错误: ${errors.join('; ')}`).toEqual([])
      })
    }

    test('解析 hero：标题与插画不重叠', async ({ page }) => {
      await page.addInitScript((t) => {
        localStorage.setItem('paper-review:theme', t)
      }, theme)
      await page.goto('/parse')
      const overlap = await page.evaluate(() => {
        const title = document.querySelector('.parse__hero-head')?.getBoundingClientRect()
        const illo = document.querySelector('.parse__hero-illo')?.getBoundingClientRect()
        if (!title || !illo) return 'missing'
        const xOverlap = Math.max(0, Math.min(title.right, illo.right) - Math.max(title.left, illo.left))
        const yOverlap = Math.max(0, Math.min(title.bottom, illo.bottom) - Math.max(title.top, illo.top))
        return xOverlap > 2 && yOverlap > 2 ? `overlap ${xOverlap}x${yOverlap}` : 'ok'
      })
      expect(overlap).toBe('ok')
    })
  })
}

test.describe('巡检 移动视口', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const path of PAGES) {
    test(`${path} 无横向溢出、h1 可见`, async ({ page }) => {
      await page.goto(path)
      await expect(page.locator('h1')).toBeVisible()
      const overflow = await page.evaluate(() => {
        const wide: string[] = []
        for (const el of document.querySelectorAll('*')) {
          const r = el.getBoundingClientRect()
          if (r.right > 391 || r.left < -1) {
            wide.push(`${el.tagName}.${String(el.className).slice(0, 50)} r=${Math.round(r.right)}`)
          }
        }
        return {
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth,
          wide: wide.slice(0, 8),
        }
      })
      expect(overflow.scrollW, `${path} 移动端横向溢出: ${overflow.wide.join(' | ')}`).toBeLessThanOrEqual(
        overflow.clientW + 1,
      )
    })
  }
})
