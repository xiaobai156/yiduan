"""夹谷笑过：窗口里只有 2 个候选却没命中 326，打印候选详情。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import scoped_candidates

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
s = next(x for x in sites if x.name == "夹谷笑过")

docs, errors = collect_documents(
    s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
    issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url,
)
print("url", s.url, "pick", s.pick, "parser", s.custom_parser)
print("docs", len(docs), "errors", errors)
cands = collect_candidates(docs, s, {BASE})
print("candidates", len(cands))
for c in cands[:10]:
    print(f"  {c.issue}期 {c.value} order={c.order} pos={c.position} anchor={c.anchor!r} snip={c.snippet[:60]!r}")
win, reason = scoped_candidates(cands, {BASE}, s.pick)
print("window", [(c.issue, c.value) for c in win], "reason", reason)
