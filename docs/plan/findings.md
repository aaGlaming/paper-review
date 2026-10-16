# 裁决

实现偏离三份依据文档时，把裁决写在这里。格式：`Ruling: 决定 — 原因 — 做错的代价`。

现在还没有新的实现裁决。导入路径仍以开发任务文档为准：使用 `POST /api/imports`。

## v0.1.0

- Ruling: 解释器统一使用 `env\agent-task\Scripts\python.exe` — 执行手册 V1 写的 `env\Scripts\python.exe` 在本机不存在 — 用错路径会把包装到不存在的环境并误判依赖缺失。
- Ruling: PyMySQL 实装 2.2.8 而 `backend\requirements.txt` 锁定 1.2.3 — requirements 是共享锁定文件且本版不使用 PyMySQL — 擅自升降级会动到同环境下其他项目，本版只记录不处理。
- Ruling: archify 产物在仓库外临时目录生成并通过全部门禁，再按字节复制进 `docs/diagrams` — 本机工作区内被删除的文件会留下回收站硬链接，archify 的原子发布按硬链接数做安全校验，在 `docs/diagrams` 下写入必然失败（`finalize-receipt-hardlinked`、`delivery-journal-candidate-hardlinked`、`output/target-indeterminate`），并残留锁、未完成交付日志和隔离目录 — 若直接在工作区内硬写，产物写不进去、旧文件被挪进隔离目录，`archify check --require-provenance` 会因残留日志判为 provenance failed。
- Ruling: 图中每个节点标注实现它的版本（v0.2.0～v0.9.0、v0.1.0 已实现、信任边界外） — v0.1.0 只落地了模型客户端，其余模块此时并不存在 — 不标注会把未实现模块画成已完成，验收时误判本版范围。

## v0.3.0

- Ruling: 本版按 `.env` 的 `MYSQL_DSN` 实连真实 MySQL（8.4.11，库 `paper_review`，utf8mb4），PyMySQL 用实装的 2.2.8，不改 `backend/requirements.txt` 的 1.2.3 锁定 — requirements 是共享锁定文件，实装版本与锁定版本不一致但本版已实测连通（`SELECT VERSION()` 返回 8.4.11，`SELECT 1` 通过），降级会波及同环境下其他项目 — 若擅自按锁定版本升降级，会动到共用环境里别的项目；若日后连接失败且确认由版本差异引起，先停下问人，不自行改依赖。
- Ruling: 本版测试连真实 MySQL，用「外层事务 + 保存点」隔离（每个用例结束整体回滚），不用独立表名前缀 — 建表要落在业务库 `paper_review` 的七张真表上，加前缀会让表名与开发计划书第七节不一致 — 若改用前缀，建出来的表名与计划书和数据字典对不上，后续版本取父块时会找不到表。
- Ruling: `constraint`、`rubric`、`dimension`、`pitfall`、`exemplar` 等表按开发计划书第七节命名，其中 `constraint` 是 MySQL 保留字，只能靠 SQLAlchemy 自动加反引号 — 计划书把表名写成 `constraint`，改名会让数据字典与代码对不上 — 若手工写 SQL 而漏掉反引号，建表与查询会直接报语法错误。

## v0.4.0

- Ruling: `paper_parent` 的表模型与仓储放在 `backend/app/retrieve/models.py`，只**只读导入** `backend/app/importing/db.py` 的引擎与会话工厂来共用连接，不改那个文件 — 本版允许修改范围不含 `backend/app/importing/`，而父块全文要落 MySQL（计划书第七节 7.2），表模型得有地方放 — 若为了放模型去改 importing，就超出本版范围、并把赛题七张表与父块表的建表责任混进同一模块；若把父块也塞进 Chroma，则直接违反「父块全文只在 MySQL」。另用 `ParentBase` 自己的 metadata 建表，`create_all` 只建 `paper_parent`，不动赛题那七张表。
- Ruling: 检索测试用临时目录里的**真实 chromadb**（`PersistentClient` + 自定义假 EmbeddingFunction，add 与 query 都显式传向量）与**真实 MySQL**，sqlite 只作兜底 — 本机实测：chromadb 1.5.9 不会拦 `doc_type` 非白名单的写入，数组型 `section_type` 用 `$in` 过滤会**静默返回空且不报错**；只有真向量库才能验证单值元数据 + `$in` 真的命中、以及父块正文确实没进 `document` 字段 — 若只用内存假件，字段类型或过滤写法写错时测试照样通过，问题会拖到上线才暴露。

## v0.5.0

- Ruling: 本版只做重排的**接口与假客户端**（`FakeRerankClient` 把候选顺序倒过来），从环境变量读 `RERANK_BASE_URL` / `RERANK_MODEL` 当**配置项**，**一个 HTTP 请求都不发**；真实 HTTP 重排留到允许修改 `backend/app/llm/client.py` 的版本 — 项目硬约束是「全项目只有 `backend/app/llm/client.py` 可以发 HTTP」，而本版允许修改范围不含该文件，在 `backend/app/retrieve/` 里另写 http 客户端会直接打破这条约束 — 若为了「先把功能跑通」在这里发请求，就出现第二个 HTTP 出口，后续 v0.6.0～v0.9.0 会继续在别的模块发请求，密钥与超时重试也会散落多处；`build_rerank_client("http")` 现在显式抛 `NotImplementedError`，把越界写成可见的失败而不是静默实现。
- Ruling: 图里的逐维检索用**可注入的检索器**（`build_review_graph(..., retriever=...)`），缺省实现不做任何检索、每维直接记「证据不足」 — 本版禁止调用 `chat()` / `embed()`，而真实检索需要查询向量，图内无法自己造出来 — 若缺省实现假装命中或偷偷调模型，就同时违反「图内不得出现模型调用」与「证据不足必须由检索结果触发」；缺省记证据不足既不假装命中，也让 v0.2.0 已有的 resume 用例继续成立。

## v0.5.1

- Ruling: 新增状态节点时必须同步在 `create_review` 的初始状态里预置该节点的计数初值，测试保留严格取值、不改为 `.get(key, 0)` — 图暂停在中间节点时，后续节点的计数键从未被写入，严格取值会 `KeyError`；而 `.get` 会分不清「键不存在」与「计数为 0」 — 若改成 `.get`，计数器将来脱线也测不出来，断言退化为永远为真，后续版本会继续漏预置。

## v0.6.0

- Ruling: 降档守卫做成纯函数 `apply_mention_guard()`，只读 `check_type = mention` 的约束，关键词取 `constraint.params.keywords`，适用范围取该约束的 `section_types` 与量规维度 `section_types` 的交集，命中不到关键词就把「充分」降一档到「基本」 — 验收要求「云团被写成静止且证据里没有下沉条件时该维不得为充分」，同时明令不得把题面字面量写进代码，只能由数据驱动 — 若按字面量写 if 分支，换一道题守卫就失效，还违反「评分代码不按题号写分支」；反过来，缺 `keywords` 或章节类型不相交时也强行降档，会把没配数据的约束变成全域降档、把所有维度压到「基本」。这两种情形都记进守卫结果的 `skipped`，不静默略过。
- Ruling: `build_review_graph` 新增可注入的 `chat`；**未注入时评分节点沿用 v0.2.0 的占位实现**（只累加 `score_node_calls`、status 记「完成」，不选档、不报错），并且规定「注入 `chat` 就必须同时给 `rubric_dimensions`」 — `backend/tests/graph/test_interrupt.py` 不在本版允许修改范围，它断言 resume 后 status 为完成、`score_node_calls == 1`、同一 review_id 二次 resume 不重算，且调用 `build_review_graph()` 时不注入任何模型 — 若改成「未注入就报失败」，P1 已通过的四条用例立刻变红而本版无权改那个文件；若默认自己造一个模型客户端，就出现第二个 HTTP 出口、越过「只有 llm/client.py 能发 HTTP」这条硬约束。
- Ruling: `weighted_sum()` 的 `total` 定义为「进入合计的维度权重之和」（`weight_sum` 同值，另给 `rubric_weight_sum` 作分母），不引入任何档位系数，充分/基本/不足 对 `total` 的贡献相同，档位只用于单列与展示 — 三份依据文档都只写「通过校验的维度按量规权重加总」，没有定义档位到分数的换算，模型给的 `score` 又被明令忽略 — 若自行发明「充分 1.0 / 基本 0.6 / 不足 0.2」这类系数，等于把一套没人批过的评分尺度写进代码，还会让「改量规权重合计才变、改模型权重不变」这条验收失去意义；代价是 `total` 只能读作「有依据的权重合计」，不能当年百分制分数用，页面必须把 `excluded` 里的维度连同原因单列。

## v0.7.0

- Ruling: 数字冲突按「**单位 + 指标名**」归组，越界按「**指标名**」匹配约束。指标名 = 数字前紧邻、**且不越过前一处数值**的那段文字（在标点或换行处断开），去掉数字、单位、括号与通用连接词后的结果；两处需单位相同且指标名相同或**互为前缀 / 后缀**才算同一指标。越界的指标上下文取自约束名里在正文出现过的最长前缀（≥3 字），完全由约束数据驱动 — 烟幕演示里 1.5 s、3.6 s、20 s、22.4 s、18.6 s 全是秒，只按单位归组会把题目给定的合法取值报成冲突；无人机速度约束单位是 m/s，而正文里导弹速度 300 m/s 也是 m/s，只按单位匹配会把 300 m/s 报成越界 — 若按单位归组与匹配，演示样例一跑就是四五条误报，「数字冲突」这条能力立刻不可信，验收里的反向断言必挂；代价是真正指向同一个量的两处，若措辞完全不同、或相距超过 24 个字符且中间没有标点，会被漏报——宁漏不误。
- Ruling: 上面这套判据的两处细节都是**被测试逼出来的**，写在这里免得后人又改回去：①「互为前缀 / 后缀」而不是「任意包含」——第一版用任意包含，短标签「起爆」落进「把起爆时刻提前」里面，于是 20 s 与 0.5 s 被并成同一指标；②指标窗口不越过前一处数值——否则「把起爆时刻提前 0.5 s 后……约 0.4 s」里，后一处会把前一处的措辞整段继承，0.5 s 与 0.4 s 被并成一组 — 两条都是实测出来的误报，不是推演 — 若改回「任意包含」或允许窗口跨过前一处数值，这两条误报会立刻回来，而它们正好落在演示样例里，演示时会直接被看见。
- Ruling: `data/samples/eval/` 的 12 篇评测论文用「同名 md + json」两份文件承载，读入函数 `load_eval_papers()` 按文件名前缀跳过 `README.md` — README 是目录说明不是样例，早期版本会因为缺同名 json 直接抛 `FileNotFoundError` — 若不做跳过，v0.8.0 的评测汇总一加目录说明就会崩；若把 gold 写进 md 的 front matter，读入要再引一个解析器，而本版不允许引入锁定清单之外的依赖。

## v0.8.0

- Ruling: 三项评测指标的分子分母按**有 gold 的可算样本**计算（12 篇 / 60 个维度项），同时在返回结果里给出**语料片数 15** 与 `demo_papers_without_gold: 3`，并把口径写进每个指标的 `caliber` 字段 — 需求 §12.4 与任务文档 §13 都写「对 15 篇输出三个数」，但实测 `data/samples/` 根下三篇演示稿没有 gold 元数据（只有 `data/samples/eval/` 的 12 篇有），而 `data/samples/` 不在 v0.8.0 允许修改范围，本版无权给它们补 gold，也不该为了让分母好看去编造人工档位 — 若硬凑 15 篇的分母，就得凭空造三篇的 gold，评测数字会变成自造答案的自证；若只报 12 而不说 15，看数字的人会以为分母缩水是遗漏。代价是这两个数必须同时出现在 `progress.md` 与接口响应里，读者要自己对齐口径。
- Ruling: 未注入 `chat` 时走**确定性结构回退**（按量规的 `section_types` 找对应章节，有非空正文就给「基本」并抄一句原话，没有就判「证据不足」），并在返回结构里用 `source="deterministic"` 标明来源；`progress.md` 里把这批数字写成「脚本自检」，**不写成模型准确率** — `.env` 的四个模型键全为空，本版无法真调模型；回退能把「读入语料 → 逐维出档位 → 与原句比对 → 汇总三项指标」这条链路跑通并暴露口径问题，但它判不出真档位 — 若把回退数字当准确率写进台账，会让「系统准确率 43%」这种结论被当成模型效果，后续版本拿它做基线就会一路错下去。要模型数字就注入 `chat`（`run_eval(chat=...)`，测试里用假 chat 验证过 `source="model"`）。
- Ruling: 评审记录两张表（`review`、`review_dimension`）放在 `backend/app/report/models.py`，用**自己的** `ReportBase` 建，只**只读导入** `backend/app/importing/db.py` 的引擎与会话工厂复用连接；同一 `review_id` 再次保存时整条记录（含当时各维的档位 / 切片编号 / 原句）一律不回写 — 本版允许修改范围不含 `backend/app/importing/`，而需求要求「新量规不回写旧记录」；把表塞进 importing 会超出范围，而允许覆盖旧记录会让「发布第 2 版量规后旧评审仍是第 1 版」这条验收失去保障 — 若允许回写，量规一升级旧评审的原句与切片编号就可能被改写，溯源就断了；代价是要改旧记录只能换一个新的 `review_id`，旧的必须留着。

## v0.8.1

- Ruling: 新增 `review_session` 表（挂在 `ReportBase` 下，随既有 `create_report_schema()` 一起建，不另开第二套建表入口），并存一次章节确认之前的会话快照 — 开发计划书 §7.2 只定义了 `review` 与 `review_dimension` 两张表，而执行手册 §3.6 冻结的三条评审路径要求「进程重启后从暂停处继续」，`InMemorySaver` 的检查点只在进程内存在，重启后没有任何东西可以还原 — 若不落这张表，`POST /api/reviews/{review_id}/resume` 在重启后只能抛 `ValueError`，P8 的解析页确认按钮会在服务重启后必挂；若改成「重启后重新 `create_review`」兜底，`parse_node_calls` 会被重置、章节树被重解析一遍（实测），确认结果被丢弃。在本表既定列之外**另加一列 `contest_id`**：确认请求体只带章节树，量规要按赛题从库里取，没有这一列就无法在重启后重新绑定当时那道赛题，只能退化成「重启后各维为空」；该列不改 `review` / `review_dimension` 的冻结字段。`save_session` / `load_session` 与 `store.py` 同款风格，同样支持可选 `session` 参数；与「旧记录不回写」不同，同一 `review_id` 再次保存会话是**覆盖**（确认时以请求体为准回写）。
- Ruling: 本版各维档位来自**确定性结构回退** `report.evaluation.deterministic_results(paper_text, dimensions)`，`model_name` 与响应里的 `source` 都记 `"deterministic"`，`note` 字段逐字写明「是脚本自检，不是模型结果」；响应里的 `score` 四个数全是 0 — `.env` 的四个模型键全为空，本版不接模型、也不改 `backend/app/llm/client.py`；回退的档位（基本 / 证据不足）不是模型选出来的，而 `weighted_sum()` 的权重合计只能表达「有依据的权重之和」、无法表达档位到分数的换算（见 v0.6.0 的裁决） — 若把回退档位当成模型结果并给出一个非零的加权分，等于把一套没人批过的评分尺度塞进接口响应，评审单的历史里会留下一个看起来像模型打分的数字；若干脆省略 `score` / `source`，读者又无法从响应本身分辨这批档位的来源。
- Ruling: 检查点恢复采用 `graph.update_state(cfg, 快照, as_node="parse")`，快照至少含 `paper_text`、`sections`、`confirmed`、`score_node_calls`、`parse_node_calls`、`retrieve_node_calls`；`parse_node_calls` 还原为 1 且不重新解析。**绝不可用 `as_node="confirm"`** — 实测新进程 + 新 saver 直接 `resume_review` 抛 `ValueError`，而 `as_node="parse"` 还原后 `next == ("confirm",)`、status 仍为「待确认」，resume 后 status 为「完成」、`score_node_calls == 1`、`retrieve_node_calls == 1`；换成 `as_node="confirm"` 得到 `next == ("retrieve",)`，**人工确认被整段跳过**，直接进检索与评分 — 「章节树由人确认后才评分」是本项目最核心的一条约束，用错这个值会让未确认的论文直接出档位，而这个错误在响应里看不出任何异常。另：图不可改（`backend/app/graph/` 不在本版允许范围），`tests/graph/test_interrupt.py` 断言未注入模型时 status 为「完成」、`score_node_calls == 1`，改图的缺省行为会让它变红而本版无权改它。实测补记：真起一次 uvicorn，创建后杀掉进程再重启同一端口，`resume` 仍返回 200 / 完成，且按库里 `cumcm-2024-C-v1` 出满五维。
- Ruling: 评审创建与继续两条接口在 v0.1.0～v0.8.0 的任何版本任务清单中均未排期，而执行手册 §3.6 已将其冻结、任务文档 §14 又按"已有的"引用；本版（v0.8.1）补实现 —— 原因是三份文档各管一段、缺少交叉核对，且 v1.7.0 提示词曾把一条自造禁令误归给任务文档 §13 —— 做错的代价是 P8 前端会对着不存在的接口开工，五个页面全部返工。另在本版删掉两处同源的旧措辞（`backend/app/api/routes.py` 的模块注释与 `backend/app/api/__init__.py` 的包注释），它们都把「不实现 `POST /api/reviews`」写成「属后续版本」。
- Ruling: 本版真库连接**没有走服务**：以当前权限 `Start-Service MySQL84` 与 `net start MySQL84` 都报「无法打开服务 / 拒绝访问」，服务至今仍是 `Stopped`（`StartType = Manual`），于是照 `sc.exe qc MySQL84` 查到的原始路径用同一份 `D:\MySQL\my.ini` 直接起了 `mysqld.exe`，3306 恢复监听后再做全部真库步骤 — 本版所有涉及真库的步骤都必须连 MySQL，而让服务起不来的是权限不是配置；改用 sqlite 兜底或把真库用例改成跳过，都会把「真库集成」这条验收悄悄降级 — 代价是：这条 `mysqld.exe` 是当前会话里的普通进程，不受服务管理器托管，注销或重启后就没了，且开机不会自启（`Manual`）。真库步骤若要复现，得先确认 3306 有监听；后续版本仍建议由人用管理员权限把服务改成自动启动。

## v0.9.0（阶段 1/6：前端工程脚手架与门禁）

- Ruling: 任务文档 §14 的允许修改目录按「修改既有文件」拟定，未覆盖从零搭建 Vue 工程所需的脚手架文件（index.html、vite.config.ts、tsconfig*.json、env.d.ts、src/main.ts、src/App.vue、src/router/、src/components/、src/styles/、tests/），本版将其纳入允许范围，backend/ 与 data/ 仍禁止 —— 原因是该清单未预料 P8 是首个前端版本、需要从零建工程 —— 做错的代价是第一步就卡在 index.html 上，或绕过范围去动后端。
- Ruling: 后端没有 CORS 中间件，而 P8 不允许改后端；前端一律用相对路径 /api/...，由 Vite dev server 代理到 http://127.0.0.1:8077 —— 原因是浏览器直连 8077 会被 CORS 挡死且报错不指向根因 —— 做错的代价是五个页面全部连不上后端，而排查会先怀疑页面代码。
- Ruling: `typescript` 用 `6.0.3` 而不是提示词第 1.2 节给的 `7.0.2` —— 按 7.0.2 装完后空跑 `npm run build` 直接失败：`ERR_PACKAGE_PATH_NOT_EXPORTED: Package subpath './lib/tsc' is not defined by "exports"`（`vue-tsc@3.3.13` 要 `require('typescript/lib/tsc')`，而 TS 7 是原生实现的包，`exports` 里不再有这条子路径；peer 写的 `>=5.0.0` 拦不住布局变化） —— 不改就没法保留提示词点名的 `vue-tsc --noEmit` 这道门禁；另一种「绕行」是把 build 降级成只跑 `vite build`，那等于把类型门禁关掉。`tsconfig.json` 的严格项一处没减，`include` 仍覆盖 `src/` 与 `tests/`。
- Ruling: 开发服务器在 `vite.config.ts` 里把 `server.host` 固定为 `127.0.0.1` —— 实测 Vite 默认只监听 `[::1]:5173`（IPv6），而 Playwright 的 `baseURL` 与就绪探测用的是 `127.0.0.1`（IPv4），两边会对不上，表现为就绪探测超时或页面连不上 —— 若不固定，E2E 会时通时不通且报错指向「服务没起来」，排查方向全错。另记两条环境事实：本机 `node`/`npm` 实际是 `v24.19.0`/`11.17.0`（文档实测写的是 `v22.22.2`/`10.9.7`，本机不存在那个版本），并按要求没有安装或切换 node；`ms-playwright` 缓存原本为空，需先装 chromium（118.1 MiB）才能跑 E2E，这不是绕行而是前提。

## v0.9.0（阶段 2/6：论文解析页）

- Ruling: 需求第 235/258 行与执行手册第 50 行要求解析产出并展示「主张、表格、文内引用」，而后端从未实现，POST /api/reviews 只返回 sections（title/section_type/level/content）；本版页面只渲染接口真给的东西，右栏为三块预留位置并显示说明，不在前端重解析 —— 原因是 P8 的允许范围不含后端，前端重解析会与服务端语义分叉 —— 做错的代价是同一篇论文出现两套解析结果，且后续后端补齐时要重写这一段。
- Ruling: 前端镜像六个章节类型 + 未分类（后端没有取词表的接口，P8 不许改后端），只在一处定义并用用例锁死 —— 原因是确认时用户要改类型、必须给出合法选项 —— 做错的代价是前端可选值与后端词表分叉，用户能选出后端不认识的值。
- Ruling: E2E 会向真库写入评审记录（review / review_dimension / review_session），而接口里没有删除路径，无法清理；本版接受这一污染并在 progress.md 记录运行后的行数 —— 原因是"确认章节树"必须走真实 HTTP 才算验过它 —— 做错的代价是长期累积测试数据；清理或测试库隔离方案挂账到后续版本。
- Ruling: resume 是同步接口、不报中间态，所以步骤指示器只点亮真实观测到的步骤，请求进行中显示不确定态，禁止用定时器伪造进度 —— 原因是需求 §12.4 要求"分步看到"，而"看到假进度"比"看到不确定态"更糟 —— 做错的代价是页面在撒谎，且超时时会显示一个从未发生的"已完成到第 N 步"。
- Ruling: 奖项字样词表从 `source-scan.spec.ts` 里搬出来放到 `tests/unit/forbidden-words.ts`，扫描时按文件名排除词表文件与写词表的那个 spec（此前只排除 spec 自身） —— 原因是阶段 2/6 的 `parse-view.spec.ts` 也要断言「不出现奖项字样」，把字面量抄进第二个测试文件会被 v1.8.0 那条全局扫描判违规 —— 做错的代价是要么把新用例里的奖项检查删掉（放宽意图），要么让全局扫描持续误报；代价是排除名单多了两个文件，但两个都是"必须持有词表"的测试夹具，其余 src/ 与 tests/ 仍在扫描范围内。

## v0.9.0（阶段 3/6：分项评分页）

- Ruling: 分项评分页不显示量规条文，只显示 dimension_code，条文位置预留并注明「接口未提供」— 没有任何接口给出维度名/权重/四档说明（GET /api/contests 只有 rubric_id 与 version），而 P8 不许改后端 — 若在前端臆造中文维度名，用户会看到与量规不符的条文，且后端补接口时页面要重写一遍。
- Ruling: 存档是第三种形状，types.ts 新增 ArchivedReview 并把 ReviewArchive 改成三态 — 实测 GET /api/reviews/{id} 只回 7 个字段，没有 score/change_list/note，原有联合类型会让人静默取到 undefined — 若照旧类型写页面，加权区会显示空白而不报错，届时会被误判成"后端没算分"。
- Ruling: score 四个数为 0 时显示「加权未产生（source=deterministic）」，不显示 0 分 — 确定性回退下后端不产生加权，页面显示 0 分等于告诉用户这篇论文零分 — 这是需求第 41 行与任务文档 §14 任务 4 要防的"假分数"的镜像，一旦显示就污染了评审结论。
- Ruling: 定位用 quote 在 sections 正文里的真实 indexOf 位置，不用 change_list 的字符偏移 — quote 是后端校验过的连续子串，位置可复现；字符偏移属于审查类条目，本页的维度类条目没有这个字段 — 若用偏移或编造位置，点击会跳到错误段落，用户会以为引用对不上，直接摧毁"可溯源"这条卖点。

## v0.9.0（阶段 4/6：一致性审查页）

- Ruling: 一致性审查页的数据源是 change_list 里 section==='题目约束与数字冲突' 的条目，不是独立的审查结果接口 — 后端没有「GET 审查结果」，findings 不落库、不进 HTTP，只被 change_list 转写成审查类条目塞进报告（实测确认）— 若去臆造一个审查接口或在前端重新跑一致性检查，等于把审查逻辑抄到前端、与服务端分叉，且拿到的是两套可能不一致的结果。
- Ruling: 字符偏移是论文全文偏移，前端用「sections 顺序拼接 + indexOf(text) 校准」复现，精确匹配优先、找不到诚实降级 — 共享状态只存 sections 不含整篇 paper_text，而 char_start 是全文偏移，段间拼接有已知偏差（content 不含标题行）— 若直接拿 char_start 去某段 content 里切，会跳错段落；若静默跳错不标注，用户会以为引用对不上，摧毁可溯源。

## v0.9.0（阶段 5/6：修改建议页）

- Ruling: 修改建议页渲染 change_list 三段全部条目并复用 v1.8.3 的偏移定位，不在前端重排、不重写动作建议 — 后端 change_list.py 已按「题目约束与数字冲突 → 证据不足 → 表述」排序，action 文案也已写好，页面只是转写 — 若前端自己 sort 或重写 action，会与服务端语义分叉，且「先改硬伤、再补证据、最后改表述」的修改顺序会被打乱。

## v0.9.0（阶段 6/6：评测对照页）

- Ruling: 评测对照页只实现汇总（三项指标），「点进单篇看 gold 差异」做占位说明并挂账 — 后端没有单篇评测接口，gold 与 expected_findings 只存在 data/samples/eval/*.json，GET /api/eval/summary 只有聚合数、GET /api/samples 只有 has_gold 布尔，而 P8 不许改后端、不许前端读 data/ — 若前端读 data/ 或臆造 gold，会与服务端数据源分叉，且绕过"不许改后端"的红线；若把单篇做成假数据，评测页就失去了可信度。
- Ruling: source='deterministic' 时三项指标是脚本自检，页面必须标注「非模型评测结果」，不把百分比当成果放大 — 确定性回退的 43.3% / 100% / 0% 是结构自检，不是模型准确率 — 若不标注，用户会把 100% 的引用精确匹配率误读成模型能力，直接误导评审结论。

## v0.9.0（阶段 7/7：前端视觉重设计）

- Ruling: 手稿风格采用方案 B——保留冷白纸底，手工纸感由纸张颗粒 SVG + 手绘线条 + 衬线引文 + 编辑部排版完成 — Sketch 规范的暖纸 #F4F0E8 会违反 source-scan 的"底色 b≥r"断言，且项目校样稿方向本就是纸隐喻而非牛皮纸 — 若强行改暖纸，要么放宽断言意图，要么把"偏冷"这条设计决策连同七版积累一起作废，代价远超收益。

## v0.9.0（阶段 8/8：手稿风修复）

- Ruling: 折线图必须按数据实时生成，静态 sketch-chart.svg 只可作空态占位 — 上一版三张指标卡 import 同一张静态图，三条折线一模一样，用户会读成"三项指标趋势相同"；方案第 10 条原文明写"数据必须精确，只有视觉表现可以是手绘的" — 若继续用静态图，评测页就从"展示指标"变成"展示装饰"，且误导性比没有图更糟。
- Ruling: 本版禁止以"截图偏暖"为由修改纸底令牌 — 实测 --pr-paper 仍是 #f6f7f9、body 计算色 rgb(246,247,249)、source-scan 的"底色 b≥r"断言仍成立，截图发黄来自截图环境 — 若照着失真的截图改纸底，会把已经正确的冷白纸改成暖纸，还要连带改掉断言理由与七版积累的方向决策。
