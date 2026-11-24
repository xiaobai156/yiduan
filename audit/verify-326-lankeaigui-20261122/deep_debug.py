"""定位 0 候选的断点：search texts / 结果标记 / issue 分段。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing import custom
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.text_utils import normalize_text
from duan_app.parsing.custom import has_site_section_result_marker

ROOT = Path(__file__).resolve().parents[2]
sites = load_sites_config(ROOT / "sites.json")
profiles = load_site_profiles(ROOT / "site_profiles.json", sites)
sites = apply_site_profiles(sites, profiles)
site = next(s for s in sites if s.name == "蓝可爱鬼")

documents, _ = collect_documents(
    site.url, 30, False, page_attempts=6, cache_bust_first=True,
    issue_filter={326}, site_name=site.name, pick=site.pick, api_url=site.api_url,
)

doc = documents[13]
texts = list(custom.iter_search_texts(doc))
print("iter_search_texts:", len(texts), "total chars", sum(len(t) for t in texts))
for i, t in enumerate(texts[:5]):
    print(f"  text{i} len={len(t)} head={t[:80]!r}")

norm = normalize_text("\n".join(texts)).replace(" ", "")
print("has_result_marker:", has_site_section_result_marker(norm))
print("锚点in:", "蓝可爱鬼" in norm)
segs = list(custom.iter_issue_segments(normalize_text(normalize_text and texts[0]), {326})) if texts else []
print("segs in text0:", len(segs))
for issue, itext, seg in segs[:3]:
    print("   ", issue, repr(seg[:80]))

# 找含 325期 的 text 并看分段结果
for i, t in enumerate(texts):
    n = normalize_text(t)
    if "325期" in n:
        ss = list(custom.iter_issue_segments(n, {326}))
        print(f"text{i} 含325期, segments={len(ss)}")
        for issue, itext, seg in ss[-3:]:
            vals, strict = custom.site_specific_values_and_strictness(
                seg, site, has_document_anchor=True, allow_repeated_duan=False, allow_multi_duan=False
            )
            print("    ", issue, vals, strict, repr(seg[:70]))
        break
