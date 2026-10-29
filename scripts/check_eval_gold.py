"""只读核验 eval gold 元数据与对应赛题量规，不修改任何样本。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.report.evaluation import _load_rubric  # noqa: E402
from backend.app.review.samples import EVAL_DIR, GOLD_FIELDS, REQUIRED_EVAL_FIELDS  # noqa: E402

ALLOWED_BANDS = {"充分", "基本", "不足", "证据不足"}


def main() -> int:
    paths = sorted(path for path in EVAL_DIR.glob("*.json") if not path.stem.upper().startswith("README"))
    issues: list[str] = []
    print("file\tpaper_id\tcontest_id\ttitle_nonempty\tgold_count\tband_distribution\texpected_findings_count\tdimension_codes_match\tissues")
    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        paper_id = str(metadata.get("paper_id") or "")
        contest_id = str(metadata.get("contest_id") or "")
        title = str(metadata.get("title") or "")
        local_issues: list[str] = []
        for field in REQUIRED_EVAL_FIELDS:
            value = metadata.get(field)
            if value is None or value == "" or value == []:
                local_issues.append(f"missing:{field}")
        if not paper_id.strip():
            local_issues.append("empty:paper_id")
        if not contest_id.strip():
            local_issues.append("empty:contest_id")
        if not title.strip():
            local_issues.append("empty:title")

        gold = metadata.get("gold")
        if not isinstance(gold, list) or len(gold) != 5:
            local_issues.append("gold_count_not_5")
            gold = gold if isinstance(gold, list) else []
        distribution: Counter[str] = Counter()
        gold_codes: list[str] = []
        for index, item in enumerate(gold):
            if not isinstance(item, dict):
                local_issues.append(f"gold_item_not_object:{index}")
                continue
            if any(field not in item for field in GOLD_FIELDS):
                local_issues.append(f"gold_fields_missing:{index}")
            code = str(item.get("dimension_code") or "")
            band = str(item.get("band") or "")
            gold_codes.append(code)
            distribution[band or "<empty>"] += 1
            if not code:
                local_issues.append(f"empty_dimension_code:{index}")
            if band not in ALLOWED_BANDS:
                local_issues.append(f"invalid_band:{index}:{band or '<empty>'}")

        findings = metadata.get("expected_findings")
        if not isinstance(findings, list):
            local_issues.append("expected_findings_not_array")
            findings_count = "invalid"
        else:
            findings_count = str(len(findings))

        rubric_codes = [
            str(item.get("dimension_code") or "")
            for item in _load_rubric(contest_id).get("dimensions") or ()
        ]
        codes_match = bool(rubric_codes) and Counter(gold_codes) == Counter(rubric_codes)
        if not codes_match:
            local_issues.append("dimension_codes_do_not_match_rubric")

        issues.extend(f"{path.name}:{item}" for item in local_issues)
        print(
            f"{path.name}\t{paper_id}\t{contest_id}\t{bool(title.strip())}\t"
            f"{len(gold)}\t{dict(sorted(distribution.items()))}\t{findings_count}\t"
            f"{codes_match}\t{';'.join(local_issues) or '-'}"
        )

    print(f"summary\tfiles={len(paths)}\tissues={len(issues)}")
    for issue in issues:
        print(f"ERROR\t{issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
