本目录存放 12 篇自建评测论文，每篇由同名两个文件组成：

- `eval-NN.md`：论文正文，用 ATX 标题分节，表格独立成块。
- `eval-NN.json`：元数据，字段为 `paper_id`、`contest_id`、`title`、`gold`、`expected_findings`。

`gold` 是五个维度的档位对照（`dimension_code` 与 `band`），`expected_findings` 是预期被查出的问题。
读入函数见 `backend/app/review/samples.py` 的 `load_eval_papers()`；档位一致率等对比计算在 v0.8.0 做。
全部为项目自建，不是真实参赛论文，数值均为构造值。

本文件是目录说明，不是评测样例，读入时按文件名前缀跳过。
