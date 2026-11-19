"""323 期：面红耳赤 写入 5段（区块 A），并清理缓存里模板 B 的十期假值。

取证（浏览器 + 项目通道双证，证据在本目录 ../verify-323-mianhongerchi-20261119/evidence/）
  区块 A（无作者锚点成绩表，blockA_score_table_tail.txt）末行：
      323期【绝杀一段】【5段】开0000准（未开奖）
    其上：319=6段(开虎05准)、320=3段(开猪20错)、321=7段(开虎41准)、322=2段(开鼠07准)
    —— 与前几轮已确认写入值逐期吻合，且 322 的 2段 已被开奖结果「鼠07」证实。
  区块 B（带「作者:面红耳赤」模板，blockB_author_anchor.txt）：
      323=7段 开鸡09准，并把 324~365 甚至更远的期数全部标成「已开奖」→ 模板占位。
  因此采用 A 的 5段；bottom 窗口被 B 尾部 [326,327,328] 占住，生产路径必 MISS。

缓存修复：今日跑批把 B 的 319-328 十期假值写回并置 status=error，覆盖了已确认的
321=7段/322=2段；本脚本改为 {321:7段, 322:2段, 323:5段}，只保留这三期已确认值。

不改解析器（用户 2026-11-15 明确暂缓根因修复）。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
PROJECT = ROOT / "杀段_解耦版"
sys.path.insert(0, str(PROJECT))

from duan_app.persistence.outputs import (  # noqa: E402
    build_failure_stats_lines,
    build_ranking_lines,
    safe_write_text,
)
from period_repetition_checker import validate_cache_integrity  # noqa: E402

PERIOD = 323
WINDOW = 10
MAX_SEARCH = 30

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
FAIL_TXT = ROOT / "七类数据统一归纳失败" / f"{PERIOD}期-段-失败.txt"

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"

SITE = "面红耳赤"
VALUE = "5段"
CONFIRMED_FP = {"321": "7段", "322": "2段", "323": "5段"}
NOTE = (
    "源页两区块：无锚点成绩表A给323=5段(开0000未开奖)，带作者锚点模板B给323=7段"
    "(且把324-365等未来期全标已开奖，属模板占位)；A的319=6段/320=3段/321=7段/322=2段"
    "与已确认值逐期吻合、322的2段已被开奖号鼠07证实，故采用A的5段；"
    "bottom窗口被B尾部未来期[326,327,328]占住致正式入口MISS"
)


def main() -> int:
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))

    # ---------- 成功 TXT ----------
    text = SUCCESS_TXT.read_text(encoding="utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    if RANK_HEADER not in lines:
        raise SystemExit("成功 TXT 缺少排行表头，终止")
    split_at = lines.index(RANK_HEADER)
    head = lines[:split_at]
    while head and not head[-1].strip():
        head.pop()

    rows: list[tuple[str, str]] = []
    for line in head:
        match = DATA_ROW.match(line)
        if not match:
            raise SystemExit(f"数据区出现无法解析的行：{line!r}")
        rows.append((match.group(1), match.group(2)))

    names = [name for _, name in rows]
    if len(names) != len(set(names)):
        raise SystemExit("数据区站点名重复，终止")
    if SITE in names:
        raise SystemExit(f"数据区已存在 {SITE}，终止以避免覆盖")
    rows.append((VALUE, SITE))

    counts: dict[str, int] = {}
    for value, _ in rows:
        counts[value] = counts.get(value, 0) + 1
    new_text = newline.join(head + [f"{VALUE} {SITE}"] + build_ranking_lines(counts)) + newline

    # ---------- 缓存 ----------
    record = next(s for s in payload["sites"] if s["name"] == SITE)
    before = {"status": record.get("status"), "fingerprint": dict(record.get("fingerprint") or {})}
    record["fingerprint"] = dict(CONFIRMED_FP)
    record["status"] = "audit"
    record.pop("error", None)
    record["notes"] = [NOTE]

    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sites = payload["sites"]
    summary = payload["_meta"]["summary"]
    summary["site_count"] = len(sites)
    summary["ok_count"] = sum(1 for s in sites if s.get("status") == "ok")
    summary["audit_count"] = sum(1 for s in sites if s.get("status") == "audit")
    summary["error_count"] = sum(1 for s in sites if s.get("status") == "error")
    summary["no_candidates_count"] = sum(1 for s in sites if s.get("status") == "no_candidates")
    summary["full_10_count"] = sum(
        1 for s in sites if len(s.get("fingerprint") or {}) >= WINDOW
    )

    # ---------- 失败 TXT ----------
    fail_text = FAIL_TXT.read_text(encoding="utf-8-sig")
    fail_newline = "\r\n" if "\r\n" in fail_text else "\n"
    kept: list[str] = []
    for line in fail_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("失败 ") and SITE in stripped:
            continue
        if stripped.startswith("curl:"):
            continue
        if stripped in {"失败分类统计", "无失败"} or re.fullmatch(r".+ \d+条", stripped):
            continue
        kept.append(line)
    remaining = [line.strip() for line in kept if line.strip().startswith("失败 ")]
    new_fail_text = (
        "".join(kept).rstrip("\r\n")
        + fail_newline.join(build_failure_stats_lines(remaining))
        + fail_newline
    )

    safe_write_text(SUCCESS_TXT, new_text)
    safe_write_text(CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    safe_write_text(FAIL_TXT, new_fail_text)

    reloaded = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    check = validate_cache_integrity(
        reloaded, reloaded["sites"], CACHE, SITES_JSON, WINDOW, MAX_SEARCH
    )
    print(json.dumps({
        "site": SITE,
        "value": VALUE,
        "period": PERIOD,
        "data_rows": len(rows),
        "unique_names": len(set(names)),
        "counts": counts,
        "total": sum(counts.values()),
        "cache_before": before,
        "cache_after": record["fingerprint"],
        "summary": summary,
        "cache_valid": check,
        "fail_txt": FAIL_TXT.read_text(encoding="utf-8-sig"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
