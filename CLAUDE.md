# paper-review

代码仓库：https://github.com/aaGlaming/paper-review

本文件只记录项目约束，不写实现。解释器使用 `D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe`，不在项目内建虚拟环境。

- 编排是 LangGraph 状态图。章节未确认不评分。
- 引用必须是切片中的连续子串。对不上则该维为引用失败，不进入加权。
- 证据不足不换算成分数，不进入加权。
- 不输出奖项、名次、获奖概率。
- 对话只走 `/chat/completions`，嵌入只走 `/embeddings`。不部署本地模型。
- 评分、审查、报告不按题号写分支。

## 提示词文档命名

新增或修订版本化文档时遵循 `docs/version/v1.0.1_命名规范.md`：

- 放 `docs/version/<月.日>/`；日期只由目录标记，**不写进文件名**。
- 文件名格式 `v<主>.<阶段位>.<修订号>_<功能描述>.md`，如 `v1.1.0_实现章节确认与检查点.md`。**版本号在最前**，功能描述在后——动宾短语、见名知义，不写「提示词」；统一下划线分隔，禁空格与特殊字符。
- 第一数字固定为 `1`（预定计划完成前不得变动）；**第二数字对齐执行手册阶段号，从 P0 的 `0` 起算**（P0→`v1.0.0`、P1→`v1.1.0`、P2→`v1.2.0` …… P8→`v1.8.0`，总验收→`v1.9.0`）；第三数字是同一阶段内的更新次数。
- 第二位填的是 **P 编号本身**，不是"第几个阶段"的序数（P1 是第二个阶段，第二位仍是 `1`）。
- **进入下一阶段 → 涨第二位；同一阶段内改动 → 只涨第三位。**
- 文档版本号与里程碑版本号（`v0.1.0`～`v1.0.0`）是两套编号，**不得互相推导**。
- 版本号**不得**写在文件名结尾。

## 云端接口

全项目只有 `backend/app/llm/client.py` 发 HTTP，只使用 httpx，不引入厂商 SDK。

- 对话：`POST {LLM_BASE_URL}/chat/completions`，请求头 `Authorization: Bearer {LLM_API_KEY}`，只读 `choices[0].message.content`，返回 `str`。
- 嵌入：`POST {LLM_BASE_URL}/embeddings`，只读 `data[].embedding`，按入参顺序返回等长的二维浮点列表。
- 配置只从环境变量读：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`EMBEDDING_MODEL`。缺失抛 `LLMConfigError`，响应结构不符抛 `LLMResponseError`，不返回空字符串或空列表。
- 超时 30s，网络层异常最多重试 1 次。密钥不打印、不回显、不落盘。

## 验证命令

在项目根目录执行：

```text
& D:\LEARN\AI\programs\AgentTask\env\agent-task\Scripts\python.exe -m pytest backend/tests/llm/test_client.py -q
```

退出码为 0 才算当前版本通过。把命令、退出码和 pytest 最后一行写入 `docs/plan/progress.md`。
