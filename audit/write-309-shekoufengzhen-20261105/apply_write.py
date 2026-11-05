"""309 期 蛇口蜂针 手动值(4段) 同步：缓存 309=4段 + 成功 TXT 排行重建。

用户于 2026-11-05 明确：该行由用户自己添加到 309期-段.txt（第 175 行 `4段 蛇口蜂针`），
并确认同步进缓存与排行。站方正文期号未更新（最新行标注 308期【4段】开:00），
故缓存 status 记 audit 并保留来源说明，不做跨期补值。
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

from duan_app.persistence.outputs import build_ranking_lines, safe_write_text  # noqa: E402
from period_repetition_checker import validate_cache_integrity  # noqa: E402

PERIOD = 309
SITE = "蛇口蜂针"
VALUE = "4段"
NOTE = "用户手动指定309期4段：站方正文期号未更新（最新行标注308期未开奖）"

CACHE = PROJECT / "recent_10_cache.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
SITES_JSON = PROJECT / "sites.json"
WINDOW = 10
MAX_SEARCH = 30

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"


def main() -> int:
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    record = next((s for s in payload["sites"] if s["name"] == SITE), None)
    if record is None:
        raise SystemExit(f"缓存中没有站点 {SITE}")

    record["fingerprint"][str(PERIOD)] = VALUE
    ordered = sorted(record["fingerprint"].items(), key=lambda kv: int(kv[0]), reverse=True)
    record["fingerprint"] = dict(ordered[:WINDOW])
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
    summary["full_10_count"] = sum(1 for s in sites if len(s.get("fingerprint") or {}) >= WINDOW)

    text = SUCCESS_TXT.read_text(encoding="utf-8-sig")
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
    if (VALUE, SITE) not in rows:
        raise SystemExit(f"数据区缺少 {VALUE} {SITE}")

    counts: dict[str, int] = {}
    for value, _ in rows:
        counts[value] = counts.get(value, 0) + 1
    if sum(counts.values()) != len(rows):
        raise SystemExit("排行合计与数据行不一致，终止")

    new_text = "\n".join(head + build_ranking_lines(counts)) + "\n"

    safe_write_text(CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    safe_write_text(SUCCESS_TXT, new_text)

    reloaded = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    check = validate_cache_integrity(
        reloaded,
        reloaded["sites"],
        CACHE,
        SITES_JSON,
        WINDOW,
        MAX_SEARCH,
    )
    print(json.dumps({
        "site": SITE,
        "value": VALUE,
        "period": PERIOD,
        "data_rows": len(rows),
        "unique": len(set(names)),
        "counts": counts,
        "total": sum(counts.values()),
        "summary": summary,
        "cache_valid": check,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
