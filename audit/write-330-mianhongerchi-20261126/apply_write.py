"""330 期 面红耳赤 写入（用户 2026-11-26 授权，沿用每期模板）：
成功 TXT 追加 `2段 面红耳赤` 并重建排行；缓存 330 补 2段、status 由 error 改 audit、
清掉模板区块 B 写入的 331-338 假值、按真区块 A 回填 321-330 十期真实值；
失败 TXT 清掉该站后无剩余失败 → 直接删除文件。

取证（audit/verify-330-mianhongerchi-20261126/）：
  区块 A（无作者锚点成绩表）尾部：
    321=7段 开虎41准 / 322=2段 开鼠07准 / 323=5段 开猴47准 / 324=1段 开鼠43准
    325=3段 开龙03准 / 326=4段 开猴23错 / 327=6段 开狗45准 / 328=2段 开牛06准
    329=7段 开猪44错 / 330期[绝杀一段][2段] 开0000准（未开奖）
  区块 B（带作者锚点模板）从 319=5段 排到 365期、001-153期，未来期全标已开奖。
  决定性证据：B 的 329 行昨天（2026-11-25）就已经写成「329期【7段】开牛17准」，
  而 A 昨天是「329期【7段】开0000准」、今天是「329期【7段】开猪44错」——
  B 的开奖结果从不随开奖变化（固定模板伪造），A 会随开奖更新（真实成绩表）。
  据此采信 A 的 330=2段。
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

PERIOD = 330
WINDOW = 10
MAX_SEARCH = 30

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
FAIL_TXT = ROOT / "七类数据统一归纳失败" / f"{PERIOD}期-段-失败.txt"

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"

NAME = "面红耳赤"
VALUE = "2段"
FP = {
    "321": "7段", "322": "2段", "323": "5段", "324": "1段", "325": "3段",
    "326": "4段", "327": "6段", "328": "2段", "329": "7段", "330": "2段",
}
NOTE = (
    "源页两区块：无作者锚点的真实成绩表A给330=2段(开0000未开奖)，"
    "其上321=7段/322=2段/323=5段/324=1段/325=3段/326=4段/327=6段/328=2段/329=7段"
    "与历次已确认写入值逐期吻合，且329的开奖结果已由「0000占位」更新为「开猪44错」(真实开奖)；"
    "带作者锚点的模板B给330=6段，但B的329行「开牛17准」从昨日至今从未变化(开奖结果固定伪造)，"
    "且331-338等未来期全标已开奖 → 模板占位。采用A的2段，已清掉模板B写入的331-338假值"
)


def main() -> int:
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
    if NAME in names:
        raise SystemExit(f"{NAME} 已在成功清单，终止")

    rows.append((VALUE, NAME))

    counts: dict[str, int] = {}
    for value, _ in rows:
        counts[value] = counts.get(value, 0) + 1
    new_text = newline.join(
        [f"{value} {name}" for value, name in rows] + build_ranking_lines(counts)
    ) + newline

    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    before: dict[str, object] = {}
    for record in payload["sites"]:
        if record["name"] == NAME:
            before = {
                "status": record.get("status"),
                "fingerprint": dict(record.get("fingerprint") or {}),
            }
            record["fingerprint"] = dict(FP)
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

    safe_write_text(SUCCESS_TXT, new_text)
    safe_write_text(CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    fail_removed = FAIL_TXT.exists()
    FAIL_TXT.unlink(missing_ok=True)

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
        "appended": f"{VALUE} {NAME}",
        "cache_before": before,
        "cache_after": {
            r["name"]: {"status": r.get("status"), "fp": r.get("fingerprint")}
            for r in reloaded["sites"] if r["name"] == NAME
        },
        "fail_txt_deleted": fail_removed,
        "fail_txt_exists_after": FAIL_TXT.exists(),
        "summary": reloaded["_meta"]["summary"],
        "cache_valid": check,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
