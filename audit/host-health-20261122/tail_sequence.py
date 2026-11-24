"""冲突站：按文档顺序打印最近几期的段值行，看 326 那两条谁接在 325 后面。"""
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
    print(f"\n===== {name} pick={s.pick} =====")
    for i, d in enumerate(docs):
        plain = html_to_text(d) if "<" in d else d
        lines = [l.strip() for l in plain.splitlines() if l.strip()]
        # 找段值行
        rows = [(j, l) for j, l in enumerate(lines)
                if re.search(rf"{BASE-2}\s*期|{BASE-1}\s*期|{BASE}\s*期", l) and ("段" in l)]
        if not rows:
            continue
        print(f" -- doc{i} --")
        for j, l in rows[-6:]:
            print(f"    {l[:95]}")
