# 报告与评测。
# 修改清单只转写已校验的维度档位与审查结果，顺序固定为题目约束和数字冲突、证据不足、表述；
# 每条建议带上游 id，删掉上游记录后对应建议不再出现。
# 评审记录落在 review 与 review_dimension 两张表（自己的 ReportBase，独立于赛题那七张表与 paper_parent），
# 旧记录一律不回写。评测是纯计算：chat=None 时走确定性结构回退，并在返回结果里标明 source，
# 那些数字是脚本自检，不是模型准确率。
# 本包不发 HTTP、不导入模型客户端、不按题号写分支。

from .catalog import list_samples
from .change_list import (
    ACTION_INSUFFICIENT,
    ACTION_PRESENTATION,
    AWARD_WORDS,
    KIND_CONSTRAINT,
    KIND_INSUFFICIENT,
    KIND_NUMBER_CONFLICT,
    KIND_PRESENTATION,
    SECTION_CONSTRAINTS,
    SECTION_INSUFFICIENT,
    SECTION_ORDER,
    SECTION_PRESENTATION,
    build_change_list,
    contains_award_words,
    render_change_list,
)
from .evaluation import (
    SOURCE_DETERMINISTIC,
    SOURCE_MODEL,
    deterministic_results,
    run_eval,
    summarize_eval,
)
from .models import ReportBase, Review, ReviewDimension, create_report_schema
from .store import load_review, save_review

__all__ = [
    "ACTION_INSUFFICIENT",
    "ACTION_PRESENTATION",
    "AWARD_WORDS",
    "KIND_CONSTRAINT",
    "KIND_INSUFFICIENT",
    "KIND_NUMBER_CONFLICT",
    "KIND_PRESENTATION",
    "SECTION_CONSTRAINTS",
    "SECTION_INSUFFICIENT",
    "SECTION_ORDER",
    "SECTION_PRESENTATION",
    "SOURCE_DETERMINISTIC",
    "SOURCE_MODEL",
    "ReportBase",
    "Review",
    "ReviewDimension",
    "build_change_list",
    "contains_award_words",
    "create_report_schema",
    "deterministic_results",
    "list_samples",
    "load_review",
    "render_change_list",
    "run_eval",
    "save_review",
    "summarize_eval",
]
