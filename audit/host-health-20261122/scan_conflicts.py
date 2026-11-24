"""只读全量体检（第二项）：每个站走生产链路，看当期是否 命中/冲突/无候选，以及是否与缓存值不一致。"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import candidate_conflict_issue_reasons, find_matches_from_candidates

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
cached = {s["name"]: s for s in cache["sites"]}
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))


def check(site):
    row = {"name": site.name, "cached": cached.get(site.name, {}).get("fingerprint", {}).get(str(BASE), "")}
    try:
        docs, errors = collect_documents(
            site.url, 30, site.allow_insecure, page_attempts=6, cache_bust_first=True,
            issue_filter={BASE}, site_name=site.name, pick=site.pick, api_url=site.api_url,
        )
        cands = collect_candidates(docs, site, {BASE})
        hits = find_matches_from_candidates(cands, {BASE}, site)
        conflicts = candidate_conflict_issue_reasons(cands, {BASE})
        row.update({
            "ok": True, "docs": len(docs), "errs": len(errors), "cand": len(cands),
            "hit": hits[0].value if hits else "", "conflict": next(iter(conflicts.values())) if conflicts else "",
            "all": sorted({(c.issue, c.value) for c in cands}),
        })
    except Exception as exc:
        row.update({"ok": False, "cand": 0, "hit": "", "conflict": "", "all": [],
                    "err": f"{type(exc).__name__}: {exc}"[:120]})
    return row


with ThreadPoolExecutor(max_workers=8) as pool:
    rows = list(pool.map(check, sites))

(HERE / "scan_conflicts.json").write_text(
    json.dumps({"base_period": BASE, "sites": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

bad_fetch = [r for r in rows if not r["ok"]]
conf = [r for r in rows if r["conflict"]]
nohit = [r for r in rows if r["ok"] and not r["hit"] and not r["conflict"]]
mismatch = [r for r in rows if r["ok"] and r["hit"] and r["cached"] and r["hit"] != r["cached"]
            and str(BASE) in cached.get(r["name"], {}).get("fingerprint", {})]
print(f"扫描 {len(rows)} 站 | 抓取失败 {len(bad_fetch)} | 同期冲突 {len(conf)} | 无命中 {len(nohit)} | 与缓存值不一致 {len(mismatch)}")
print("\n## 同期冲突（同站同期多个不同段值）")
for r in conf:
    print(f"  {r['name']:<10} 缓存={r['cached'] or '—':<4} 候选={r['all']} <- {r['conflict']}")
print("\n## 无命中")
for r in nohit:
    print(f"  {r['name']:<10} 缓存={r['cached'] or '—':<4} cand={r['cand']}")
print("\n## 当前抓到值 != 缓存值")
for r in mismatch:
    print(f"  {r['name']:<10} 现在={r['hit']} 缓存={r['cached']} 候选={r['all']}")
