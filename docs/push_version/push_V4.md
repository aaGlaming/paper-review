# paper-review 第四版（push_V4 · 前端第二版上传）完整说明

> **文档用途**：作为分支 `v1.8.2_Frontend-Version-2` 推送 GitHub 之前的版本档案，供后续开发开始前先行阅读。
> **生成时间**：2026-10-17 19:45
> **代码目录**：`D:\LEARN\AI\programs\AgentTask\Projects\paper-review`
> **代码仓库**：https://github.com/aaGlaming/paper-review
> **本版分支**：`v1.8.2_Frontend-Version-2`
> **本版提交**：`5ec493c` — commit message：**前端第二版上传**；49 个文件、+2075 / −214 行（另含 2 个二进制资产）
> **上一分支**：`v1.8.0_First-version-modification-of-the-frontend`（`3fb98a8`，即 push_V3 记录的「前端第一版修改」）
> **质量基线**：`npm run build` 0 · `vitest` **106 passed** · `playwright` **43 passed** · `pytest backend/tests` **134 passed**（四道门禁均于提交前复跑，退出码全 0）
> **事实来源**：本文件所有结论均为实测（门禁实跑、`git diff --cached --name-status` 实查、源码实读、`du` 实测文件体积）；未使用推测值。

---

## 1. 这一版做了什么

第三版（push_V3）交付的是**五个页面 + 手稿风格 + 昼夜主题**。用户此前的反馈是"页面过于单调、内容布局缺少视觉焦点、页面之间构图过于相似，整体像未经精细设计的基础原型"。

于是先有设计提示词 `docs/version/10.17/v1.9.0_前端页面重新设计.md`（Phase 1 — Editorial Layout Refinement），再由执行方落地成本版：**编辑式排版细化 + 每页背景画 + 空态插画**。

```text
push_V3（第一版修改）                push_V4（本版）
──────────────────────────          ──────────────────────────
页面构图相似、缺视觉焦点       →   非对称双栏、层级化标题、节奏化留白
空态是纯文字                  →   五个空态各配一张手稿插画
页面只有纸底                  →   每页一幅大图 + 一幅小图的背景画
测试 97 单测 + 19 E2E         →   测试 106 单测 + 43 E2E
```

### 1.1 改动范围（`git diff --cached --name-status` 实测，49 个文件）

| 状态 | 文件 | 说明 |
|---|---|---|
| **A** | `frontend/src/components/PageArt.vue` | 每页背景画组件（大图 + 小图双图组合） |
| **A** | `frontend/src/components/illustrations/` 6 个 `.vue` | `EmptyIllustration` / `ParseEmptyIllustration` / `ScoringEmptyIllustration` / `ConsistencyEmptyIllustration` / `SuggestionsEmptyIllustration` / `EvalSingleIllustration` |
| **A** | `frontend/src/assets/sketch/` 14 个 SVG + 1 个 JPG | 5 个 `bg-*`、5 个 `spot-*`、`sketch-corner-mark`、`sketch-margin-draft`、`photo-background.jpg` |
| **A** | `docs/design/sketch-svg/` 13 个 SVG | 设计源，与前端资产两份一致 |
| **A** | `frontend/pictures/background.png` | 设计源稿（2.5 MB，未被前端引用，仅作源档留存） |
| **A** | `frontend/tests/unit/background.spec.ts` | 背景画单测（94 行） |
| **A** | `frontend/tests/unit/illustrations.spec.ts` | 插画单测（54 行） |
| **A** | `frontend/tests/e2e/background.spec.ts` | 背景画 E2E（101 行） |
| **A** | `frontend/tests/e2e/polish-audit.spec.ts` | 排版审计 E2E（77 行） |
| **A** | `docs/version/10.17/v1.9.0_前端页面重新设计.md` | 本轮设计提示词（19,211 B） |
| **M** | `frontend/src/App.vue` | 布局骨架接入背景画 |
| **M** | `frontend/src/views/` 五个页面 | 编辑式排版细化（改动量最大：解析页 +142/−47、评分页 +49/−46、建议页 +44/−45、评测页 +59/−37） |
| **M** | `frontend/src/components/SectionReader.vue`、`SectionTree.vue` | 排版细化 |
| **M** | `frontend/src/styles/sketch.css` | 新增背景画与插画复用类 |
| **M** | `frontend/src/styles/tokens.css` | 末尾追加背景画透明度等令牌，**既有令牌一行未动** |
| **M** | `.gitignore` | 补 `.pytest_tmp/` |

**未改动**：`backend/` 全部、`frontend/src/api/`、`frontend/src/router/`、`frontend/src/composables/`、`ThemeToggle.vue`、`useTheme.ts`、五个视图之外的组件。

---

## 2. 核心实现

### 2.1 `PageArt.vue` — 每页背景画

| 项 | 内容 |
|---|---|
| 形态 | **大图 + 小图双图组合**，大图贴内容区一侧空白、小图贴另一处留白 |
| 定位 | `position: fixed`，不占文档流、不推挤内容 |
| 无障碍 | 容器与两张图均 `aria-hidden="true"`，**不进无障碍树** |
| 交互 | `pointer-events: none`，**不挡任何点击**（E2E 有点击穿透断言） |
| 配色 | 走墨色变量 + 透明度令牌，**跟随昼夜主题**，不需要两套图 |
| 响应式 | `900px` 以下只留小图（大图隐藏）、`390px` 以下全藏，不挤内容 |
| 用法 | 页面传 `art`（大图）与 `spot`（小图）两个地址，可选 `layout: 'right' \| 'left'` |

### 2.2 15 个新增 SVG 资产

| 文件 | 用途 |
|---|---|
| `bg-parse` / `bg-scoring` / `bg-consistency` / `bg-suggestions` / `bg-eval` | 五个页面各一幅大图 |
| `spot-parse` / `spot-scoring` / `spot-consistency` / `spot-suggestions` / `spot-eval` | 五个页面各一幅小图 |
| `sketch-corner-mark` | 页缘角标 |
| `sketch-margin-draft` | 页缘线稿 |
| `photo-background.jpg` | 纸张照片底图（188 KB） |

全部沿用既有绘制约定：`stroke="currentColor"`、路径微弯不取直、`stroke-linecap/linejoin="round"`、`fill="none"`、无十六进制色值、无渐变、无滤镜、无动画。设计源落在 `docs/design/sketch-svg/`，与 `frontend/src/assets/sketch/` 两份一致。

### 2.3 空态插画（6 个组件）

`components/illustrations/` 下每个空态一张手稿插画，空态从"纯文字说明"变成"插画 + 说明 + 去向链接"：

| 组件 | 用在 |
|---|---|
| `ParseEmptyIllustration` | 解析页无章节树时 |
| `ScoringEmptyIllustration` | 评分页无报告时 |
| `ConsistencyEmptyIllustration` | 审查页无结果时 |
| `SuggestionsEmptyIllustration` | 建议页无建议时 |
| `EvalSingleIllustration` | `/eval/:paperId` 单篇占位 |
| `EmptyIllustration` | 通用兜底 |

### 2.4 编辑式排版（五个页面 + 两个组件）

按设计提示词的要求落地，不新建组件系统、不改变业务逻辑：

- **非对称双栏**替代均分双栏，内容列比例不一；
- **层级化标题**：页面主标题 → 副标题 → 区块标题 → 元信息，字号与字重逐级递减；
- **大小不一但有逻辑关系的内容模块**，替代此前的等宽卡片平铺；
- **横向分组 + 纵向节奏 + 留白**，让每页有可辨的构图；
- 复用既有组件与主题变量，`tokens.css` 只在末尾追加新令牌。

---

## 3. 测试与门禁

### 3.1 新增测试（4 个文件、326 行）

| 文件 | 断言重点 |
|---|---|
| `unit/background.spec.ts` | 背景画 `aria-hidden`、不渲染进无障碍树、颜色走令牌 |
| `unit/illustrations.spec.ts` | 6 个插画组件均可挂载、无裸色值、无 emoji |
| `e2e/background.spec.ts` | **点击穿透**（背景画上方点按钮仍生效）、双主题下可见、900/390px 响应式收起 |
| `e2e/polish-audit.spec.ts` | 五页标题层级、非对称布局存在、无横向滚动 |

### 3.2 四道门禁（提交前复跑，退出码全 0）

| 门禁 | 结果 | 与 push_V3 对比 |
|---|---|---|
| `npm run build`（含 `vue-tsc --noEmit`） | 退出码 **0**，✓ built in 1.60s | 持平 |
| `npx vitest run` | **106 passed**（16 个 spec） | 97 → **+9** |
| `npx playwright test` | **43 passed** | 19 → **+24** |
| `pytest backend/tests -q` | **134 passed in 7.54s** | 持平（后端零改动） |

---

## 4. 两处仓库卫生处理

### 4.1 `.gitignore` 补 `.pytest_tmp/`

本机 pytest 有环境坑：默认临时根在 `%TEMP%`，清理旧目录时一次删 85 个文件会被安全策略拦截，表现为**测试全绿但退出码 1**。解法是 `PYTEST_DEBUG_TEMPROOT` 指向项目内的 `.pytest_tmp/`。但该目录**此前未被 `.gitignore` 覆盖**，`git add -A` 会把上百个测试临时文件一起带入暂存区。本版在 `.gitignore` 末尾补上一行，并已把误入的文件撤出暂存区（提交内容里 0 个 `.pytest_tmp/` 文件）。

### 4.2 恢复 `docs/design/sketch-preview.png`

该文件（317,659 B）**连续第二次**处于"已删除"状态，而 `docs/design/sketch-style.md` 第 13 行仍写着"或直接看 `docs/design/sketch-preview.png`"。删除它会留下断链引用，且文件已在 `65c6449` 入库、恢复无成本，因此本版再次恢复。

> **若确认不再保留该二进制样张**，正确做法是同步修改 `sketch-style.md` 第 13 行的引用（例如改为"用 `frontend/shot-sketch.mjs` 重新生成"），而不是单删文件。

---

## 5. 遗留问题（本版未处理）

| # | 事项 | 说明 |
|---|---|---|
| 1 | **模型未实测** | `.env` 已配 DeepSeek（`deepseek-v4-flash`），选档仍走确定性回退；`deepseek-v4-flash` 默认开 thinking 模式，首次接入必须实测 JSON 能否解析 |
| 2 | **5 个后端接口缺口** | 量规条文、单篇评测、`EMBEDDING_BASE_URL` 独立配置、真实重排、审查结果落库 |
| 3 | **主张 / 表格 / 引用未产出** | 解析页三个预留位 |
| 4 | 论文文件上传 | 只收 Markdown 文本或 `sample_id` |
| 5 | 三篇演示稿无 `gold` | 评测可算样本 12 篇，需求要 15 篇 |
| 6 | 可观测性为零 | 无应用日志、无 `/metrics`、无链路追踪、无健康检查 |
| 7 | `compose.yaml` 空壳 | 四服务无可运行配置 |
| 8 | bundle 未拆包 | Element Plus 全量引入；本版新增 15 个 SVG 与 1 个 JPG 后体积进一步上升 |
| 9 | E2E 写库污染 | `review` / `review_dimension` / `review_session` 持续增长，无删除接口 |
| 10 | `frontend/pictures/background.png` 2.5 MB | 设计源稿，未被前端引用；入库是为保留源档，若介意体积可在后续版本改存外链 |

---

## 附录 A：分支与提交关系

```text
main                                              2a6964b  后端V1推送
 ├─ v1.8.0_Frontend-draft                         65c6449  docs: 补 push_V2 版本档案
 │   └─ 1c5d024  P8前端完成：五个页面 + 手稿风格设计 + 文档体系
 ├─ v1.8.0_First-version-modification-of-the-frontend
 │                                                  3fb98a8  docs: 补 push_V3 版本档案
 │   └─ 0af0e56  前端第一版修改（昼夜主题）
 └─ v1.8.2_Frontend-Version-2                       5ec493c  前端第二版上传   ← 本版
```

| 项 | 值 |
|---|---|
| 本版分支 | `v1.8.2_Frontend-Version-2` |
| 本版提交 | `5ec493c` |
| 规模 | 49 个文件，+2075 / −214 行（另含 `background.png` 2.5 MB 与 `photo-background.jpg` 188 KB 两个二进制） |
| 基线提交 | `3fb98a8` |
| 远程 | https://github.com/aaGlaming/paper-review |
| PR 入口 | https://github.com/aaGlaming/paper-review/pull/new/v1.8.2_Frontend-Version-2 |

**推送前安全检查（已执行）**：暂存区无 `.env`、无 `node_modules/`、无 `dist/`、无 `playwright-report/`、无 `test-results/`、**无 `.pytest_tmp/`**（该目录曾被 `git add -A` 误入 38 个临时文件，已撤出并补进 `.gitignore`）；`git ls-files --error-unmatch .env` 确认 `.env` 未被追踪。

## 附录 B：常用命令

```text
# 四道门禁（当前预期：build 0 / vitest 106 / playwright 43 / pytest 134）
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm run build && npx vitest run && npx playwright test
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q

# pytest 环境坑（测试全绿但退出码 1 时；目录需先存在）
mkdir -p .pytest_tmp
$env:PYTEST_DEBUG_TEMPROOT="D:\LEARN\AI\programs\AgentTask\Projects\paper-review\.pytest_tmp"

# MySQL（StartType=Manual，开机不自启）
Start-Process "D:\MySQL\Server8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=D:\MySQL\my.ini" -WindowStyle Hidden

# 8077 被占用时
$c = Get-NetTCPConnection -LocalPort 8077 -ErrorAction SilentlyContinue
if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }

# 切到本版分支
git checkout v1.8.2_Frontend-Version-2
```
