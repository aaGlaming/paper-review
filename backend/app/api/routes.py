"""接入层：赛题目录六条路径 + 样例、评测与评审记录三条只读路径。

导入路径固定为 `POST /api/imports`（任务文档第 4.4 节的裁决），
不实现 `/api/catalog/imports`。不实现上传文件，也不实现 `POST /api/reviews`（属后续版本）。

坏包一律返回 400，响应体带 `filename` 与 `field`，页面据此指出改哪个文件的哪个字段。
响应体里不出现奖项字样。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..importing import catalog, db
from ..report import catalog as report_catalog
from ..report import evaluation as report_evaluation
from ..report import store as report_store

PROJECT_ROOT = Path(__file__).resolve().parents[3]

router = APIRouter(prefix="/api")


class ImportRequest(BaseModel):
    """数据包目录。相对路径按项目根目录解析，本版不实现上传文件。"""

    package_dir: str


def get_session() -> Iterator[Session]:
    """每个请求一个会话：成功提交，出错回滚。"""
    with db.session_scope() as session:
        yield session


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


@router.get("/reviews/{review_id}")
def get_review(review_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """读取一条历史评审记录。存档里的赛题编号、量规版本与当时原句原样返回。"""
    record = report_store.load_review(review_id, session=session)
    if record is None:
        raise HTTPException(status_code=404, detail=f"找不到评审记录 {review_id}")
    return record


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
