"""329 期 面红耳赤 只读取证探针：生产候选 vs 去锚点全候选。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.domain import Site
from duan_app.selection import scoped_candidates
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
ISSUE = 330

sites = load_sites_config(ROOT / "sites.json")
profiles = load_site_profiles(ROOT / "site_profiles.json", sites)
sites = apply_site_profiles(sites, profiles)
site = next(s for s in sites if s.name == "面红耳赤")
print("url", site.url, "pick", site.pick)

documents, errors = collect_documents(
    site.url, 30, False,
    page_attempts=6, cache_bust_first=True,
    issue_filter={ISSUE}, site_name=site.name, pick=site.pick, api_url=site.api_url,
)
print(f"documents={len(documents)} errors={errors}")
out_dir = Path(__file__).resolve().parent / "evidence"
out_dir.mkdir(exist_ok=True)

plain_lines = []
for index, text in enumerate(documents):
    plain = html_to_text(text) if "<" in text else text
    for line in plain.splitlines():
        line = line.strip()
        if line and "期" in line:
            plain_lines.append(f"doc{index}\t{line}")
(out_dir / "all_docs_issue_lines.txt").write_text("\n".join(plain_lines), encoding="utf-8")

production = collect_candidates(documents, site)
print(f"production candidates={len(production)}")
for cand in production[:12]:
    print(f"  prod issue={cand.issue} value={cand.value} pos={cand.position} anchor={cand.anchor!r}")

anchorless = Site("", "", "bottom")
all_cands = collect_candidates(documents, anchorless)
print(f"anchorless candidates={len(all_cands)}")
window, reason = scoped_candidates(all_cands, {ISSUE}, "bottom")
print(f"bottom window issues={sorted({c.issue for c in window})} reason={reason}")
hits = [c for c in all_cands if c.issue == ISSUE]
print(f"issue {ISSUE} hits={len(hits)}")
(out_dir / "anchorless_issue_hits.txt").write_text(
    "\n".join(f"pos={c.position}\t{c.issue}期\t{c.value}\t{c.snippet}" for c in hits), encoding="utf-8")

nearby = [c for c in all_cands if c.issue in range(ISSUE - 8, ISSUE + 1)]
nearby.sort(key=lambda c: (c.position, c.order))
(out_dir / "anchorless_tail_table.txt").write_text(
    "\n".join(f"pos={c.position}\t{c.issue}期\t{c.value}\t{c.snippet}" for c in nearby), encoding="utf-8")
for c in nearby:
    print(f"  A pos={c.position} {c.issue}期 {c.value} {c.snippet[:60]}")
