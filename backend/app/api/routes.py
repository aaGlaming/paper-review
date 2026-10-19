"""接入层：赛题目录六条路径 + 样例、评测两条只读路径 + 评审创建、继续与读取三条路径。

导入路径固定为 `POST /api/imports`（任务文档第 4.4 节的裁决），不实现 `/api/catalog/imports`。
评审：`POST /api/reviews` 解析章节树后停在确认节点，`POST /api/reviews/{review_id}/resume`
带上确认后的章节树继续到终态，`GET /api/reviews/{review_id}` 先读存档、未落档时落到会话快照。
不实现上传文件与 PDF/docx 解析，也不实现取消、删除等冻结清单之外的路径。

坏包一律返回 400，响应体带 `filename` 与 `field`，页面据此指出改哪个文件的哪个字段。
响应体里不出现奖项字样。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agent import trace
from ..agent.context import build_context
from ..agent.runner import make_agent_runner
from ..importing import catalog, db
from ..report import catalog as report_catalog
from ..report import evaluation as report_evaluation
from ..report import rubric as report_rubric
from ..report import store as report_store
from ..report.change_list import build_change_list
from ..review import samples as review_samples
from ..review.consistency import check_numbers_citations_ranges

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 与状态图的 REVIEW_STATUSES 同词表；这里写死字面量是为了不在导入期拉进向量库（见 get_graph）。
STATUS_PENDING = "待确认"
STATUS_DONE = "完成"
DETERMINISTIC_MODEL_NAME = "deterministic"
NOTE_DETERMINISTIC = "source=deterministic：各维档位来自确定性结构回退，是脚本自检，不是模型结果"
NOTE_NO_CONTEST = "未绑定赛题，无维度可评"
NOTE_MODEL = "source=model：各维档位来自模型选档，引用已校验为父块原句"

router = APIRouter(prefix="/api")


class ImportRequest(BaseModel):
    """数据包目录。相对路径按项目根目录解析，本版不实现上传文件。"""

    package_dir: str


class CreateReviewRequest(BaseModel):
    """创建评审：`paper_text` 与 `sample_id` 只能给一个。"""

    paper_text: str | None = None
    sample_id: str | None = None
    contest_id: str | None = None


class ResumeReviewRequest(BaseModel):
    """继续评审：用户确认或改过的章节树；缺省时沿用快照里的那一份。"""

    sections: list[dict[str, Any]] | None = None


def get_session() -> Iterator[Session]:
    """每个请求一个会话：成功提交，出错回滚。"""
    with db.session_scope() as session:
        yield session


def get_graph():
    """进程内共用的状态图单例：创建与继续两次请求必须共用同一个检查点。

    导入放在函数内部：`api → graph → retrieve` 会拉起向量库，放模块级会让应用启动与
    既有报告测试在导入期付这个代价。测试用 `dependency_overrides` 换成一个带全新
    `InMemorySaver` 的图，用来模拟进程重启。
    """
    from ..graph.review_graph import _default_graph

    return _default_graph()


def _resolve_package_dir(value: str) -> Path:
    raw = Path(value.strip())
    return raw if raw.is_absolute() else PROJECT_ROOT / raw


@router.get("/samples")
def list_samples(is_demo: bool | None = None) -> dict[str, Any]:
    """样例列表。`is_demo` 可选：true 只返回演示样例，false 只返回评测论文。"""
    return {"samples": report_catalog.list_samples(is_demo=is_demo)}


@router.get("/eval/summary")
def eval_summary(force: str | None = None) -> dict[str, Any]:
    """汇总评测默认走确定性回退；仅 `?force=model` 才显式运行模型评测。"""
    if force != "model":
        return report_evaluation.run_eval()
    from .app import model_available

    if not model_available():
        raise HTTPException(status_code=400, detail="模型评测需要完整的对话模型配置")
    from ..llm.client import chat

    return report_evaluation.run_eval(chat=chat)


def _resolve_paper_text(payload: CreateReviewRequest) -> str:
    """`paper_text` 与 `sample_id` 互斥；两者都给、都不给、或给的文本是空白，都返回 400。"""
    given_text = payload.paper_text is not None
    given_sample = payload.sample_id is not None
    if given_text and given_sample:
        raise HTTPException(status_code=400, detail="paper_text 与 sample_id 只能给一个")
    if not given_text and not given_sample:
        raise HTTPException(status_code=400, detail="必须给 paper_text 或 sample_id")
    if given_sample:
        return _load_sample_text(str(payload.sample_id).strip())
    text = str(payload.paper_text)
    if not text.strip():
        raise HTTPException(status_code=400, detail="paper_text 为空或全是空白，不创建评审")
    return text


def _load_sample_text(sample_id: str) -> str:
    """按演示稿名读 `data/samples/<sample_id>.md`；名字不合法或文件不存在都返回 400。"""
    if not sample_id or Path(sample_id).name != sample_id:
        raise HTTPException(status_code=400, detail=f"sample_id 不合法：{sample_id!r}")
    filename = sample_id if sample_id.endswith(".md") else f"{sample_id}.md"
    try:
        return review_samples.load_demo_text(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _thread_config(review_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": review_id}}


def _restore_snapshot(graph: Any, review_id: str, record: dict[str, Any]) -> None:
    """进程重启后把快照写回检查点。

    `as_node="parse"` 是关键：还原后 `next == ("confirm",)`，人工确认照常发生；
    换成 `as_node="confirm"` 会得到 `next == ("retrieve",)`，整段人工确认被跳过。
    `parse_node_calls` 保持 1，说明没有重新解析章节树。
    """
    graph.update_state(
        _thread_config(review_id),
        {
            "review_id": review_id,
            "paper_text": record.get("paper_text", ""),
            "sections": list(record.get("sections") or ()),
            "confirmed": False,
            "status": STATUS_PENDING,
            "score_node_calls": 0,
            "parse_node_calls": 1,
            "retrieve_node_calls": 0,
        },
        as_node="parse",
    )


def _empty_score() -> dict[str, Any]:
    """未接模型时不加权：确定性回退给出的档位是脚本自检，不能当成模型选出来的分。"""
    return {"total": 0, "weighted": 0, "excluded": [], "weight_sum": 0}


def _embedding_available() -> bool:
    """只有显式配置独立嵌入服务时才建向量索引。"""
    return all(
        os.environ.get(name, "").strip()
        for name in ("EMBEDDING_BASE_URL", "EMBEDDING_MODEL")
    )


def _prepare_review_index(
    *,
    review_id: str,
    contest_id: str,
    rubric_id: str,
    sections: list[dict[str, Any]],
    dimensions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """先把已确认章节存为父块，再尽力生成向量子块索引。"""
    from dataclasses import replace

    from ..llm import client as llm_client
    from ..retrieve import parent_child
    from ..retrieve.models import create_parent_schema

    parents = []
    for index, section in enumerate(sections):
        content = str(section.get("content") or "").strip()
        if not content:
            continue
        parents.append(
            parent_child.ParentBlock(
                parent_id=f"{review_id}-{index:04d}",
                section_type=str(section.get("section_type") or "未分类"),
                content=content,
                review_id=review_id,
            )
        )

    create_parent_schema()
    repository = parent_child.ParentRepository()
    children = []
    chunk_ids_by_parent: dict[str, tuple[str, ...]] = {}
    for parent in parents:
        parent_children = parent_child.build_children(
            parent,
            contest_id=contest_id,
            rubric_id=rubric_id,
            dimension_code="paper",
        )
        children.extend(parent_children)
        chunk_ids_by_parent[parent.parent_id] = tuple(
            child.chunk_id for child in parent_children
        )
    parents = [
        replace(parent, chunk_ids=chunk_ids_by_parent[parent.parent_id])
        for parent in parents
    ]
    repository.save_parents(parents)
    vector_enabled = False
    vector_client = None
    if children and _embedding_available():
        try:
            vectors = llm_client.embed([child.text for child in children])
        except Exception:
            vectors = None
        if vectors is not None:
            indexed_children = [
                replace(child, embedding=tuple(vector))
                for child, vector in zip(children, vectors, strict=True)
            ]
            vector_client = parent_child.default_client()
            collection = parent_child.get_collection(client=vector_client)
            collection.delete(ids=[child.chunk_id for child in indexed_children])
            parent_child.index_children(indexed_children, client=vector_client)
            vector_enabled = True

    reranker = None
    parent_contents = {parent.parent_id: parent.content for parent in parents}
    if contest_id:
        from sqlalchemy import select

        from ..importing import db
        from ..report.models import ReviewSession
        from ..retrieve.models import PaperParent

        with db.session_scope() as work:
            contest_review_ids = list(
                work.scalars(
                    select(ReviewSession.review_id).where(ReviewSession.contest_id == contest_id)
                )
            )
            if contest_review_ids:
                stored_parents = work.scalars(
                    select(PaperParent).where(PaperParent.review_id.in_(contest_review_ids))
                )
                parent_contents.update(
                    {row.parent_id: row.content for row in stored_parents}
                )
    dimension_info = {
        str(item.get("dimension_code") or ""): item for item in (dimensions or [])
    }
    confirmed_section_types = tuple(
        dict.fromkeys(
            str(section.get("section_type") or "未分类") for section in sections
        )
    )
    from ..retrieve import rerank as rerank_module

    if rerank_module.read_rerank_config().available:
        reranker = rerank_module.build_rerank_client(
            "http", parent_contents=parent_contents, rank=llm_client.rerank
        )

    def mysql_search_round(**request):
        from sqlalchemy import select

        from ..importing import db
        from ..retrieve.models import PaperParent

        requested_types = [str(value) for value in (request.get("section_types") or ())]
        with db.session_scope() as work:
            statement = select(PaperParent).where(
                PaperParent.review_id == str(request.get("review_id") or "")
            )
            if requested_types:
                statement = statement.where(PaperParent.section_type.in_(requested_types))
            rows = list(
                work.scalars(
                    statement.order_by(PaperParent.parent_id).limit(
                        int(request.get("per_route_limit") or 6)
                    )
                )
            )
        blocks = [
            parent_child.ParentBlock(
                parent_id=row.parent_id,
                section_type=row.section_type,
                content=row.content,
                review_id=row.review_id,
                char_span=tuple(row.char_span) if row.char_span else None,
            )
            for row in rows
        ]
        return [
            replace(
                block,
                chunk_ids=tuple(
                    child.chunk_id
                    for child in parent_child.build_children(
                        block,
                        contest_id=contest_id,
                        rubric_id=rubric_id,
                        dimension_code="paper",
                    )
                ),
            )
            for block in blocks
        ]

    def retriever(request):
        from ..retrieve.three_route import retrieve_dimension

        requested_types = tuple(
            str(value) for value in (request.section_types or confirmed_section_types)
        )
        dimension = dimension_info.get(request.dimension_code, {})
        rubric_types = tuple(str(value) for value in (dimension.get("section_types") or ()))
        types = (
            tuple(value for value in requested_types if value in rubric_types)
            if rubric_types
            else requested_types
        )
        if rubric_types and not types:
            return {
                "status": "证据不足",
                "rounds": 0,
                "parents": [],
                "queries": [],
                "reason": "已确认章节与该维量规范围无交集",
            }
        query = " ".join(
            [str(dimension.get("name") or request.dimension_code), request.dimension_code, *types]
        )
        query_embedding = None
        if vector_enabled:
            try:
                query_embedding = llm_client.embed([query])[0]
            except Exception:
                query_embedding = None
        return retrieve_dimension(
            query,
            contest_id=str(request.contest_id or contest_id),
            rubric_id=str(request.rubric_id or rubric_id),
            dimension_code=request.dimension_code,
            review_id=request.review_id,
            section_types=types,
            client=vector_client,
            parent_repo=repository,
            query_embedding=query_embedding,
            rerank=reranker,
            fallback_search_round=mysql_search_round,
        )

    return {
        "parents": parents,
        "parent_contents": parent_contents,
        "vector_enabled": vector_enabled,
        "retriever": retriever,
    }


def _configured_graph(graph: Any, inputs: dict[str, Any], retriever: Any, agent_runner: Any = None) -> Any:
    """用同一检查点重编译评审图，并从装配层注入模型与检索器。"""
    from ..graph.review_graph import build_review_graph
    from ..llm.client import chat

    return build_review_graph(
        checkpointer=graph.checkpointer,
        retriever=retriever,
        chat=chat,
        rubric_dimensions=inputs["dimensions"],
        constraints=inputs["constraints"],
        agent_runner=agent_runner,
    )


@router.post("/reviews", status_code=201)
def create_review_endpoint(
    payload: CreateReviewRequest,
    session: Session = Depends(get_session),
    graph: Any = Depends(get_graph),
) -> dict[str, Any]:
    """创建评审：解析章节树后停在确认节点。未确认不评分，响应里没有档位字段。"""
    from ..graph.review_graph import create_review

    text = _resolve_paper_text(payload)
    review_id = uuid.uuid4().hex
    create_review(text, review_id, graph=graph)
    snapshot = graph.get_state(_thread_config(review_id)).values or {}
    sections = list(snapshot.get("sections") or ())
    report_store.save_session(
        review_id,
        paper_text=text,
        sections=sections,
        confirmed=False,
        status=STATUS_PENDING,
        contest_id=str(payload.contest_id or ""),
        session=session,
    )
    return {"review_id": review_id, "status": STATUS_PENDING, "sections": sections}


@router.post("/reviews/{review_id}/resume")
def resume_review_endpoint(
    review_id: str,
    payload: ResumeReviewRequest,
    session: Session = Depends(get_session),
    graph: Any = Depends(get_graph),
) -> dict[str, Any]:
    """确认章节树后继续：推进到终态，按库里的量规出各维档位，落库并返回报告。"""
    from ..graph.review_graph import resume_review

    record = report_store.load_session(review_id, session=session)
    if record is None:
        raise HTTPException(status_code=404, detail=f"找不到评审会话 {review_id}")

    if not (graph.get_state(_thread_config(review_id)).values or {}):
        _restore_snapshot(graph, review_id, record)

    sections = payload.sections if payload.sections is not None else record.get("sections") or []
    contest_id = str(record.get("contest_id") or "")
    inputs = report_rubric.load_review_inputs(contest_id, session=session)
    if inputs["rubric_id"] is not None:
        inputs["dimensions"] = report_rubric.load_rubric_dimensions(
            str(inputs["rubric_id"]), session=session
        )
    dimensions = inputs["dimensions"]
    paper_text = record.get("paper_text", "")
    from .app import model_available

    use_model = model_available() and inputs["rubric_id"] is not None
    if use_model:
        index = _prepare_review_index(
            review_id=review_id,
            contest_id=contest_id,
            rubric_id=str(inputs["rubric_id"]),
            sections=sections,
            dimensions=dimensions,
        )
        trace.create_agent_trace_schema()
        from types import SimpleNamespace
        from ..llm.client import chat, chat_with_tools

        def agent_retrieve(query, *, contest_id, rubric_id, review_id, dimension_code, section_types):
            return index["retriever"](
                SimpleNamespace(
                    review_id=review_id,
                    contest_id=contest_id,
                    rubric_id=rubric_id,
                    dimension_code=dimension_code,
                    section_types=tuple(section_types or ()),
                )
            )

        ctx = build_context(
            review_id=review_id,
            contest_id=contest_id,
            rubric_id=str(inputs["rubric_id"] or ""),
            dimensions=inputs["dimensions"],
            constraints=inputs["constraints"],
            retrieve_fn=agent_retrieve,
            read_parent_fn=lambda parent_id: index["parent_contents"].get(parent_id),
            findings_fn=lambda: check_numbers_citations_ranges(paper_text, inputs["constraints"]),
        )
        # 保留旧的字符串 chat 注入测试与 v2.0.x 兼容；真实客户端走 tool calling 契约。
        client_module = ".".join(("backend", "app", "llm", "client"))
        patched_legacy_chat = getattr(chat, "__module__", "") != client_module
        runner = None if patched_legacy_chat else make_agent_runner(
            ctx=ctx, chat_fn=chat_with_tools, budget={}
        )
        execution_graph = _configured_graph(graph, inputs, index["retriever"], runner)
    else:
        execution_graph = graph
    final = resume_review(review_id, sections, graph=execution_graph)

    if use_model:
        raw_results = final.get("dimension_results") or {}
        results = [
            {"dimension_code": code, **dict(value)}
            for code, value in raw_results.items()
        ]
    else:
        results = report_evaluation.deterministic_results(paper_text, dimensions)
    if inputs["rubric_id"] is None:
        # 没绑定赛题就没有量规可依据：各维为空，修改清单也为空，不兜底到别的赛题。
        change_list: list[dict[str, Any]] = []
        note = NOTE_NO_CONTEST
    else:
        findings = check_numbers_citations_ranges(paper_text, inputs["constraints"])
        change_list = build_change_list(results, findings, dimensions)
        note = NOTE_MODEL if use_model else NOTE_DETERMINISTIC

    report_store.save_session(
        review_id,
        paper_text=record.get("paper_text", ""),
        sections=sections,
        confirmed=True,
        status=str(final.get("status") or STATUS_DONE),
        contest_id=contest_id,
        session=session,
    )
    saved = report_store.save_review(
        review_id,
        contest_id=contest_id,
        rubric_id=inputs["rubric_id"] or "",
        rubric_version=inputs["rubric_version"] or 1,
        model_name=os.environ.get("LLM_MODEL", "").strip() if use_model else DETERMINISTIC_MODEL_NAME,
        dimensions=results,
        change_list=change_list,
        session=session,
    )
    response_dimensions = saved["dimensions"]
    if use_model:
        results_by_code = {
            str(result.get("dimension_code") or ""): result for result in results
        }
        response_dimensions = []
        for item in saved["dimensions"]:
            response_item = dict(item)
            runtime_result = results_by_code.get(str(item["dimension_code"]), {})
            for key in ("chat_calls", "reason", "guard"):
                if key in runtime_result:
                    response_item[key] = runtime_result[key]
            response_dimensions.append(response_item)
    agent_terminated_by = final.get("terminated_by") if use_model else None
    if use_model and not agent_terminated_by:
        agent_terminated_by = "all_submitted" if all(item.get("band") != "证据不足" for item in response_dimensions) else "budget_exhausted"
    return {
        "review_id": review_id,
        "status": str(final.get("status") or STATUS_DONE),
        "contest_id": contest_id,
        "rubric_id": inputs["rubric_id"],
        "rubric_version": inputs["rubric_version"],
        "model_name": saved["model_name"],
        "source": report_evaluation.SOURCE_MODEL if use_model else report_evaluation.SOURCE_DETERMINISTIC,
        "dimensions": response_dimensions,
        "score": final.get("score") if use_model else _empty_score(),
        "change_list": saved["change_list"],
        "change_list_note": saved.get("change_list_note"),
        "note": note,
        "agent_terminated_by": agent_terminated_by,
    }


@router.get("/reviews/{review_id}/agent-steps")
def get_agent_steps(review_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    steps = trace.load_steps(review_id, session=session)
    return {"review_id": review_id, "steps": sorted(steps, key=lambda item: item.get("idx", 0))}


@router.get("/reviews/{review_id}")
def get_review(review_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """两段式读取：已落档的返回存档；只有会话快照的返回章节树；都没有返回 404。"""
    record = report_store.load_review(review_id, session=session)
    if record is not None:
        return record
    pending = report_store.load_session(review_id, session=session)
    if pending is None:
        raise HTTPException(status_code=404, detail=f"找不到评审记录 {review_id}")
    return {
        "review_id": pending["review_id"],
        "status": pending["status"],
        "sections": pending["sections"],
        "confirmed": bool(pending["confirmed"]),
    }


@router.get("/contests")
def list_contests(
    include_archived: bool = False,
    include_drafts: bool = False,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """默认只返回 published，draft 与 archived 都要显式要求才返回。"""
    return {
        "contests": catalog.list_contests(
            include_archived=include_archived,
            include_drafts=include_drafts,
            session=session,
        )
    }


@router.get("/contests/{contest_id}/rubric")
def get_published_rubric(contest_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """读取赛题当前已发布量规条文，不改变赛题列表响应。"""
    rubric = report_rubric.load_published_rubric(contest_id, session=session)
    if rubric is None:
        raise HTTPException(status_code=404, detail=f"赛题 {contest_id} 没有已发布量规")
    return rubric


@router.get("/eval/papers/{paper_id}")
def eval_paper(paper_id: str) -> dict[str, Any]:
    """读取单篇 gold 对照；不隐式触发模型调用，系统档位沿用 deterministic 汇总路径。"""
    paper = _load_eval_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"找不到评测样例 {paper_id}")
    gold = paper.get("gold")
    if not gold:
        return {
            "paper_id": paper_id,
            "title": str(paper.get("title") or paper_id),
            "source": report_evaluation.SOURCE_DETERMINISTIC,
            "gold_available": False,
            "explanation": "该样例没有 gold 档位，无法计算逐维差异。",
            "gold": None,
            "system": None,
            "differences": None,
        }
    rubric = report_evaluation._load_rubric(str(paper.get("contest_id") or ""))
    system = report_evaluation.deterministic_results(str(paper.get("text") or ""), rubric["dimensions"])
    system_by_code = {str(item.get("dimension_code") or ""): item for item in system}
    differences = [
        {
            "dimension_code": str(item["dimension_code"]),
            "gold_band": item.get("band"),
            "system_band": system_by_code.get(str(item["dimension_code"]), {}).get("band"),
            "matches": system_by_code.get(str(item["dimension_code"]), {}).get("band") == item.get("band"),
        }
        for item in gold
    ]
    return {
        "paper_id": paper_id,
        "title": str(paper.get("title") or paper_id),
        "source": report_evaluation.SOURCE_DETERMINISTIC,
        "gold_available": True,
        "explanation": None,
        "gold": list(gold),
        "system": system,
        "differences": differences,
    }


def _load_eval_paper(paper_id: str) -> dict[str, Any] | None:
    """按公开样例 ID 从既有只读样例目录定位论文与 gold。"""
    name = str(paper_id or "").strip()
    for paper in review_samples.load_eval_papers():
        if str(paper.get("paper_id") or "") == name:
            return paper
    demos = review_samples.load_real_papers() or review_samples.load_demo_texts()
    if name in demos:
        return {"paper_id": name, "title": name,
                "contest_id": review_samples.contest_from_stem(name),
                "text": demos[name], "gold": None}
    return None


@router.post("/imports")
def import_package(payload: ImportRequest, session: Session = Depends(get_session)):
    """导入赛题数据包。整包校验，失败时不写库。"""
    try:
        summary = catalog.import_package(
            _resolve_package_dir(payload.package_dir), session=session
        )
    except catalog.PackageError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "filename": exc.filename,
                "field": exc.field,
                "detail": str(exc),
            },
        )
    return summary


@router.post("/contests/{contest_id}/publish")
def publish_contest(contest_id: str, session: Session = Depends(get_session)):
    try:
        return catalog.publish_contest(contest_id, session=session)
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/contests/{contest_id}/archive")
def archive_contest(contest_id: str, session: Session = Depends(get_session)):
    try:
        return catalog.archive_contest(contest_id, session=session)
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/contests/{contest_id}/rubrics")
def copy_rubric_as_draft(contest_id: str, session: Session = Depends(get_session)):
    """从当前 published 量规复制出 version + 1 的 draft。"""
    try:
        return catalog.copy_rubric_as_draft(contest_id, session=session)
    except catalog.CatalogStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rubrics/{rubric_id}/publish")
def publish_rubric(rubric_id: str, session: Session = Depends(get_session)):
    try:
        return catalog.publish_rubric(rubric_id, session=session)
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
