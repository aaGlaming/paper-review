"""赛题目录：数据包校验、导入、发布、归档、复制下一版量规。

校验先于写库：任何一个坏包都在写库之前抛 PackageError，携带出错的文件名与字段名，
库里已发布的数据保持不变（导入不会部分写入）。

导入代码里不出现任何题号字面量，三道赛题与自建夹具的差异全部来自 JSON 数据；
量规的差异放在 rubric 的 evidence_prompts 与 section_types 里，硬性条件的差异放在 constraints 里。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from ..observability.logging import log_event

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import db
from .models import Constraint, Contest, Dimension, Exemplar, Pitfall, Rubric

PACKAGE_FILES = (
    "contest.json",
    "constraints.json",
    "rubric.json",
    "pitfalls.json",
    "exemplars.json",
)
REQUIRED_CONTEST_FIELDS = ("contest_id", "year", "problem_code", "title", "statement", "status")
CONTEST_STATUSES = ("draft", "published", "archived")
RUBRIC_STATUSES = ("draft", "published", "archived")
DIMENSION_CODES = ("assumption", "modeling", "solution", "constraint_check", "presentation")
DIMENSION_NAMES = {
    "assumption": "假设的合理性",
    "modeling": "建模是否针对本题",
    "solution": "求解与结果",
    "constraint_check": "检验与题目约束",
    "presentation": "表述与结构",
}
CHECK_TYPES = ("mention", "numeric_range", "required_case")
BAND_NAMES = ("充分", "基本", "不足", "证据不足")
SCORED_BANDS = ("充分", "基本", "不足")
INSUFFICIENT_BAND = "证据不足"
WEIGHT_TOTAL = 100


class PackageError(ValueError):
    """数据包校验失败。携带出错的文件名与字段名，便于页面指出改哪里。"""

    def __init__(self, filename: str, field: str, message: str) -> None:
        self.filename = filename
        self.field = field
        super().__init__(f"{filename} 的 {field}：{message}")


class CatalogError(Exception):
    """目录操作失败：找不到赛题或量规。"""


class CatalogStateError(CatalogError):
    """当前状态不允许该操作，例如赛题还没有已发布量规。"""


@contextmanager
def _session(session: Session | None) -> Iterator[Session]:
    """有外部会话就用外部会话（不提交，由调用方决定），否则自己开一个并提交。"""
    if session is not None:
        yield session
        return
    with db.session_scope() as owned:
        yield owned


# --- 读取与校验 ----------------------------------------------------------------


def _read_json(package_dir: Path, filename: str) -> dict[str, Any]:
    path = package_dir / filename
    if not path.is_file():
        raise PackageError(filename, "-", f"数据包缺少 {filename}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(filename, "<json>", f"不是合法 JSON：{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PackageError(filename, "<root>", "顶层必须是 JSON 对象")
    return payload


def _require_fields(filename: str, payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise PackageError(filename, field, "缺必填字段")


def _require_string_list(filename: str, field: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PackageError(filename, field, "必须是非空字符串数组")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PackageError(filename, field, "必须是非空字符串数组")
    return [item.strip() for item in value]


def _validate_bands(filename: str, prefix: str, bands: Any) -> list[dict[str, Any]]:
    if not isinstance(bands, list) or not bands:
        raise PackageError(filename, f"{prefix}.bands", "四档必须齐全")
    seen: dict[str, dict[str, Any]] = {}
    for band in bands:
        if not isinstance(band, dict):
            raise PackageError(filename, f"{prefix}.bands", "每一档必须是对象")
        name = band.get("band")
        if name not in BAND_NAMES:
            raise PackageError(filename, f"{prefix}.bands", f"档位只能是 {'、'.join(BAND_NAMES)}")
        if name in seen:
            raise PackageError(filename, f"{prefix}.bands", f"档位 {name} 重复")
        score = band.get("score")
        if name == INSUFFICIENT_BAND:
            if score is not None:
                raise PackageError(
                    filename, f"{prefix}.bands[{name}].score", "证据不足的 score 必须为空"
                )
        else:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise PackageError(
                    filename, f"{prefix}.bands[{name}].score", "前三档的 score 必须是数字"
                )
        description = band.get("description")
        if description is not None and not isinstance(description, str):
            raise PackageError(filename, f"{prefix}.bands[{name}].description", "必须是字符串")
        seen[name] = {
            "band": name,
            "score": None if name == INSUFFICIENT_BAND else score,
            "description": description,
        }
    missing = [name for name in BAND_NAMES if name not in seen]
    if missing:
        raise PackageError(filename, f"{prefix}.bands", f"缺少档位 {'、'.join(missing)}")
    return [seen[name] for name in BAND_NAMES]


def _validate_dimensions(filename: str, rubric_payload: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = rubric_payload.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise PackageError(filename, "dimensions", "必须是非空数组")

    normalized: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    total_weight = 0
    for index, dimension in enumerate(dimensions):
        prefix = f"dimensions[{index}]"
        if not isinstance(dimension, dict):
            raise PackageError(filename, prefix, "必须是对象")
        _require_fields(
            filename,
            dimension,
            ("code", "name", "weight", "evidence_prompts", "section_types", "bands"),
        )
        code = dimension["code"]
        if code not in DIMENSION_CODES:
            raise PackageError(
                filename, f"{prefix}.code", f"只能是 {'、'.join(DIMENSION_CODES)}"
            )
        if code in seen_codes:
            raise PackageError(filename, f"{prefix}.code", f"维度 {code} 重复")
        seen_codes.add(code)
        if dimension["name"] != DIMENSION_NAMES[code]:
            raise PackageError(
                filename, f"{prefix}.name", f"维度 {code} 的名称必须是「{DIMENSION_NAMES[code]}」"
            )
        weight = dimension["weight"]
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise PackageError(filename, f"{prefix}.weight", "必须是数字")
        total_weight += weight
        normalized.append(
            {
                "code": code,
                "name": dimension["name"],
                "weight": int(weight),
                "evidence_prompts": _require_string_list(
                    filename, f"{prefix}.evidence_prompts", dimension["evidence_prompts"]
                ),
                "section_types": _require_string_list(
                    filename, f"{prefix}.section_types", dimension["section_types"]
                ),
                "bands": _validate_bands(filename, prefix, dimension["bands"]),
            }
        )

    missing = [code for code in DIMENSION_CODES if code not in seen_codes]
    if missing:
        raise PackageError(filename, "dimensions", f"缺少维度 {'、'.join(missing)}")
    if total_weight != WEIGHT_TOTAL:
        raise PackageError(
            filename,
            "dimensions.weight",
            f"五个维度权重合计为 {total_weight}，必须为 {WEIGHT_TOTAL}",
        )
    return normalized


def validate_package(package_dir: str | Path) -> dict[str, Any]:
    """读五个 JSON 并整包校验。任一不满足即抛 PackageError，不写库。"""
    path = Path(package_dir)
    if not path.is_dir():
        raise PackageError("contest.json", "-", f"数据包目录不存在：{path}")

    contest = _read_json(path, "contest.json")
    constraints_payload = _read_json(path, "constraints.json")
    rubric_payload = _read_json(path, "rubric.json")
    pitfalls_payload = _read_json(path, "pitfalls.json")
    exemplars_payload = _read_json(path, "exemplars.json")

    _require_fields("contest.json", contest, REQUIRED_CONTEST_FIELDS)
    if contest["status"] not in CONTEST_STATUSES:
        raise PackageError(
            "contest.json", "status", f"只能是 {'、'.join(CONTEST_STATUSES)}"
        )
    if isinstance(contest["year"], bool) or not isinstance(contest["year"], int):
        raise PackageError("contest.json", "year", "必须是整数年份")
    contest_id = str(contest["contest_id"]).strip()

    for filename, payload in (
        ("constraints.json", constraints_payload),
        ("rubric.json", rubric_payload),
        ("pitfalls.json", pitfalls_payload),
        ("exemplars.json", exemplars_payload),
    ):
        if str(payload.get("contest_id", "")).strip() != contest_id:
            raise PackageError(filename, "contest_id", f"必须与 contest.json 的 {contest_id} 一致")

    constraints = constraints_payload.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        raise PackageError("constraints.json", "constraints", "必须是非空数组")
    normalized_constraints: list[dict[str, Any]] = []
    for index, one in enumerate(constraints):
        prefix = f"constraints[{index}]"
        if not isinstance(one, dict):
            raise PackageError("constraints.json", prefix, "必须是对象")
        _require_fields(
            "constraints.json",
            one,
            ("constraint_id", "name", "check_type", "params", "section_types"),
        )
        check_type = one["check_type"]
        if check_type not in CHECK_TYPES:
            raise PackageError(
                "constraints.json",
                f"{prefix}.check_type",
                f"只能是 {'、'.join(CHECK_TYPES)}",
            )
        params = one["params"]
        if not isinstance(params, dict):
            raise PackageError("constraints.json", f"{prefix}.params", "必须是对象")
        if check_type == "numeric_range":
            for key in ("min", "max"):
                value = params.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise PackageError(
                        "constraints.json", f"{prefix}.params.{key}", "numeric_range 需要数字 min 与 max"
                    )
        if check_type == "required_case":
            for key in ("label", "artifact"):
                if not str(params.get(key, "")).strip():
                    raise PackageError(
                        "constraints.json",
                        f"{prefix}.params.{key}",
                        "required_case 需要 label 与 artifact",
                    )
        normalized_constraints.append(
            {
                "constraint_id": str(one["constraint_id"]),
                "contest_id": contest_id,
                "name": str(one["name"]),
                "check_type": check_type,
                "params": params,
                "section_types": _require_string_list(
                    "constraints.json", f"{prefix}.section_types", one["section_types"]
                ),
            }
        )

    version = rubric_payload.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PackageError("rubric.json", "version", "必须是不小于 1 的整数")
    rubric_status = rubric_payload.get("status", "draft")
    if rubric_status not in RUBRIC_STATUSES:
        raise PackageError("rubric.json", "status", f"只能是 {'、'.join(RUBRIC_STATUSES)}")
    dimensions = _validate_dimensions("rubric.json", rubric_payload)

    pitfalls = pitfalls_payload.get("pitfalls")
    if not isinstance(pitfalls, list):
        raise PackageError("pitfalls.json", "pitfalls", "必须是数组")
    normalized_pitfalls: list[dict[str, Any]] = []
    for index, one in enumerate(pitfalls):
        prefix = f"pitfalls[{index}]"
        if not isinstance(one, dict):
            raise PackageError("pitfalls.json", prefix, "必须是对象")
        _require_fields(
            "pitfalls.json",
            one,
            ("pitfall_id", "contest_id", "dimension_code", "phenomenon", "action", "section_types"),
        )
        if one["dimension_code"] not in DIMENSION_CODES:
            raise PackageError(
                "pitfalls.json",
                f"{prefix}.dimension_code",
                f"只能是 {'、'.join(DIMENSION_CODES)}",
            )
        normalized_pitfalls.append(
            {
                "pitfall_id": str(one["pitfall_id"]),
                "contest_id": contest_id,
                "dimension_code": one["dimension_code"],
                "phenomenon": str(one["phenomenon"]),
                "action": str(one["action"]),
                "section_types": _require_string_list(
                    "pitfalls.json", f"{prefix}.section_types", one["section_types"]
                ),
            }
        )

    exemplars = exemplars_payload.get("exemplars")
    if not isinstance(exemplars, list):
        raise PackageError("exemplars.json", "exemplars", "必须是数组")
    normalized_exemplars: list[dict[str, Any]] = []
    for index, one in enumerate(exemplars):
        prefix = f"exemplars[{index}]"
        if not isinstance(one, dict):
            raise PackageError("exemplars.json", prefix, "必须是对象")
        _require_fields(
            "exemplars.json",
            one,
            ("exemplar_id", "contest_id", "dimension_code", "band", "excerpt"),
        )
        if one["dimension_code"] not in DIMENSION_CODES:
            raise PackageError(
                "exemplars.json",
                f"{prefix}.dimension_code",
                f"只能是 {'、'.join(DIMENSION_CODES)}",
            )
        if one["band"] not in SCORED_BANDS:
            raise PackageError(
                "exemplars.json",
                f"{prefix}.band",
                f"样例评语只能取 {'、'.join(SCORED_BANDS)}",
            )
        normalized_exemplars.append(
            {
                "exemplar_id": str(one["exemplar_id"]),
                "contest_id": contest_id,
                "dimension_code": one["dimension_code"],
                "band": one["band"],
                "excerpt": str(one["excerpt"]),
            }
        )

    return {
        "contest": {
            "contest_id": contest_id,
            "year": int(contest["year"]),
            "problem_code": str(contest["problem_code"]),
            "title": str(contest["title"]),
            "statement": str(contest["statement"]),
            "status": contest["status"],
        },
        "constraints": normalized_constraints,
        "rubric": {
            "contest_id": contest_id,
            "version": version,
            "status": rubric_status,
            "dimensions": dimensions,
        },
        "pitfalls": normalized_pitfalls,
        "exemplars": normalized_exemplars,
    }


# --- 写库 ----------------------------------------------------------------------


def _split_bands(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(band) for band in bands]


def _write_package(session: Session, data: dict[str, Any]) -> dict[str, Any]:
    contest = data["contest"]
    contest_id = contest["contest_id"]
    version = data["rubric"]["version"]
    rubric_id = f"{contest_id}-v{version}"

    with session.begin_nested():
        row = session.get(Contest, contest_id)
        if row is None:
            row = Contest(contest_id=contest_id, status=contest["status"])
            session.add(row)
        row.year = contest["year"]
        row.problem_code = contest["problem_code"]
        row.title = contest["title"]
        row.statement = contest["statement"]

        session.execute(delete(Constraint).where(Constraint.contest_id == contest_id))
        session.execute(delete(Pitfall).where(Pitfall.contest_id == contest_id))
        session.execute(delete(Exemplar).where(Exemplar.contest_id == contest_id))
        old_rubric_ids = list(
            session.scalars(select(Rubric.rubric_id).where(Rubric.contest_id == contest_id))
        )
        if old_rubric_ids:
            session.execute(delete(Dimension).where(Dimension.rubric_id.in_(old_rubric_ids)))
            session.execute(delete(Rubric).where(Rubric.rubric_id.in_(old_rubric_ids)))
        session.flush()

        for one in data["constraints"]:
            session.add(Constraint(**one))
        for one in data["pitfalls"]:
            session.add(Pitfall(**one))
        for one in data["exemplars"]:
            session.add(Exemplar(**one))

        session.add(
            Rubric(
                rubric_id=rubric_id,
                contest_id=contest_id,
                version=version,
                status="draft",
                source_template_id=None,
            )
        )
        session.flush()
        for dimension in data["rubric"]["dimensions"]:
            session.add(
                Dimension(
                    dimension_id=f"{rubric_id}-{dimension['code']}",
                    rubric_id=rubric_id,
                    code=dimension["code"],
                    name=dimension["name"],
                    weight=dimension["weight"],
                    evidence_prompts=list(dimension["evidence_prompts"]),
                    section_types=list(dimension["section_types"]),
                    bands=_split_bands(dimension["bands"]),
                )
            )
        session.flush()

    return {
        "contest_id": contest_id,
        "rubric_id": rubric_id,
        "version": version,
        "dimensions": len(data["rubric"]["dimensions"]),
        "constraints": len(data["constraints"]),
        "pitfalls": len(data["pitfalls"]),
        "exemplars": len(data["exemplars"]),
    }


def import_package(package_dir: str | Path, *, session: Session | None = None) -> dict[str, Any]:
    """读目录下五个 JSON，整包校验，通过才写库；失败时抛 PackageError 且不写库。"""
    try:
        data = validate_package(package_dir)
    except PackageError as exc:
        log_event(
            "importing", "import_rejected", level="WARNING",
            filename=Path(str(exc.filename)).name, field=str(exc.field),
            reason=str(exc).splitlines()[0][:500],
        )
        raise
    with _session(session) as work:
        result = _write_package(work, data)
    log_event(
        "importing", "import_finished", contest_id=result.get("contest_id"),
        accepted=1, rejected=0, rejected_fields=[],
    )
    return result


# --- 目录操作 ------------------------------------------------------------------


def publish_contest(contest_id: str, *, session: Session | None = None) -> dict[str, Any]:
    """把赛题与它当前那一版量规设为可预审，其余量规置为 archived。"""
    with _session(session) as work:
        contest = work.get(Contest, contest_id)
        if contest is None:
            raise CatalogError(f"找不到赛题 {contest_id}")
        rubrics = list(
            work.scalars(
                select(Rubric).where(Rubric.contest_id == contest_id).order_by(Rubric.version)
            )
        )
        contest.status = "published"
        target = None
        if rubrics:
            published = [one for one in rubrics if one.status == "published"]
            target = published[0] if published else rubrics[-1]
            for one in rubrics:
                if one is target:
                    one.status = "published"
                elif one.status == "published":
                    one.status = "archived"
        work.flush()
        return {
            "contest_id": contest_id,
            "status": contest.status,
            "rubric_id": target.rubric_id if target else None,
            "rubric_version": target.version if target else None,
        }


def archive_contest(contest_id: str, *, session: Session | None = None) -> dict[str, Any]:
    """把赛题置为 archived。历史评审记录不属本版，不做处理。"""
    with _session(session) as work:
        contest = work.get(Contest, contest_id)
        if contest is None:
            raise CatalogError(f"找不到赛题 {contest_id}")
        contest.status = "archived"
        work.flush()
        return {"contest_id": contest_id, "status": contest.status}


def copy_rubric_as_draft(contest_id: str, *, session: Session | None = None) -> dict[str, Any]:
    """从当前 published 量规复制出 version + 1 的 draft，维度内容原样带过来。"""
    with _session(session) as work:
        contest = work.get(Contest, contest_id)
        if contest is None:
            raise CatalogError(f"找不到赛题 {contest_id}")
        source = work.scalars(
            select(Rubric)
            .where(Rubric.contest_id == contest_id, Rubric.status == "published")
            .order_by(Rubric.version.desc())
        ).first()
        if source is None:
            raise CatalogStateError(f"赛题 {contest_id} 没有已发布量规，无法复制下一版")

        new_version = source.version + 1
        new_rubric_id = f"{contest_id}-v{new_version}"
        source_dimensions = list(
            work.scalars(
                select(Dimension)
                .where(Dimension.rubric_id == source.rubric_id)
                .order_by(Dimension.dimension_id)
            )
        )
        with work.begin_nested():
            existing = work.get(Rubric, new_rubric_id)
            if existing is not None:
                work.execute(delete(Dimension).where(Dimension.rubric_id == new_rubric_id))
                work.delete(existing)
                work.flush()
            work.add(
                Rubric(
                    rubric_id=new_rubric_id,
                    contest_id=contest_id,
                    version=new_version,
                    status="draft",
                    source_template_id=source.source_template_id,
                )
            )
            work.flush()
            for dimension in source_dimensions:
                work.add(
                    Dimension(
                        dimension_id=f"{new_rubric_id}-{dimension.code}",
                        rubric_id=new_rubric_id,
                        code=dimension.code,
                        name=dimension.name,
                        weight=dimension.weight,
                        evidence_prompts=list(dimension.evidence_prompts),
                        section_types=list(dimension.section_types),
                        bands=[dict(band) for band in dimension.bands],
                    )
                )
            work.flush()
        return {
            "contest_id": contest_id,
            "rubric_id": new_rubric_id,
            "version": new_version,
            "status": "draft",
        }


def publish_rubric(rubric_id: str, *, session: Session | None = None) -> dict[str, Any]:
    """发布该版量规。同一赛题同时只能有一条 published，其余已发布的置为 archived。"""
    with _session(session) as work:
        rubric = work.get(Rubric, rubric_id)
        if rubric is None:
            raise CatalogError(f"找不到量规 {rubric_id}")
        others = list(
            work.scalars(
                select(Rubric).where(
                    Rubric.contest_id == rubric.contest_id, Rubric.rubric_id != rubric_id
                )
            )
        )
        rubric.status = "published"
        archived: list[str] = []
        for one in others:
            if one.status == "published":
                one.status = "archived"
                archived.append(one.rubric_id)
        work.flush()
        return {
            "contest_id": rubric.contest_id,
            "rubric_id": rubric_id,
            "version": rubric.version,
            "status": rubric.status,
            "archived_rubric_ids": archived,
        }


def _pick_rubric(rubrics: list[Rubric]) -> Rubric | None:
    if not rubrics:
        return None
    published = [one for one in rubrics if one.status == "published"]
    if published:
        return sorted(published, key=lambda one: one.version)[-1]
    return sorted(rubrics, key=lambda one: one.version)[-1]


def list_contests(
    include_archived: bool = False,
    include_drafts: bool = False,
    *,
    session: Session | None = None,
) -> list[dict[str, Any]]:
    """默认只返回 published；draft 与 archived 都要显式要求才返回。"""
    statuses = ["published"]
    if include_archived:
        statuses.append("archived")
    if include_drafts:
        statuses.append("draft")

    with _session(session) as work:
        contests = list(
            work.scalars(
                select(Contest)
                .where(Contest.status.in_(statuses))
                .order_by(Contest.year, Contest.contest_id)
            )
        )
        if not contests:
            return []
        contest_ids = [one.contest_id for one in contests]
        constraints = list(
            work.scalars(
                select(Constraint)
                .where(Constraint.contest_id.in_(contest_ids))
                .order_by(Constraint.constraint_id)
            )
        )
        rubrics = list(work.scalars(select(Rubric).where(Rubric.contest_id.in_(contest_ids))))
        pitfall_counts = dict(
            work.execute(
                select(Pitfall.contest_id, func.count())
                .where(Pitfall.contest_id.in_(contest_ids))
                .group_by(Pitfall.contest_id)
            ).all()
        )
        exemplar_counts = dict(
            work.execute(
                select(Exemplar.contest_id, func.count())
                .where(Exemplar.contest_id.in_(contest_ids))
                .group_by(Exemplar.contest_id)
            ).all()
        )

        items: list[dict[str, Any]] = []
        for contest in contests:
            rubric = _pick_rubric([one for one in rubrics if one.contest_id == contest.contest_id])
            items.append(
                {
                    "contest_id": contest.contest_id,
                    "year": contest.year,
                    "problem_code": contest.problem_code,
                    "title": contest.title,
                    "statement": contest.statement,
                    "status": contest.status,
                    "rubric": (
                        {
                            "rubric_id": rubric.rubric_id,
                            "version": rubric.version,
                            "status": rubric.status,
                        }
                        if rubric
                        else None
                    ),
                    "constraints": [
                        {
                            "constraint_id": one.constraint_id,
                            "name": one.name,
                            "check_type": one.check_type,
                            "params": one.params,
                            "section_types": one.section_types,
                        }
                        for one in constraints
                        if one.contest_id == contest.contest_id
                    ],
                    "pitfall_count": int(pitfall_counts.get(contest.contest_id, 0)),
                    "exemplar_count": int(exemplar_counts.get(contest.contest_id, 0)),
                }
            )
        return items
