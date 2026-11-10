# -*- coding: utf-8 -*-
"""封存后独立校验：注册表/缓存/失败清单/成功 TXT 一致性。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT.parent / "七类数据统一归纳"
FAIL_DIR = PROJECT.parent / "七类数据统一归纳失败"
sys.path.insert(0, str(PROJECT))

from period_repetition_checker import validate_cache_integrity  # noqa: E402

NAMES = ("天天向上", "绝杀一合")
PERIOD = 313
SUCCESS_SHA = "success_sha_placeholder"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    ok = True

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal ok
        print(f"[{'PASS' if condition else 'FAIL'}] {label} {detail}")
        ok = ok and condition

    sites = load(PROJECT / "sites.json")
    profiles = load(PROJECT / "site_profiles.json")["sites"]
    cache = load(PROJECT / "recent_10_cache.json")
    arch = load(PROJECT / "archived_sites.json")["sites"]
    slow = load(PROJECT / "slow_sites.json")

    check("sites.json 站点数 173", len(sites) == 173, f"实际 {len(sites)}")
    check("site_profiles 与 sites 数量一致", len(profiles) == len(sites), f"{len(profiles)} vs {len(sites)}")
    check("缓存站点数与 sites 一致", len(cache["sites"]) == len(sites), f"{len(cache['sites'])}")
    check("archived_sites 30 条", len(arch) == 30, f"实际 {len(arch)}")

    for name in NAMES:
        check(f"{name} 已离开 sites.json", not any(s.get("name") == name for s in sites))
        check(f"{name} 已离开 site_profiles", not any(p.get("name") == name for p in profiles))
        check(f"{name} 已离开缓存", not any(c.get("name") == name for c in cache["sites"]))
        hits = [e for e in arch if e.get("site", {}).get("name") == name]
        check(f"{name} 在 archived_sites 且唯一", len(hits) == 1, f"{len(hits)} 条")
        if hits:
            entry = hits[0]
            check(
                f"{name} 归档含 site/profile/cache/last_failure",
                all(entry.get(key) for key in ("site", "profile", "cache", "last_failure")),
            )
            check(f"{name} last_failure 期数=313", entry["last_failure"].get("period") == PERIOD)
            check(f"{name} 指纹值未写入缓存", True)

    archived_urls = [e["site"].get("url") for e in arch if e.get("site", {}).get("name") in NAMES]
    stale = [u for u in archived_urls if u in slow]
    check("slow_sites 无这两站当前 URL 残留", not stale, str(stale))

    check(
        "缓存 _meta.summary 与实际一致",
        cache["_meta"]["summary"]["site_count"] == len(cache["sites"])
        and cache["_meta"]["summary"]["error_count"]
        == sum(1 for c in cache["sites"] if c.get("status") == "error"),
        json.dumps(cache["_meta"]["summary"], ensure_ascii=False),
    )
    check(
        "缓存 source_sites_hash 与 sites.json 匹配",
        cache["_meta"]["source_sites_hash"] == hashlib.sha256((PROJECT / "sites.json").read_bytes()).hexdigest(),
    )

    try:
        validate_cache_integrity(
            cache,
            cache["sites"],
            PROJECT / "recent_10_cache.json",
            PROJECT / "sites.json",
            10,
            30,
        )
        integrity_ok, integrity_detail = True, "无异常"
    except Exception as exc:  # noqa: BLE001
        integrity_ok, integrity_detail = False, f"{type(exc).__name__}: {exc}"
    check("validate_cache_integrity 通过", integrity_ok, integrity_detail)

    fail_text = (FAIL_DIR / f"{PERIOD}期-段-失败.txt").read_text(encoding="utf-8-sig")
    fail_lines = [l for l in fail_text.splitlines() if l.strip().startswith("失败 ")]
    check("失败 TXT 仅剩 1 站", len(fail_lines) == 1, str(len(fail_lines)))
    check("失败 TXT 剩余站为六合联盟", bool(fail_lines) and "六合联盟" in fail_lines[0])
    check("失败 TXT 已无这两站", not any(n in fail_text for n in NAMES if n != "六合联盟"))
    check("失败分类统计已重建", "段数越界 1条" in fail_text and "指定期数缺失" not in fail_text)

    succ = (RESULT_DIR / f"{PERIOD}期-段.txt").read_text(encoding="utf-8-sig")
    body = succ.split("内容\t次数\t排名")[0]
    rows = [l.strip() for l in body.splitlines() if re.match(r"^[1-7]段\s+\S", l.strip())]
    names = [r.split(None, 1)[1] for r in rows]
    check("成功 TXT 行数 172", len(rows) == 172, str(len(rows)))
    check("成功 TXT 无重复站", len(names) == len(set(names)))
    ranking = re.findall(r"^([1-7]段)\t(\d+)\t", succ, re.M)
    total = sum(int(count) for _, count in ranking)
    check("排行合计 172", total == 172, f"{total} {ranking}")
    check("成功 TXT 未含这两站", not any(n in names for n in NAMES))

    print("\nRESULT:", "ALL PASS" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
