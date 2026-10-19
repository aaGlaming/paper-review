# Phase-2 第二期验收报告（v2.3.1 收尾续跑）

> 验收对象：P12～P15。所有中文文件均以 UTF-8 写入。真实证据保存在 `docs/plan/acceptance/calls/`。

## 一、验收环境与基线

- 后端：127.0.0.1:8077；P0 体检接口 HTTP 200。
- 后端基线：`python.exe -m pytest backend/tests -q`，退出码 0，末行 `231 passed, 2 warnings in 8.27s`。
- agent 包：13 个 Python 文件齐全。
- `routes.py` 路由装饰器计数：14。
- `tools.py` 的 `_SubmitArgs.band` 使用 `Literal["充分", "基本", "不足", "证据不足"]`。
- `parent_child.py` 的 `_where` 和 `child_metadata` 均包含 `review_id`。
- 确定性评测：band agreement 26/60，quote exact match 60/60。
- 测试轨迹隔离修复：修复前全量测试增加 43 行孤儿轨迹；修复后增加 0 行。最终数据库为 agent_step 1250 行，r/r1 为 0 行，critique 为 0 行。
- 文档门禁：`python scripts/check_docs_encoding.py docs --strict` 退出码 0。

## 二、五条判据

| 判据 | 结论 | 证据 |
|---|---|---|
| 1 控制流由模型决定 | 通过 | v1.0.4 的 10 篇真实链路记录了 10 种动作序列 |
| 2 工具与参数校验 | 通过 | 六工具注册、Literal 档位枚举、真实引用错误见既有测试与 v1.0.4 证据 |
| 3 循环与终止条件 | 通过 | 四类终止原因均有既有真实轨迹；递归与预算分开记录 |
| 4 轨迹可回放 | 通过 | agent_step 表、只读接口、v2.3.1 P0.4 隔离后的 1250 行 |
| 5 自我修正 | **部分满足** | 本次真实链路 critique=0；单元测试覆盖 guard 降档，但没有真实 critique 降档轨迹 |

## 三、判据 5 真实取证

### 3.1 验收夹具

复制并发布的新赛题为 `probe-critique-acceptance`。导入返回 5 个维度、6 条约束，发布返回 HTTP 200。量规沿用 2024-A，新增 mention 约束关键词为“量子纠缠校准”。关键词在论文样本中复核为 0 命中。

导入时发现原题 exemplars 的主键是全局唯一键，直接复制会与已有记录冲突；为使新赛题包可导入，仅将 pitfall/exemplar 主键改为新赛题前缀，其余字段和语义未变。此调整记录在本报告缺陷清单中。

### 3.2 真实调用

- review_id：`6015ed3b3f1e4e8fbc430efab3204320`
- 创建：HTTP 200，contest_id 为新赛题。
- resume：HTTP 200，status=完成，source=model，agent_terminated_by=all_submitted。
- 五维 band：constraint_check=基本、modeling=基本、presentation=基本、solution=基本、assumption=基本。
- agent_step：31 行；node=critique 的行数为 0。
- 五维响应中的 guard 均为 `downgraded=false`，没有出现“充分”被 guard 降为“基本”的实际行。
- 完整创建、resume、轨迹响应与分支结论见 `calls/v240-01-critique.json`。

### 3.3 结论

本次属于分支 B 的部分满足。真实模型没有提交“充分”，所以没有形成可被 critique 复核的充分档样本。结构上，`tools.py:207` 在 `submit_dimension` 写入结果前先调用 `apply_mention_guard`；`critique.py:77-81` 只处理“充分/基本”，而 runner 当前以 `chat_fn=None` 调用 critique。若提交层已经把“充分”降为“基本”，critique 的 guard 分支不会再降；本次则更早地由模型直接选为“基本”。因此拿到的是 submit 层和代码路径证据，没有真实 critique 降档证据，判据 5 不写成完全通过。

## 四、首期 18 条回归

| 条号 | 判定 | 证据 |
|---|---|---|
| 1.1 | 通过（结构未变） | 本版未改相关模块；git diff --stat |
| 1.2 | 通过（结构未变） | 同上 |
| 1.3 | 通过（结构未变） | 确定性评测 26/60、60/60 |
| 2.1 | 通过（结构未变） | 同上 |
| 2.2 | 通过（结构未变） | 同上 |
| 2.3 | 通过（结构未变） | 同上 |
| 3.1 | 通过（结构未变） | rubric API 与五维量规未改 |
| 3.2 | 通过（结构未变） | 既有测试与页面代码未改 |
| 3.3 | 通过（结构未变） | change_list 代码未改 |
| 3.4 | 通过（结构未变） | 受控词扫描逻辑未改 |
| 4.1 | 通过（结构未变） | evaluation.py 未改 |
| 4.2 | 通过（结构未变） | 前端本版未改 |
| 4.3 | 通过（结构未变） | 存档兼容逻辑未改 |
| 5.1 | 通过（结构未变） | 目录导入与发布接口返回 200 |
| 5.2 | 通过（结构未变） | 坏包校验逻辑未改 |
| 5.3 | 通过（结构未变） | 量规版本发布逻辑未改 |
| 5.4 | 通过（结构未变） | 归档逻辑未改 |
| 5.5 | 通过（结构未变） | 端点与模型关键词检查未改 |

本版三条必须真跑的回归：

- 证据不足不计分：`weighted_sum` 返回 total=0、weight_sum=0、excluded=1。
- 引用失败不进加权：`call_tool` 返回 `ok=false`、`error_code=quote_not_substring`，且 `ctx.results` 为空。
- 报告全文受控词扫描：命中 0。

## 五、成本与延迟

| 指标 | 首期 | 本期可引用实测 |
|---|---:|---:|
| 单篇 chat 次数 | 5 | v1.0.4 的 10 篇真实链路已记录，单篇随模型决策变化 |
| 工具调用次数 | 0 | v1.0.4 汇总记录为 45 次主动提交，轨迹总行 270 |
| 端到端秒数 | report-V2 基线 | 合计 233.6 s，均值 23.4 s，最大 36.6 s |
| token | 不可测 | 不可测；agent_step 未记录 usage |

以上样本均在 15 页以内，单篇延迟仍低于 3 分钟时限。

## 六、发现的缺陷与处置

1. P0 测试轨迹污染已修复：限定 `/tests/agent/` 的 SQLite StaticPool fixture 后，行数从修复前 +43 变为 +0，231 条测试保持全绿。
2. 验收夹具原始 exemplar 主键与已导入赛题冲突；已在新包内加新赛题前缀后成功导入，属于数据包命名缺陷，产品代码未改。
3. critique 真实触发仍未取得；当前真实 runner 传入 `chat_fn=None`，且本次模型没有提交充分档。该项保持部分满足。

## 七、挂账清单

- 在后续版本取得一条真实“提交充分、证据缺必提条件”的样本，再验证 `node=critique/action=downgrade`。
- 若要让 critique 独立调用模型，需要先立 Ruling，明确 runner 的 critique chat_fn 注入方式；本版不改产品语义。
- 验收夹具 `probe-critique-acceptance` 仅用于本次取证，不参与真实评测集。
