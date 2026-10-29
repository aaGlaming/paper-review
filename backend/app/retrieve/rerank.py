"""重排接口、结果校验与假客户端。

签名固定：输入是**查询**与**已经过滤后的候选**，输出是这些候选的新顺序。
硬约束：输出集合必须与输入集合完全相同——**不得加入任何新文档，也不得把被过滤掉的段加回来**。

真实请求只通过 `backend/app/llm/client.py` 发送；本模块只把候选 ID 映射为父块全文，
并将返回的排序下标映射回原候选 ID。假客户端仍用于离线测试。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Protocol, Sequence

RERANK_BASE_URL_ENV = "RERANK_BASE_URL"
RERANK_MODEL_ENV = "RERANK_MODEL"
RERANK_API_KEY_ENV = "RERANK_API_KEY"
FAKE_CLIENT_NAME = "fake"


@dataclass(frozen=True)
class RerankConfig:
    """重排配置项。只读环境变量；本版不用它发请求，空值按未配置处理。"""

    base_url: str = ""
    model: str = ""
    api_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def available(self) -> bool:
        return bool(self.configured and self.api_key)


def read_rerank_config() -> RerankConfig:
    """读 RERANK_BASE_URL 与 RERANK_MODEL。不打印、不回显，也不发请求。"""
    return RerankConfig(
        base_url=os.environ.get(RERANK_BASE_URL_ENV, "").strip(),
        model=os.environ.get(RERANK_MODEL_ENV, "").strip(),
        api_key=os.environ.get(RERANK_API_KEY_ENV, "").strip(),
    )


def validate_rerank_order(candidates: Sequence[str], reordered: Iterable[str]) -> list[str]:
    """输出集合必须与输入集合完全相同：加入新文档或漏掉候选都抛错。"""
    expected = [str(candidate) for candidate in candidates]
    got = [str(chunk_id) for chunk_id in reordered]
    if sorted(got) != sorted(expected):
        raise ValueError("重排只能改变顺序：输出集合必须与已过滤的候选集合完全相同")
    return got


class RerankClient(Protocol):
    """重排客户端协议：输入查询与已过滤候选，输出这些候选的新顺序。"""

    def rerank(self, query: str, candidates: Sequence[str]) -> list[str]: ...


class FakeRerankClient:
    """假重排客户端：把原顺序倒过来，用来证明它不能加入新文档。"""

    def __init__(self, *, reverse: bool = True) -> None:
        self.reverse = reverse
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def rerank(self, query: str, candidates: Sequence[str]) -> list[str]:
        ids = [str(candidate) for candidate in candidates]
        self.calls.append((query, tuple(ids)))
        return list(reversed(ids)) if self.reverse else list(ids)

    def __call__(self, query: str, candidates: Sequence[str]) -> list[str]:
        return self.rerank(query, candidates)


class SiliconFlowRerankClient:
    """硅基流动 Cohere 风格重排适配器，只把文档下标映射回父块 ID。"""

    def __init__(
        self,
        parent_contents: Mapping[str, str],
        rank: Callable[[str, Sequence[str]], Sequence[int]],
    ) -> None:
        self.parent_contents = dict(parent_contents)
        self.rank = rank

    def rerank(self, query: str, candidates: Sequence[str]) -> list[str]:
        ids = [str(candidate) for candidate in candidates]
        try:
            documents = [self.parent_contents[parent_id] for parent_id in ids]
        except KeyError as exc:
            raise ValueError(f"缺少父块全文：{exc.args[0]}") from exc
        indices = list(self.rank(query, documents))
        if any(isinstance(index, bool) or not isinstance(index, int) for index in indices):
            raise ValueError("重排返回的 index 必须是整数")
        if sorted(indices) != list(range(len(ids))):
            raise ValueError("重排必须完整覆盖候选，且 index 不得越界或重复")
        return [ids[index] for index in indices]


def build_rerank_client(
    name: str = FAKE_CLIENT_NAME,
    *,
    parent_contents: Mapping[str, str] | None = None,
    rank: Callable[[str, Sequence[str]], Sequence[int]] | None = None,
) -> RerankClient:
    """取重排客户端；真实请求函数由装配层注入，HTTP 仅由模型客户端发出。"""
    if name == FAKE_CLIENT_NAME:
        return FakeRerankClient()
    if name in {"http", "real"}:
        config = read_rerank_config()
        if not config.available:
            raise NotImplementedError("RERANK_BASE_URL、RERANK_API_KEY 与 RERANK_MODEL 未配置")
        if parent_contents is None or rank is None:
            raise ValueError("真实重排需要 parent_contents 与 rank 调用函数")
        return SiliconFlowRerankClient(parent_contents, rank)
    raise ValueError(f"未知的重排客户端：{name}")
