"""冲突站：把两个 326 候选各自的上下文行打出来，看哪个是模板、哪个是真实表。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
by = {s.name: s for s in sites}

for name in sys.argv[1:]:
    s = by[name]
    docs, _ = collect_documents(s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
                                issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url)
    print(f"\n===== {name} =====")
    for i, d in enumerate(docs):
        plain = html_to_text(d) if "<" in d else d
        lines = [l.strip() for l in plain.splitlines() if l.strip()]
        idx = [j for j, l in enumerate(lines) if re.search(rf"{BASE}\s*期", l)]
        if not idx:
            continue
        print(f" doc{i} 共{len(lines)}行 326命中{len(idx)}处")
        for j in idx:
            lo, hi = max(0, j - 2), min(len(lines), j + 4)
            for k in range(lo, hi):
                mark = ">>" if k == j else "  "
                print(f"   {mark} {lines[k][:80]}")
            print("   ---")
