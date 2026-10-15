# 重排与再检索测试。
# 全部用内存假件：假向量存储（记录每路的过滤条件）、内存父块仓储、假重排客户端；
# 不起 Docker、不访问网络、不下载嵌入模型，也不导入 backend.app.llm.client。
# 图侧的行为断言也写在本文件里（未确认时不进 retrieve、每维各检索一次）。

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.graph import review_graph  # noqa: E402
from backend.app.graph.review_graph import build_review_graph, create_review, resume_review  # noqa: E402
from backend.app.importing.catalog import DIMENSION_CODES  # noqa: E402
from backend.app.retrieve import parent_child, three_route  # noqa: E402
from backend.app.retrieve.parent_child import ChildChunk, ParentBlock, index_children  # noqa: E402
from backend.app.retrieve.rerank import (  # noqa: E402
    FakeRerankClient,
    build_rerank_client,
    read_rerank_config,
    validate_rerank_order,
)
from backend.app.retrieve.three_route import (  # noqa: E402
    MAX_PARENTS,
    PER_ROUTE_LIMIT,
    STATUS_HIT,
    STATUS_INSUFFICIENT,
    retrieve_dimension,
)

CONTEST = "cumcm-2024-A"
RUBRIC = "cumcm-2024-A-v1"
VECTOR = [0.1, 0.2, 0.3, 0.4]

PAPER_TEXT = "\n".join(
    [
        "# 板凳龙运动分析",
        "",
        "## 一、模型假设",
        "忽略板凳宽度，把手视为质点。",
        "",
        "## 二、模型的建立",
        "给出螺距与龙头速度的关系。",
        "",
        "## 三、模型求解",
        "用迭代法逐段求解。",
        "",
        "## 四、结果分析",
        "总时间为 412 s。",
        "",
        "## 五、模型检验",
        "把手速度不超过 2 m/s。",
        "",
        "## 参考文献",
        "[1] 自建样例。",
    ]
)


# --- 假件 ----------------------------------------------------------------------


class FakeCollection:
    """最小可用的假向量集合：支持 $and / $in 过滤，并记录每次查询。"""

    def __init__(self, calls: list) -> None:
        self._rows: list[dict] = []
        self.calls = calls

    def add(self, ids, documents, metadatas, embeddings) -> None:
        for index, chunk_id in enumerate(ids):
            self._rows.append(
                {
                    "id": chunk_id,
                    "document": documents[index],
                    "metadata": metadatas[index],
                }
            )

    def count(self) -> int:
        return len(self._rows)

    def get(self, include=None) -> dict:
        return {
            "ids": [row["id"] for row in self._rows],
            "documents": [row["document"] for row in self._rows],
            "metadatas": [row["metadata"] for row in self._rows],
        }

    @staticmethod
    def _matches(metadata: dict, where: dict) -> bool:
        for clause in where["$and"]:
            for key, expected in clause.items():
                if isinstance(expected, dict) and "$in" in expected:
                    if metadata.get(key) not in expected["$in"]:
                        return False
                elif metadata.get(key) != expected:
                    return False
        return True

    def query(self, query_embeddings, n_results, where, include) -> dict:
        self.calls.append({"where": where, "n_results": n_results})
        hits = [row for row in self._rows if self._matches(row["metadata"], where)]
        hits = hits[:n_results]
        return {
            "ids": [[row["id"] for row in hits]],
            "metadatas": [[row["metadata"] for row in hits]],
            "documents": [[row["document"] for row in hits]],
        }


class FakeVectorClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._collections: dict[str, FakeCollection] = {}

    def get_or_create_collection(self, name, embedding_function=None, metadata=None):
        return self._collections.setdefault(name, FakeCollection(self.calls))


class FakeParentRepo:
    """内存父块仓储：接口与 MySQL 仓储一致。"""

    def __init__(self) -> None:
        self.rows: dict[str, ParentBlock] = {}

    def save_parents(self, parents) -> int:
        items = list(parents)
        for parent in items:
            self.rows[parent.parent_id] = parent
        return len(items)

    def get_parents(self, parent_ids) -> list[ParentBlock]:
        return [self.rows[pid] for pid in parent_ids if pid in self.rows]


@pytest.fixture()
def client() -> FakeVectorClient:
    return FakeVectorClient()


@pytest.fixture()
def repo() -> FakeParentRepo:
    return FakeParentRepo()


def _seed(client, repo, *, route: str, parent_id: str, section_type: str = "假设", text: str | None = None) -> None:
    body = text or f"{route} 路线下的父块全文 {parent_id}"
    repo.save_parents(
        [
            ParentBlock(
                parent_id=parent_id,
                section_type=section_type,
                content=body,
                review_id="rv-1",
                char_span=(0, len(body)),
            )
        ]
    )
    child = ChildChunk(
        chunk_id=f"{parent_id}-00",
        parent_id=parent_id,
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        section_type=section_type,
        text=body[:20],
        char_start=0,
        char_end=20,
        doc_type=route,
    )
    index_children([child], client=client, embeddings=[VECTOR])


def _search(route: str, count: int) -> list[ParentBlock]:
    return [
        ParentBlock(
            parent_id=f"{route}-p{index}",
            section_type="假设",
            content=f"{route} 父块 {index}",
            review_id="rv-1",
        )
        for index in range(count)
    ]


def _counting_round(rounds_results: list[list[ParentBlock]]):
    calls: list[dict] = []

    def search_round(**kwargs) -> list[ParentBlock]:
        calls.append(kwargs)
        index = len(calls) - 1
        return rounds_results[index] if index < len(rounds_results) else []

    return search_round, calls


class RecordingRetriever:
    """图用的假检索器：记录每个维度被请求了几次。"""

    def __init__(self) -> None:
        self.requests: list = []

    def __call__(self, request):
        self.requests.append(request)
        return {
            "status": STATUS_HIT,
            "rounds": 1,
            "parents": [
                {
                    "parent_id": f"{request.dimension_code}-p1",
                    "section_type": "假设",
                    "content": "父块全文",
                    "chunk_ids": ["c1"],
                }
            ],
        }


# --- 用例 1-4：重排与合并截断 --------------------------------------------------


def test_rerank_keeps_the_same_id_set(client, repo):
    _seed(client, repo, route="paper_child", parent_id="p-1")
    _seed(client, repo, route="paper_child", parent_id="p-2")

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        client=client,
        parent_repo=repo,
        query_embedding=VECTOR,
        rerank=FakeRerankClient(),
    )

    ids = [block.parent_id for block in result.parents]
    assert set(ids) == {"p-1", "p-2"}
    assert ids == ["p-2", "p-1"], "假重排客户端把顺序倒过来"


def test_rerank_cannot_add_ids_outside_the_candidates(client, repo):
    _seed(client, repo, route="paper_child", parent_id="p-1")
    _seed(client, repo, route="paper_child", parent_id="p-2")

    def evil(_query: str, _ids: list[str]) -> list[str]:
        return ["p-不在候选里"]

    with pytest.raises(ValueError):
        retrieve_dimension(
            "假设怎么写",
            contest_id=CONTEST,
            rubric_id=RUBRIC,
            dimension_code="assumption",
            client=client,
            parent_repo=repo,
            query_embedding=VECTOR,
            rerank=evil,
        )

    with pytest.raises(ValueError):
        validate_rerank_order(["a", "b"], ["a", "b", "c"])
    with pytest.raises(ValueError):
        validate_rerank_order(["a", "b"], ["a"])


def test_more_than_four_candidates_are_truncated_to_four(client, repo):
    for index in range(6):
        _seed(client, repo, route="paper_child", parent_id=f"p-{index}")

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        client=client,
        parent_repo=repo,
        query_embedding=VECTOR,
        rerank=FakeRerankClient(),
    )

    assert MAX_PARENTS == 4
    assert len(result.parents) == MAX_PARENTS
    assert result.status == STATUS_HIT


def test_three_routes_merge_then_cap_at_four_total(client, repo):
    for route in ("band_text", "paper_child", "pitfall"):
        for index in range(3):
            _seed(client, repo, route=route, parent_id=f"{route}-{index}")

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        client=client,
        parent_repo=repo,
        query_embedding=VECTOR,
        rerank=FakeRerankClient(),
    )

    assert len(result.parents) == MAX_PARENTS, "三路合并后总共 4 段，不是每路各 4 段"
    assert len(client.calls) == 3, "三路各查一次"
    route_filters = []
    for call in client.calls:
        doc_type_clause = [
            clause
            for clause in call["where"]["$and"]
            if "doc_type" in clause
        ]
        assert doc_type_clause, "每一路都要按 doc_type 过滤"
        route_filters.append(doc_type_clause[0]["doc_type"]["$in"][0])
    assert sorted(route_filters) == ["band_text", "paper_child", "pitfall"]
    assert all(call["n_results"] >= PER_ROUTE_LIMIT for call in client.calls)


# --- 用例 5-8：两轮检索的次数与状态 -------------------------------------------


def test_first_round_hit_does_not_search_again():
    search_round, calls = _counting_round([_search("paper_child", 3)])

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        search_round=search_round,
    )

    assert result.rounds == 1
    assert len(calls) == 1, "第一轮有结果就不许再查"
    assert result.status == STATUS_HIT


def test_second_round_runs_after_empty_first_round():
    search_round, calls = _counting_round([[], _search("band_text", 2)])

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        search_round=search_round,
    )

    assert len(calls) == 2
    assert result.rounds == 2
    assert result.status == STATUS_HIT
    assert calls[1]["query"] != calls[0]["query"], "第二轮要改写查询"
    assert result.queries[0] != result.queries[1]


def test_two_empty_rounds_are_insufficient_evidence_with_exactly_two_rounds():
    search_round, calls = _counting_round([[], []])

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        search_round=search_round,
    )

    assert result.status == STATUS_INSUFFICIENT
    assert result.rounds == 2
    assert len(calls) == 2, "不得出现第三次检索"
    assert result.parents == ()


def test_empty_retrieval_uses_no_model_client():
    search_round, _calls = _counting_round([[], []])

    result = retrieve_dimension(
        "假设怎么写",
        contest_id=CONTEST,
        rubric_id=RUBRIC,
        dimension_code="assumption",
        search_round=search_round,
    )

    assert result.status == STATUS_INSUFFICIENT
    for module in (three_route, parent_child, review_graph):
        imported = {
            value.__name__
            for value in vars(module).values()
            if isinstance(value, ModuleType)
        }
        assert not any(name.startswith("backend.app.llm") for name in imported)


# --- 用例 9-10：图侧的确认闸门与逐维检索 --------------------------------------


def test_unconfirmed_sections_never_reach_retrieve_node():
    retriever = RecordingRetriever()
    graph = build_review_graph(retriever=retriever)
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}

    snapshot = graph.get_state(config)
    assert snapshot.next == ("confirm",)
    assert retriever.requests == [], "未确认时不进 retrieve"
    assert snapshot.values["retrieve_node_calls"] == 0
    assert snapshot.values["score_node_calls"] == 0


def test_confirmed_review_retrieves_every_dimension_once():
    retriever = RecordingRetriever()
    graph = build_review_graph(retriever=retriever)
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = graph.get_state(config).values["sections"]

    final = resume_review(review_id, sections, graph=graph)

    assert final["retrieve_node_calls"] == 1
    assert len(retriever.requests) == len(DIMENSION_CODES)
    assert {request.dimension_code for request in retriever.requests} == set(DIMENSION_CODES)
    assert set(final["retrievals"]) == set(DIMENSION_CODES)
    for dimension_code, outcome in final["retrievals"].items():
        assert outcome["status"] in {STATUS_HIT, STATUS_INSUFFICIENT}
        assert outcome["parents"], dimension_code
        assert outcome["parents"][0]["content"] == "父块全文"
    assert final["status"] == "完成"
    assert final["score_node_calls"] == 1


def test_graph_without_retriever_marks_every_dimension_insufficient():
    graph = build_review_graph()
    review_id = create_review(PAPER_TEXT, graph=graph)
    config = {"configurable": {"thread_id": review_id}}
    sections = graph.get_state(config).values["sections"]

    final = resume_review(review_id, sections, graph=graph)

    assert set(final["retrievals"]) == set(DIMENSION_CODES)
    assert all(
        outcome["status"] == STATUS_INSUFFICIENT for outcome in final["retrievals"].values()
    )


# --- 用例 11-12：配置与源码约束 ------------------------------------------------


def test_rerank_config_reads_env_without_sending_http(monkeypatch):
    monkeypatch.setenv("RERANK_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("RERANK_MODEL", "unit-rerank-model")

    config = read_rerank_config()

    assert config.base_url == "https://example.invalid/v1"
    assert config.model == "unit-rerank-model"
    assert config.configured is True

    monkeypatch.delenv("RERANK_BASE_URL")
    monkeypatch.delenv("RERANK_MODEL")
    empty = read_rerank_config()
    assert empty.configured is False

    assert isinstance(build_rerank_client(), FakeRerankClient)
    with pytest.raises(NotImplementedError):
        build_rerank_client("http")


def test_sources_have_no_http_and_no_llm_client():
    paths = sorted((PROJECT_ROOT / "backend" / "app" / "retrieve").glob("*.py"))
    paths += sorted((PROJECT_ROOT / "backend" / "app" / "graph").glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in ("httpx", "requests", "urllib", "aiohttp", "openai", "backend.app.llm"):
            assert token not in source, f"{path}: {token}"
