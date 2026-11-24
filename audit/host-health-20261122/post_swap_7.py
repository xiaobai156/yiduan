"""换地址后复跑这 7 站的生产链路，验证是否原地不跳、取值不变。"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import find_matches_from_candidates

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
cached = {s["name"]: s for s in cache["sites"]}
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
TARGETS = ["夹谷笑过", "没有之后", "天朗气清", "巷议街谈", "六合联盟", "高温凯子", "悠闲自在"]
by = {s.name: s for s in sites}


def check(name):
    s = by[name]
    cfg = urlparse(s.url).hostname
    docs, errs = collect_documents(s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
                                   issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url)
    landed = set()
    for d in docs:
        pass
    cands = collect_candidates(docs, s, {BASE})
    hits = find_matches_from_candidates(cands, {BASE}, s)
    got = hits[0].value if hits else ""
    old = cached[name]["fingerprint"].get(str(BASE), "")
    return {"name": name, "cfg": cfg, "docs": len(docs), "errs": len(errs),
            "value": got, "cached": old, "same": got == old,
            "cands": [(c.issue, c.value) for c in cands]}


with ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(check, TARGETS))

print(f"{'站点':<8} {'站数文档':<6} {'抓到':<5} {'缓存':<5} {'一致':<4} 候选")
for r in rows:
    print(f"{r['name']:<8} {r['docs']:<8} {r['value'] or '—':<6} {r['cached'] or '—':<6} "
          f"{'是' if r['same'] else '否':<5} {r['cands']}")
print()
ok = all(r["same"] and r["value"] for r in rows)
print("全部一致" if ok else "存在不一致")
