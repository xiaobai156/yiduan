"""换 URL 后走生产候选链路，确认抓取正常、失败原因是否仍是「无定位」。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import find_matches_from_candidates
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
sites = apply_site_profiles(
    load_sites_config(ROOT / "sites.json"),
    load_site_profiles(ROOT / "site_profiles.json", load_sites_config(ROOT / "sites.json")),
)
site = next(s for s in sites if s.name == "蓝可爱鬼")
docs, errors = collect_documents(
    site.url, 30, False, page_attempts=6, cache_bust_first=True,
    issue_filter={326}, site_name=site.name, pick=site.pick, api_url=site.api_url,
)
cands = collect_candidates(docs, site, {326})
hits = find_matches_from_candidates(cands, {326}, site)
rows = sum(1 for d in docs for l in html_to_text(d).splitlines() if "期:[杀一段]" in l)
print(f"url={site.url}")
print(f"docs={len(docs)} errors={errors} 数据行={rows} candidates={len(cands)} 命中={[(m.issue,m.value) for m in hits]}")
