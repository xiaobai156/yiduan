"""319 期 面红耳赤 按真区块 A 写入 6段：成功 TXT + 缓存 + 失败清单。

用户 2026-11-15 确认：源页同一脚本内有两个区块——
  A) xia05 脚本 payload#37 尾部（无作者锚点）：314=7段 … 318=4段、319期【6段】开0000准（未开奖），
     与本机缓存历史（304=1段、305=3段、306=6段、307=2段、308=7段、309=5段、314=7段）逐期吻合 → 真实续写；
  B) topic-content 带「作者:面红耳赤」锚点：319=5段 … 328=3段 全部标「已开奖」，含未来期 → 站方模板占位。
解析器要求作者锚点，故 A 被丢弃、bottom 窗口取到 B 尾部 [326,327,328] 判失败。
本脚本只按已确认结论落盘：写入 6段、清掉失败轮从 B 写入的 320–328 假值，不改解析器。
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

PERIOD = 319
SITE = "面红耳赤"
VALUE = "6段"
NOTE = (
    "源页两区块冲突：采用无作者锚点的真实成绩表区块A（319未开奖），"
    "已清掉模板区块B写入的320-328假值"
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
    dropped = sorted(
        [p for p in (record.get("fingerprint") or {}) if int(p) > PERIOD],
        key=int,
        reverse=True,
    )

    # 成绩表区块 A 的 319 是真值，但只保留当前期，其余未来期一律清空。
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

    # 失败清单：照 duan_app/retry_failed.py:91 merge_failures 的同一逻辑重建。
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
        "unique": len(set(names)),
        "counts": counts,
        "total": sum(counts.values()),
        "dropped_fingerprint_periods": dropped,
        "summary": summary,
        "cache_valid": check,
        "fail_tail": FAIL_TXT.read_text(encoding="utf-8-sig").splitlines()[-3:],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
