"""重排接口、结果校验与假客户端。

签名固定：输入是**查询**与**已经过滤后的候选**，输出是这些候选的新顺序。
硬约束：输出集合必须与输入集合完全相同——**不得加入任何新文档，也不得把被过滤掉的段加回来**。

本版**不发任何 HTTP**：项目硬约束是「全项目只有 `backend/app/llm/client.py` 可以发 HTTP」，
而本版允许修改范围不含该文件，所以真实重排留到允许修改它的版本（见 `docs/plan/findings.md` 的 Ruling）。
这里只从环境变量读 `RERANK_BASE_URL` 与 `RERANK_MODEL` 作为**配置项**，并把「未配置」如实报出来。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

RERANK_BASE_URL_ENV = "RERANK_BASE_URL"
RERANK_MODEL_ENV = "RERANK_MODEL"
FAKE_CLIENT_NAME = "fake"


@dataclass(frozen=True)
class RerankConfig:
    """重排配置项。只读环境变量；本版不用它发请求，空值按未配置处理。"""

    base_url: str = ""
    model: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


def read_rerank_config() -> RerankConfig:
    """读 RERANK_BASE_URL 与 RERANK_MODEL。不打印、不回显，也不发请求。"""
    return RerankConfig(
        base_url=os.environ.get(RERANK_BASE_URL_ENV, "").strip(),
        model=os.environ.get(RERANK_MODEL_ENV, "").strip(),
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


def build_rerank_client(name: str = FAKE_CLIENT_NAME) -> RerankClient:
    """取重排客户端。本版只提供假客户端；真实 HTTP 实现留到后续版本。"""
    if name == FAKE_CLIENT_NAME:
        return FakeRerankClient()
    if name in {"http", "real"}:
        config = read_rerank_config()
        raise NotImplementedError(
            "真实重排要发 HTTP，而本版不允许在 llm/client.py 之外发请求，"
            "所以留到允许修改该文件的版本；"
            f"RERANK_BASE_URL 与 RERANK_MODEL：{'已配置' if config.configured else '未配置'}"
        )
    raise ValueError(f"未知的重排客户端：{name}")
