# -*- coding: utf-8 -*-
"""诊断 force_submit 为何补交 0 条。

不复现上下文，只做一件事：把某个 review 的**真实父块证据**取出来，
重放一次补交请求，打印模型原始返回与逐条拒绝原因。只读，不改库。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import create_engine, text

from backend.app.agent.runner import _decode_force
from backend.app.agent.tools import BANDS
from backend.app.llm import client as llm_client
from backend.app.scoring.selection import quote_is_substring


def main() -> int:
    e = create_engine(os.environ["MYSQL_DSN"])
    with e.connect() as c:
        rid = c.execute(text(
            "select review_id from review order by created_at desc limit 1")).scalar()
        rows = c.execute(text(
            "select dimension_code, band from review_dimension where review_id=:r"),
            {"r": rid}).fetchall()
        parents = c.execute(text(
            "select parent_id, content from paper_parent where review_id=:r"),
            {"r": rid}).fetchall()
    print("review_id:", rid)
    print("维度结果:", [(r[0], r[1]) for r in rows])
    print("父块数:", len(parents))

    missing = [r[0] for r in rows if r[1] == "证据不足"]
    if not missing:
        print("没有缺失维度")
        return 0
    print("缺失维度:", missing)

    # 真实父块按 section_type 分组：证据取自父块，命中任一维度都可作为证据
    all_parents = [{"parent_id": p[0], "content": p[1]} for p in parents]
    total_chars = sum(len(p["content"]) for p in all_parents)
    print("父块总字数:", total_chars)
    for p in all_parents[:6]:
        print("   %-24s %5d 字" % (p["parent_id"][:24], len(p["content"])))

    evidence = [{"dimension_code": code,
                 "parents": [{"parent_id": p["parent_id"], "chunk_ids": [],
                              "content": p["content"]} for p in all_parents[:4]]}
                for code in missing]
    payload = json.dumps(evidence, ensure_ascii=False)
    print("\n送入证据长度:", len(payload), "字符（每维 4 段父块全文）")

    prompt = ("仅完成交卷，不再检索。请为以下每个缺失维度返回 JSON 数组，"
              "每项含 dimension_code、band、quote、chunk_id；"
              "quote 必须逐字复制对应父块 content 的连续片段：" + payload)
    resp = llm_client.chat_with_tools(
        [{"role": "user", "content": prompt}],
        [{"type": "function", "function": {
            "name": "force_submit",
            "description": "Return final dimension submissions",
            "parameters": {"type": "object", "properties": {"items": {"type": "array"}}}}}],
        temperature=0.2,
    )
    print("\n=== 模型原始返回（截断 1500 字）===")
    print(str(resp)[:1500])

    items = _decode_force(resp)
    print("\n=== 解析出 %d 条 ===" % len(items))
    for it in items:
        code = str(it.get("dimension_code") or "")
        band = it.get("band")
        quote = it.get("quote") or ""
        chunk_id = str(it.get("chunk_id") or "")
        reasons = []
        if code not in missing:
            reasons.append("维度不在 missing")
        if band not in BANDS:
            reasons.append("band 非法=%r" % (band,))
        if not isinstance(quote, str) or not quote:
            reasons.append("quote 为空")
        if not chunk_id:
            reasons.append("chunk_id 为空")
        if not reasons:
            if not quote_is_substring(quote, all_parents[:4]):
                reasons.append("quote 非父块连续子串")
        print("  %-16s band=%-8s len=%-4d chunk=%-8s -> %s" % (
            code, band, len(quote), chunk_id[:8],
            "通过" if not reasons else "拒绝：" + "；".join(reasons)))
        if quote:
            print("      quote 前 80 字: %s" % quote[:80])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())