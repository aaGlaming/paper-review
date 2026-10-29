# -*- coding: utf-8 -*-
"""OCR 文本 -> Markdown 的共享规则（标题识别与段落合并）。

`pdf_to_md.py`（首次转换）与 `retitle_md.py`（重新整理已有文本）都用这里，
保证两条路径的判定完全一致。

两个关键约束：
1. 标题必须能被 backend/app/graph/review_graph.py 的 `_classify()` 认出，
   所以标题文本要含 假设/模型/建模/求解/检验/结果/参考文献 之一。
2. 判定要「严」：正文行里到处是「模型」「求解」，光看关键词会把正文判成标题。
   因此额外的硬条件是——短、且不含句读标点。
"""
from __future__ import annotations

import re

SECTION_WORDS = ("假设", "模型", "建模", "求解", "检验", "结果",
                 "参考文献", "references", "bibliography")

# 不含关键词但确实是章节的标题
EXTRA_TITLES = ("摘要", "问题重述", "问题分析", "符号说明", "符号约定",
                "模型评价", "模型推广", "模型改进", "附录", "关键词", "关键字")

# 一级标题的编号形式：「一、」「第一章」「1.」
H1_PATTERNS = (
    re.compile(r"^第[一二三四五六七八九十]+[章节部分]\s*"),
    re.compile(r"^[一二三四五六七八九十]+\s*[、.．]\s*"),
    re.compile(r"^\d{1,2}\s*[、.．]\s*(?=\S)"),
)
# 二级编号：「1.1」「2.3.1」
H2_PATTERN = re.compile(r"^\d{1,2}(\.\d{1,2}){1,2}\s+\S")

# 标题里不该出现的标点（出现即判为正文）
TITLE_FORBIDDEN = "。，；：！？、,;:!?"

# 段落终止标点
END_PUNCT = ("。", "？", "！", "；", "”", "）")

# OCR 常见误识别
OCR_FIXES = (
    ("resultl", "result1"),
    ("resultZ", "result2"),
    ("resultz", "result2"),
)

MAX_TITLE_LEN = 24
MAX_TITLE_LEN_WITH_NUMBER = 30


def strip_marker(line: str) -> str:
    """去掉「一、」「1.」这类编号。"""
    for pattern in H1_PATTERNS:
        if pattern.match(line):
            return pattern.sub("", line).strip()
    return line.strip()


def is_title(line: str) -> bool:
    """判一行是不是章节标题。宁可漏判（当正文），也不要把正文判成标题。"""
    raw = line.strip()
    if not raw:
        return False
    bare = strip_marker(raw)
    if not bare:
        return False
    # 硬条件一：短
    limit = MAX_TITLE_LEN_WITH_NUMBER if bare != raw else MAX_TITLE_LEN
    if len(bare) > limit:
        return False
    # 硬条件二：不含句读标点
    if any(ch in bare for ch in TITLE_FORBIDDEN):
        return False
    low = bare.lower()
    if any(word in low for word in SECTION_WORDS):
        return True
    if any(bare.startswith(t) for t in EXTRA_TITLES):
        return True
    return False


def normalize(text: str) -> str:
    """去掉页眉页脚碎片与纯页码。"""
    for bad, good in OCR_FIXES:
        text = text.replace(bad, good)
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"[-—_\s]{3,}", s):
            continue
        if re.fullmatch(r"\d{1,3}", s):
            continue
        out.append(s)
    return "\n".join(out)


def build_markdown(pages: list[str]) -> str:
    """把逐页文本拼成 Markdown：加标题、合并断行、压掉多余空行。

    附录之后的标题一律不再提升：附录里是 Python/MATLAB 代码，大量 `print(已求解…)`
    这类行会被误判成「求解」章节，进而被检索当成论证证据。整段并入「附录」一节。
    """
    blocks: list[str] = []   # 输出块，元素是「标题行」或「段落」
    in_appendix = False

    for page_text in pages:
        pending = ""          # 待合并的正文片段

        def flush() -> None:
            nonlocal pending
            if pending:
                blocks.append(pending)
                pending = ""

        for line in page_text.split("\n"):
            s = line.strip()
            if not s:
                continue
            if in_appendix:
                # 附录内不再开新标题，全部按正文并入
                if pending and not pending.endswith(END_PUNCT):
                    pending += s
                else:
                    flush()
                    pending = s
                continue
            if is_title(s):
                flush()
                title = strip_marker(s)
                blocks.append("## " + title if H2_PATTERN.match(title) else "# " + title)
                if any(k in title.lower() for k in ("附录", "appendix")):
                    in_appendix = True
                continue
            # 正文：上一片段没结束就接着写，否则新开一段
            if pending and not pending.endswith(END_PUNCT):
                pending += s
            else:
                flush()
                pending = s
        flush()

    # 论文大标题常常不含章节关键词（如「板凳龙运动路径的优化分析」），
    # 会被判成正文，导致第一个 # 变成「摘要」、前端列表全显示「摘要」。
    # 这里按「短句 + 紧跟摘要」把它补成标题。
    if (len(blocks) > 1
            and not blocks[0].startswith("#")
            and blocks[1].startswith("# 摘要")
            and len(blocks[0]) <= 40
            and not any(ch in blocks[0] for ch in TITLE_FORBIDDEN)):
        blocks[0] = "# " + blocks[0]

    return "\n\n".join(blocks).strip() + "\n"
