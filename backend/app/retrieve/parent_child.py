"""父子块检索：先过滤子块，再按 parent_id 取回父块全文。

顺序固定，不得调换：**过滤 → 召回 → 取父块**，重排只改顺序、不改变过滤条件。
本版不实现重排（属 P4），但函数签名里留了 `rerank` 位置，并且会拒绝把候选之外的东西加回来。

分工：
- 子块（文本 + 元数据 + 向量）进 Chroma，`doc_type` 由白名单约束；
- 父块全文只留在 MySQL（`paper_parent`，见 models.py）；
- 送入后续步骤的是父块全文，不是子块碎片。

本版不调用 `chat()` / `embed()`，不导入模型客户端，不访问网络：向量一律由调用方显式传入
（`index_children` 的 `embeddings`、`search_children_then_parents` 的 `query_embedding`），
模块内的占位 EmbeddingFunction 一旦被调用就直接报错，避免 Chroma 去下载默认嵌入模型。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PaperParent

# Chroma 的 doc_type 白名单。实测写成 paper_parent 也能写进去，所以白名单必须自己拦。
DOC_TYPES = ("paper_child", "band_text", "pitfall", "exemplar", "contest_statement", "review_record")
CHILD_DOC_TYPE = "paper_child"

COLLECTION_NAME = "paper_review"
CHROMA_DIR = Path(__file__).resolve().parents[3] / "chroma_data"

METADATA_KEYS = (
    "contest_id",
    "rubric_id",
    "parent_id",
    "doc_type",
    "dimension_code",
    "section_type",
    "char_start",
    "char_end",
)

DEFAULT_LIMIT = 4
DEFAULT_MAX_CHARS = 200
DEFAULT_CANDIDATE_FACTOR = 3

_TABLE_PIPE = "|"
_TABLE_RULE = re.compile(r"^[\s|:-]+$")


class DocTypeError(ValueError):
    """doc_type 超出白名单。让 Chroma 自己拦是不可靠的，实测非白名单也能写进去。"""


class ExplicitEmbeddingsOnly(EmbeddingFunction):
    """占位 EF：本模块一律显式传向量，绝不让 Chroma 触发默认嵌入模型。"""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        raise RuntimeError("本版不调用嵌入模型：请在写入与查询时显式传 embeddings")

    @staticmethod
    def name() -> str:
        return "explicit-embeddings-only"


@dataclass(frozen=True)
class TextChunk:
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ChildChunk:
    chunk_id: str
    parent_id: str
    contest_id: str
    rubric_id: str
    dimension_code: str
    section_type: str
    text: str
    char_start: int
    char_end: int
    doc_type: str = CHILD_DOC_TYPE
    embedding: tuple[float, ...] | None = None
    # 检索必须能按本次论文隔离：同一赛题下多篇论文共用一个 collection，
    # 少了这个键就会召回别的论文的父块，引用因此指向别人的论文。
    review_id: str = ""


@dataclass(frozen=True)
class ParentBlock:
    parent_id: str
    section_type: str
    content: str
    review_id: str | None = None
    char_span: tuple[int, int] | None = None
    chunk_ids: tuple[str, ...] = ()


# --- 切块 ----------------------------------------------------------------------


def _blocks_with_offsets(text: str) -> list[tuple[str, int, int]]:
    """按空行切出块，并带上在原文本里的偏移（end 不含结尾空行）。"""
    blocks: list[tuple[str, int, int]] = []
    start: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = offset
        elif start is not None:
            raw = text[start:offset]
            body = raw.rstrip("\n")
            blocks.append((body, start, start + len(body)))
            start = None
        offset += len(line)
    if start is not None:
        raw = text[start:]
        body = raw.rstrip("\n")
        blocks.append((body, start, start + len(body)))
    return blocks


def _is_table_block(block: str) -> bool:
    """两行以上带竖线，或出现 Markdown 表格分隔行，算表格块。"""
    lines = [line for line in block.splitlines() if line.strip()]
    piped = [line for line in lines if _TABLE_PIPE in line]
    if len(piped) < 2:
        return False
    return any(_TABLE_RULE.match(line.strip()) and "-" in line for line in piped) or len(piped) >= 2


def split_into_chunks(text: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[TextChunk]:
    """切块：表格单独成块，不与前后段落合并；相邻段落可并到一块，超过 max_chars 就断开。

    每个块都带 char_start / char_end，且 `text[char_start:char_end] == chunk.text`。
    """
    if not text:
        return []
    chunks: list[TextChunk] = []
    group_start: int | None = None
    group_end: int | None = None

    def flush() -> None:
        nonlocal group_start, group_end
        if group_start is None or group_end is None:
            return
        chunks.append(TextChunk(text[group_start:group_end], group_start, group_end))
        group_start = None
        group_end = None

    for body, start, end in _blocks_with_offsets(text):
        if _is_table_block(body):
            flush()
            chunks.append(TextChunk(text[start:end], start, end))
            continue
        if group_start is None:
            group_start, group_end = start, end
        elif end - group_start > max_chars:
            flush()
            group_start, group_end = start, end
        else:
            group_end = end
    flush()
    return chunks


def build_children(
    parent: ParentBlock,
    *,
    contest_id: str,
    rubric_id: str,
    dimension_code: str,
    section_type: str | None = None,
    doc_type: str = CHILD_DOC_TYPE,
    max_chars: int = DEFAULT_MAX_CHARS,
    embeddings: Sequence[Sequence[float]] | None = None,
    review_id: str = "",
) -> list[ChildChunk]:
    """把父块全文切成子块并附上元数据。子块只带片段文本，父块全文不进 Chroma。

    `review_id` 缺省取父块自身的 review_id，保证检索能按本次论文隔离。
    """
    _require_doc_type(doc_type)
    resolved_section = section_type or parent.section_type
    _require_single_value(resolved_section, parent.parent_id)
    resolved_review = review_id or parent.review_id or ""

    children: list[ChildChunk] = []
    for index, chunk in enumerate(split_into_chunks(parent.content, max_chars=max_chars)):
        vector = tuple(float(value) for value in embeddings[index]) if embeddings is not None else None
        children.append(
            ChildChunk(
                chunk_id=f"{parent.parent_id}-{index:02d}",
                parent_id=parent.parent_id,
                contest_id=str(contest_id),
                rubric_id=str(rubric_id),
                dimension_code=str(dimension_code),
                section_type=str(resolved_section),
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                doc_type=doc_type,
                embedding=vector,
                review_id=str(resolved_review),
            )
        )
    return children


# --- 校验 ----------------------------------------------------------------------


def _require_doc_type(doc_type: str) -> None:
    if doc_type not in DOC_TYPES:
        raise DocTypeError(f"doc_type 只能是 {'、'.join(DOC_TYPES)}，收到 {doc_type!r}")


def _require_single_value(section_type: Any, where: str) -> None:
    if isinstance(section_type, (list, tuple, set, frozenset)):
        raise ValueError(f"section_type 必须是单值字符串，{where} 收到数组；数组元数据用 $in 过滤会静默返回空")


def child_metadata(child: ChildChunk) -> dict[str, Any]:
    """子块元数据：至少这九个键，全部是单值。"""
    _require_doc_type(child.doc_type)
    _require_single_value(child.section_type, child.chunk_id)
    return {
        "contest_id": str(child.contest_id),
        "rubric_id": str(child.rubric_id),
        "parent_id": str(child.parent_id),
        "doc_type": child.doc_type,
        "dimension_code": str(child.dimension_code),
        "section_type": str(child.section_type),
        "char_start": int(child.char_start),
        "char_end": int(child.char_end),
        "review_id": str(child.review_id),
    }


def _resolve_embeddings(
    items: Sequence[ChildChunk], embeddings: Sequence[Sequence[float]] | None
) -> list[list[float]]:
    if embeddings is not None:
        vectors = [[float(value) for value in vector] for vector in embeddings]
        if len(vectors) != len(items):
            raise ValueError("embeddings 的条数必须与子块条数一致")
        return vectors
    vectors = []
    for child in items:
        if child.embedding is None:
            raise ValueError("本版不调用嵌入模型：请显式传 embeddings，或在子块上带向量")
        vectors.append([float(value) for value in child.embedding])
    return vectors


# --- 子块写入 ------------------------------------------------------------------


_CLIENT: Any = None


def set_client_for_tests(client: Any) -> None:
    """Replace the persistent client for isolated tests."""
    global _CLIENT
    _CLIENT = client


def reset_client_for_tests() -> None:
    """Drop the cached client so the next lookup uses the configured default."""
    global _CLIENT
    _CLIENT = None


def default_client() -> Any:
    """默认向量库：本地持久化目录，按需创建，导入本模块时不建连接。"""
    global _CLIENT
    if _CLIENT is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _CLIENT


def get_collection(client: Any = None, *, embedding_function: Any = None) -> Any:
    resolved = client if client is not None else default_client()
    function = embedding_function if embedding_function is not None else ExplicitEmbeddingsOnly()
    return resolved.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=function,
        metadata={"hnsw:space": "cosine"},
    )


def index_children(
    children: Iterable[ChildChunk],
    *,
    client: Any = None,
    embedding_function: Any = None,
    embeddings: Sequence[Sequence[float]] | None = None,
) -> int:
    """把子块写进 Chroma。doc_type 超出白名单直接抛错；父块全文不在这里出现。"""
    items = list(children)
    if not items:
        return 0
    for child in items:
        _require_doc_type(child.doc_type)
        _require_single_value(child.section_type, child.chunk_id)
    vectors = _resolve_embeddings(items, embeddings)
    collection = get_collection(client, embedding_function=embedding_function)
    collection.add(
        ids=[child.chunk_id for child in items],
        documents=[child.text for child in items],
        metadatas=[child_metadata(child) for child in items],
        embeddings=vectors,
    )
    return len(items)


# --- 父块仓储（MySQL） ---------------------------------------------------------


def _to_block(row: PaperParent) -> ParentBlock:
    span = tuple(row.char_span) if row.char_span else None
    return ParentBlock(
        parent_id=row.parent_id,
        section_type=row.section_type,
        content=row.content,
        review_id=row.review_id,
        char_span=span,  # type: ignore[arg-type]
    )


class ParentRepository:
    """父块全文仓储。session_factory 可注入；默认只读复用 importing.db 的会话工厂。"""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory

    def _factory(self) -> Callable[[], Session]:
        if self._session_factory is not None:
            return self._session_factory
        from ..importing import db

        return db.get_session_factory()

    def save_parents(self, parents: Iterable[ParentBlock]) -> int:
        items = list(parents)
        if not items:
            return 0
        session = self._factory()()
        try:
            for parent in items:
                if not parent.review_id:
                    raise ValueError(f"父块 {parent.parent_id} 缺少 review_id")
                row = session.get(PaperParent, parent.parent_id)
                if row is None:
                    row = PaperParent(parent_id=parent.parent_id)
                    session.add(row)
                row.review_id = str(parent.review_id)
                row.section_type = str(parent.section_type)
                row.content = parent.content
                row.char_span = list(parent.char_span) if parent.char_span else None
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return len(items)

    def get_parents(self, parent_ids: Iterable[str]) -> list[ParentBlock]:
        ids = [str(parent_id) for parent_id in parent_ids]
        if not ids:
            return []
        session = self._factory()()
        try:
            rows = list(session.scalars(select(PaperParent).where(PaperParent.parent_id.in_(ids))))
        finally:
            session.close()
        by_id = {row.parent_id: _to_block(row) for row in rows}
        return [by_id[parent_id] for parent_id in ids if parent_id in by_id]


_DEFAULT_REPO: ParentRepository | None = None


def default_parent_repo() -> ParentRepository:
    global _DEFAULT_REPO
    if _DEFAULT_REPO is None:
        _DEFAULT_REPO = ParentRepository()
    return _DEFAULT_REPO


def save_parents(
    parents: Iterable[ParentBlock], *, repo: ParentRepository | None = None
) -> int:
    """把父块全文写进 MySQL。"""
    return (repo if repo is not None else default_parent_repo()).save_parents(parents)


def get_parents(
    parent_ids: Iterable[str], *, repo: ParentRepository | None = None
) -> list[ParentBlock]:
    """按 parent_id 取回父块全文，返回顺序与传入的 id 顺序一致。"""
    return (repo if repo is not None else default_parent_repo()).get_parents(parent_ids)


# --- 检索 ----------------------------------------------------------------------


def _where(
    contest_id: str,
    rubric_id: str,
    section_types: Any = None,
    doc_types: Any = None,
    review_id: str | None = None,
) -> dict[str, Any]:
    """过滤条件全部交给向量库：先过滤，再谈排序与截断。section_type 走单值 $in。

    论文检索必须传 review_id，避免同赛题的其他论文进入候选；评审记录检索按 contest_id
    隔离，不传 review_id，这是唯一合法例外。rubric_id 为空时不加过滤，以允许跨量规版本检索。
    """
    clauses: list[dict[str, Any]] = []
    if str(contest_id).strip():
        clauses.append({"contest_id": str(contest_id)})
    if str(rubric_id).strip():
        clauses.append({"rubric_id": str(rubric_id)})
    if review_id:
        clauses.append({"review_id": str(review_id)})
    if section_types:
        values = [section_types] if isinstance(section_types, str) else list(section_types)
        values = [str(value) for value in values if str(value).strip()]
        if values:
            clauses.append({"section_type": {"$in": values}})
    if doc_types:
        routes = [doc_types] if isinstance(doc_types, str) else list(doc_types)
        routes = [str(route) for route in routes if str(route).strip()]
        if routes:
            clauses.append({"doc_type": {"$in": routes}})
    return {"$and": clauses}


def search_children_then_parents(
    query: str,
    *,
    contest_id: str,
    rubric_id: str,
    review_id: str | None = None,
    section_types: Sequence[str] | str | None = None,
    limit: int = DEFAULT_LIMIT,
    client: Any = None,
    parent_repo: ParentRepository | None = None,
    query_embedding: Sequence[float] | None = None,
    embedding_function: Any = None,
    rerank: Callable[[str, list[str]], Iterable[str]] | None = None,
    candidate_factor: int = DEFAULT_CANDIDATE_FACTOR,
    doc_types: Sequence[str] | str | None = None,
) -> list[ParentBlock]:
    """先按 contest_id、rubric_id、review_id、section_types 过滤子块，再按 parent_id 取回父块全文。

    `rerank` 只能改变候选顺序，不能把被过滤掉的片段加回来；`doc_types` 用来分路
    （档位说明 / 论文子块 / 扣分点）。返回项含 parent_id、section_type、content（来自 MySQL）
    与 chunk_ids（命中的子块 id）。
    """
    if limit < 1:
        raise ValueError("limit 必须是不小于 1 的整数")
    if query_embedding is None:
        raise ValueError("本版不调用嵌入模型：请显式传 query_embedding")

    collection = get_collection(client, embedding_function=embedding_function)
    where = _where(contest_id, rubric_id, section_types, doc_types, review_id)

    available = collection.count()
    wanted = max(limit * max(int(candidate_factor), 1), limit)
    n_results = max(1, min(wanted, int(available))) if available else 1
    result = collection.query(
        query_embeddings=[[float(value) for value in query_embedding]],
        n_results=n_results,
        where=where,
        include=["metadatas"],
    )

    ids = list(result["ids"][0]) if result.get("ids") else []
    metadatas = list(result["metadatas"][0]) if result.get("metadatas") else []
    if not ids:
        return []
    meta_by_id = dict(zip(ids, metadatas))

    order = list(ids)
    if rerank is not None:
        reordered = [str(chunk_id) for chunk_id in rerank(query, list(ids))]
        if sorted(reordered) != sorted(ids):
            raise ValueError("重排只能改变顺序，不能加入被过滤掉的片段")
        order = reordered

    chunks_by_parent: dict[str, list[str]] = {}
    parent_order: list[str] = []
    for chunk_id in order:
        parent_id = str(meta_by_id[chunk_id]["parent_id"])
        chunks_by_parent.setdefault(parent_id, []).append(chunk_id)
        if parent_id not in parent_order:
            parent_order.append(parent_id)

    selected = parent_order[:limit]
    repo = parent_repo if parent_repo is not None else default_parent_repo()
    blocks = {block.parent_id: block for block in repo.get_parents(selected)}
    return [
        replace(blocks[parent_id], chunk_ids=tuple(chunks_by_parent.get(parent_id, ())))
        for parent_id in selected
        if parent_id in blocks
    ]
