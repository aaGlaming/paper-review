# data 目录归档说明

> 更新：2026-10-19 · 归档前 `data/` 顶层混放三套赛题的原始 PDF，与系统读取路径混在一起

## 一、当前结构

```text
data/
├── papers/                          原始素材（按赛题归档，代码不直接读）
│   ├── cumcm-2024-A/
│   │   ├── A题.pdf                  题面（文件名以「题」结尾）
│   │   ├── A016.pdf  A053.pdf  A163.pdf  A178.pdf  A242.pdf
│   ├── cumcm-2024-C/
│   │   ├── C题.pdf
│   │   ├── C038.pdf  C063.pdf  C094.pdf  C234.pdf
│   └── cumcm-2025-A/
│       ├── A题.pdf
│       └── A196.pdf
├── contests/<赛题>/                  赛题数据包（代码读取，导入与评审都依赖）
│   ├── contest.json                 题面元信息 + statement 全文
│   ├── rubric.json                  五维量规
│   ├── constraints.json             硬约束
│   ├── pitfalls.json                常见错误
│   └── exemplars.json               优秀片段
└── samples/                         论文正文与评测集（代码读取）
    ├── <赛题>-<编号>.md              由 PDF OCR 转出的正文，共 10 篇
    ├── eval/                        12 篇评测论文（md + gold json）
    └── bench-dragon.md / planting.md / smoke.md   测试夹具，勿删
```

## 二、两条路径分工

| 目录 | 谁读 | 能不能改结构 |
|---|---|---|
| `papers/` | 只有 `scripts/` 下的转换脚本 | **可以自由调整**，代码不依赖 |
| `contests/` | `backend/app/importing/catalog.py`、`report/evaluation.py` | **不能动**，改路径即改产品行为 |
| `samples/` | `backend/app/review/samples.py`、`report/catalog.py`、四个测试文件 | **不能动** |

## 三、脚本不再写死题号

`batch_papers.py` 与 `update_statements.py` 原先硬编码三道题号和 `data/cumcm-*/论文/` 路径，现改为**扫描 `data/papers/` 的子目录自动发现**：

- 新增赛题只需 `mkdir data/papers/<赛题>/` 并放入 PDF，不改代码；
- 题面 PDF 按文件名后缀「题.pdf」识别并从论文批次中排除。

用法：

```bash
python scripts/batch_papers.py            # 转缺失的论文（默认 4 路并行）
python scripts/batch_papers.py --only A053
python scripts/update_statements.py       # 用题面 PDF 刷新 contest.json 的 statement
```

## 四、10 篇论文的来历

原始 PDF 均为**扫描件**（无文本层），正文由 `scripts/pdf_to_md.py` 经 OCR 转出：

- 工具：`rapidocr-onnxruntime`，200 dpi；
- 规模：约 2.6 万～5.6 万字符，共 519 个章节；
- 已知上限：公式、表格、图片标注会丢失，不适合据此评估评分质量，只适合验证流程与判定逻辑；
- 章节切分与分类规则见 `backend/app/graph/review_graph.py` 的 `_SECTION_KEYWORDS`。

## 五、三篇演示稿为什么留着

`bench-dragon.md`、`planting.md`、`smoke.md` 不是废数据，是**测试夹具**——`tests/report/test_review_flow.py`、`tests/review/test_demo_conflicts.py`、`tests/scoring/test_quote_and_weight.py` 按文件名直接读取并断言具体结果，且 `report/evaluation.py` 用 `len(DEMO_FILES)` 作为语料口径。删除会直接让 231 条测试失败。

系统界面不再展示它们：`list_samples()` 优先列 `papers/` 转出的真实论文，一篇都没有时才回退到这三篇。
## 六、验收夹具

contests/probe-critique-acceptance/ 是 Phase-2 判据 5 的验收夹具，只用于取证 mention guard 与 critique 路径，不参与真实评测集。
