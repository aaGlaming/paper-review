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

test('经 5173 的 Vite 代理请求 /api/contests，三道正式赛题均已发布且带量规', async ({ request }) => {
  const response = await request.get('/api/contests')
  expect(response.status()).toBe(200)

  const body = (await response.json()) as {
    contests: Array<{
      contest_id: string
      year: number
      problem_code: string
      status: string
      rubric: { rubric_id: string } | null
    }>
  }

  // 不断死总数（验收探针包也会 published 入库）；
  // 改断三道正式赛题（年份 + 题号定位，不写赛题 ID 字面量，见 source-scan 禁令）
  // 都在、都是 published、都带 rubric——比数数更严。
  const required = [
    { year: 2024, problem_code: 'A' },
    { year: 2024, problem_code: 'C' },
    { year: 2025, problem_code: 'A' },
  ]
  for (const { year, problem_code } of required) {
    const contest = body.contests.find(
      (item) => item.year === year && item.problem_code === problem_code,
    )
    expect(contest, `${year}/${problem_code}`).toBeTruthy()
    expect(contest?.status).toBe('published')
    expect(contest?.rubric?.rubric_id).toBeTruthy()
  }
})
