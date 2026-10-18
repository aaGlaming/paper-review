from __future__ import annotations

from backend.app.retrieve.parent_child import ParentBlock
from backend.app.retrieve.three_route import STATUS_HIT, retrieve_dimension


def test_retrieve_dimension_uses_review_scoped_mysql_fallback_without_vectors():
    seen = []

    def mysql_search_round(**request):
        seen.append(request)
        return [
            ParentBlock("paper-1", "模型", "模型章节证据", review_id="review-1"),
        ]

    result = retrieve_dimension(
        "模型依据",
        contest_id="contest-x",
        rubric_id="rubric-x",
        dimension_code="modeling",
        section_types=["模型"],
        review_id="review-1",
        query_embedding=None,
        fallback_search_round=mysql_search_round,
    )

    assert result.status == STATUS_HIT
    assert [parent.parent_id for parent in result.parents] == ["paper-1"]
    assert seen[0]["review_id"] == "review-1"
    assert seen[0]["query_embedding"] is None
