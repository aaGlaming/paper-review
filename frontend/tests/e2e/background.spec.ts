// 背景走查：每页独立背景插画（PageArt 双图）真实生效且不挡内容。
import { expect, test } from '@playwright/test'

const PAGE_ART: Record<string, [string, string]> = {
  // 每页大图/小图的 data URL 内容标记（中文注释，Vite 内联保留）
  '/parse': ['解析页背景', '赛题标签'],
  '/scoring': ['评分面背景', '砝码天平'],
  '/consistency': ['审查页背景', '对账单'],
  '/suggestions': ['建议页背景', '铅笔改稿'],
  '/eval': ['评测页背景', '样例对照卡'],
}

for (const [path, marks] of Object.entries(PAGE_ART)) {
  test(`${path} 有独立背景双图、不挡交互`, async ({ page }) => {
    await page.goto(path)
    await expect(page.locator('.page-art__main')).toBeVisible()
    await expect(page.locator('.page-art__spot')).toBeVisible()

    const probe = await page.evaluate(() => {
      const main = document.querySelector('.page-art__main') as HTMLImageElement
      const spot = document.querySelector('.page-art__spot') as HTMLImageElement
      const cs = getComputedStyle(main)
      return {
        mainSrc: main.currentSrc || main.src,
        spotSrc: spot.currentSrc || spot.src,
        events: cs.pointerEvents,
        opacity: Number(cs.opacity),
        mainW: main.getBoundingClientRect().width,
      }
    })

    // 每页自己的大图/小图（Vite 内联成 data URL，断内容里的中文注释标记）
    expect(decodeURIComponent(probe.mainSrc), `${path} 大图`).toContain(marks[0])
    expect(decodeURIComponent(probe.spotSrc), `${path} 小图`).toContain(marks[1])
    // 穿透、不抢内容
    expect(probe.events).toBe('none')
    expect(probe.opacity).toBeLessThanOrEqual(0.4)
    expect(probe.mainW).toBeGreaterThan(0)
  })
}

test('全局照片底图生效：铺满视口、在内容之下、不挡交互', async ({ page }) => {
  await page.goto('/parse')
  await expect(page.locator('h1')).toHaveText('论文解析')

  const probe = await page.evaluate(() => {
    const el = document.querySelector('.photo-bg') as HTMLElement
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    return {
      image: cs.backgroundImage,
      size: cs.backgroundSize,
      events: cs.pointerEvents,
      z: cs.zIndex,
      w: Math.round(r.width),
      h: Math.round(r.height),
      vw: window.innerWidth,
      vh: window.innerHeight,
    }
  })

  // 照片 + 纱罩两层（纱罩是 linear-gradient，照片是 jpg）
  expect(probe.image).toContain('linear-gradient')
  expect(probe.image).toContain('.jpg')
  expect(probe.size).toContain('cover')
  // 铺满视口、在内容之下、穿透
  expect(probe.w).toBeGreaterThanOrEqual(probe.vw - 1)
  expect(probe.h).toBeGreaterThanOrEqual(probe.vh - 1)
  expect(Number(probe.z)).toBeLessThan(0)
  expect(probe.events).toBe('none')
})

test('背景三层生效：网格/线稿有尺寸、内容区可点', async ({ page }) => {
  await page.goto('/parse')
  await expect(page.locator('h1')).toHaveText('论文解析')

  const probe = await page.evaluate(() => {
    const shellBefore = getComputedStyle(document.querySelector('.shell')!, '::before')
    const bodyBefore = getComputedStyle(document.querySelector('.shell__body')!, '::before')
    return {
      draftImage: shellBefore.backgroundImage.slice(-30),
      draftOpacity: shellBefore.opacity,
      cornerImage: bodyBefore.backgroundImage.slice(-30),
      cornerOpacity: bodyBefore.opacity,
      shellEvents: shellBefore.pointerEvents,
    }
  })

  // 线稿与角标贴上各自的 SVG（Vite 把小 SVG 内联成 data URL，断 svg 标记即可）
  expect(probe.draftImage).toContain('svg')
  expect(probe.cornerImage).toContain('svg')
  // 透明度在氛围区间（可见但不抢内容：线稿 ≤0.35，角标 ≤0.4）
  expect(Number(probe.draftOpacity)).toBeLessThanOrEqual(0.35)
  expect(Number(probe.cornerOpacity)).toBeLessThanOrEqual(0.4)
  // 穿透
  expect(probe.shellEvents).toBe('none')

  // 内容可交互：导航五个入口都能点
  await page.getByRole('link', { name: '评测对照', exact: true }).click()
  await expect(page.locator('h1')).toHaveText('评测对照')
})
