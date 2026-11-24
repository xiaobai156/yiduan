"""对 7 个发生跳转的站，走完整生产链路（collect_documents → collect_candidates → find_matches），
确认跳转是否影响取数。只读，不写任何正式文件。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.selection import find_matches_from_candidates, scoped_candidates

ROOT = Path(__file__).resolve().parents[2]
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
raw = load_sites_config(ROOT / "sites.json")
sites = apply_site_profiles(raw, load_site_profiles(ROOT / "site_profiles.json", raw))

TARGETS = ["夹谷笑过", "没有之后", "天朗气清", "巷议街谈", "六合联盟", "高温凯子", "悠闲自在"]
by_name = {s.name: s for s in sites}

for name in TARGETS:
    s = by_name[name]
    try:
        docs, errors = collect_documents(
            s.url, 30, s.allow_insecure, page_attempts=6, cache_bust_first=True,
            issue_filter={BASE}, site_name=s.name, pick=s.pick, api_url=s.api_url,
        )
        cands = collect_candidates(docs, s, {BASE})
        hits = find_matches_from_candidates(cands, {BASE}, s)
        win, reason = scoped_candidates(cands, {BASE}, s.pick)
        got = [(m.issue, m.value) for m in hits]
        print(f"{name:<8} docs={len(docs):<4} err={len(errors)} cand={len(cands):<4} "
              f"window={len(win):<3} 命中={got} {'' if got else 'reason=' + reason}")
    except Exception as exc:
        print(f"{name:<8} FAIL {type(exc).__name__}: {exc}"[:150])
