"""规则审查：数字一致性、引用存在性、题目约束（mention / numeric_range / required_case）。

本模块是纯函数集合：不连数据库、不读文件、不发 HTTP、不调模型；文本与约束都由调用方传入。
每条结果都带原文里的字符偏移（`evidence` 列表），供页面定位。

v0.7.0 的两条误报防线：
- **数字冲突按指标归组，不按单位归组**。同一份稿子里可能有多处秒数分别指投放时刻、起爆间隔与
  有效时间窗，只有指向同一个量的那几处才算冲突。指标取数字前紧邻的那段文字（在标点或换行处断开），
  去掉数字、单位、括号与通用连接词后的结果；两处**单位相同，且指标相同或互为前缀 / 后缀**，才归为一组。
- **越界按指标匹配约束，不按单位匹配**。同一单位下可能同时存在多个量（例如导弹速度与无人机速度
  都是 m/s），只有出现在该约束指标上下文里的数值才拿去与 min / max 比较。指标上下文取自约束名里
  在正文中出现过的最长前缀，完全由约束数据驱动，代码里不写任何题面字面量。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

KIND_NUMBER_CONFLICT = "数字冲突"
KIND_CITATION_MISSING = "引用缺失"
KIND_RANGE_VIOLATION = "越界"
KIND_CASE_MISSING = "缺少情形"
KIND_MENTION_MISSING = "未提到条件"

# 单位表：长的排前面，保证 m/s 先于 m 命中。约束里的 unit 也按同一套识别。
MEASUREMENT_UNITS: tuple[str, ...] = (
    "m/s",
    "km/h",
    "万元",
    "亿元",
    "分钟",
    "小时",
    "kg",
    "min",
    "km",
    "cm",
    "ms",
    "s",
    "秒",
    "m",
    "米",
    "h",
    "%",
    "℃",
    "元",
)

# 指标归一化时要去掉的通用连接词（只剥尾部，剥完为止）。
GENERIC_TAIL_WORDS: tuple[str, ...] = (
    "不超过",
    "不低于",
    "不高于",
    "合计",
    "总计",
    "之间",
    "以内",
    "左右",
    "为",
    "是",
    "达",
    "约",
    "共",
    "以",
    "后",
    "前",
    "内",
    "时",
    "中",
    "上",
    "下",
    "至",
    "和",
    "及",
)

LABEL_CUT_CHARS = "，,。；;：:！!？?、\n\t"
LABEL_WINDOW = 24
MIN_SUBJECT_LENGTH = 3
VALUE_EPSILON = 1e-9

_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d{1,3})\]")
_REFERENCE_HEADINGS = ("参考文献", "references", "bibliography")


def _sorted_units() -> tuple[str, ...]:
    return tuple(sorted(MEASUREMENT_UNITS, key=len, reverse=True))


def _sorted_tail_words() -> tuple[str, ...]:
    return tuple(sorted(GENERIC_TAIL_WORDS, key=len, reverse=True))


def _measurement_regex() -> re.Pattern[str]:
    units = "|".join(re.escape(unit) for unit in _sorted_units())
    return re.compile(rf"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{units})")


def _evidence(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "char_start": int(item["char_start"]),
        "char_end": int(item["char_end"]),
        "text": str(item["text"]),
    }


def find_matches(text: str, needle: str) -> list[dict[str, object]]:
    """找出 needle 在 text 里的全部出现位置，带字符偏移。"""
    if not text or not needle:
        return []
    matches: list[dict[str, object]] = []
    start = text.find(needle)
    while start >= 0:
        matches.append({"char_start": start, "char_end": start + len(needle), "text": needle})
        start = text.find(needle, start + 1)
    return matches


def section_spans(text: str) -> list[dict[str, object]]:
    """按 ATX 标题切出章节区间。title 不含 # 号，char_end 到下一个标题为止。"""
    headings = list(_HEADING_RE.finditer(text))
    spans: list[dict[str, object]] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        spans.append(
            {
                "title": match.group(2).strip(),
                "level": len(match.group(1)),
                "char_start": match.start(),
                "char_end": end,
            }
        )
    return spans


def iter_measurements(text: str) -> list[dict[str, object]]:
    """找出正文里所有“数值 + 单位”的出现，带字符偏移。"""
    measurements: list[dict[str, object]] = []
    for match in _measurement_regex().finditer(text):
        measurements.append(
            {
                "value": float(match.group("value")),
                "unit": match.group("unit"),
                "char_start": match.start(),
                "char_end": match.end(),
                "text": match.group(0),
            }
        )
    return measurements


def _label_window(text: str, start: int, lower_bound: int = 0) -> str:
    """数字前紧邻的一段文字，在标点或换行处断开。

    `lower_bound` 取上一处数值的末尾：指标窗口不许越过前一处数值，否则前一处数值的措辞会漏进来，
    把「把起爆时刻提前 0.5 s 后……约 0.4 s」这种相邻但不同指标的两处错认成同一指标。
    """
    window = text[max(lower_bound, start - LABEL_WINDOW) : start]
    cut = max((window.rfind(char) for char in LABEL_CUT_CHARS), default=-1)
    if cut >= 0:
        window = window[cut + 1 :]
    return window


def measure_with_windows(text: str) -> list[dict[str, object]]:
    """每处「数值 + 单位」连同它前面的指标窗口与归一化后的指标名。"""
    results: list[dict[str, object]] = []
    previous_end = 0
    for measurement in iter_measurements(text):
        start = int(measurement["char_start"])
        window = _label_window(text, start, lower_bound=previous_end)
        results.append({**measurement, "window": window, "label": normalize_label(window)})
        previous_end = int(measurement["char_end"])
    return results


def _strip_tail_words(value: str) -> str:
    text = value
    changed = True
    while changed and len(text) > 1:
        changed = False
        for word in _sorted_tail_words():
            if text.endswith(word) and len(text) > len(word):
                text = text[: -len(word)]
                changed = True
                break
    return text


def normalize_label(window: str) -> str:
    """把数字前的文字归一成指标名：去掉表格分隔、括号、数字与单位，再剥掉尾部通用词。"""
    text = re.sub(r"[|｜]", " ", window)
    text = re.sub(r"[（(][^）)]*[）)]", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?", " ", text)
    for unit in _sorted_units():
        text = text.replace(unit, " ")
    text = text.replace("～", " ").replace("~", " ").replace("-", " ").replace("—", " ")
    text = re.sub(r"\s+", "", text)
    return _strip_tail_words(text.strip())


def labels_related(left: str, right: str) -> bool:
    """两处是否指向同一个指标。

    判据是「相同，或一方是另一方的前缀 / 后缀」。用前缀 / 后缀而不是任意包含，是因为短标签
    可能恰好出现在另一个无关指标名中间（例如短标签「起爆」出现在「把起爆时刻提前」中间），
    那不是同一个指标，报出来就是误报。
    """
    if len(left) < 2 or len(right) < 2:
        return False
    if left == right:
        return True
    return left.startswith(right) or right.startswith(left) or left.endswith(right) or right.endswith(left)


def check_number_conflicts(text: str) -> list[dict[str, object]]:
    """同一指标在不同位置取值不同 -> 数字冲突。按指标归组，不按单位归组。"""
    groups: list[dict[str, object]] = []
    for measurement in measure_with_windows(text):
        label = str(measurement["label"])
        for group in groups:
            if group["unit"] != measurement["unit"]:
                continue
            if labels_related(str(group["label"]), label):
                group["items"].append(measurement)
                break
        else:
            groups.append({"unit": measurement["unit"], "label": label, "items": [measurement]})

    findings: list[dict[str, object]] = []
    for group in groups:
        items = list(group["items"])
        values = {round(float(item["value"]), 6) for item in items}
        if len(items) < 2 or len(values) < 2:
            continue
        label = str(group["label"]) or f"同单位数值（{group['unit']}）"
        shown = "、".join(str(item["text"]) for item in items)
        findings.append(
            {
                "kind": KIND_NUMBER_CONFLICT,
                "constraint_id": None,
                "indicator": label,
                "evidence": [_evidence(item) for item in items],
                "message": f"同一指标「{label}」在不同位置取值不同：{shown}",
            }
        )
    return findings


def split_references(text: str) -> tuple[str, str]:
    """按最后一个“参考文献”类标题把正文与文献列表分开。"""
    for span in reversed(section_spans(text)):
        title = str(span["title"]).lower()
        if any(heading in title for heading in _REFERENCE_HEADINGS):
            start = int(span["char_start"])
            return text[:start], text[start:]
    return text, ""


def check_citations(text: str) -> list[dict[str, object]]:
    """正文引用了、参考文献列表里却没有的编号 -> 引用缺失。"""
    body, references = split_references(text)
    listed = {int(match.group(1)) for match in _CITATION_RE.finditer(references)}
    collected: dict[int, list[dict[str, object]]] = {}
    for match in _CITATION_RE.finditer(body):
        number = int(match.group(1))
        if number in listed:
            continue
        collected.setdefault(number, []).append(
            {
                "char_start": match.start(),
                "char_end": match.end(),
                "text": match.group(0),
            }
        )
    findings: list[dict[str, object]] = []
    for number in sorted(collected):
        findings.append(
            {
                "kind": KIND_CITATION_MISSING,
                "constraint_id": None,
                "indicator": f"引用 [{number}]",
                "evidence": collected[number],
                "message": f"正文引用了 [{number}]，参考文献列表里没有这一条",
            }
        )
    return findings


def _params(constraint: Mapping[str, object]) -> dict[str, object]:
    params = constraint.get("params")
    return dict(params) if isinstance(params, Mapping) else {}


def _indicator_subjects(constraint: Mapping[str, object], text: str) -> list[str]:
    """约束名里在正文出现过的最长前缀，用来把这约束绑到具体指标上（≥3 字，避免过短误配）。"""
    name = str(constraint.get("name") or "")
    if not name:
        return []
    cut = len(name)
    for index, char in enumerate(name):
        if char.isdigit():
            cut = index
            break
    phrase = re.sub(r"[（(][^）)]*[）)]", "", name[:cut])
    for unit in _sorted_units():
        phrase = phrase.replace(unit, "")
    phrase = _strip_tail_words(re.sub(r"\s+", "", phrase))
    if len(phrase) < MIN_SUBJECT_LENGTH:
        return []
    subjects = []
    for length in range(MIN_SUBJECT_LENGTH, len(phrase) + 1):
        prefix = phrase[:length]
        if prefix in text:
            subjects.append(prefix)
    return subjects


def check_mention(text: str, constraint: Mapping[str, object]) -> list[dict[str, object]]:
    """mention：关键词全部未命中 -> 未提到该条件。命中任一关键词即视为提到。"""
    keywords = [
        str(item) for item in (_params(constraint).get("keywords") or ()) if str(item).strip()
    ]
    if not keywords:
        return []
    if any(find_matches(text, keyword) for keyword in keywords):
        return []
    name = str(constraint.get("name") or "未命名条件")
    return [
        {
            "kind": KIND_MENTION_MISSING,
            "constraint_id": constraint.get("constraint_id"),
            "indicator": name,
            "evidence": [],
            "message": f"正文没有提到题目条件「{name}」",
        }
    ]


def check_numeric_range(text: str, constraint: Mapping[str, object]) -> list[dict[str, object]]:
    """numeric_range：只检查落在该约束指标上下文里的数值，按 min / max 判断越界。"""
    params = _params(constraint)
    unit = str(params.get("unit") or "")
    low = params.get("min")
    high = params.get("max")
    if not unit or low is None or high is None:
        return []
    subjects = _indicator_subjects(constraint, text)
    if not subjects:
        return []
    name = str(constraint.get("name") or unit)
    findings: list[dict[str, object]] = []
    for measurement in measure_with_windows(text):
        if measurement["unit"] != unit:
            continue
        window = str(measurement["window"])
        if not any(subject in window for subject in subjects):
            continue
        value = float(measurement["value"])
        if value < float(low) - VALUE_EPSILON or value > float(high) + VALUE_EPSILON:
            findings.append(
                {
                    "kind": KIND_RANGE_VIOLATION,
                    "constraint_id": constraint.get("constraint_id"),
                    "indicator": name,
                    "evidence": [_evidence(measurement)],
                    "message": (
                        f"「{name}」要求取值在 {low}～{high} {unit} 之间，"
                        f"正文出现 {measurement['text']}，超出该范围"
                    ),
                }
            )
    return findings


def check_required_case(text: str, constraint: Mapping[str, object]) -> list[dict[str, object]]:
    """required_case：结果文件（artifact）没有出现在正文里 -> 缺少该情形。"""
    params = _params(constraint)
    artifact = str(params.get("artifact") or "")
    label = str(params.get("label") or artifact)
    if artifact and artifact in text:
        return []
    return [
        {
            "kind": KIND_CASE_MISSING,
            "constraint_id": constraint.get("constraint_id"),
            "indicator": label,
            "evidence": [],
            "message": f"正文没有给出「{label}」情形（缺少 {artifact}）",
        }
    ]


# 已注册检查：key 与 constraint.check_type 同名，页面与状态图按这个表分派。
REGISTERED_CHECKS = {
    "mention": check_mention,
    "numeric_range": check_numeric_range,
    "required_case": check_required_case,
}


def check_numbers_citations_ranges(
    text: str, constraints: Iterable[Mapping[str, object]] | None = None
) -> list[dict[str, object]]:
    """一次跑完数字冲突、引用缺失与三类已注册检查。"""
    findings: list[dict[str, object]] = []
    findings.extend(check_number_conflicts(text))
    findings.extend(check_citations(text))
    for constraint in constraints or ():
        if not isinstance(constraint, Mapping):
            continue
        checker = REGISTERED_CHECKS.get(str(constraint.get("check_type")))
        if checker is None:
            continue
        findings.extend(checker(text, constraint))
    return findings
