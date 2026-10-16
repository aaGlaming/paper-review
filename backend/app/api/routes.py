"""接入层：赛题目录六条路径 + 样例、评测两条只读路径 + 评审创建、继续与读取三条路径。

导入路径固定为 `POST /api/imports`（任务文档第 4.4 节的裁决），不实现 `/api/catalog/imports`。
评审：`POST /api/reviews` 解析章节树后停在确认节点，`POST /api/reviews/{review_id}/resume`
带上确认后的章节树继续到终态，`GET /api/reviews/{review_id}` 先读存档、未落档时落到会话快照。
不实现上传文件与 PDF/docx 解析，也不实现取消、删除等冻结清单之外的路径。

坏包一律返回 400，响应体带 `filename` 与 `field`，页面据此指出改哪个文件的哪个字段。
响应体里不出现奖项字样。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
def eval_summary() -> dict[str, Any]:
    """三项评测指标。未注入模型，走确定性结构回退，返回体里带 source 标明来源。"""
    return report_evaluation.run_eval()


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
    final = resume_review(review_id, sections, graph=graph)

    contest_id = str(record.get("contest_id") or "")
    inputs = report_rubric.load_review_inputs(contest_id, session=session)
    dimensions = inputs["dimensions"]
    paper_text = record.get("paper_text", "")
    results = report_evaluation.deterministic_results(paper_text, dimensions)
    if inputs["rubric_id"] is None:
        # 没绑定赛题就没有量规可依据：各维为空，修改清单也为空，不兜底到别的赛题。
        change_list: list[dict[str, Any]] = []
        note = NOTE_NO_CONTEST
    else:
        findings = check_numbers_citations_ranges(paper_text, inputs["constraints"])
        change_list = build_change_list(results, findings, dimensions)
        note = NOTE_DETERMINISTIC

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
        model_name=DETERMINISTIC_MODEL_NAME,
        dimensions=results,
        session=session,
    )
    return {
        "review_id": review_id,
        "status": str(final.get("status") or STATUS_DONE),
        "contest_id": contest_id,
        "rubric_id": inputs["rubric_id"],
        "rubric_version": inputs["rubric_version"],
        "model_name": saved["model_name"],
        "source": report_evaluation.SOURCE_DETERMINISTIC,
        "dimensions": saved["dimensions"],
        "score": _empty_score(),
        "change_list": change_list,
        "note": note,
    }


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
