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
