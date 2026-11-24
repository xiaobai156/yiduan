"""326 期两处修正（用户 2026-11-22 授权）：

1. 面红耳赤：成功 TXT 里被日常跑批按模板区块 B 写成了 5段，按真区块 A 改为 4段，
   重算排行；缓存 326 同步改 4段。
2. 蓝可爱鬼：缓存被今日跑批失败清空成 error/{}，从 git HEAD 恢复 314-323 十期真实值，
   status 改回 ok（326 期本身判定为无数据，不写入成功 TXT）。

取证：
  面红耳赤 doc45（无作者锚点成绩表）末行 `326期[绝杀一段][4段]开0000准`（未开奖），
    其上 324=1段 开鼠43准、325=3段 开龙03准，与已确认写入值逐期吻合。
  doc8（带作者锚点模板）给 326=5段 开猪19准，并把 327-365 全部标成已开奖 → 模板占位。
  蓝可爱鬼 326：标题 `326期[蓝可爱鬼][绝禁一段]已公开`，正文 303 行止于
    `325期:[杀一段]《4段》开:？00准`（期号未改、开奖位占位），无 326 数据行 → 无数据。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
PROJECT = ROOT / "杀段_解耦版"
sys.path.insert(0, str(PROJECT))

from duan_app.persistence.outputs import build_ranking_lines, safe_write_text  # noqa: E402
from period_repetition_checker import validate_cache_integrity  # noqa: E402

PERIOD = 326
WINDOW = 10
MAX_SEARCH = 30

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"

ANN = "面红耳赤"
ANN_OLD = "5段"
ANN_NEW = "4段"
ANN_FP = {
    "321": "7段", "322": "2段", "323": "5段",
    "324": "1段", "325": "3段", "326": "4段",
}
ANN_NOTE = (
    "源页两区块：无作者锚点成绩表A给326=4段(开0000未开奖，且324=1段/325=3段与已确认值逐期吻合)，"
    "带作者锚点模板B给326=5段并把327-365全标已开奖(模板占位)；采用A的4段。"
    "分析：日常跑批按B写入5段，本次按取证改回4段"
)

BLUE = "蓝可爱鬼"
BLUE_NOTE = (
    "缓存指纹从git HEAD恢复(今日跑批失败曾清空成error/{})；"
    "326期站方标题已改为326期但正文303行止于325期(开奖位？00占位)，无当期值"
)


def main() -> int:
    # ---------- 成功 TXT：面红耳赤 5段 -> 4段 ----------
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
    if names.count(ANN) != 1:
        raise SystemExit(f"数据区 {ANN} 出现 {names.count(ANN)} 次，终止")
    if (ANN_OLD, ANN) not in rows:
        raise SystemExit(f"未找到 {ANN_OLD} {ANN}，终止")

    index = rows.index((ANN_OLD, ANN))
    rows[index] = (ANN_NEW, ANN)

    counts: dict[str, int] = {}
    for value, _ in rows:
        counts[value] = counts.get(value, 0) + 1
    new_text = newline.join(
        [f"{value} {name}" for value, name in rows] + build_ranking_lines(counts)
    ) + newline

    # ---------- 缓存 ----------
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))

    head_raw = subprocess.run(
        ["git", "show", "HEAD:recent_10_cache.json"],
        cwd=PROJECT, capture_output=True, check=True,
    ).stdout.decode("utf-8-sig")
    head_blue = next(s for s in json.loads(head_raw)["sites"] if s["name"] == BLUE)

    before: dict[str, dict[str, object]] = {}
    for record in payload["sites"]:
        if record["name"] == ANN:
            before[ANN] = {
                "status": record.get("status"),
                "fingerprint": dict(record.get("fingerprint") or {}),
            }
            record["fingerprint"] = dict(ANN_FP)
            record["status"] = "audit"
            record.pop("error", None)
            record["notes"] = [ANN_NOTE]
        elif record["name"] == BLUE:
            before[BLUE] = {
                "status": record.get("status"),
                "fingerprint": dict(record.get("fingerprint") or {}),
                "notes": record.get("notes"),
            }
            record["fingerprint"] = dict(head_blue["fingerprint"])
            record["status"] = "ok"
            record.pop("error", None)
            record["notes"] = [BLUE_NOTE]

    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sites = payload["sites"]
    summary = payload["_meta"]["summary"]
    summary["site_count"] = len(sites)
    summary["ok_count"] = sum(1 for s in sites if s.get("status") == "ok")
    summary["audit_count"] = sum(1 for s in sites if s.get("status") == "audit")
    summary["error_count"] = sum(1 for s in sites if s.get("status") == "error")
    summary["no_candidates_count"] = sum(
        1 for s in sites if s.get("status") == "no_candidates"
    )
    summary["full_10_count"] = sum(
        1 for s in sites if len(s.get("fingerprint") or {}) >= WINDOW
    )

    safe_write_text(SUCCESS_TXT, new_text)
    safe_write_text(CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    reloaded = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    check = validate_cache_integrity(
        reloaded, reloaded["sites"], CACHE, SITES_JSON, WINDOW, MAX_SEARCH
    )

    final_rows = [
        (m.group(1), m.group(2))
        for m in (DATA_ROW.match(l) for l in new_text.splitlines())
        if m
    ]
    print(json.dumps({
        "period": PERIOD,
        "data_rows": len(final_rows),
        "unique_names": len({name for _, name in final_rows}),
        "rank_counts": counts,
        "rank_total": sum(counts.values()),
        "ann_line": f"{ANN_NEW} {ANN}",
        "cache_before": before,
        "cache_after": {
            r["name"]: {"status": r.get("status"), "fp": r.get("fingerprint")}
            for r in reloaded["sites"] if r["name"] in (ANN, BLUE)
        },
        "summary": reloaded["_meta"]["summary"],
        "cache_valid": check,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
