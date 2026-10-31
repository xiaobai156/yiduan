# -*- coding: utf-8 -*-
"""封存后回读校验：禾尽风起（304 期）。只读，不写任何文件。"""
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT.parent / "七类数据统一归纳"
FAIL_DIR = PROJECT.parent / "七类数据统一归纳失败"
NAME = "禾尽风起"
URL = "https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a47ecaa57dc857ae1bf570e?url=txbb"
PERIOD = 304
SUCCESS_HASH_EXPECTED = "6b69e23b603d1f1c4cc2a172cd30ec46df6c64de18b341cc215eae72b32fc1eb"

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), f"{label}{(' | ' + detail) if detail else ''}"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    sites_path = PROJECT / "sites.json"
    profiles_path = PROJECT / "site_profiles.json"
    slow_path = PROJECT / "slow_sites.json"
    arch_path = PROJECT / "archived_sites.json"
    cache_path = PROJECT / "recent_10_cache.json"

    sites = read_json(sites_path)
    profiles = read_json(profiles_path)
    slow = read_json(slow_path)
    arch = read_json(arch_path)
    cache = read_json(cache_path)

    check(len(sites) == 175, "sites.json 站点数=175", f"实际 {len(sites)}")
    check(all(s.get("name") != NAME for s in sites), "sites.json 已移除该站")
    check(all(s.get("name") and s.get("url") and s.get("pick") in ("top", "bottom") for s in sites),
          "sites.json 每条 name/url/pick 完整")
    check(len({s["url"] for s in sites}) == len(sites), "sites.json URL 无重复")
    check(len({s["name"] for s in sites}) == len(sites), "sites.json 站名无重复")

    check(len(profiles.get("sites", [])) == 175, "site_profiles.json 画像数=175", f"实际 {len(profiles.get('sites', []))}")
    check(all(p.get("name") != NAME for p in profiles["sites"]), "site_profiles.json 已移除该站")
    check(profiles.get("schema") == "duan_site_profiles.v1", "site_profiles.json schema 未变", str(profiles.get("schema")))

    check(URL not in slow, "slow_sites.json 已移除该站 URL")
    check(all(k.startswith("http") for k in slow), "slow_sites.json 键均为 URL")

    check(arch.get("schema") == "duan_archived_sites.v1", "archived_sites.json schema 未变", str(arch.get("schema")))
    check(len(arch["sites"]) == 28, "archived_sites.json 条目数=28", f"实际 {len(arch['sites'])}")
    entry = next((a for a in arch["sites"] if a.get("site", {}).get("name") == NAME), None)
    check(entry is not None, "封存条目已写入")
    if entry:
        check(entry.get("site", {}).get("url") == URL, "封存条目 URL 一致")
        check(entry.get("site", {}).get("pick") == "bottom", "封存条目方向=bottom")
        check(entry.get("last_failure", {}).get("period") == PERIOD, "封存条目失败期数=304")
        check(bool(entry.get("reason")), "封存条目含原因")
        check(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$", str(entry.get("archived_at"))) is not None,
              "archived_at 格式正确", str(entry.get("archived_at")))
        check(entry.get("profile", {}).get("site_id") == "e85f0c8df4964a13", "封存条目含画像快照")
        check(entry.get("cache", {}).get("status") == "error", "封存条目含当时缓存快照")
        check(isinstance(entry.get("slow_site"), dict), "封存条目含慢站快照")

    check(cache.get("base_period") == PERIOD, "缓存 base_period=304", str(cache.get("base_period")))
    check(cache.get("periods") == 10, "缓存窗口=10", str(cache.get("periods")))
    check(len(cache["sites"]) == 175, "缓存站点数=175", f"实际 {len(cache['sites'])}")
    check(all(c.get("name") != NAME for c in cache["sites"]), "缓存已移除该站")
    check(cache["_meta"]["source_sites_hash"] == hashlib.sha256(sites_path.read_bytes()).hexdigest(),
          "缓存 source_sites_hash 与 sites.json 实际哈希一致")
    check(cache["_meta"].get("format") == "duan_recent_10_cache.v2", "缓存格式版本 v2")
    check(Path(cache["_meta"]["source_sites"]).resolve() == sites_path.resolve(), "缓存 source_sites 指向本项目 sites.json")

    records = cache["sites"]
    expect = {
        "site_count": len(records),
        "ok_count": sum(1 for r in records if r.get("status") == "ok"),
        "audit_count": sum(1 for r in records if r.get("status") == "audit"),
        "error_count": sum(1 for r in records if r.get("status") == "error"),
        "no_candidates_count": sum(1 for r in records if r.get("status") == "no_candidates"),
        "full_10_count": sum(1 for r in records if len([v for v in (r.get("fingerprint") or {}).values() if str(v).strip()]) == 10),
    }
    check(cache["_meta"]["summary"] == expect, "缓存 summary 与站点数据自洽", json.dumps(expect, ensure_ascii=False))
    check(expect["error_count"] == 0, "缓存已无 error 站点", f"error={expect['error_count']}")
    check(sum(1 for r in records if str(PERIOD) in (r.get("fingerprint") or {})) == 175,
          "缓存 304 期值站点数=175")
    check(all(len(r.get("fingerprint") or {}) >= 1 for r in records), "缓存每站至少 1 期指纹")

    fail_txt = FAIL_DIR / f"{PERIOD}期-段-失败.txt"
    check(not fail_txt.exists(), "304 期失败 TXT 已删除（清单清空不留空壳）")

    succ = RESULT_DIR / f"{PERIOD}期-段.txt"
    check(succ.exists(), "304 期成功 TXT 仍在")
    if succ.exists():
        digest = hashlib.sha256(succ.read_bytes()).hexdigest()
        check(digest == SUCCESS_HASH_EXPECTED, "成功 TXT 哈希未变", digest)
        body = [l for l in succ.read_text(encoding="utf-8-sig").splitlines() if re.fullmatch(r"[1-7]段 .+", l)]
        check(len(body) == 175, "成功 TXT 数据行=175", f"实际 {len(body)}")
        check(all(NAME not in l for l in body), "成功 TXT 不含被封存站")

    baks = [p for p in PROJECT.rglob("*.bak") if ".git" not in p.parts]
    check(not baks, "未新增 .bak 文件", str(baks[:3]))
    tmps = [p for p in PROJECT.rglob(".tmp-*") if ".git" not in p.parts]
    check(not tmps, "未残留临时文件", str(tmps[:3]))

    passed = sum(1 for ok, _ in results if ok)
    for ok, label in results:
        print(("PASS  " if ok else "FAIL  ") + label)
    print(f"\n{passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
