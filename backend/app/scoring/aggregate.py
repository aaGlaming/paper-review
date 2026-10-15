"""加权合计：只累加状态允许加权的维度，权重只读量规数据。

规则逐条对应 v0.6.0 验收：
- `band` 属于（充分、基本、不足）且 `status` 不是「引用失败」的维度才进入合计；
- `band` 为「证据不足」的维度不参与求和；
- `status` 为「引用失败」或「失败」的维度不参与求和；
- 权重只读 `dimensions`；模型返回里若出现 `weight` 或 `score`，一律忽略，不报错也不使用。

本模块是纯函数：不连数据库、不发 HTTP、不导入 `backend.app.importing`、不导入模型客户端。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

# 档位只有四个；前三个可以进入合计，第四个不参与求和。
BANDS: tuple[str, ...] = ("充分", "基本", "不足", "证据不足")
WEIGHTED_BANDS: tuple[str, ...] = ("充分", "基本", "不足")

STATUS_INSUFFICIENT = "证据不足"
STATUS_CITATION_FAILURE = "引用失败"
STATUS_FAILURE = "失败"
# 维度状态词表：前三个就是「选档成功」时的档位本身，后三个是三种不进入加权的情形。
SCORE_STATUSES: tuple[str, ...] = (
    "充分",
    "基本",
    "不足",
    STATUS_INSUFFICIENT,
    STATUS_CITATION_FAILURE,
    STATUS_FAILURE,
)

REASON_INSUFFICIENT = "证据不足不参与加权"
REASON_CITATION_FAILURE = "引用失败不参与加权"
REASON_FAILURE = "选档失败不参与加权"
REASON_BAND_MISSING = "档位缺失或不合法"
REASON_UNKNOWN_DIMENSION = "量规里没有这一维，权重按 0 计"


def dimension_code_of(item: Mapping[str, Any]) -> str:
    """维度编码：量规数据写 dimension_code，量规表里这一列叫 code，两种都认。"""
    if not isinstance(item, Mapping):
        return ""
    return str(item.get("dimension_code") or item.get("code") or "")


def _to_weight(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def weight_table(dimensions: Iterable[Mapping[str, Any]] | None) -> dict[str, int]:
    """权重表只来自量规数据。"""
    table: dict[str, int] = {}
    for dimension in dimensions or ():
        code = dimension_code_of(dimension)
        if code:
            table[code] = _to_weight(dimension.get("weight"))
    return table


def weighted_sum(
    dimensions: Sequence[Mapping[str, Any]] | None,
    dimension_results: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """把通过校验的维度按量规权重加总。

    `total` 与 `weight_sum` 都是「进入合计的维度权重之和」；`rubric_weight_sum` 是量规全部维度的权重之和，
    用来说明还有多少权重没有依据。被排除的维度连同原因一起返回，页面据此单列。
    """
    table = weight_table(dimensions)
    weighted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    total = 0

    for result in dimension_results or ():
        code = dimension_code_of(result)
        band = result.get("band") if isinstance(result, Mapping) else None
        status = result.get("status") if isinstance(result, Mapping) else None
        weight = table.get(code, 0)
        entry = {
            "dimension_code": code,
            "band": band,
            "status": status,
            "weight": weight,
        }

        if code not in table:
            excluded.append({**entry, "contribution": 0, "reason": REASON_UNKNOWN_DIMENSION})
        elif band == STATUS_INSUFFICIENT:
            excluded.append({**entry, "contribution": 0, "reason": REASON_INSUFFICIENT})
        elif status == STATUS_CITATION_FAILURE:
            excluded.append({**entry, "contribution": 0, "reason": REASON_CITATION_FAILURE})
        elif status == STATUS_FAILURE:
            excluded.append({**entry, "contribution": 0, "reason": REASON_FAILURE})
        elif band not in WEIGHTED_BANDS:
            excluded.append({**entry, "contribution": 0, "reason": REASON_BAND_MISSING})
        else:
            total += weight
            weighted.append({**entry, "contribution": weight})

    return {
        "total": total,
        "weight_sum": total,
        "rubric_weight_sum": sum(table.values()),
        "weighted": weighted,
        "excluded": excluded,
    }
