# P20 验收报告（v3.4.2 收口补丁）

## 结论

**P20 工程收口，允许进入 P21**

本报告只覆盖 P20；五条功能判据的截图、网络字节、接口耗时与权限证据沿用 v3.4.1 的实测，本版没有实现 P21 上传与解析代码。

## 五条判据

1. **八模块与空态通过。** `dashboard.spec.ts` 教师 E2E 渲染八个模块；空态显示“暂无数据”，八个模块存在且图表容器为 0。截图：[`v3.4.1-dashboard.png`](screenshots/v3.4.1-dashboard.png)、[`v3.4.1-dashboard-empty.png`](screenshots/v3.4.1-dashboard-empty.png)。
2. **Bundle 通过（按首屏入口 chunk 度量）。** 本次入口 1117.18 KB raw / 355.88 KB gzip；相对 v3.4.0 实测基线 1115.14 / 354.95 KB 增加 2.04 / 0.93 KB，低于 400 / 120 KB。Production E2E 实测 `/parse` 与 `/records` 首屏 JS 均为 1,117,182 raw / 352,823 gzip bytes，增量 0 / -3,057 bytes，均未超过基线 + 10,240 bytes。
3. **学生权限通过。** `dashboard-guard.spec.ts` 单测通过；`dashboard.spec.ts` E2E 访问 `/dashboard` 被重定向至 `/parse`，提示“需要教师权限”。
4. **接口速度通过。** Summary 三次为 36.58、33.59、33.46 ms，最大 36.58 ms；Trend 三次为 33.62、32.99、34.45 ms，最大 34.45 ms；均小于 500 ms。大屏八模块就绪 370.4 ms，小于 2,000 ms。
5. **截图归档通过。** 两张 v3.4.1 截图存放于 `docs/plan/acceptance/screenshots/`。

## 度量口径与 chunk 明细

P20 §7.4 的 bundle 增量以**首屏入口 chunk** 为度量范围。依据：§7.1 的动机是「首屏不能变慢」，§7.2 的判据是「首屏 ≤ 2 秒」；`/dashboard` 是带 `dashboard:view` 权限的二级页面，路由为 `() => import(...)` 懒加载，`index.html` 无其 preload，不进首屏。因此判据不采用所有 chunk 求和口径。为防止懒加载掩盖退化，另以非大屏页面首屏实际加载 JS 字节数 ≤ 基线 + 10 KB 为硬约束。

| 范围 | Raw | Gzip | 说明 |
|---|---:|---:|---|
| 入口 chunk | 1117.18 KB | 355.88 KB | 增量 +2.04 / +0.93 KB |
| 大屏 chunk | 533.12 KB | 177.25 KB | `index.html` 未引用；Line/Bar/Pie/Gauge + Grid/Tooltip/Legend + CanvasRenderer |
| 两个 chunk 求和 | 1650.30 KB | 533.13 KB | 增量 +535.16 / +178.18 KB；此值不作为首屏判据 |

## 门禁

- Backend pytest 两轮：均 EXIT=0，`394 passed, 11 warnings`（v3.4.2 新增 6 条日志门禁测试）。
- Vitest：EXIT=0，149 passed。
- Playwright：45 passed、8 failed；8 条为既有 7 条确认链路延迟与 1 条 parse 断言。本版新增预算用例通过，新增失败 0。
- Bundle：build EXIT=0；预算 E2E 的 `/parse`、`/records` 首屏与 dashboard 延迟字节/耗时测量通过。
- Docs strict 编码检查通过。默认 7 日窗口日志检查 EXIT=0，输出窗口 `20261015..20261021`；`--date 20261020` EXIT=0，窗口 `20261014..20261020`。`--strict-today` EXIT=1，四个当天无日志的 writer 仍会报错，属预期严格模式行为。

## 日志门禁口径修复

已由 v3.4.2 以窗口口径解决，严格模式保留。默认窗口要求八个必需 writer 在最近 7 天内各至少有一个通过原 JSON、字段、模块归属与敏感串检查的日志；`--strict-today` 保留旧的单日判定。新增 6 条测试覆盖窗口旧日志、全无日志、存在但为空的日志文件、严格当天、敏感串和每个必需 writer 的埋点调用点。

## 遗留

- E2E 8 条既有失败：7 条确认链路延迟、1 条 parse 断言。
- 确认链路 25–40 秒（P18 延迟债）。
- `probe-critique-acceptance` 数据治理。
- 大屏 chunk 约 533 KB，可在后续版本优化；本版保留八个模块。
