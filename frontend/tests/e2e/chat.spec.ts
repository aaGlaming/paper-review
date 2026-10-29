import { expect, test } from '@playwright/test'

test.describe('教师问询页', () => {
test.use({ storageState: './tests/e2e/.auth/teacher.json' })

test('教师可打开 AI 问询页并新建会话', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByRole('heading', { name: 'AI 问询' })).toBeVisible()
  await expect(page.getByRole('complementary', { name: '问询会话' })).toBeVisible()
  await expect(page.getByRole('region', { name: '问询消息' })).toBeVisible()
  await expect(page.getByText('你正在问询全部', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '新建会话' }).click()
  await expect(page.getByText('某条记录的假设维为什么判证据不足？')).toBeVisible()
  await expect(page.getByText('这道题有多少学生的建模维是证据不足？')).toBeVisible()
  await expect(page.getByText('把本周提交整理成一段教研会摘要')).toBeVisible()
})

test('例问填入输入框，冲突汇总不调用问答模型', async ({ page }) => {
  await page.goto('/chat')
  await page.getByRole('button', { name: '新建会话' }).click()
  await page.getByRole('button', { name: '某条记录的假设维为什么判证据不足？' }).click()
  await expect(page.getByRole('textbox', { name: '问询内容' })).toHaveValue('某条记录的假设维为什么判证据不足？')
  await page.getByRole('button', { name: '冲突汇总' }).click()
  await expect(page.locator('[data-analytics-result]')).toBeVisible()
})
})

test('学生直接访问问询页会回到解析页', async ({ page }) => {
  await page.goto('/chat', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/parse$/)
})
