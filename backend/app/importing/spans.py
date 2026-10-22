"""Shared source ranges for parsed sections in the original paper text."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..graph.review_graph import _HEADING_RE


class SectionRangeMismatch(ValueError):
    """The persisted section structure no longer matches its source text."""


def sections_with_source_ranges(
    paper_text: str, sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach contiguous half-open ranges; each ATX heading belongs to its section.

    Ranges cover the complete source, including headings and blank separators.
    `_parse_sections` strips surrounding whitespace from `content`, so consumers
    compare the stripped body after the heading line with that normalized field.
    This function is strict; GET detail catches `SectionRangeMismatch` and omits
    ranges for compatibility, while artifact extraction turns it into HTTP 409.
    """
    if not isinstance(sections, list):
        raise SectionRangeMismatch("sections must be a list")
    headings = list(_HEADING_RE.finditer(paper_text))
    spans: list[tuple[int, int]] = []
    if not headings:
        if paper_text:
            spans.append((0, len(paper_text)))
    else:
        has_preamble = bool(paper_text[: headings[0].start()].strip())
        if has_preamble:
            spans.append((0, headings[0].start()))
        for index, heading in enumerate(headings):
            start = heading.start()
            if index == 0 and not has_preamble:
                start = 0  # Leading whitespace is owned by the first headed section.
            end = headings[index + 1].start() if index + 1 < len(headings) else len(paper_text)
            spans.append((start, end))

    if len(spans) != len(sections):
        raise SectionRangeMismatch("confirmed sections do not match the source headings")
    if spans and (spans[0][0] != 0 or spans[-1][1] != len(paper_text)):
        raise SectionRangeMismatch("section ranges do not cover the complete source")
    if any(left[1] != right[0] for left, right in zip(spans, spans[1:])):
        raise SectionRangeMismatch("section ranges are not contiguous")

    preamble_count = int(bool(headings and paper_text[: headings[0].start()].strip()))
    for index, (section, (start, end)) in enumerate(zip(sections, spans, strict=True)):
        if not isinstance(section, Mapping):
            raise SectionRangeMismatch(f"section {index} is not an object")
        heading_index = index - preamble_count if headings else -1
        if heading_index >= 0:
            actual_title = headings[heading_index].group(2).strip()
            if str(section.get("title") or "").strip() != actual_title:
                raise SectionRangeMismatch(f"section {index} title does not match its source heading")

    return [
        {**section, "char_start": start, "char_end": end}
        for section, (start, end) in zip(sections, spans, strict=True)
    ]
