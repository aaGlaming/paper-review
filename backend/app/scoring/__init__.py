# 评分层。
# 加权合计是纯函数：权重只读量规数据，证据不足与引用失败不进入合计。
# 选档的确定性部分（JSON 解析、原句子串校验、降档守卫）也在本包内，同样不连数据库、不发 HTTP。
# 模型只负责在给定证据里选档；权重加总、原句是否为子串、题目条件是否被提到，都由代码完成。

from .aggregate import (
    BANDS,
    REASON_BAND_MISSING,
    REASON_CITATION_FAILURE,
    REASON_FAILURE,
    REASON_INSUFFICIENT,
    REASON_UNKNOWN_DIMENSION,
    SCORE_STATUSES,
    STATUS_CITATION_FAILURE,
    STATUS_FAILURE,
    STATUS_INSUFFICIENT,
    WEIGHTED_BANDS,
    dimension_code_of,
    weight_table,
    weighted_sum,
)
from .selection import (
    DOWNGRADED_BAND,
    JSON_FIELDS,
    MAX_CHAT_ATTEMPTS,
    SCORING_TEMPERATURE,
    ScoringParseError,
    apply_mention_guard,
    build_scoring_messages,
    join_evidence,
    parse_scoring_json,
    quote_is_substring,
)

__all__ = [
    "BANDS",
    "DOWNGRADED_BAND",
    "JSON_FIELDS",
    "MAX_CHAT_ATTEMPTS",
    "REASON_BAND_MISSING",
    "REASON_CITATION_FAILURE",
    "REASON_FAILURE",
    "REASON_INSUFFICIENT",
    "REASON_UNKNOWN_DIMENSION",
    "SCORE_STATUSES",
    "SCORING_TEMPERATURE",
    "STATUS_CITATION_FAILURE",
    "STATUS_FAILURE",
    "STATUS_INSUFFICIENT",
    "ScoringParseError",
    "WEIGHTED_BANDS",
    "apply_mention_guard",
    "build_scoring_messages",
    "dimension_code_of",
    "join_evidence",
    "parse_scoring_json",
    "quote_is_substring",
    "weight_table",
    "weighted_sum",
]
