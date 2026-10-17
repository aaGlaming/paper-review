# paper-review 第三版（push_V3 · 前端第一版修改）完整说明

> **文档用途**：作为分支 `v1.8.0_First-version-modification-of-the-frontend` 推送 GitHub 之前的版本档案，供后续开发开始前先行阅读。
> **生成时间**：2026-10-17 17:05
> **代码目录**：`D:\LEARN\AI\programs\AgentTask\Projects\paper-review`
> **代码仓库**：https://github.com/aaGlaming/paper-review
> **本版分支**：`v1.8.0_First-version-modification-of-the-frontend`
> **本版提交**：`0af0e56` — commit message：**前端第一版修改**；18 个文件、+1149 / −5 行
> **上一分支**：`v0.9.0-p8-frontend` 已重命名为 **`v1.8.0_Frontend-draft`**（远程旧名已删除，指向 `65c6449`）
> **质量基线**：`npm run build` 0 · `vitest` **97 passed** · `playwright` **19 passed** · `pytest backend/tests` **134 passed**（四道门禁均于提交前复跑，退出码全 0）
> **事实来源**：本文件所有结论均为实测（门禁实跑、`git diff --cached --name-status` 实查、源码实读）；未使用推测值。

---

## 1. 这一版做了什么

第二版（`push_V2`，分支 `v1.8.0_Frontend-draft`）交付的是**五个页面 + 手稿风格设计资产**。用户看过截图后的反馈是"并没有完全改成手稿风，而且前端展示的一致性不好"，于是先有 `v1.8.7` 修掉三个 bug（圈注跑位、评测折线图为静态图、修改建议页未手稿化），再有本版做**前端整体手稿风改造 + 昼夜主题**。

```text
push_V2（Frontend-draft）            push_V3（本版）
──────────────────────────          ──────────────────────────
五页已上手绘元素但有 3 个 bug   →   三个 bug 已修（v1.8.7）
只有白天模式                   →   白天 / 黑夜双主题
无主题切换入口                  →   导航栏 ThemeToggle 按钮
tokens.css 无暗色令牌           →   追加 [data-theme='dark'] 覆盖块
测试 92 单测 + 18 E2E          →   测试 97 单测 + 19 E2E
```

### 1.1 改动范围（`git diff --cached --name-status` 实测）

| 状态 | 文件 | 说明 |
|---|---|---|
| **A** | `frontend/src/composables/useTheme.ts` | 主题状态组合式函数 |
| **A** | `frontend/src/components/ThemeToggle.vue` | 主题切换按钮 |
| **A** | `frontend/src/assets/sketch/sketch-sun.svg` | 白天图标 |
| **A** | `frontend/src/assets/sketch/sketch-moon.svg` | 黑夜图标 |
| **A** | `frontend/tests/unit/theme-toggle.spec.ts` | 主题单测（72 行） |
| **A** | `frontend/tests/e2e/theme.spec.ts` | 主题 E2E |
| **A** | `docs/design/sketch-svg/sketch-sun.svg` | 设计源（与前端资产字节一致） |
| **A** | `docs/design/sketch-svg/sketch-moon.svg` | 设计源 |
| **A** | `docs/version/explain/v1.0.1_前端页面修改说明.md` | 本轮修改总说明 |
| **A** | `docs/version/explain/v1.0.2_前端页面修改说明.md` | 新增 SVG 清单 |
| **A** | `docs/version/explain/项目进度报告V3.md` | 全量进度快照 |
| **M** | `frontend/src/components/AppNav.vue` | 导航栏放入切换按钮 |
| **M** | `frontend/src/main.ts` | 初始化主题 |
| **M** | `frontend/src/styles/tokens.css` | 末尾追加暗色覆盖块（既有令牌一行未动） |
| **M** | `frontend/tests/unit/sketch-fix.spec.ts` | 适配主题 |
| **M** | `frontend/tests/unit/visual-contract.spec.ts` | 适配主题 |
| **R100** | `docs/开发任务拆解与迭代流程.md` → `docs/questions/同名` | 纯移动，**内容零改动** |
| **R100** | `docs/项目文件树.md` → `docs/questions/同名` | 纯移动，**内容零改动** |

**未改动**：`backend/` 全部、`frontend/src/api/`、`frontend/src/router/`、`frontend/src/views/`、`frontend/src/composables/` 下其余三个、`frontend/src/components/` 下其余七个、`.env`、`compose.yaml`、`CLAUDE.md`。

### 1.2 一处主动恢复

工作区里 `docs/design/sketch-preview.png`（317,659 B）处于**已删除**状态，但 `docs/design/sketch-style.md` §0 明确写着"或直接看 `docs/design/sketch-preview.png`"。删除它会留下断链引用，且该文件已在 `65c6449` 入库、恢复无成本，因此本版**将其恢复**。若后续决定不保留二进制样张，应同步修改设计文档的引用，而不是单删文件。

---

## 2. 核心实现：昼夜主题

### 2.1 `useTheme.ts` — 主题状态

| 项 | 内容 |
|---|---|
| 状态 | `'light' \| 'dark'` 两态，**不引入第三种** |
| 持久化 | `localStorage`，键 `paper-review:theme`，跨会话记住偏好 |
| 与评审流程的存储隔离 | 评审流程用 `sessionStorage`（键 `paper-review:review-flow`），主题用 `localStorage`——**两者分开**，清会话不影响主题偏好 |
| 缺省值 | 无存储时取 `light`（白天） |
| 依赖 | **零**。只用 `vue` 的 `ref`，不装 Pinia、不装 vueuse |
| 副作用 | 只改根节点 `data-theme` 属性与配色，**不改布局、字体、组件结构与手绘风格** |
| 无定时器、无网络请求 | 源码内无 `setInterval` / `setTimeout` / `fetch` |

### 2.2 `ThemeToggle.vue` — 切换按钮

| 项 | 内容 |
|---|---|
| 位置 | 导航栏右侧（`AppNav.vue` 内） |
| 尺寸 | 36×36，`inline-flex` 居中 |
| 图标 | 白天显示 `sketch-moon.svg`（点击切到黑夜）、黑夜显示 `sketch-sun.svg`——**图标表示"将要切换到哪一边"**，不是当前状态 |
| 无障碍 | `aria-label` 与 `title` 随当前主题变化，键盘可聚焦 |
| 样式 | 图标用 `currentColor`，颜色跟随主题令牌 |

### 2.3 `tokens.css` — 暗色令牌覆盖

关键约束：**只在文件末尾追加一个 `[data-theme='dark']` 块，既有令牌一行未动**。

```css
/* 白天 = :root 缺省（上面既有的令牌一行未动）；黑夜 = [data-theme='dark'] 覆盖。 */
[data-theme='dark'] {
  /* 纸底转深、墨色转浅、三个语义色各自保留可辨性 */
  …
}
```

这样做的理由：

1. **白天模式零风险**——`:root` 里的令牌是 v1.8.0～v1.8.7 七版攒下来的，一行不动意味着白天模式的视觉与全部 97 个单测、19 个 E2E 的断言基线不变；
2. **暗色是可叠加的一层**——切主题只换 `data-theme` 属性，不重新挂载组件、不重启应用；
3. **不新增色值文件**——暗色色值仍然只出现在 `tokens.css` 这一个文件里，守住"唯一颜色来源"的项目红线。

### 2.4 与手稿风格的关系

昼夜切换**不改**手稿语言：手绘边框、圈注、胶带、衬线引文、等宽数据、纸张颗粒在两种主题下都保留，只是纸底与墨色互换。新增的日月图标也沿用同一套绘制约定（`stroke="currentColor"`、路径微弯、`stroke-linecap="round"`）。

---

## 3. 测试与门禁

### 3.1 新增测试

| 文件 | 覆盖内容 |
|---|---|
| `tests/unit/theme-toggle.spec.ts` | 按钮渲染与 `data-testid="theme-toggle"`；点击切换 `data-theme`；`localStorage` 持久化；缺省为 `light`；无定时器/无网络请求 |
| `tests/e2e/theme.spec.ts` | 两种主题下五个页面均可访问；切主题后无横向滚动；刷新后主题保持 |

### 3.2 四道门禁（提交前复跑，退出码全 0）

| 门禁 | 结果 | 与 push_V2 对比 |
|---|---|---|
| `npm run build`（含 `vue-tsc --noEmit`） | 退出码 **0**，✓ built in 2.21s | 持平 |
| `npx vitest run` | **97 passed**（14 个 spec） | 92 → **+5** |
| `npx playwright test` | **19 passed** | 18 → **+1** |
| `pytest backend/tests -q` | **134 passed in 17.61s** | 持平（后端零改动） |

---

## 4. 文档整理

| 文档 | 内容 |
|---|---|
| `docs/version/explain/v1.0.1_前端页面修改说明.md` | 本轮修改总说明：目标（手稿风 + 昼夜，不动功能与接口）、范围、结论 |
| `docs/version/explain/v1.0.2_前端页面修改说明.md` | 新增 SVG 文件清单与设计说明，注明设计源与前端资产两份字节一致 |
| `docs/version/explain/项目进度报告V3.md` | 597 行全量进度快照：18 项验证台账、代码资产、11 条接口 + Postman 测试方法、2 张 mermaid 架构图、可观测性评估、遗留问题分级 |
| `docs/questions/` | 新建目录，`开发任务拆解与迭代流程.md` 与 `项目文件树.md` 从 `docs/` 根移入（**R100 纯移动，内容零改动**） |

---

## 5. 遗留问题（本版未处理）

| # | 事项 | 说明 |
|---|---|---|
| 1 | **模型未实测** | `.env` 已配 DeepSeek（`deepseek-v4-flash`），但选档仍走确定性回退。`deepseek-v4-flash` 默认开 thinking 模式，首次接入必须实测 JSON 能否解析 |
| 2 | **5 个后端接口缺口** | 量规条文、单篇评测、`EMBEDDING_BASE_URL` 独立配置、真实重排、审查结果落库 |
| 3 | **主张 / 表格 / 引用未产出** | 解析页三个预留位 |
| 4 | 论文文件上传 | 只收 Markdown 文本或 `sample_id` |
| 5 | 三篇演示稿无 `gold` | 评测可算样本 12 篇，需求要 15 篇 |
| 6 | 可观测性为零 | 无应用日志、无 `/metrics`、无链路追踪、无健康检查 |
| 7 | `compose.yaml` 空壳 | 四服务无可运行配置 |
| 8 | bundle 1,047 kB 未拆包 | Element Plus 全量引入 |
| 9 | E2E 写库污染 | `review` 89 / `review_dimension` 435 / `review_session` 95 行，无删除接口 |
| 10 | `app.py` 版本号字面量 `0.3.0` | 与进度不符 |

---

## 附录 A：分支与提交关系

```text
main                                    2a6964b  后端V1推送
 └─ v1.8.0_Frontend-draft               65c6449  docs: 补 push_V2 版本档案
     ├─ 1c5d024  P8前端完成：五个页面 + 手稿风格设计 + 文档体系
     └─ v1.8.0_First-version-modification-of-the-frontend
                                         0af0e56  前端第一版修改   ← 本版
```

| 项 | 值 |
|---|---|
| 本版分支 | `v1.8.0_First-version-modification-of-the-frontend` |
| 本版提交 | `0af0e56` |
| 规模 | 18 个文件，+1149 / −5 行 |
| 基线提交 | `65c6449`（原 `v0.9.0-p8-frontend`，已重命名为 `v1.8.0_Frontend-draft`） |
| 远程 | https://github.com/aaGlaming/paper-review |
| PR 入口 | https://github.com/aaGlaming/paper-review/pull/new/v1.8.0_First-version-modification-of-the-frontend |

**推送前安全检查（已执行）**：暂存区无 `.env`、无 `node_modules/`、无 `dist/`、无 `playwright-report/`、无 `test-results/`、无 `.pytest_tmp/`；`git ls-files --error-unmatch .env` 确认 `.env` 未被追踪；两个文档移动在 `--name-status` 里显示为 `R100`（内容 100% 未变），无意外删除。

## 附录 B：常用命令

```text
# 四道门禁
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
npm run build && npx vitest run && npx playwright test
cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q

# pytest 环境坑（测试全绿但退出码 1 时）
mkdir -p .pytest_tmp
$env:PYTEST_DEBUG_TEMPROOT="D:\LEARN\AI\programs\AgentTask\Projects\paper-review\.pytest_tmp"

# MySQL（StartType=Manual，开机不自启）
Start-Process "D:\MySQL\Server8.4\bin\mysqld.exe" -ArgumentList "--defaults-file=D:\MySQL\my.ini" -WindowStyle Hidden

# 8077 被占用时
$c = Get-NetTCPConnection -LocalPort 8077 -ErrorAction SilentlyContinue
if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }

# 切到本版分支
git checkout v1.8.0_First-version-modification-of-the-frontend
```
