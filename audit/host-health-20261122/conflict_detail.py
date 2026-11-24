"""冲突站逐候选打印位置/锚点/片段，判断哪条是真、哪条是模板。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
by = {s.name: s for s in sites}

for name in sys.argv[1:]:
    s = by[name]
    docs, errs = collect_documents(s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
                                   issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url)
    cands = collect_candidates(docs, s, {BASE})
    print(f"\n=== {name} pick={s.pick} parser={s.custom_parser} docs={len(docs)} cand={len(cands)} ===")
    for c in cands:
        print(f"  {c.issue}期 {c.value} order={c.order} pos={c.position} anchor={c.anchor!r}")
        print(f"      {c.snippet[:90]!r}")
