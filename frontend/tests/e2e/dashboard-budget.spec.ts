import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { gzipSync } from 'node:zlib'

type JsBytes = { raw: number; gzip: number }

async function collectJs(page: import('@playwright/test').Page) {
  const pending: Promise<JsBytes | null>[] = []
  page.on('response', (response) => {
    if (!/\.js(?:$|\?)/.test(response.url())) return
    pending.push((async () => {
      const headers = await response.allHeaders()
      const body = await response.body()
      const raw = body.byteLength
      const encoding = headers['content-encoding']?.toLowerCase()
      const wireGzip = encoding?.includes('gzip')
        ? Number(headers['content-length']) || gzipSync(body).byteLength
        : gzipSync(body).byteLength
      return { raw, gzip: wireGzip }
    })().catch(() => null))
  })
  return async (): Promise<JsBytes> => {
    const rows = (await Promise.all(pending)).filter((row): row is JsBytes => row !== null)
    return rows.reduce((sum, row) => ({ raw: sum.raw + row.raw, gzip: sum.gzip + row.gzip }), { raw: 0, gzip: 0 })
  }
}

test('records actual first-screen JS and deferred dashboard bytes', async ({ browser }) => {
  const baselines = { raw: 1_117_182, gzip: 355_880 }
  const teacherState = JSON.parse(fs.readFileSync('./tests/e2e/.auth/teacher.json', 'utf8'))
  teacherState.origins[0].origin = 'http://127.0.0.1:5174'
  const context = await browser.newContext({
    baseURL: 'http://127.0.0.1:5174',
    storageState: teacherState,
  })
  const page = await context.newPage()
  await page.route('**/api/dashboard/summary', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      cached: false,
      cards: { total_submissions: 0, weekly_new: 0, parse_only: 0, pending_conflicts: 0, gold_agreement: null },
      contests: [], bands: [], insufficient_top: [], conflicts: [], hotspots: [],
      citation: { failure_count: 0, total_dimensions: 0, citation_rate: 0 }, gold: null,
    }),
  }))
  await page.route('**/api/dashboard/trend**', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ cached: false, days: 30, series: [] }),
  }))
  const parseBytes = await collectJs(page)
  await page.goto('/parse')
  await page.waitForLoadState('load')
  const parse = await parseBytes()

  const recordsPage = await context.newPage()
  const recordsBytes = await collectJs(recordsPage)
  await recordsPage.goto('/records')
  await recordsPage.waitForLoadState('load')
  const records = await recordsBytes()
  await recordsPage.close()

  const beforeDashboard = await context.newPage()
  const dashboardBytes = await collectJs(beforeDashboard)
  const started = performance.now()
  await beforeDashboard.goto('/dashboard')
  await expect(beforeDashboard.locator('[data-dashboard-module]')).toHaveCount(8)
  const dashboardMs = performance.now() - started
  const dashboard = await dashboardBytes()

  const withinRaw = baselines.raw + 10_240
  const withinGzip = baselines.gzip + 10_240
  console.log(`BUDGET parse raw=${parse.raw} gzip=${parse.gzip} deltaRaw=${parse.raw - baselines.raw} deltaGzip=${parse.gzip - baselines.gzip}`)
  console.log(`BUDGET records raw=${records.raw} gzip=${records.gzip} deltaRaw=${records.raw - baselines.raw} deltaGzip=${records.gzip - baselines.gzip}`)
  console.log(`BUDGET dashboard extra raw=${dashboard.raw} gzip=${dashboard.gzip} interactive=${dashboardMs.toFixed(1)}ms`)
  expect(parse.raw).toBeLessThanOrEqual(withinRaw)
  expect(parse.gzip).toBeLessThanOrEqual(withinGzip)
  expect(records.raw).toBeLessThanOrEqual(withinRaw)
  expect(records.gzip).toBeLessThanOrEqual(withinGzip)
  expect(dashboardMs).toBeLessThanOrEqual(2000)
  await beforeDashboard.close()
  await context.close()
})
