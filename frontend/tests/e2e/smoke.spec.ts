import { expect, test } from '@playwright/test'

const NAV = [
  { label: '论文解析', path: '/parse' },
  { label: '分项评分', path: '/scoring' },
  { label: '一致性审查', path: '/consistency' },
  { label: '修改建议', path: '/suggestions' },
  { label: '评测对照', path: '/eval' },
]

test('五个导航入口逐个点开都能看到各自的页面标题', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/parse$/)
  await expect(page.locator('h1')).toHaveText(NAV[0]?.label ?? '')

  for (const item of NAV.slice(1)) {
    await page.getByRole('link', { name: item.label, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`${item.path}$`))
    await expect(page.locator('h1')).toHaveText(item.label)
  }

  // 带参数的那条路由用同一个组件
  await page.goto('/eval/demo-01')
  await expect(page.locator('h1')).toHaveText('评测对照')
})

test('经 5173 的 Vite 代理请求 /api/contests，拿到恰好三道已发布赛题', async ({ request }) => {
  const response = await request.get('/api/contests')
  expect(response.status()).toBe(200)

  const body = (await response.json()) as {
    contests: Array<{ status: string; rubric: { rubric_id: string } | null }>
  }

  expect(body.contests).toHaveLength(3)
  for (const contest of body.contests) {
    expect(contest.status).toBe('published')
    expect(contest.rubric?.rubric_id).toBeTruthy()
  }
})
