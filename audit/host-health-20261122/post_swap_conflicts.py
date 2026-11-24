"""换地址后检查这 7 站是否还有同期冲突（原来 夹谷笑过 有 5段/7段 冲突）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import candidate_conflict_issue_reasons

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))
by = {s.name: s for s in sites}

for name in ["夹谷笑过", "没有之后", "天朗气清", "巷议街谈", "六合联盟", "高温凯子", "悠闲自在"]:
    s = by[name]
    docs, errs = collect_documents(s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
                                   issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url)
    cands = collect_candidates(docs, s, {BASE})
    conf = candidate_conflict_issue_reasons(cands, {BASE})
    print(f"{name:<8} cand={len(cands)} 冲突={bool(conf)} {[(c.issue,c.value) for c in cands]}")
