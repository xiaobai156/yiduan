"""夹谷笑过：原配置地址 vs 新落地地址，候选差异对比（原来 2 个候选，现在 1 个）。"""
from __future__ import annotations

import json
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
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
s = next(x for x in sites if x.name == "夹谷笑过")

OLD = "https://qwpapph.el7s4-pbxnj-aemcbt.work:16677/topic/702079.html"
for label, url in (("旧配置", OLD), ("新落地", s.url)):
    t = replace(s, url=url)
    docs, errs = collect_documents(url, 30, t.allow_insecure, page_attempts=6, cache_bust_first=True,
                                   issue_filter={BASE}, site_name=t.name, pick=t.pick, api_url=t.api_url)
    cands = collect_candidates(docs, t, {BASE})
    rows = sum(1 for d in docs for l in html_to_text(d).splitlines() if "段" in l and "期" in l)
    print(f"{label}: docs={len(docs)} errs={errs} 段值行={rows} cand={[(c.issue,c.value,c.snippet[:34]) for c in cands]}")
