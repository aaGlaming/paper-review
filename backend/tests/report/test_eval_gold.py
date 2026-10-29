from __future__ import annotations

from collections import Counter

from backend.app.report import evaluation
from backend.app.review import samples


def test_eval_gold_required_fields_bands_and_findings_shape():
    papers = samples.load_eval_papers()

    assert papers
    for paper in papers:
        assert str(paper.get("paper_id") or "").strip()
        assert str(paper.get("contest_id") or "").strip()
        assert str(paper.get("title") or "").strip()
        gold = paper.get("gold")
        assert isinstance(gold, list) and len(gold) == 5
        assert all(item.get("band") in {"充分", "基本", "不足", "证据不足"} for item in gold)
        assert isinstance(paper.get("expected_findings"), list)


def test_eval_gold_dimension_codes_match_contest_rubric_exactly():
    for paper in samples.load_eval_papers():
        rubric = evaluation._load_rubric(str(paper["contest_id"]))
        rubric_codes = [str(item.get("dimension_code") or "") for item in rubric["dimensions"]]
        gold_codes = [str(item.get("dimension_code") or "") for item in paper["gold"]]

        assert all(rubric_codes), f"{paper['paper_id']}: rubric has an empty dimension code"
        assert Counter(gold_codes) == Counter(rubric_codes), (
            f"{paper['paper_id']} ({paper['contest_id']}): gold dimension codes "
            f"{gold_codes} do not exactly match rubric codes {rubric_codes}"
        )
