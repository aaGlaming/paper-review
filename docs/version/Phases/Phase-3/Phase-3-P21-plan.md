# P21（P17）上传与解析增强细则

> 本文把 Phase-3 总体计划中保留下来的 P21 范围展开为可分版执行契约。需求分析 V3 §9.1 原文当前不在仓库；以下内容只据可核对的计划行、现有代码和样本推导，原文补齐后必须逐项校准。本文件中的工程建议不冒充原始需求。

## 1. 证据来源与缺口

| 结论 | 可追溯来源 | 证据及边界 |
|---|---|---|
| P21 输入类型为 md、docx、pdf，产物为主张、表格、引用 | `docs/version/Phases/Phase-3/Phase-3-plan.md:22,56,480` | 计划列出了类型与三类产物，没有大小、页数、编码、字段或解析准确率条款。 |
| P21 先于 P22，供 align 消费 | `docs/version/Phases/Phase-3/Phase-3-plan.md:32,63,480-481` | P22 的 align 读取 P21 产物；这是顺序关系，不等于 P22 算法要求。 |
| 原文为空白时不得创建评审 | `backend/app/api/routes.py:115-128`；`docs/version/Phases/Phase-1/paper-review.md:127` | `_resolve_paper_text` 对空白文本返回 400；Phase-1 PDF 路径要求抽取失败报错，不把空字符串当论文。 |
| section 切分依赖 ATX 标题 | `backend/app/graph/review_graph.py:74,127-172` | `_HEADING_RE` 识别 `#` 标题；无标题时正文会整体成为「未分类」。 |
| review、dimension、session 的既有列与命名 | `backend/app/report/models.py:33-78` | `Review` 主键 `review_id`；`ReviewDimension` 以 review 和 dimension 组成主键并级联；`ReviewSession.paper_text` 保存评审文本。 |
| parent 的原文定位口径 | `backend/app/retrieve/models.py:22-29` | `PaperParent.char_span` 保存起止字符位置；新产物位置沿用半开区间 `[char_start, char_end)`，相对于规范化后的评审文本。 |
| 样本中的正例与反例 | `data/samples/smoke.md:8-9,40-42`；`data/samples/planting.md:37-42,51-52` | 摘要中的结论和方括号引用、Markdown 表格、参考文献条目及正文提及表格均为可核对示例。样本注明是演示材料，不是权威答案。 |
| PDF 原始归档形态 | `data/papers/` | 归档有 13 个 PDF，分布在多层目录；读取页数的本地探测因至少一个文件无法由当前 PDF reader 解码而未得到可靠全量上限。 |
| P20 已收口 | `docs/plan/acceptance/report-P20.md:5-7` | P20 五条证据沿用 v3.4.1 实测；报告明确本阶段尚未实现上传和解析。 |
| 需求分析原文缺失 | 当前仓库检索 `docs/` 未找到需求分析 V3 §9.1 原文 | 因此本细则不声称复述 §9.1；字段、限制和拆版内容中凡无原文支持者均标为工程推导或待决，不应视为已批准的产品要求。 |

## 2. 输入契约

### 2.1 已有计划支持的输入

系统上传仅接受 Markdown（`.md`）与 Word（`.docx`）。PDF 作为离线一次性导入材料：离线 OCR 或文本整理结果以 Markdown 形式上传，运行时不做 PDF 解析；归档 PDF 仅作原始凭证。扩展名白名单是工程校验建议，MIME 类型不能单独证明内容格式。空文件、只含空白的文本、抽取后为空的文档都必须拒绝并返回可读原因，不得创建空 `paper_text` 或空评审。

### 2.2 大小与页数上限：决策值与来源

需求分析 V3 §9.1 原文尚未找到。下面数值是**工程决策**，不是声称来自缺失需求；若取得需求分析 V3 §9.1 原文，以原文覆盖本表。

| 项 | 值 | 依据 | 来源 |
|---|---:|---|---|
| 单文件字节 | ≤ 20,000,000 bytes（20 MB，十进制） | 按 `data/samples/` 最大单文件 122.3 KB / 52,648 字符与 `data/papers/` 最大 9.21 MB 留出约 2 倍于最大归档 PDF 的字节余量，同时限制单次上传和落盘空间。 | 工程决策；样本与归档大小为本机实测。 |
| PDF 页数（离线归档参考） | ≤ 80 页；不是运行时上传限制 | `data/papers/` 经一次性离线探测最大 62 页，80 页留 18 页（约 29%）余量。此值用于离线资料处理决策，不形成线上 PDF 接收或解析承诺。 | 工程决策；归档页数为本机实测。 |
| 规范化文本 | ≤ 200,000 个 Unicode 字符 | 按最大单文件样本 52,648 字符留出约 3.8 倍字符量余量；另测得样本目录的最高字符数是 56,185，按此仍留出约 3.56 倍余量。字符上限独立于字节上限，按解码、去 BOM、换行规范化后的文本计数。 | 工程决策；样本字符数为本机实测。 |
| 本版允许类型 | 上传 `.md`、`.docx`；PDF 仅离线导入 | Markdown 严格按 UTF-8/GB18030 解码；DOCX 结构转文本；离线 OCR/文本整理结果以 Markdown 进入系统，运行时不解析 PDF。 | 工程决策；原 v3.5.3 PDF 探测计划因口径变更取消。 |

上述 `data/samples/` 最大单文件 122.3 KB / 52,648 字符、另有样本最高 56,185 字符，`data/papers/` 最大 9.21 MB 与 `pdfminer.six` 实测最大 62 页用于留出余量，不替代需求原文。DOCX 页数受字体和渲染器影响，不在本版定义页数判定。

### 2.3 编码与文本抽取

- Markdown：先按 UTF-8（允许并剥离 UTF-8 BOM）严格解码；UTF-8 失败时再按 GB18030 严格解码。两者均失败时返回“文件编码不是有效 UTF-8/GB18030”，不得用替换字符静默损坏原文。解码后统一 `CRLF`/`CR` 为 `LF`；字符数与 `paper_chars` 在此规范化后计数，落盘仍保存原始字节。编码顺序与换行归一化是工程推导，待 §9.1 校准。
- DOCX：容器/XML 中的文本由解析器解码为 Unicode；本条所称 UTF-8/GB18030 输入规则不用于 DOCX 内部 XML。抽取与段落顺序必须在 v3.5.2 固定并测试。
- PDF：PDF 文本层与 OCR 的判定不在系统内实现；归档 PDF 仅作原始凭证。需要导入的 PDF 由系统外工具转换/识别为 Markdown 后上传，OCR 产物进入系统时按普通 Markdown 处理。外部转换可能带来识别错误与定位偏差，来源由导入方负责。
- 任一格式抽取结果为空或全空白时返回包含文件名/格式和失败阶段的可读错误，不创建评审。此规则沿用 Phase-1 `paper-review.md:127`。

## 3. 中间格式与 section 兜底

DOCX 在系统内转为带 ATX 标题的规范化 Markdown，再交给现有 `_parse_sections`；PDF 不进入运行时转换链路，离线 OCR/文本整理结果作为 Markdown 输入。原因是 `review_graph.py` 的 `_HEADING_RE` 只识别 `#` 标题；直接传原始段落或文档对象不会形成现有 section 树。转换结果作为 `ReviewSession.paper_text` 的规范化文本，产物字符偏移统一指向这一文本，使用 Python Unicode 字符索引的半开区间 `[start, end)`，与 `PaperParent.char_span` 的起止偏移口径一致。

缺少标题时沿用现有实现：正文整体进入「未分类」，不根据字号猜标题。字号推断会引入版式规则和误分类，当前没有需求或已验证依据。解析器若能明确提取标题，则生成 ATX 标题；不能明确提取时保留为正文并让 `_parse_sections` 兜底。

## 4. 三类产物

共同要求：每条记录绑定 `review_id`，有稳定 `ordinal`，并以规范化 `paper_text` 的字符半开区间定位。偏移必须满足 `0 <= char_start < char_end <= len(paper_text)`；前端用它定位高亮，P22 align 用它回读证据上下文。各类字段分列保存，不用万能 JSON。

| 类型 | 判定依据（工程推导，待 §9.1 校准） | 最小必填字段 | 样本正例 | 样本反例 |
|---|---|---|---|---|
| `claim`（主张） | 能被原文位置核验的结果、方法结论或明确论断；不把标题、背景陈述自动当作主张。 | `review_id`、`artifact_type`、`ordinal`、字符区间、`claim_text`；`section_type` 可空，供评分与 P22 align 使用。 | `smoke.md:8-9` 摘要中“有效遮蔽时长为 22.4 s”是可定位的结果主张。 | `smoke.md:3` 的演示材料免责声明是说明文字，不是研究结论主张。 |
| `table`（表格） | 文档中实际存在的行列结构；正文提到“表”或文件名不构成表格产物。 | `review_id`、`artifact_type`、`ordinal`、字符区间、`table_markdown`；按行列拆分不是本阶段必需，规范化 Markdown 保留结构供前端展示、P22 对齐。 | `planting.md:37-40` 的 `项目/数值` Markdown 表格。 | `planting.md:42` 正文提及“表 1”及结果文件，但该句本身不是表格。 |
| `citation`（文内引用） | 正文中明确指向来源的引用标记；文末参考文献表条目单独不算文内引用。 | `review_id`、`artifact_type`、`ordinal`、字符区间、`citation_text`；评分与 P22 align 可消费引用原文和位置。 | `smoke.md:8-9` 句末的 `[12]`。 | `smoke.md:40-42` 的参考文献列表条目是书目，不是正文中的引用锚点。 |

表格采用 `table_markdown` 保存片段，不额外存行号/列号：本版没有按单元格消费方，Markdown 行列标记已足以展示和后续读取；若 P22 要单元格级对齐，应由证据和独立迁移再增加列。`section_type` 取现有 section 类型，可空；存在时帮助评分、P22 align 和前端显示章节归属，不新造术语体系。

## 5. `review_artifact` 表结构

本版实现列如下；每列都对应已有消费者或稳定性约束：

| 列 | 类型 / 约束 | 为什么需要、谁消费 |
|---|---|---|
| `artifact_id` | 整数自增主键 | 唯一标识一条产物，供只读 API 和前端作为行键；不承担跨评审顺序。 |
| `review_id` | `VARCHAR(64)`，非空，外键到 `review.review_id`，`ON DELETE CASCADE` | 归属父评审；API 按它筛选，数据库负责清理孤儿。 |
| `ordinal` | 非负整数，非空；唯一约束 `(review_id, ordinal)` | 同一评审内的确定顺序；前端按此呈现，P22 可复现读取顺序。 |
| `artifact_type` | `VARCHAR(16)`，非空；仅允许常量元组 `claim/table/citation` | 区分解析类型；API/前端选择对应列，写入函数在落库前拒绝非法值。 |
| `section_type` | 可空 `VARCHAR(32)` | 复用现有 section 分类；评分、P22 align 和前端可显示章节上下文。 |
| `char_start`, `char_end` | 非空整数，半开字符区间 | 回定位到规范化文本；前端高亮，P22 align 回读上下文。 |
| `claim_text` | 可空 `TEXT` | 仅 `claim` 必填；评分及 P22 align 消费主张文本。 |
| `table_markdown` | 可空 `TEXT` | 仅 `table` 必填；前端展示结构，P22 可读取表格证据。 |
| `citation_text` | 可空 `TEXT` | 仅 `citation` 必填；评分及 P22 align 消费引用锚点。 |

不增加通用 JSON、不存重复的创建时间或源文件名：当前消费者可由 `review_id` 与 `ReviewSession.paper_text` 建立上下文，计划未定义源文件元数据契约。`save_artifacts` 文档字符串必须写明：`claim` 要有非空 `claim_text`，`table` 要有非空 `table_markdown`，`citation` 要有非空 `citation_text`；所有类型都要有有效字符区间和非负 ordinal，且 ordinal 在同一批次/评审内不可重复。缺项以可读异常拒绝，不能静默丢弃。

## 6. HTTP 接口契约

本阶段仅暴露只读 `GET /api/reviews/{review_id}/artifacts`。教师可读全部已存在评审，学生只读自己的评审；复用 routes 中 `_check_review_access` 的归属检查。评审存在但没有产物时返回 `200 []`；不存在的评审沿用现有 404 行为。响应按 `ordinal, artifact_id` 稳定排序，并仅返回契约表中的必要列。

本阶段不提供 HTTP 写入接口。没有受控上传与解析来源时，开放写接口会允许客户端手工灌入无法验证来源的产物。内部 `save_artifacts(review_id, items, session=None)` 仅供本阶段契约测试调用；后续正式写入只能由受控解析流程调用。

## 7. P21 完成判据与拆版

### P21 整体完成判据

- [ ] 找回并逐条对照需求分析 V3 §9.1 原文，校准本细则中所有标为推导/待决的字段与限制。
- [ ] md/docx 的文件、编码与大小边界有契约测试；PDF 只作离线原始凭证，离线整理为 Markdown 后再导入；坏文件、空抽取均返回可读错误且不创建空评审。
- [ ] DOCX 转为 ATX Markdown 后能由 `_parse_sections` 得到 section；无标题回退为「未分类」。PDF 不在线解析。
- [ ] claim、table、citation 三类产物均有类型字段校验、有效原文偏移、稳定顺序、正反例测试，并可通过只读 API 按归属读取；claim 按本节规则抽取，不合并相互矛盾的主张。
- [ ] 归档 PDF 的文本层/OCR 判定与转换在系统外完成，结果以 Markdown 导入；系统运行路径不承诺判页或解析。
- [ ] 解析过程具备可观测日志；落库仅由已验证的解析流程触发，学生/教师读取权限通过测试。
- [ ] P22 消费契约由 align 侧测试验证；本判据不要求本阶段实现 align。

### 分版计划

| 版本 | 范围 | 退出判据 |
|---|---|---|
| v3.5.0 | 本版：重写细则；`review_artifact` DDL、内部校验保存函数和只读 API；不上传、不解析。 | 迁移幂等；三类非法/缺字段校验；级联与顺序测试；教师可读、学生仅本人、空列表 200；非目标边界写入 progress。 |
| v3.5.1 | 实现 `POST /api/uploads` 的 multipart Markdown 上传；仅 `.md`，限制 20,000,000 bytes 与规范化后 200,000 字符；严格 UTF-8 BOM / GB18030 解码。DOCX/PDF 入口明确拒绝。 | Markdown 正常、编码、空白、字节/字符边界、类型、权限、落库回滚与落盘清理测试通过；拒绝请求不创建 review、不落盘。 |
| v3.5.2 | Markdown 与 DOCX 文本提取、规范化 ATX Markdown 和 section 解析。 | UTF-8/GB18030、BOM、坏编码、空抽取、标题与未分类回退有固定测试；解析文本与字符偏移一致。 |
| v3.5.4 | 对已上传 Markdown 按本节规则确定性抽取 claim/table/citation，经受控 extract 端点事务性幂等写入。原 v3.5.3 PDF 探测计划因口径变更取消。 | 三类正反例、字段完整性、原文区间、稳定 ordinal、幂等替换、权限与事务回滚测试通过；无模型调用。 |
| v3.5.5 | 前端读取并展示三类产物；PDF 继续只作为离线原始凭证，外部处理结果以 Markdown 上传；对齐交给 P22。 | 教师与学生读取权限、空态、来源定位、三类展示及端到端回归通过；不在线解析 PDF，P22 尚未实现。 |
| v3.5.6 | P21 工程收口：核对需求分析 V3 §9.1 原文、补齐端到端契约证据与交接文档。 | 原文缺口已校准或明确保留；P21 输入、产物、权限和偏移契约可追溯，P22 消费侧有独立验收入口。 |

各版退出判据是执行建议，须在恢复 §9.1 后调整，不作为缺失原文的替代。

## 8. 非目标与明确边界

- `align` 节点、赛题匹配、错题即停与维度映射属于 P22，不在 P21 实现。
- 不重做现有 section 分类词表，不依字号猜标题；切不出标题时沿用「未分类」。
- v3.5.0 不做上传 HTTP 接口，不解析 DOCX，不引入解析或 OCR 依赖，不改前端。
- PDF 解析与 OCR 不属于运行时路径；归档 PDF 仅作原始凭证，离线 OCR/整理结果以 Markdown 导入。
- v3.5.0 不改评审、评分、检索或日志业务写入路径；数据库写操作仅新建 `review_artifact` DDL 与测试夹具数据。
- 不在没有原文证据时承诺体积/页数上限、OCR 准确率、表格单元格坐标或引用解析精度。
