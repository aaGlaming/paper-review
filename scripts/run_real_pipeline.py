# -*- coding: utf-8 -*-
"""真实论文全链路回归：10 篇逐篇走 parse -> confirm -> retrieve -> score -> report。

对每篇记录：五维档位、每维 quote 是否为论文原句、耗时、终止原因、
agent_step 轨迹条数、档位分布与「证据不足」占比。

用法：
    python scripts/run_real_pipeline.py                 # 全 10 篇
    python scripts/run_real_pipeline.py --only a016     # 只跑文件名含该串的
    python scripts/run_real_pipeline.py --report        # 额外打印汇总表
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = PROJECT_ROOT / "data" / "samples"
OUT_DIR = PROJECT_ROOT / "docs" / "plan" / "acceptance" / "calls"
BASE = "http://127.0.0.1:8077/api"
# 展示名不参与匹配
FIXTURES = {"bench-dragon.md", "planting.md", "smoke.md", "README.md"}


def http_json(url: str, payload: dict | None = None, timeout: int = 600) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw[:300]}


def contest_of(stem: str) -> str:
    """从文件名推断赛题：<contest_id>-<编号>。不写死题号列表。"""
    head, sep, _ = stem.rpartition("-")
    return head if sep else ""


def is_quote_in_paper(quote: str, text: str) -> bool | None:
    """引用是否能在论文原文中找到。空引用返回 None（无法判定）。"""
    if not quote:
        return None
    return quote in text


def run_one(paper: Path) -> dict:
    stem = paper.stem
    text = paper.read_text(encoding="utf-8")
    contest_id = contest_of(stem)
    rec: dict = {"sample_id": stem, "contest_id": contest_id,
                 "chars": len(text), "error": None}

    status, created = http_json(f"{BASE}/reviews",
                                {"paper_text": text, "contest_id": contest_id})
    # 创建成功是 201 Created，其余一律按失败处理
    if status != 201 or not created.get("review_id"):
        rec["error"] = f"create HTTP {status}: {str(created)[:200]}"
        return rec
    review_id = created["review_id"]
    rec["review_id"] = review_id
    rec["status_after_create"] = created.get("status")
    rec["sections"] = len(created.get("sections") or [])

    started = time.time()
    status, done = http_json(f"{BASE}/reviews/{review_id}/resume", {})
    rec["elapsed_sec"] = round(time.time() - started, 1)
    if status != 200:
        rec["error"] = f"resume HTTP {status}: {str(done)[:200]}"
        return rec

    rec["status"] = done.get("status")
    rec["source"] = done.get("source")
    rec["terminated_by"] = done.get("agent_terminated_by")
    dims = done.get("dimensions") or []
    rec["dimension_count"] = len(dims)
    rec["bands"] = {}
    rec["quote_checks"] = {}
    detail = []
    for d in dims:
        code = d.get("dimension_code") or ""
        band = d.get("band") or ""
        quote = d.get("quote") or ""
        rec["bands"][code] = band
        hit = is_quote_in_paper(quote, text)
        rec["quote_checks"][code] = "空" if hit is None else ("原句" if hit else "非原句")
        detail.append({"dimension_code": code, "band": band,
                       "chat_calls": d.get("chat_calls"),
                       "quote_len": len(quote),
                       "quote_is_substring": hit})
    rec["dimensions_detail"] = detail
    rec["insufficient"] = sum(1 for b in rec["bands"].values() if b == "证据不足")

    _, steps = http_json(f"{BASE}/reviews/{review_id}/agent-steps")
    # 接口返回的键以实际响应为准，容错两种命名
    items = steps.get("agent_steps") or steps.get("steps") or []
    if isinstance(items, dict):
        items = items.get("items") or []
    rec["agent_step_rows"] = len(items)
    rec["actions"] = sorted({i.get("action") for i in items if i.get("action")})
    # 提交有两条路径：模型主动调 submit_dimension，或收尾时由 force_submit 补交
    rec["submit_ok"] = sum(1 for i in items
                           if i.get("action") == "submit_dimension" and i.get("ok"))
    force_notes = [str(i.get("result_note") or "") for i in items
                   if i.get("action") == "force_submit"]
    rec["force_submit"] = force_notes
    rec["forced_count"] = sum(
        int(x.split("补交")[1].split("条")[0].strip())
        for x in force_notes if "补交" in x)
    rec["critique_rows"] = sum(1 for i in items if i.get("node") == "critique")
    rec["nodes"] = sorted({i.get("node") for i in items if i.get("node")})

    score = done.get("score") or {}
    rec["score_total"] = score.get("total")
    rec["score_excluded"] = score.get("excluded")
    return rec


def print_row(rec: dict) -> None:
    if rec.get("error"):
        print("  %-22s 失败：%s" % (rec["sample_id"], rec["error"][:90]))
        return
    bands = " ".join("%s=%s" % (k[:4], v) for k, v in rec["bands"].items())
    quotes = sum(1 for v in rec["quote_checks"].values() if v == "原句")
    nonorig = sum(1 for v in rec["quote_checks"].values() if v == "非原句")
    print("  %-22s %5.1fs src=%-10s 终止=%-18s 轨迹%3d 主动提交%d 补交%d 引用%d原句/%d非原句"
          % (rec["sample_id"], rec["elapsed_sec"], rec["source"] or "-",
             rec["terminated_by"] or "-", rec["agent_step_rows"], rec["submit_ok"],
             rec.get("forced_count", 0), quotes, nonorig))
    print("      %s" % bands)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    papers = sorted(p for p in SAMPLES.glob("*.md") if p.name not in FIXTURES)
    if args.only:
        key = args.only.lower()
        papers = [p for p in papers if key in p.stem.lower()]
    if not papers:
        print("没有可跑的论文")
        return 1

    print("真实论文全链路回归：%d 篇（真实 embed / rerank / chat）\n" % len(papers))
    results = []
    for i, paper in enumerate(papers, 1):
        print("[%d/%d] %s" % (i, len(papers), paper.stem))
        rec = run_one(paper)
        results.append(rec)
        print_row(rec)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "real-pipeline-10papers.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("\n明细已写入：%s" % out.relative_to(PROJECT_ROOT))

    ok = [r for r in results if not r.get("error")]
    print("\n===== 汇总 =====")
    print("成功 %d / %d" % (len(ok), len(results)))
    if ok:
        print("端到端耗时：合计 %.1f s，均值 %.1f s，最大 %.1f s"
              % (sum(r["elapsed_sec"] for r in ok),
                 sum(r["elapsed_sec"] for r in ok) / len(ok),
                 max(r["elapsed_sec"] for r in ok)))
        print("轨迹总行数：%d，submit 成功：%d，critique 轨迹：%d"
              % (sum(r["agent_step_rows"] for r in ok),
                 sum(r["submit_ok"] for r in ok),
                 sum(r["critique_rows"] for r in ok)))
        dist: dict[str, int] = {}
        for r in ok:
            for b in r["bands"].values():
                dist[b] = dist.get(b, 0) + 1
        print("档位分布：%s" % dist)
        print("证据不足占比：%d / %d 维"
              % (sum(r["insufficient"] for r in ok),
                 sum(r["dimension_count"] for r in ok)))
        seqs = {tuple(r["actions"]) for r in ok}
        print("不同动作序列数：%d（%d 篇）" % (len(seqs), len(ok)))
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())