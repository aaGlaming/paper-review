# 规则审查。
# check_numbers_citations_ranges() 一次跑完数字一致性、引用存在性与三类已注册检查
# （mention / numeric_range / required_case）。每条结果都带原文里的字符偏移，供页面定位。
# 数字冲突按指标归组而不按单位归组；越界按指标匹配约束而不按单位匹配。
# 本包不连数据库、不读向量库、不发 HTTP、不调模型：文本与约束由调用方传入。
# samples.py 只负责把演示稿与评测样例读进来。

from .consistency import (
    KIND_CASE_MISSING,
    KIND_CITATION_MISSING,
    KIND_MENTION_MISSING,
    KIND_NUMBER_CONFLICT,
    KIND_RANGE_VIOLATION,
    REGISTERED_CHECKS,
    check_citations,
    check_mention,
    check_number_conflicts,
    check_numbers_citations_ranges,
    check_numeric_range,
    check_required_case,
    find_matches,
    iter_measurements,
    normalize_label,
    section_spans,
    split_references,
)
from .samples import (
    DEMO_FILES,
    EVAL_DIR,
    SAMPLES_DIR,
    load_demo_text,
    load_demo_texts,
    load_eval_papers,
)

__all__ = [
    "DEMO_FILES",
    "EVAL_DIR",
    "KIND_CASE_MISSING",
    "KIND_CITATION_MISSING",
    "KIND_MENTION_MISSING",
    "KIND_NUMBER_CONFLICT",
    "KIND_RANGE_VIOLATION",
    "REGISTERED_CHECKS",
    "SAMPLES_DIR",
    "check_citations",
    "check_mention",
    "check_number_conflicts",
    "check_numbers_citations_ranges",
    "check_numeric_range",
    "check_required_case",
    "find_matches",
    "iter_measurements",
    "load_demo_text",
    "load_demo_texts",
    "load_eval_papers",
    "normalize_label",
    "section_spans",
    "split_references",
]
