"""用一个有值的期（325）对比两个入口地址的候选结果是否等价。"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles

ROOT = Path(__file__).resolve().parents[2]
sites = load_sites_config(ROOT / "sites.json")
profiles = load_site_profiles(ROOT / "site_profiles.json", sites)
sites = apply_site_profiles(sites, profiles)
site = next(s for s in sites if s.name == "蓝可爱鬼")

for label, url in (
    ("现配置 zdwcig", site.url),
    ("易记 255560", "https://255560.com/topic/350479.html"),
):
    s = replace(site, url=url)
    docs, errors = collect_documents(
        url, 30, False, page_attempts=6, cache_bust_first=True,
        issue_filter={325}, site_name=s.name, pick=s.pick, api_url=s.api_url,
    )
    cands = collect_candidates(docs, s, {325})
    print(f"{label}: docs={len(docs)} errors={errors}")
    for c in cands:
        print(f"   {c.issue}期 {c.value} order={c.order} anchor={c.anchor!r}")
