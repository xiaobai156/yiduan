"""320 期 面红耳赤 写入 3段：成功 TXT + 当前期缓存 + 清失败清单。

2026-11-16 取证（audit/verify-320-mianhongerchi-20261116/）：
同一页面（https://pcfwjde.22zu6-81144-kdlkyf.xyz:16677/topic/436704.html）内两块：

  A) xia05 脚本里的成绩表（无作者锚点，doc_44）：314期7段 开鼠31准 … 318期4段 开蛇38准
     319期【6段】开虎05准、320期【3段】开0000准（未开奖），末尾带 1段:01-07 … 7段:43-49 图例。
     319=6段 现已被开奖结果「虎05」证实 —— 与 2026-11-15 用户确认写入的 6段 一致。

  B) topic-content 带「作者:面红耳赤」锚点（doc_8）：319期【5段】开鸡45准 … 328期【3段】开兔03准，
     含未来期且标「已开奖」→ 站方模板占位。

方向 bottom 的窗口取到 B 尾部 [326,327,328]，所以正式入口一直 MISS。但 320 的段值两块并不冲突：
A 给【3段】(开0000 未开奖)，B 也给【3段】(开虎28 假开奖) → 320 = 3段 无歧义。

本脚本只落盘已证实的当前期：写入 3段，清掉缓存里由模板区块 B 产生的 321-328 假值，
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

PERIOD = 320
SITE = "面红耳赤"
VALUE = "3段"
NOTE = (
    "源页两区块：无锚点成绩表A给320=3段(开0000未开奖)、带作者锚点模板B也给3段(标已开奖)，"
    "两区块段值一致故采用3段；bottom窗口被B尾部未来期[326,327,328]占住致正式入口MISS，"
    "已清掉模板B写入的321-328假值"
)

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
FAIL_TXT = ROOT / "七类数据统一归纳失败" / f"{PERIOD}期-段-失败.txt"
WINDOW = 10
MAX_SEARCH = 30

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"


def main() -> int:
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    record = next((s for s in payload["sites"] if s["name"] == SITE), None)
    if record is None:
        raise SystemExit(f"缓存中没有站点 {SITE}")
    before_fp = dict(record.get("fingerprint") or {})
    dropped = sorted(
        [p for p in before_fp if int(p) != PERIOD],
        key=int,
        reverse=True,
    )

    record["fingerprint"] = {str(PERIOD): VALUE}
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

    fail_text = FAIL_TXT.read_text(encoding="utf-8-sig")
    fail_newline = "\r\n" if "\r\n" in fail_text else "\n"
    kept: list[str] = []
    for line in fail_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("失败 ") and SITE in stripped:
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
        "fingerprint_before": before_fp,
        "fingerprint_after": {str(PERIOD): VALUE},
        "dropped_periods": dropped,
        "summary": summary,
        "cache_valid": check,
        "fail_tail": FAIL_TXT.read_text(encoding="utf-8-sig").splitlines()[-3:],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
