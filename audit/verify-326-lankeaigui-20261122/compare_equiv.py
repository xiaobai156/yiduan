"""两个入口地址的完整等价性对比：文档数、数据行、候选、325 期命中。"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.text_utils import html_to_text

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
        issue_filter=None, site_name=s.name, pick=s.pick, api_url=s.api_url,
    )
    rows = 0
    for d in docs:
        plain = html_to_text(d) if "<" in d else d
        rows += sum(1 for l in plain.splitlines() if "期:[杀一段]" in l)
    cands = collect_candidates(docs, s)
    issues = sorted({c.issue for c in cands})
    print(f"{label}: docs={len(docs)} errors={errors} 数据行={rows} candidates={len(cands)} "
          f"issue范围={issues[:3]}..{issues[-3:] if issues else []}")
    tail = [c for c in cands if c.issue >= 323]
    for c in tail[:6]:
        print(f"    {c.issue}期 {c.value} anchor={c.anchor!r}")
