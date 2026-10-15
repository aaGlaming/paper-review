"""逐维检索：三路材料先各自过滤召回，再合并去重、一次重排、截断到最多 4 段。

顺序固定，不得调换：
1. 三路（档位说明 `band_text`、论文子块 `paper_child`、扣分点 `pitfall`）**各自**按
   `contest_id`、`rubric_id`、`section_type` 过滤并召回；
2. 合并三路候选，按 `parent_id` 去重（命中同一父块的 `chunk_ids` 合并保留）；
3. 对合并后的候选做**一次**重排，只改顺序，不加回被过滤掉的片段；
4. 截断到**最多 4 段**——是「三路合并后总共 4 段」，不是每路各 4 段。

两轮检索：第一轮有结果就不再查；第一轮为空才改写查询再查一轮；第二轮仍为空则该维状态为
「证据不足」，检索函数调用次数**恰为 2**，不得出现第三次。「证据不足」由检索结果触发，
不由模型临时决定跳过检索。

本版不调用 `chat()` / `embed()`，不导入模型客户端，不发 HTTP：向量由调用方显式传入。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from .parent_child import ParentBlock, ParentRepository, search_children_then_parents
from .rerank import validate_rerank_order

BAND_TEXT_ROUTE = "band_text"
PAPER_CHILD_ROUTE = "paper_child"
PITFALL_ROUTE = "pitfall"
ROUTES: tuple[str, ...] = (BAND_TEXT_ROUTE, PAPER_CHILD_ROUTE, PITFALL_ROUTE)

MAX_PARENTS = 4
PER_ROUTE_LIMIT = 6
MAX_ROUNDS = 2

STATUS_HIT = "命中"
STATUS_INSUFFICIENT = "证据不足"
# 维度只有这两个状态：命中，或由检索结果触发的证据不足。
DIMENSION_STATUSES: tuple[str, ...] = (STATUS_HIT, STATUS_INSUFFICIENT)


@dataclass(frozen=True)
class DimensionRetrieval:
    """一个维度的检索结果：状态、轮数、查询与父块列表。"""

    dimension_code: str
    status: str
    rounds: int
    queries: tuple[str, ...] = ()
    parents: tuple[ParentBlock, ...] = ()
    route_hits: Mapping[str, int] = field(default_factory=dict)


def default_rewrite(query: str, round_index: int, dimension_code: str) -> str:
    """第二轮改写查询：确定性拼装，不调用模型。"""
    return f"{query}｜{dimension_code}｜换一种问法（第 {round_index} 轮）"


def merge_candidates(blocks: Iterable[ParentBlock]) -> list[ParentBlock]:
    """按 parent_id 去重；命中同一父块的 chunk_ids 合并保留，顺序取首次出现。"""
    merged: dict[str, ParentBlock] = {}
    for block in blocks:
        existing = merged.get(block.parent_id)
        if existing is None:
            merged[block.parent_id] = block
            continue
        extra = tuple(cid for cid in block.chunk_ids if cid not in existing.chunk_ids)
        if extra:
            merged[block.parent_id] = replace(existing, chunk_ids=(*existing.chunk_ids, *extra))
    return list(merged.values())


def default_search_round(
    *,
    query: str,
    contest_id: str,
    rubric_id: str,
    dimension_code: str,
    section_types: Sequence[str] | str | None = None,
    client: Any = None,
    parent_repo: ParentRepository | None = None,
    query_embedding: Sequence[float] | None = None,
    embedding_function: Any = None,
    per_route_limit: int = PER_ROUTE_LIMIT,
) -> list[ParentBlock]:
    """一轮检索：三路各自过滤召回，然后合并去重（不重排、不截断）。"""
    found: list[ParentBlock] = []
    for route in ROUTES:
        found.extend(
            search_children_then_parents(
                query,
                contest_id=contest_id,
                rubric_id=rubric_id,
                section_types=section_types,
                limit=per_route_limit,
                client=client,
                parent_repo=parent_repo,
                query_embedding=query_embedding,
                embedding_function=embedding_function,
                doc_types=(route,),
            )
        )
    return merge_candidates(found)


def _call_rerank(rerank: Any, query: str, candidates: Sequence[str]) -> list[str]:
    if hasattr(rerank, "rerank"):
        return list(rerank.rerank(query, list(candidates)))
    return list(rerank(query, list(candidates)))


def retrieve_dimension(
    query: str,
    *,
    contest_id: str,
    rubric_id: str,
    dimension_code: str,
    section_types: Sequence[str] | str | None = None,
    client: Any = None,
    parent_repo: ParentRepository | None = None,
    query_embedding: Sequence[float] | None = None,
    embedding_function: Any = None,
    rerank: Any = None,
    limit: int = MAX_PARENTS,
    per_route_limit: int = PER_ROUTE_LIMIT,
    search_round: Callable[..., list[ParentBlock]] | None = None,
    rewrite_query: Callable[[str, int, str], str] | None = None,
) -> DimensionRetrieval:
    """逐维检索。最多两轮；合并后只重排一次，最后截断到 `limit`（缺省 4）段。"""
    if limit < 1:
        raise ValueError("limit 必须是不小于 1 的整数")

    round_fn = search_round if search_round is not None else default_search_round
    rewrite_fn = rewrite_query if rewrite_query is not None else default_rewrite

    rounds = 0
    queries: list[str] = []
    merged: list[ParentBlock] = []
    current = query
    while rounds < MAX_ROUNDS:
        rounds += 1
        queries.append(current)
        merged = merge_candidates(
            round_fn(
                query=current,
                contest_id=contest_id,
                rubric_id=rubric_id,
                dimension_code=dimension_code,
                section_types=section_types,
                client=client,
                parent_repo=parent_repo,
                query_embedding=query_embedding,
                embedding_function=embedding_function,
                per_route_limit=per_route_limit,
            )
        )
        if merged:
            break
        current = rewrite_fn(current, rounds + 1, dimension_code)

    if not merged:
        return DimensionRetrieval(
            dimension_code=dimension_code,
            status=STATUS_INSUFFICIENT,
            rounds=rounds,
            queries=tuple(queries),
        )

    order = [block.parent_id for block in merged]
    if rerank is not None:
        order = validate_rerank_order(order, _call_rerank(rerank, query, order))

    by_id = {block.parent_id: block for block in merged}
    return DimensionRetrieval(
        dimension_code=dimension_code,
        status=STATUS_HIT,
        rounds=rounds,
        queries=tuple(queries),
        parents=tuple(by_id[parent_id] for parent_id in order[:limit]),
    )
