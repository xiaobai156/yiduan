"""用生产匹配器对比两个入口在 325 期（有值）上的结果是否一致。"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import find_matches_from_candidates

ROOT = Path(__file__).resolve().parents[2]
sites = load_sites_config(ROOT / "sites.json")
profiles = load_site_profiles(ROOT / "site_profiles.json", sites)
sites = apply_site_profiles(sites, profiles)
site = next(s for s in sites if s.name == "蓝可爱鬼")

for label, url in (
    ("现配置", site.url),
    ("255560", "https://255560.com/topic/350479.html"),
    ("255560b", "https://255560b.com/topic/350479.html"),
):
    s = replace(site, url=url)
    try:
        docs, errors = collect_documents(
            url, 30, False, page_attempts=6, cache_bust_first=True,
            issue_filter={325}, site_name=s.name, pick=s.pick, api_url=s.api_url,
        )
        cands = collect_candidates(docs, s, {325})
        hits = find_matches_from_candidates(cands, {325}, s)
        got = [(m.issue, m.value) for m in hits]
        print(f"{label}: docs={len(docs)} err={errors} cand={len(cands)} -> {got}")
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__}: {exc}")
