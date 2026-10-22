# P24 容器骨架与 CORS 报告（v3.8.0）

## 结论

**骨架已就绪，未验证。**本阶段交付静态容器草案、最小 CORS 与可复跑校验；没有构建镜像或启动容器，服务运行状态尚未验证。

`docker --version` 原始失败输出（退出码 127）：

```text
/usr/bin/bash: line 1: docker: command not found
```

## 判据核对

| 判据 | 结论 | 证据 |
|---|---|---|
| 三条 CORS 用例，包含未知源无 ACAO 头 | 满足 | `test_allowed_origin_is_reflected`、`test_unknown_origin_gets_no_allow_origin_header`、`test_preflight_allows_configured_origin_and_method`；`3 passed`。未知源 `http://evil.example` 响应没有 `access-control-allow-origin`。另用指定解释器验证默认值、逗号分隔与 `*` 启动时报错。 |
| 静态校验脚本 | 满足 | `scripts/check_container_skeleton.py` EXIT=0，末行 `summary checks=17 issues=0`。仅用标准库与 PyYAML 6.0.3；没有 Docker 调用或子进程。 |
| 四个 UNVERIFIED 标注 | 满足 | `compose.yaml` 的 frontend/backend/mysql/chroma 各有注释及 `x-verification` 字符串；脚本逐服务检查通过。 |
| Dockerfile 五项要点 | 满足 | `backend/Dockerfile` 首行 UNVERIFIED、`python:3.11-slim`、依赖先复制安装再复制 app、非 root `USER app`、工厂入口 `--factory`；只复制 `app/` 与 requirements，没有复制测试、数据、日志或密钥。末尾注明镜像预期 ≥1GB。 |
| .dockerignore 四项 | 满足 | `.env`、`chroma_data`、`logs`、`node_modules` 均存在；同时排除 `frontend/dist`、上传目录、测试、文档等。 |
| 业务代码未改 | 部分可核 | 本版仅在 `backend/app/api/app.py` 增加 CORS 配置；既有业务路由与 `request_logging_middleware` 未改。开工前工作区已有 50 个已跟踪文件的 diff，结束时为 51 个；全局 `git diff --stat` 因既有未提交改动不能只列 CORS 与测试。本版前后差异已按改前快照区分，未清理或覆盖既有改动。 |
| 无数据写入 | 满足（实现范围） | 本版 CORS、容器草案和静态脚本不写业务数据。Playwright 正常链路新增 review=6、review_dimension=30；review_artifact 保持 24，属于用户预期的 E2E 写入，非本版实现写入。 |

## 门禁结果

- 指定解释器收集后端测试：改前 `469 tests collected`；本版新增 3 条 CORS 用例后为 `472 tests collected`。
- `backend/tests` 连跑两遍：均 EXIT=0，分别 `472 passed, 11 warnings in 195.96s` 与 `472 passed, 11 warnings in 189.98s`。
- `frontend && npm run build` EXIT=0。入口 `index-DMhEH2ho.js` 为 1,125.84 KB raw / 358.45 KB gzip；大屏 chunk 为 533.37 KB / 177.35 KB。没有因 P24 改动前端。
- `frontend && npx vitest run --reporter=dot` EXIT=0，32 个文件、159 tests passed。
- `frontend && npx playwright test` EXIT=1：46 passed、8 failed。新增失败 0；八条都卡在 `confirmed-card` 5 秒等待，逐条如下：
  - `consistency.spec.ts:6`：解析确认链路，`confirmed-card` 未出现。
  - `parse.spec.ts:8`：完整链路，`confirmed-card` 未出现。
  - `parse.spec.ts:61`：粘贴链路，`confirmed-card` 未出现。
  - `scoring.spec.ts:14`：解析到评分链路，`confirmed-card` 未出现。
  - `sketch-fix.spec.ts:6`：评分几何链路，`confirmed-card` 未出现。
  - `sketch-fix.spec.ts:36`：一致性几何链路，`confirmed-card` 未出现。
  - `suggestions.spec.ts:6`：修改建议链路，`confirmed-card` 未出现。
  - `visual.spec.ts:26`：评分高亮链路，`confirmed-card` 未出现。
- `scripts/check_logs.py` EXIT=0，末行 `[ok] 15 dirs, 8 writers, 0 issue (window=20261015..20261021)`。
- `scripts/check_docs_encoding.py docs --strict` EXIT=0，末行 `合计 121 个文件，有问题 0 个`。
- Playwright 预算用例记录首屏 `/parse` 与 `/records` 均为 1,125,849 raw / 355,347 gzip bytes；相对基线增量均为 +8,667 raw / -533 gzip bytes。进入 dashboard 后额外加载 1,659,223 raw / 531,198 gzip bytes，交互耗时 396.0 ms。

## 草案范围与遗留

- `compose.yaml` 的 Chroma tag 使用 `chromadb/chroma:1.5.9` 对齐 Python 依赖版本；本机没有 Docker，未验证该镜像 tag 是否可拉取。
- 镜像未构建过；禁止将本报告解释为容器运行验证。
- `frontend/` 没有 Dockerfile，compose 中以注释说明该服务不可构建。
- chromadb 使镜像预期体积 ≥1GB，这是未验收范围内的已知代价。
- 当前后端仍运行于 `127.0.0.1:8077`，listener PID 12232；本版没有重启后端。
- 八条 `confirmed-card` 超时移交 P25，由 P25 逐条决定修复、调整等待策略或书面豁免。
