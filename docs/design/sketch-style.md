# 手稿风格（Sketch / Hand-drawn）前端设计方案

> 适用范围：`paper-review` 前端五个页面的视觉与布局重设计。
> 依据：提示词模板第 7 章「前端 UI 设计」× WEB-UI Style「一、Sketch」。
> 版本：v1.0.0 · 日期：2026-10-16 · 配套资产：`docs/design/sketch-svg/`（14 个原创 SVG）

---

## 0. 这份方案怎么用

- 它是**设计规范 + 落地提示词**二合一：第 1～11 节是规范，第 12 节是一段可以直接粘贴给 AI 的提示词。
- 所有 SVG 资产已画好放在 `docs/design/sketch-svg/`，落地时整目录复制到 `frontend/src/assets/sketch/`。
- **想先看效果**：用浏览器打开 `docs/design/sketch-preview.html`（样张，含全部 14 个 SVG 的实时渲染与用法说明），或直接看 `docs/design/sketch-preview.png`。
- 改了 SVG 想重新出图：在 `frontend/` 下执行 `node shot-sketch.mjs`（用项目已有的 Playwright + chromium，不引新依赖）。
- **先看第 2 节的三个冲突**再决定动不动手——其中第一个需要你拍板。

---

## 1. 风格定位

**一句话**：像一位资深产品设计师在纸上画完的评审工作台——纸、墨、铅笔、少量批注色；排版是编辑部式的，线条是手绘的，数据是精确的。

参考气质（不照搬）：建筑师草图、产品设计师 sketchbook、独立设计工作室、Swiss Editorial、Braun 式克制。

**不要做成**：儿童绘画网站、营销落地页、AI SaaS 模板、深色电竞 UI。

关键分寸（来自 Sketch 规范第 15 条）：**大部分 UI 保持正常 CSS border，只有少部分重点区域用手绘边框**。手绘是辅助视觉语言，不是主视觉噱头。

---

## 2. 与项目现状的三个冲突（先读这节）

### 冲突一：纸底色——暖纸 vs 现有冷白纸（**需要你拍板**）

Sketch 规范要求暖纸 `#F4F0E8`，但项目 `tokens.css` 第 7 行明写「不用暖奶油色（近 #F4F1EA 那一类一律不用）」，且 `source-scan.spec.ts` 有一条硬断言：**底色蓝分量必须 ≥ 红分量**（`--pr-paper` 的 b ≥ r）。`#F4F0E8` 是 r=244 / b=232，**这条断言会直接失败**。

| 选项 | 做法 | 代价 |
|---|---|---|
| **A. 全盘采纳暖纸** | `tokens.css` 的 `--pr-paper` 改成 `#F4F0E8`，同时把 `source-scan` 那条断言从「偏冷或中性」改成「暖纸」并说明理由 | 改动的是**方向性决策**，不是放宽意图；但要把理由写进 Ruling，且现有 82 个单测里依赖底色令牌的都要复核 |
| **B. 保留冷白纸（推荐）** | 纸底不动，手工纸感全靠**纸张颗粒 SVG + 手绘线条 + 衬线引文 + 编辑部排版**完成 | 零测试风险；纸的"暖度"弱一些，但项目本来就是"校样稿"而非"牛皮纸"，冷白纸 + 墨 + 衬线的组合同样成立 |

**我的建议是 B**：项目现有方向已经是纸隐喻（`--pr-paper`、`--pr-font-quote` 衬线引文、`--pr-leading-quote` 放宽行高），手稿风格要补的是**线条、字体元素、随性布局**这三件事，不是把纸换成另一种颜色。若你更想要 Sketch 文档里那种暖纸，选 A，我把断言理由一并写进提示词。

### 冲突二：手写字体 vs 不引网络字体

项目约束（提示词模板 7.1）：**中文用系统字体栈，不要需要额外加载的网络字体**。而 Sketch 推荐 Caveat / Patrick Hand。

处置：**不引入任何网络字体**。手写感用三样东西补：

1. **原创 SVG 手写标注**——短标注（`looks good` / `TODO` / `v2`）直接画成 SVG path，比任何字体都统一；
2. 中文批注用系统字体 + **轻微旋转（-1.5°～1.5°）+ 墨色/铅笔色**，做出"写上去"的感觉；
3. 手写体只可能出现在**装饰性英文字符串**上，且必须内联 SVG，不引字体文件。

### 冲突三：Editorial 非对称布局 vs 1040px 工作台版心

Sketch 要 12 栏非对称、oversized typography；项目是 1040px 居中版心的桌面工作台。

处置：**保留 1040px 版心，把"编辑部感"做进版心内部**——超大编号、细线分隔、非对称双栏（7:5 而非 1:1）、刻意留白、跨越分隔线的内容块。不做全屏通排。

---

## 3. 色彩系统

### 纸与墨（沿用项目现有令牌，不新增）

| 令牌 | 值 | 用途 |
|---|---|---|
| `--pr-paper` | `#f6f7f9` | 页面纸底（选项 B 下不动） |
| `--pr-surface` | `#ffffff` | 卡片纸面 |
| `--pr-ink` | `#1b2430` | 正文墨色 |
| `--pr-ink-muted` | `#4a5563` | 次要文字 |
| `--pr-ink-faint` | `#6d7885` | 批注、元信息 |
| `--pr-rule` | `#d6dbe2` | 分隔细线 |
| `--pr-rule-strong` | `#b3bcc6` | 手绘线条的"重笔" |

### 批注色（Sketch 的 designer marker 色，克制使用）

项目已有三个语义色，手稿风格**正好复用**，不新增：

| 语义 | 令牌 | 值 | 手稿里的角色 |
|---|---|---|---|
| 冲突 / 硬伤 | `--pr-conflict` | `#a93b2b` | Muted Red，对应 Sketch 的 annotation red |
| 越界 | `--pr-range` | `#7a5a12` | Ochre，圈注与测量标记 |
| 证据不足 | `--pr-insufficient` | `#64707d` | Graphite，铅笔灰 |

**比例铁律**：70% 纸墨中性 + 20% 结构与留白 + 10% 批注色。任何单一批注色不得主导界面。

---

## 4. 字体排印

| 层级 | 字体 | 字号 | 说明 |
|---|---|---|---|
| 界面正文 | 系统 sans（现有 `--pr-font-ui`） | 14px | 不变 |
| 论文原句 | 衬线（现有 `--pr-font-quote`） | 14px / 行高 1.85 | **这是手稿感的灵魂**：引文必须看起来"引自别处" |
| 数据字段 | 等宽（现有 `--pr-font-data`） | 13px | 字符偏移、切片编号、`FIG.01` 这类编号 |
| 页面大标题 | 界面 sans，字重 600 | 20px | 不用艺术字 |
| 批注 | 系统 sans + 斜体或微旋转 | 12px | 颜色用 `--pr-ink-faint` 或批注色 |

**大字号的用法**：手稿感的"大"不靠字体大小，靠**编号与留白**——`01 / 02 / 03` 用等宽体放到 28px，配大段空白，就是编辑部排版。Sketch 规范的 oversized typography 在 1040px 工作台上这样落地，不破坏信息密度。

---

## 5. 布局与网格

### 骨架

```text
┌───────────────────────────────────────────────┐
│  01  论文解析    分项评分    一致性审查    …    │  ← 顶部：编号 + 五个入口，激活项带手绘下划线
├───────────────────────────────────────────────┤
│                                               │
│         （1040px 版心，内部非对称）             │
│                                               │
└───────────────────────────────────────────────┘
```

- 版心 `--pr-measure: 1040px` **不变**。
- 导航：左侧放流程编号与品牌，中间五个入口，激活项用 `sketch-underline.svg` 而非 CSS 下划线。
- 五步流程的递进用**编号 01–05** 表达：每个页面的 `h1` 旁带一个等宽体大编号，用户随时知道自己在第几步。

### 页面内部：非对称双栏

- 默认 **7:5** 双栏（主导区宽、辅助区窄），不用 1:1。
- 部分内容块**跨越分隔**：例如分项评分页的维度卡可以横向越界 24px，制造草图上的"画出去"感。
- 卡片之间留白 ≥ 24px，允许个别卡片**轻微错位**（`transform: rotate(-0.4deg)` 级别，肉眼几乎不察但打破了齐整）。
- 细线分隔大量使用（水平 rule），形成"展览目录 / 报纸"式的阅读节奏。

### 各页主导区

| 页面 | 主导区（宽栏） | 辅助区（窄栏） |
|---|---|---|
| 论文解析 | 章节树 + 正文对照 | 输入区、预留位说明 |
| 分项评分 | 维度卡（档位 + 原句） | 加权小节、步骤指示 |
| 一致性审查 | 冲突列表 | 定位提示、偏移信息 |
| 修改建议 | 三段清单 | 上游指针统计 |
| 评测对照 | 三项指标卡 | 口径与来源说明 |

---

## 6. Sketch 元素词典（每个元素都有设计目的）

| 元素 | 资产 | 只用在这些地方 |
|---|---|---|
| 手绘右箭头 | `sketch-arrow-right.svg` | 流程推进、动作建议的"下一步" |
| 手绘弯箭头 | `sketch-arrow-down.svg` | 从结论指向证据（如"这一维的证据在→"） |
| 手绘圆圈 | `sketch-circle.svg` | 圈住关键数据：档位、命中数、`412 s` 这类冲突数值 |
| 手绘下划线 | `sketch-underline.svg` | 导航激活态、页面标题强调 |
| 手绘卡片边框 | `sketch-card-border.svg` | **只用于重点卡片**（维度卡、冲突条），普通卡片仍用 CSS border |
| 胶带 | `sketch-tape.svg` | 「已确认」结果卡、评测指标卡，营造"贴在纸上" |
| 铅笔 | `sketch-pencil.svg` | 空态插图、未确认提示 |
| 放大镜 | `sketch-magnifier.svg` | 「定位原句」按钮 |
| 章节树 | `sketch-doc-tree.svg` | 解析页章节树标题 |
| 清单 | `sketch-check-list.svg` | 量规相关说明、修改建议三段 |
| 折线图 | `sketch-chart.svg` | 评测对照页的指标可视化 |
| 引文标记 | `sketch-quote.svg` | 论文原句左侧标记 |
| 流程点 | `sketch-flow-dots.svg` | 步骤指示器的"当前步" |
| 纸张颗粒 | `sketch-paper-grain.svg` | 全局底色之上，opacity ≤ 0.035 |

**克制红线**：一屏之内手绘元素不超过 3 处；箭头和圈注是"设计师批注"，出现超过 3 处就变成儿童画。

---

## 7. 组件规范

### 导航

- 极简：编号 + 文字入口，无渐变、无毛玻璃、无发光。
- 激活态：`sketch-underline.svg` 做下划线（`background-image` + `background-repeat: no-x`，或直接 `<img>` 叠在文字下）。
- 非激活态：`--pr-ink-faint`。

### 按钮

- 不用大胶囊。细边框 + 4px 圆角 + 极轻纸影（`2px 3px 0 rgba(27,36,48,0.08)`）。
- 主按钮：墨底米白字（`--pr-ink` 底 + `--pr-surface` 字）。
- 次按钮：透明纸底 + 墨边框。
- Hover：位移 1–2px，或下划线由左向右展开（`sketch-underline` 的 width 动画）。
- **Element Plus 的按钮一律覆盖主题变量**，不改内部类名。

### 卡片

- 普通卡：1px `--pr-rule` 边框 + `--pr-surface` 底 + 4px 圆角。
- 重点卡（维度卡 / 冲突条）：叠 `sketch-card-border.svg` 做手绘边框（SVG 用 `position:absolute; inset:0` 覆盖，`color` 继承墨色）。
- 「已确认」「三项指标」两类卡可加 `sketch-tape.svg` 贴在顶部中央。
- 卡片间距 ≥ 24px，个别卡 `rotate(-0.4deg)`。

### 表单

- Input：纸底 + 石墨细边 + 小标签 + 充足留白。
- Focus：手绘下划线或局部批注色，**不要蓝色发光描边**（Element Plus 的 focus 样式要被覆盖）。
- 赛题下拉、正文 textarea 是项目里唯一该用 Element Plus 的两处。

### 表格

- 只用细水平线，几乎不用竖线。
- 不用彩色表头、不用大面积灰底、不用圆角容器。
- 斑马纹用极淡的纸色交替（`--pr-surface` / `--pr-slot-bg`）。

### 图表

- `sketch-chart.svg` 的视觉语言：石墨笔触、不完美曲线、手绘坐标轴、数据点小圈。
- **数据必须精确，只有表现是手绘的**（Sketch 规范第 10 条原文）。
- 轴标签用手写批注的排版方式（等宽体 + 微旋转）。

### 图标

- 只用 `sketch-svg/` 里的细线条图标，全部 24×24 viewBox、`stroke="currentColor"`。
- 禁 3D、渐变、霓虹、✨✦ 这类 AI 装饰，禁 emoji 当图标。

---

## 8. 五个页面草图

### 论文解析 `/parse`

```text
01  论文解析                                    ← 编号 + h1（手绘下划线）
────────────────────────────────────────────────
[ 选题下拉 ]  [ 演示稿① ] [ 演示稿② ] [ 演示稿③ ]      ← 表单区（Element Plus）
────────────────────────────────────────────────
┌─章节树──────────┐  ┌─正文─────────────────┐
│ ▸ 摘要          │  │  把手简化为孔中心点。 │
│ ▸ 一、模型假设  │  │  …                   │
│ ▸ 二、求解      │  └──────────────────────┘
└────────────────┘  ┌─预留位─────────────────┐
                    │ 主张/表格/引用：接口未提供│
[ 确认章节树 ]      └──────────────────────┘
```

### 分项评分 `/scoring`

```text
02  分项评分
────────────────────────────────────────────────
assumption                        ┌ 手绘圈住档位 ┐
[基本]  ← 档位徽标                 └──────────────┘
┌─手绘边框卡────────────────────────┐
│ "为简化计算，本文忽略板凳宽度…"     │  ← 衬线引文 + sketch-quote
│ 切片：chunk-0c1f        [定位原句] │  ← 等宽数据 + 放大镜图标
└──────────────────────────────────┘
constraint_check
[证据不足]  ← 灰蓝批注色，不给原句、不给分数
```

### 一致性审查 `/consistency`

```text
03  一致性审查
────────────────────────────────────────────────
数字冲突 · 盘入终止时刻                        ← finding_kind 徽标
  412 s   ← 可点，点后滚动到该字符偏移并高亮
  386 s   ← 可点
  ↘ "把两处数值改成同一口径"     ← 弯箭头指向 action
```

### 修改建议 `/suggestions`

```text
04  修改建议
────────────────────────────────────────────────
先改硬伤 · 题目约束与数字冲突      ← 三段顺序，前端不重排
  ────────────────────────────
  数字冲突  盘入终止时刻    上游 finding:数字冲突:盘入终止时刻
  越界      …              上游 finding:越界:…
再补证据 · 证据不足
最后改表述 · 表述
```

### 评测对照 `/eval`

```text
05  评测对照
────────────────────────────────────────────────
┌─档位一致率──────┐ ┌─引用精确匹配──┐ ┌─证据不足命中──┐
│ 43.3%  26/60    │ │ 100%  60/60  │ │ 0%   0/2     │
│ ＿＿＿           │ │ ＿＿＿        │ │ ＿＿＿        │  ← 手绘下划线压底
└─────────────────┘ └──────────────┘ └──────────────┘
   ↑ 每张卡顶部贴 sketch-tape，折线图用 sketch-chart
source=deterministic：脚本自检，非模型准确率  ← note 原文必须可见
```

---

## 9. 原创 SVG 资产清单

全部放在 `docs/design/sketch-svg/`，落地时复制到 `frontend/src/assets/sketch/`。

| 文件 | viewBox | 用法 |
|---|---|---|
| `sketch-arrow-right.svg` | 56×24 | 流程箭头，`color` 控色 |
| `sketch-arrow-down.svg` | 40×56 | 弯箭头，指向证据 |
| `sketch-circle.svg` | 140×90 | 圈注，可 `width/height` 缩放套任意元素 |
| `sketch-underline.svg` | 200×14 | 下划线，`preserveAspectRatio="none"` 可横向拉伸 |
| `sketch-card-border.svg` | 240×140 | 卡片手绘边框，`preserveAspectRatio="none"` 平铺满卡片 |
| `sketch-pencil.svg` | 24×24 | 铅笔图标 |
| `sketch-tape.svg` | 72×26 | 胶带，贴卡片顶部 |
| `sketch-magnifier.svg` | 24×24 | 定位按钮 |
| `sketch-doc-tree.svg` | 24×24 | 章节树 |
| `sketch-check-list.svg` | 24×24 | 清单 |
| `sketch-chart.svg` | 220×120 | 手绘折线图 |
| `sketch-quote.svg` | 24×24 | 引文标记 |
| `sketch-flow-dots.svg` | 24×24 | 流程点 |
| `sketch-paper-grain.svg` | 300×300 | `feTurbulence` 纸纹，opacity ≤ 0.035 |

**绘制约定**（新增 SVG 时遵守）：`stroke="currentColor"`（线条类）、`stroke-width` 1.2–1.8、`stroke-linecap/linejoin="round"`、`fill="none"`；路径一律微弯不取直；重点形状描两遍，第二遍 `opacity 0.45–0.55` 且略偏移。

---

## 10. 动效

- 只保留三类：**hover 位移 1–2px**、**下划线由左向右展开**、**卡片轻微抬升**。
- 缓动统一用项目既有的 `--pr-motion-confirm`（220ms）。
- 禁：入场 fade、逐卡片动画、粒子、3D、发光、blur。
- `prefers-reduced-motion` 下全部关闭。

---

## 11. 可访问性与红线

1. 对比度：正文 `--pr-ink` on `--pr-paper` ≥ 12:1；批注色文字不小于 4.5:1（`--pr-conflict` 需配 `--pr-conflict-soft` 底使用）。
2. 手绘线条只是装饰，`aria-hidden="true"`，不承担信息传达。
3. 焦点态清晰可见（手绘下划线 + 批注色），键盘可达。
4. **项目红线不变**：不输出奖项/名次/获奖概率；不按题号写分支；`.vue` 里不出现十六进制色值（新颜色只能加进 `tokens.css` 末尾）；空态文案不含档位词/审查词/建议词；86 个 `data-testid` 一个不丢；每页恰好一个 `h1` 且无条件渲染。

---

## 12. 落地提示词（可直接粘贴）

```text
你正在开发 D:\LEARN\AI\programs\AgentTask\Projects\paper-review。
先读 docs/design/sketch-style.md（设计方案，含 14 个 SVG 资产的用法）、
docs/version/10.16/v1.8.6_重新设计前端视觉与布局.md（本轮的约束与测试契约）、
docs/plan/progress.md，以及 frontend/src/styles/tokens.css（唯一允许出现颜色字面量的文件）。
前端栈：Vue 3.5 + Vite 8 + Element Plus 2.14 + vue-router 5 + TypeScript，全部 <script setup lang="ts">。
后端解释器：D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe。
不要安装 node，不要创建 Python 虚拟环境，不要引入任何新依赖（图标/动画/Markdown/图表库一律不加）。

本版任务：按 docs/design/sketch-style.md 把手稿风格（Sketch / Hand-drawn）落到五个页面上。
纸底色采用方案 B：保留现有冷白纸底 --pr-paper #f6f7f9 不改，
手工纸感由纸张颗粒 SVG + 手绘线条 + 衬线引文 + 编辑部排版完成。
（若我另行确认改用暖纸 #F4F0E8，则同时改 tokens.css 与 source-scan 的底色断言并记 Ruling。）

【第一步】资产落地
把 docs/design/sketch-svg/ 整目录复制到 frontend/src/assets/sketch/（新建目录，共 14 个 SVG，一个不改内容）。
新增 frontend/src/styles/sketch.css，只做三件事：引入纸张颗粒做全局极淡底纹（opacity ≤ 0.035）、
定义 .sk-underline / .sk-card-frame / .sk-tape 三个复用类、声明手绘元素的三条绘制约定。
新颜色仍只准加进 tokens.css 末尾，既有令牌一行不许改。

【第二步】骨架（App.vue + AppNav.vue）
- 导航左侧加流程编号 01–05 与品牌名，中间五个入口，激活项用 sketch-underline.svg 做下划线。
- 五个 data-nav-item 入口、文案顺序、main 元素一个都不能少（app-shell.spec.ts 断言 links 数为 5）。
- 每页 h1 旁加等宽体大编号（01 论文解析 / 02 分项评分 / 03 一致性审查 / 04 修改建议 / 05 评测对照），
  h1 本身保持恰好一个、文案不变、无条件渲染。

【第三步】页面（按主导区逐个改，一次一页）
1. 论文解析：章节树与正文做成 7:5 非对称双栏；章节树标题用 sketch-doc-tree；正文原句左侧加 sketch-quote。
2. 分项评分：维度卡用 sketch-card-border 手绘边框 + sketch-tape；档位徽标可被 sketch-circle 圈住
   （用 absolute 定位的 SVG 套在徽标外，不改 DOM 结构）；证据不足的卡继续用 --pr-insufficient，
   不给原句不给分数；「定位原句」按钮加 sketch-magnifier。
3. 一致性审查：冲突条用 sketch-card-border；冲突数值（如 412 s）可被 sketch-circle 圈住；
   action 前加 sketch-arrow-down 指向；定位逻辑（indexOf 真实子串、找不到诚实降级）一行不许改。
4. 修改建议：三段分组保留，段标题加等宽编号与细 rule；每条的上游指针用等宽体；
   段与段之间用 sketch-arrow-right 表示"先改硬伤 → 再补证据 → 最后改表述"的推进方向。
5. 评测对照：三张指标卡用 sketch-tape 贴顶 + sketch-chart 做折线；
   rate 为 null 显示「—（无样本）」；source 与 note 原文必须可见，不许把百分比放大当成果。
   本页不需要 StageTracker（六步是单次评审的，不是评测汇总的）。

【第四步】统一细节
- 普通卡片仍用 1px --pr-rule 边框；只有维度卡/冲突条/指标卡三类用手绘边框，一屏不超过 3 处。
- 卡片间距 ≥ 24px；允许个别卡片 rotate(-0.4deg)。
- 按钮：细边 + 4px 圆角 + 2px 3px 0 纸影；hover 位移 1-2px 或下划线展开。
- 表单 focus 用手绘下划线或批注色，覆盖 Element Plus 的蓝色描边。
- 动效只用 --pr-motion-confirm，禁 fade / animation / hover 位移组合（source-scan 会扫）。
- 1280×800 与 1920×1080 两个视口下都不许出现横向滚动。

【验收】四道门禁退出码全 0：
  cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review\frontend
  npm run build
  npx vitest run
  npx playwright test
  cd /d D:\LEARN\AI\programs\AgentTask\Projects\paper-review
  & D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests -q

必须守住的契约（破了就是没做完，不是"测试写错了"）：
- 每页恰好一个 h1、文案 = 导航名、无条件渲染；
- 86 个 data-testid 一个不少；
- 五个 data-nav-item 与 main 元素不丢；
- .vue 与 .css（除 tokens.css）无十六进制色值；无 fade；无 animation:；不同时含 hover 与 translate；
- tokens.css 仍含 --pr-motion-confirm、--pr-paper（b≥r）、--pr-ink（非纯黑、max<140）、--el-color-primary:；
- 空态文案文字不改（仍不含档位词/审查词/建议词）；
- frontend/package.json、package-lock.json、backend/ 一行不变。

把命令、退出码和最后一行写入 docs/plan/progress.md 的「## v0.9.0（阶段 7/7：前端视觉重设计）」小节，
并把下面这条 Ruling 照抄进 docs/plan/findings.md：

- Ruling: 手稿风格采用方案 B——保留冷白纸底，手工纸感由纸张颗粒 SVG + 手绘线条 + 衬线引文 + 编辑部排版完成 — Sketch 规范的暖纸 #F4F0E8 会违反 source-scan 的"底色 b≥r"断言，且项目校样稿方向本就是纸隐喻而非牛皮纸 — 若强行改暖纸，要么放宽断言意图，要么把"偏冷"这条设计决策连同七版积累一起作废，代价远超收益。
```

---

## 13. 怎么验证这版做对了

1. **四道门禁全绿**（build / vitest / playwright / pytest）。
2. **两视口无横向滚动**（1280×800、1920×1080），用 Playwright 断言 `scrollWidth <= innerWidth + 1`。
3. **手绘元素密度自检**：任一屏截图数手绘元素，超过 3 处就撤掉几处。
4. **灰度测试**：把页面转灰度（浏览器滤镜或截图去色），信息层级仍然清楚——这说明视觉重点来自排版而非颜色，正是 Sketch 规范第 18 条的要求。
5. **纸感测试**：把 `sketch-paper-grain.svg` 的 opacity 调到 0 看是否仍然成立。成立才说明纸感不是靠噪点堆的。
