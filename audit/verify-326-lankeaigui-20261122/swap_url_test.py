"""用易记域名替换 URL，跑一遍完整抓取+候选，看是否等价可用。"""
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
    ("现配置", site.url),
    ("易记域名", "https://255560.com/topic/350479.html"),
):
    s = replace(site, url=url)
    docs, errors = collect_documents(
        url, 30, False, page_attempts=6, cache_bust_first=True,
        issue_filter={326}, site_name=s.name, pick=s.pick, api_url=s.api_url,
    )
    cands = collect_candidates(docs, s)
    plain_all = []
    for text in docs:
        plain_all.extend(text.splitlines())
    print(f"{label}: {url}")
    print(f"  docs={len(docs)} errors={errors} candidates={len(cands)} "
          f"含326数据行={sum(1 for l in plain_all if '326期' in l and '段' in l)}")
