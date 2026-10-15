# 父子块检索测试。
# 向量库用临时目录里的真实 chromadb（PersistentClient + 自定义假 EmbeddingFunction，
# add 与 query 都显式传 embeddings，不下载嵌入模型）；父块仓储用真实 MySQL，
# 只读复用 backend.app.importing.db 的引擎与会话工厂。两者都在本机，不起 Docker、不访问网络。
# 本文件不导入 backend.app.llm.client，也不调用 chat() / embed()。

from __future__ import annotations

import sys
from pathlib import Path

import chromadb
import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.importing import db as importing_db  # noqa: E402
from backend.app.retrieve import models as retrieve_models  # noqa: E402
from backend.app.retrieve import parent_child  # noqa: E402
from backend.app.retrieve.parent_child import (  # noqa: E402
    DOC_TYPES,
    ChildChunk,
    ParentBlock,
    build_children,
    index_children,
    search_children_then_parents,
    split_into_chunks,
)

DIMENSIONS = 8
CONTEST_A = "cumcm-2024-A"
CONTEST_C = "cumcm-2024-C"
RUBRIC = "cumcm-2024-A-v1"
RUBRIC_B = "cumcm-2024-A-v2"


class FakeEmbeddingFunction(EmbeddingFunction):
    """固定维度假向量：只为让 chromadb 有 EF 可用，真实向量一律显式传入。"""

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.05 * ((index % 5) + 1)] * self.dimensions for index, _ in enumerate(input)]

    @staticmethod
    def name() -> str:
        return "fake-fixed-vector-8d"

    def get_config(self) -> dict:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict) -> "FakeEmbeddingFunction":
        return FakeEmbeddingFunction(int(config.get("dimensions", DIMENSIONS)))


def _vector(seed: int) -> list[float]:
    return [round(0.1 * ((seed % 7) + 1), 3)] * DIMENSIONS


def _probe_mysql(dsn: str | None) -> bool:
    if not dsn:
        return False
    try:
        engine = create_engine(dsn, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


try:
    _DSN = importing_db.get_dsn()
except Exception:
    _DSN = None

MYSQL_REACHABLE = _probe_mysql(_DSN)


def _resolve_engine():
    if MYSQL_REACHABLE:
        return create_engine(_DSN, pool_pre_ping=True), "mysql"
    return create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}), "sqlite"


ENGINE, BACKEND = _resolve_engine()
retrieve_models.ParentBase.metadata.create_all(ENGINE)


@pytest.fixture()
def ef() -> FakeEmbeddingFunction:
    return FakeEmbeddingFunction()


@pytest.fixture()
def store(tmp_path) -> chromadb.ClientAPI:
    """每个用例一个临时目录里的 Chroma，互不残留。"""
    return chromadb.PersistentClient(path=str(tmp_path / "chroma"))


@pytest.fixture()
def repo():
    """真库里的父块仓储：外层事务 + 保存点，用例结束整体回滚。"""
    connection = ENGINE.connect()
    transaction = connection.begin()

    def factory() -> Session:
        return Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield parent_child.ParentRepository(session_factory=factory)
    finally:
        transaction.rollback()
        connection.close()


def _parent(parent_id: str, content: str, section_type: str = "假设", review_id: str = "rv-1") -> ParentBlock:
    return ParentBlock(
        parent_id=parent_id,
        section_type=section_type,
        content=content,
        review_id=review_id,
        char_span=(0, len(content)),
    )


def _child(
    chunk_id: str,
    parent_id: str,
    text: str,
    *,
    contest_id: str = CONTEST_A,
    rubric_id: str = RUBRIC,
    section_type: str = "假设",
    dimension_code: str = "assumption",
    doc_type: str = "paper_child",
    char_start: int = 0,
) -> ChildChunk:
    return ChildChunk(
        chunk_id=chunk_id,
        parent_id=parent_id,
        contest_id=contest_id,
        rubric_id=rubric_id,
        dimension_code=dimension_code,
        section_type=section_type,
        text=text,
        char_start=char_start,
        char_end=char_start + len(text),
        doc_type=doc_type,
    )


def _index(store, ef, children) -> None:
    index_children(
        children,
        client=store,
        embedding_function=ef,
        embeddings=[_vector(index + 1) for index in range(len(children))],
    )


def _stored(store, ef) -> dict:
    return parent_child.get_collection(store, embedding_function=ef).get(include=["documents", "metadatas"])


class _RecordingCollection:
    """记录传给向量库的 where 与 n_results，用来证明过滤交给了向量库。"""

    def __init__(self, collection, calls: list) -> None:
        self._collection = collection
        self.calls = calls

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self._collection.query(**kwargs)

    def add(self, **kwargs):
        return self._collection.add(**kwargs)

    def count(self):
        return self._collection.count()

    def get(self, **kwargs):
        return self._collection.get(**kwargs)


class _RecordingClient:
    """客户端代理：只记录查询参数，其余行为透传真实 Chroma。"""

    def __init__(self, client) -> None:
        self._client = client
        self.calls: list[dict] = []

    def get_or_create_collection(self, **kwargs):
        return _RecordingCollection(self._client.get_or_create_collection(**kwargs), self.calls)


def _long_paragraph(marker: str) -> str:
    return f"{marker}：" + "该假设只在连接处生效，不改变碰撞判定。" * 8


# --- 用例 1 -------------------------------------------------------------------


def test_children_of_another_contest_are_not_returned(store, ef, repo):
    repo.save_parents([_parent("p-a", "A 题假设全文"), _parent("p-c", "C 题假设全文")])
    _index(
        store,
        ef,
        [
            _child("c-a", "p-a", "A 题假设片段"),
            _child("c-c", "p-c", "C 题假设片段", contest_id=CONTEST_C),
        ],
    )

    found = search_children_then_parents(
        "假设怎么写",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(1),
    )

    assert len(found) == 1
    assert {block.parent_id for block in found} == {"p-a"}
    assert [block.content for block in found] == ["A 题假设全文"]


# --- 用例 2 -------------------------------------------------------------------


def test_parent_text_never_lands_in_chroma(store, ef, repo):
    parent_content = "\n\n".join(
        [_long_paragraph("假设一"), _long_paragraph("假设二")]
    )
    parent = _parent("p-a", parent_content)
    repo.save_parents([parent])
    children = build_children(
        parent,
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        dimension_code="assumption",
    )
    assert len(children) > 1, "父块应当被切成多个子块"
    _index(store, ef, children)

    stored = _stored(store, ef)
    documents = stored["documents"] or []
    assert documents, "子块应当写进了向量库"
    assert all(document != parent_content for document in documents)
    assert all(document in parent_content for document in documents)
    assert all(len(document) < len(parent_content) for document in documents)
    assert {metadata["doc_type"] for metadata in stored["metadatas"]} == {"paper_child"}


# --- 用例 3 -------------------------------------------------------------------


def test_returned_text_equals_mysql_parent_not_child_fragment(store, ef, repo):
    parent = _parent("p-a", "完整假设段：忽略板凳宽度只在碰撞判定之外成立，其余推导保留板凳宽度。")
    repo.save_parents([parent])
    child = _child("c-a", "p-a", "忽略板凳宽度")
    _index(store, ef, [child])

    found = search_children_then_parents(
        "板凳宽度",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(2),
    )

    assert len(found) == 1
    assert found[0].content == parent.content
    assert found[0].content != child.text
    assert found[0].chunk_ids == ("c-a",)
    assert found[0].section_type == "假设"


# --- 用例 4 -------------------------------------------------------------------


def test_table_is_its_own_chunk(store, ef):
    text = "\n".join(
        [
            "第一段说明假设。",
            "",
            "| 时刻 | 速度 |",
            "| --- | --- |",
            "| 1 s | 1 m/s |",
            "",
            "第二段说明检验。",
        ]
    )

    chunks = split_into_chunks(text)

    assert len(chunks) == 3
    table = chunks[1]
    assert "|" in table.text
    assert "时刻" in table.text and "1 s" in table.text
    assert "第一段" not in table.text and "第二段" not in table.text
    assert "|" not in chunks[0].text and "|" not in chunks[2].text
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text


# --- 用例 5 -------------------------------------------------------------------


def test_doc_type_outside_whitelist_is_rejected(store, ef):
    assert len(DOC_TYPES) == 5
    assert "paper_parent" not in DOC_TYPES

    with pytest.raises(ValueError):
        _index(store, ef, [_child("c-bad", "p-a", "不许写进来的父块", doc_type="paper_parent")])

    assert _stored(store, ef)["ids"] == []


# --- 用例 6 -------------------------------------------------------------------


def test_section_type_filter_applies(store, ef, repo):
    repo.save_parents(
        [
            _parent("p-assume", "假设原文", section_type="假设"),
            _parent("p-model", "模型原文", section_type="模型"),
        ]
    )
    _index(
        store,
        ef,
        [
            _child("c-assume", "p-assume", "假设片段", section_type="假设"),
            _child("c-model", "p-model", "模型片段", section_type="模型", dimension_code="modeling"),
        ],
    )

    found = search_children_then_parents(
        "模型",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        section_types=["假设"],
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(3),
    )

    assert {block.parent_id for block in found} == {"p-assume"}


# --- 用例 7 -------------------------------------------------------------------


def test_rubric_id_filter_applies(store, ef, repo):
    repo.save_parents([_parent("p-v1", "第一版量规下的父块"), _parent("p-v2", "第二版量规下的父块")])
    _index(
        store,
        ef,
        [
            _child("c-v1", "p-v1", "第一版片段", rubric_id=RUBRIC),
            _child("c-v2", "p-v2", "第二版片段", rubric_id=RUBRIC_B),
        ],
    )

    found = search_children_then_parents(
        "量规",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC_B,
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(4),
    )

    assert {block.parent_id for block in found} == {"p-v2"}


# --- 用例 8 -------------------------------------------------------------------


def test_filter_runs_before_truncation(store, ef, repo):
    parents = [_parent(f"p-{index}", f"父块 {index} 全文") for index in range(6)]
    repo.save_parents(parents)
    children = [
        _child(f"c-{index}", f"p-{index}", f"子块 {index}", char_start=index) for index in range(6)
    ]
    children.append(_child("c-other", "p-other", "别的赛题", contest_id=CONTEST_C))
    repo.save_parents([_parent("p-other", "别的赛题父块")])
    _index(store, ef, children)

    recorder = _RecordingClient(store)
    found = search_children_then_parents(
        "父块",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        limit=4,
        client=recorder,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(5),
    )

    assert len(found) == 4
    assert all(block.parent_id.startswith("p-") and block.parent_id != "p-other" for block in found)
    assert recorder.calls, "应当向向量库发过一次查询"
    sent_where = recorder.calls[0]["where"]
    assert {"contest_id": CONTEST_A} in sent_where["$and"]
    assert {"rubric_id": RUBRIC} in sent_where["$and"]
    assert recorder.calls[0]["n_results"] >= 4


# --- 用例 9 -------------------------------------------------------------------


def test_rerank_hook_only_reorders(store, ef, repo):
    repo.save_parents([_parent(f"p-{index}", f"父块 {index}") for index in range(3)])
    _index(store, ef, [_child(f"c-{index}", f"p-{index}", f"片段 {index}") for index in range(3)])

    plain = search_children_then_parents(
        "片段",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        limit=3,
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(6),
    )
    reversed_ids = [block.parent_id for block in reversed(plain)]

    reordered = search_children_then_parents(
        "片段",
        contest_id=CONTEST_A,
        rubric_id=RUBRIC,
        limit=3,
        client=store,
        parent_repo=repo,
        embedding_function=ef,
        query_embedding=_vector(6),
        rerank=lambda _query, chunk_ids: list(reversed(chunk_ids)),
    )

    assert [block.parent_id for block in reordered] == reversed_ids
    assert {block.parent_id for block in reordered} == {block.parent_id for block in plain}


def test_rerank_hook_cannot_add_filtered_chunks(store, ef, repo):
    repo.save_parents([_parent(f"p-{index}", f"父块 {index}") for index in range(2)])
    _index(store, ef, [_child(f"c-{index}", f"p-{index}", f"片段 {index}") for index in range(2)])

    with pytest.raises(ValueError):
        search_children_then_parents(
            "片段",
            contest_id=CONTEST_A,
            rubric_id=RUBRIC,
            client=store,
            parent_repo=repo,
            embedding_function=ef,
            query_embedding=_vector(7),
            rerank=lambda _query, chunk_ids: [*chunk_ids, "c-不在候选里"],
        )


# --- 加固断言 -----------------------------------------------------------------


def test_metadata_section_type_is_a_single_value(store, ef, repo):
    repo.save_parents([_parent("p-a", "假设全文")])
    _index(store, ef, [_child("c-a", "p-a", "假设片段", section_type="假设")])

    metadatas = _stored(store, ef)["metadatas"]
    assert metadatas
    for metadata in metadatas:
        assert isinstance(metadata["section_type"], str)
        assert not isinstance(metadata["section_type"], list)
        for key in (
            "contest_id",
            "rubric_id",
            "parent_id",
            "doc_type",
            "dimension_code",
            "section_type",
            "char_start",
            "char_end",
        ):
            assert key in metadata, key


def test_query_without_embedding_is_refused(store, ef, repo):
    with pytest.raises(ValueError):
        search_children_then_parents(
            "片段",
            contest_id=CONTEST_A,
            rubric_id=RUBRIC,
            client=store,
            parent_repo=repo,
            embedding_function=ef,
        )


def test_module_has_no_http_and_no_llm_client():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "retrieve").glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in ("httpx", "requests", "urllib", "aiohttp", "openai", "backend.app.llm"):
            assert token not in source, f"{path}: {token}"
    from types import ModuleType

    imported = {
        value.__name__
        for value in vars(parent_child).values()
        if isinstance(value, ModuleType)
    }
    assert not any(name.startswith("backend.app.llm") for name in imported)


def test_backend_selection_follows_availability():
    assert BACKEND in {"mysql", "sqlite"}
    if MYSQL_REACHABLE:
        assert BACKEND == "mysql", "MYSQL_DSN 可连时必须连真实 MySQL"
