"""进程内指标累积与 Prometheus 文本格式输出（手写 exposition，不引 prometheus_client）。

三条口径先说清楚，否则看板会被读歪：

1. **计数只在本进程内累积，进程重启即归零**，这是 counter 的正常语义；
   多 worker 各记各的，不做聚合。要跨进程聚合得上 pushgateway 或多进程模式，
   本项目单进程部署，用不上。
2. **除预置的那一条零值行外，未观测到的标签组合不输出零值行**。
   `paper_review_reviews_total{status="完成"}` 会以 0 起步，看板有基线；
   而 `llm_calls_total` 在第一次模型调用之前只有 HELP/TYPE、没有样本行——
   这在 exposition 里是合法的（指标族存在、序列为空），Prometheus 查出来是
   「无数据」而不是 0。反过来给 `失败` 也播一条恒为 0 的行更糟：
   运维会以为没有失败，实际是失败路径压根不走这里。
3. `reviews_total` 只在 `save_review` 真正落库成功后 `+1`，而失败路径在落库之前
   就抛了异常，因此这个 counter 实际统计的是**走完保存的成功评审**；
   失败次数看 `logs/errors/`，不要拿这个指标当失败率分母。
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

_LOCK = threading.Lock()
# 桶边界按 le 语义累积：某次观测值 <= 某个边界时，该边界及其右边的所有桶都 +1。
LLM_BUCKETS: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0, 10.0, float("inf"))
RETRIEVE_BUCKETS: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0, float("inf"))
# `save_review` 成功时只会记这一个状态（见 report/store.py），先播一条零值行，
# 免得第一次评审之前看板显示「无数据」而不是 0。失败路径不落库，不给它播零值。
_SEED_REVIEW_STATUSES: tuple[str, ...] = ("完成",)
_reviews: dict[str, int] = {}
_auth: dict[str, int] = {"success": 0, "failure": 0}
_llm_calls: dict[tuple[str, str], int] = {}
_llm_buckets: dict[float, int] = {bucket: 0 for bucket in LLM_BUCKETS}
_llm_sum = 0.0
_llm_count = 0
_retrieve_buckets: dict[float, int] = {bucket: 0 for bucket in RETRIEVE_BUCKETS}


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _number(value: float | int) -> str:
    if value == float("inf"):
        return "+Inf"
    if isinstance(value, int):
        return str(value)
    return format(value, ".6f").rstrip("0").rstrip(".") or "0"


def _review_series() -> list[str]:
    """已观测到的状态与预置零值状态的并集，顺序稳定。"""
    return sorted(set(_SEED_REVIEW_STATUSES) | set(_reviews))


def _bucket_lines(name: str, buckets: Iterable[float], values: dict[float, int]) -> list[str]:
    return [
        f'{name}_bucket{{le="{_number(boundary)}"}} {values[boundary]}'
        for boundary in buckets
    ]


def inc_reviews(status: str) -> None:
    with _LOCK:
        _reviews[str(status)] = _reviews.get(str(status), 0) + 1


def inc_auth(ok: bool) -> None:
    """登录成败计数。成功与失败各算各的，互不影响。"""
    with _LOCK:
        key = "success" if ok else "failure"
        _auth[key] = _auth.get(key, 0) + 1


def observe_llm(model: str, ok: bool, elapsed_s: float) -> None:
    global _llm_sum, _llm_count
    elapsed = max(0.0, float(elapsed_s))
    result = "ok" if ok else "error"
    with _LOCK:
        key = (str(model), result)
        _llm_calls[key] = _llm_calls.get(key, 0) + 1
        _llm_sum += elapsed
        _llm_count += 1
        for boundary in LLM_BUCKETS:
            if elapsed <= boundary:
                _llm_buckets[boundary] += 1


def observe_retrieve_parents(count: int) -> None:
    amount = max(0, int(count))
    with _LOCK:
        for boundary in RETRIEVE_BUCKETS:
            if amount <= boundary:
                _retrieve_buckets[boundary] += 1


def render() -> str:
    with _LOCK:
        lines = [
            "# HELP paper_review_reviews_total 评审总数（按状态）",
            "# TYPE paper_review_reviews_total counter",
        ]
        for status in _review_series():
            lines.append(
                f'paper_review_reviews_total{{status="{_escape(status)}"}} {_reviews.get(status, 0)}'
            )

        lines.extend([
            "# HELP paper_review_llm_calls_total 模型调用次数（按模型与结果）",
            "# TYPE paper_review_llm_calls_total counter",
        ])
        for (model, result), count in sorted(_llm_calls.items()):
            lines.append(
                f'paper_review_llm_calls_total{{model="{_escape(model)}",result="{_escape(result)}"}} {count}'
            )

        lines.extend([
            "# HELP paper_review_llm_latency_seconds 模型调用耗时",
            "# TYPE paper_review_llm_latency_seconds histogram",
            *_bucket_lines("paper_review_llm_latency_seconds", LLM_BUCKETS, _llm_buckets),
            f"paper_review_llm_latency_seconds_sum {_number(_llm_sum)}",
            f"paper_review_llm_latency_seconds_count {_llm_count}",
            "# HELP paper_review_retrieve_parents 每维最终保留的父块数",
            "# TYPE paper_review_retrieve_parents histogram",
            *_bucket_lines("paper_review_retrieve_parents", RETRIEVE_BUCKETS, _retrieve_buckets),
            "# HELP paper_review_auth_total 登录次数（P17 已接登录成败）",
            "# TYPE paper_review_auth_total counter",
            f'paper_review_auth_total{{result="success"}} {_auth.get("success", 0)}',
            f'paper_review_auth_total{{result="failure"}} {_auth.get("failure", 0)}',
        ])
        return "\n".join(lines) + "\n"


def reset_metrics_for_tests() -> None:
    global _llm_sum, _llm_count
    with _LOCK:
        _reviews.clear()
        _auth.clear()
        _auth.update({"success": 0, "failure": 0})
        _llm_calls.clear()
        for values in (_llm_buckets, _retrieve_buckets):
            for bucket in values:
                values[bucket] = 0
        _llm_sum = 0.0
        _llm_count = 0
