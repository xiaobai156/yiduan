"""325 期：面红耳赤 写入 3段（区块 A）。失败清单只剩该站，写入后整份失败 TXT 删除。

取证（浏览器 + 项目通道双证，证据在 ../verify-325-mianhongerchi-20261121/）
  面红耳赤 区块 A（无作者锚点真实成绩表）尾部：
      319=6段 开虎05准 / 320=3段 开猪20错 / 321=7段 开虎41准 / 322=2段 开鼠07准
      323=5段 开猴47准 / 324=1段 开鼠43准 / 325期【绝杀一段】【3段】开0000准（未开奖）
    A 的 319-324 与已确认写入值逐期吻合，324 的 1段 已被开奖号「鼠43」证实。
  面红耳赤 区块 B（带「作者:面红耳赤」模板）给 325=4段 开虎04准，但 B 把 326-365
    乃至 001-153 期全部标成「已开奖」→ 模板占位，不采信。
  bottom 窗口被 B 尾部 [326,327,328] 占住，生产路径必然 MISS（probe 复现：生产 10 候选
    全来自 B，去锚点 372 候选里 A 的 325 行 pos=450000020）。

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

PERIOD = 325
WINDOW = 10
MAX_SEARCH = 30

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
FAIL_TXT = ROOT / "七类数据统一归纳失败" / f"{PERIOD}期-段-失败.txt"

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"

SITE = "面红耳赤"
VALUE = "3段"
CONFIRMED_FP = {"321": "7段", "322": "2段", "323": "5段", "324": "1段", "325": "3段"}
NOTE = (
    "源页两区块：无锚点成绩表A给325=3段(开0000未开奖)，带作者锚点模板B给325=4段"
    "(且把326-365乃至001-153期全标已开奖，属模板占位)；A的319-324与已确认值逐期吻合、"
    "324=1段已被开奖号鼠43证实，故采用A的3段；"
    "bottom窗口被B尾部未来期[326,327,328]占住致正式入口MISS"
)


def main() -> int:
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
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
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

    # ---------- 失败 TXT（无剩余失败即删除文件） ----------
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
    new_fail_text = None
    if remaining:
        new_fail_text = (
            "".join(kept).rstrip("\r\n")
            + fail_newline.join(build_failure_stats_lines(remaining))
            + fail_newline
        )

    safe_write_text(SUCCESS_TXT, new_text)
    safe_write_text(CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if new_fail_text is None:
        FAIL_TXT.unlink(missing_ok=True)
    else:
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
        "fail_txt_exists": FAIL_TXT.exists(),
        "fail_remaining": remaining,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
