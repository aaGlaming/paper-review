# P23 收口报告（v3.7.2）

## 一、结论

P23 按当前计划范围收口，允许进入 P24；本轮保留 12 篇 gold、不扩充分母，并将分母小于 5 的非零指标呈现为“样本过少”。

## 二、判据核对

| 判据 | 结论 | 证据 |
|---|---|---|
| 12 篇 gold 的字段、维度码和档位满足契约，文件保持只读 | 满足 | `scripts/check_eval_gold.py`；`backend/tests/report/test_eval_gold.py::test_eval_gold_dimension_codes_match_contest_rubric_exactly`；门禁前后 12 个 JSON 的 SHA256 清单一致（见 progress） |
| 不改变原始 rate，并标记小样本和零分母 | 满足 | `backend/tests/report/test_report_and_eval.py::test_eval_metrics_mark_small_denominator_without_changing_rates`、`::test_empty_eval_metric_is_not_low_sample`；保留 `1/2` 的 `rate≈0.5` 既有断言 |
| 小样本卡隐藏百分比、显示分母说明且不绘制折线；常规卡仍显示百分比 | 满足 | `frontend/tests/unit/metric-card.spec.ts` 两条用例；`frontend/tests/unit/eval-view.spec.ts` 的评测页契约用例 |
| 回归门禁稳定，既有确认链路红灯逐条登记 | 满足（新增失败 0） | pytest 两遍均 `469 passed`；build EXIT=0；Vitest `159 passed`；Playwright `46 passed / 8 failed`，8 条均为下表逐项移交的 `confirmed-card` 5 秒等待失败；Gold、日志与文档编码检查通过，详见 v3.7.2 progress |
| 不新增、改写 gold，不运行模型评测，不改评分链路或 Chroma | 满足 | 12 个 gold JSON 的 SHA256 门禁前后对照；本轮未调用模型评测 API，未改评分图与 Chroma |

## 三、不补 gold 的决定

本轮不执行 §8.1 中“可选补 1 篇”：v3.7.0 的 136 条人工复核候选分布为 2024-A 133 条、2024-C 3 条、2025-A 0 条，候选主要集中在 `constraint_check`。现有 gold 已按赛题 4/4/4 均衡；只给 2024-A 补 1 篇会变成 5/4/4。若要保持均衡还需给 2025-A 补样本，但该赛题没有候选，本轮物理上做不到。把证据不足标注从 2 增至 4 仍只有三个取值级别，不会增加新的信息级别。

可回滚条件：若将来出现 ≥3 条证据不足标注且分布在 ≥2 个赛题，再补入样本。

## 四、遗留

- “证据不足” gold 分母仍为 2；本版只把它从百分比降到“样本过少”，没有消除样本稀缺。
- 模型档 13/60 无法复跑；数值来自历史单次记录 `docs/plan/acceptance/calls/16-eval-model.json`，不是本次实测，本轮未请求模型评测。
- `source=deterministic` 的 26/60 也只引用 v3.7.0 的历史复算；本版只改变小样本呈现，未重新跑整套评测，也未改原始 rate。
- `run_eval()` 不注入 `agent_runner`，评测不度量工具调用、`critique` 降档或预算终止。

## 五、移交清单

- 以下八条 `confirmed-card` 超时移交 P25 收口。P25 必须逐条署名并从“修复 / 改等待策略 / 书面豁免”中选择处置，不得只写“沿用”：
  1. `frontend/tests/e2e/consistency.spec.ts`：确认卡未在 5 秒内出现。
  2. `frontend/tests/e2e/parse.spec.ts` 完整链路：确认卡未在 5 秒内出现。
  3. `frontend/tests/e2e/parse.spec.ts` 粘贴正文链路：确认卡未在 5 秒内出现。
  4. `frontend/tests/e2e/scoring.spec.ts`：确认卡未在 5 秒内出现。
  5. `frontend/tests/e2e/sketch-fix.spec.ts` 评分链路：确认卡未在 5 秒内出现。
  6. `frontend/tests/e2e/sketch-fix.spec.ts` 一致性链路：确认卡未在 5 秒内出现。
  7. `frontend/tests/e2e/suggestions.spec.ts`：确认卡未在 5 秒内出现。
  8. `frontend/tests/e2e/visual.spec.ts`：确认卡未在 5 秒内出现。
- P24 只交付骨架与草案，不列为验收阶段。
- P26 回归首期 18 条与三期八条。
