"""322 期：面红耳赤 写入 2段（区块A），并修复两站缓存被今日跑批覆盖/清空的问题。

一、面红耳赤 322 = 2段（采用无锚点成绩表区块 A）
   浏览器实开 + 项目通道（audit/verify-322-mianhongerchi-shenshendaodao-20261118/）双证：
     A) 无作者锚点成绩表，末行 `322期【绝杀一段】【2段】开0000准`（未开奖），
        其上 319=6段、320=3段、321=7段 与前几轮已确认写入值一致；
     B) 带「作者:面红耳赤」模板块，`322期【绝杀一段】【1段】开羊47准`，且把 323-328
        未来期全部标成「已开奖」→ 站方模板占位，段值不可信（1段 对应 01-07，与标注的
        开奖号 47 自相矛盾）。
   方向 bottom 的窗口仍被 B 尾部 [326,327,328] 占住，故正式入口必 MISS。

二、神神道道 322 = 3段（正式入口 retry 已写入）
   浏览器实开：末行 `322期:绝杀一段【3段】开:00中`（未开奖），另一处
   `322期:绝杀一段【1段】开:47中` 位于 314→365 的模板长链里，属占位假值。

三、缓存修复（今日跑批导致）
   面红耳赤：今日跑批把模板 B 的 319-328 十期假值写回、status=error，
             覆盖了此前已确认的 321=7段；本脚本改为 {321:7段, 322:2段}。
   神神道道：今日跑批抓取失败，把原来 311-320 十期历史清空成 {}，
             retry 只补了 322=3段（notes 出现「仅抓到1期」）；
             本脚本恢复原有十期并滚动到最近十期。

本脚本不改解析器（用户 2026-11-15 明确暂缓根因修复）。
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

PERIOD = 322
WINDOW = 10
MAX_SEARCH = 30

CACHE = PROJECT / "recent_10_cache.json"
SITES_JSON = PROJECT / "sites.json"
SUCCESS_TXT = ROOT / "七类数据统一归纳" / f"{PERIOD}期-段.txt"
FAIL_TXT = ROOT / "七类数据统一归纳失败" / f"{PERIOD}期-段-失败.txt"

DATA_ROW = re.compile(r"^([1-7]段)\s+(\S.*?)\s*$")
RANK_HEADER = "内容\t次数\t排名"

# 面红耳赤：本次写入 2段；同时恢复被今日跑批覆盖的 321=7段（已确认）
SITE = "面红耳赤"
VALUE = "2段"
RESTORED_FP = {"321": "7段", "322": "2段"}
NOTE = (
    "源页两区块：无锚点成绩表A给322=2段(开0000未开奖)、带作者锚点模板B给322=1段"
    "(标开羊47，但1段区间01-07与47矛盾，且B把323-328未来期都标已开奖)；"
    "A的近三期319=6段/320=3段/321=7段与此前已确认值一致，故采用A的2段；"
    "bottom窗口被B尾部未来期[326,327,328]占住致正式入口MISS"
)

# 神神道道：retry 已写入 322=3段，这里补回被清空的十期历史
SHENSHEN = "神神道道"
SHENSHEN_RESTORED = {
    "311": "3段", "312": "1段", "313": "3段", "314": "2段", "315": "4段",
    "316": "1段", "317": "2段", "318": "3段", "319": "6段", "320": "1段",
}  # 全部取自 git HEAD（上一轮已提交的真实抓取值），不新增任何猜测期


def main() -> int:
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))

    # ---------- 面红耳赤：成功 TXT ----------
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
    by_name = {s["name"]: s for s in payload["sites"]}
    red = by_name[SITE]
    red_before = {"status": red.get("status"), "fingerprint": dict(red.get("fingerprint") or {})}
    red["fingerprint"] = dict(RESTORED_FP)
    red["status"] = "audit"
    red.pop("error", None)
    red["notes"] = [NOTE]

    ss = by_name[SHENSHEN]
    ss_before = {"status": ss.get("status"), "fingerprint": dict(ss.get("fingerprint") or {})}
    restored = dict(SHENSHEN_RESTORED)
    restored[str(PERIOD)] = (ss.get("fingerprint") or {}).get(str(PERIOD), "3段")
    ordered = sorted(restored.items(), key=lambda kv: int(kv[0]))[-WINDOW:]
    ss["fingerprint"] = {k: v for k, v in ordered}
    ss["status"] = "audit"
    ss.pop("error", None)
    ss["notes"] = [
        "抓取或解析异常（今日跑批首轮 SSL 握手失败，缓存历史被清空成空表），"
        "本轮经正式入口重抓得 322=3段；311-320 十期为上一轮已提交的真实抓取值原样补回，"
        "321 期本站当日未抓到，保留空缺不猜值"
    ]

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
        "mianhongerchi_before": red_before,
        "mianhongerchi_after": red["fingerprint"],
        "shenshendaodao_before": ss_before,
        "shenshendaodao_after": ss["fingerprint"],
        "summary": summary,
        "cache_valid": check,
        "fail_txt": FAIL_TXT.read_text(encoding="utf-8-sig"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
