"""326 期 蓝可爱鬼 只读取证探针：看抓取通道拿到什么、脚本为什么加载失败。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.parsing.custom import collect_candidates
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
ISSUE = 326
OUT = Path(__file__).resolve().parent / "evidence"
OUT.mkdir(exist_ok=True)

sites = load_sites_config(ROOT / "sites.json")
profiles = load_site_profiles(ROOT / "site_profiles.json", sites)
sites = apply_site_profiles(sites, profiles)
site = next(s for s in sites if s.name == "蓝可爱鬼")
print("url", site.url, "pick", site.pick, "sources", site.document_sources)

documents, errors = collect_documents(
    site.url, 30, False,
    page_attempts=6, cache_bust_first=True,
    issue_filter={ISSUE}, site_name=site.name, pick=site.pick, api_url=site.api_url,
)
print(f"documents={len(documents)}")
print(f"errors={errors}")

plain_all = []
for index, text in enumerate(documents):
    plain = html_to_text(text) if "<" in text else text
    head = plain.strip().replace("\n", " ⏎ ")[:160]
    print(f"  doc{index} len={len(text)} plain_len={len(plain)} head={head!r}")
    for line in plain.splitlines():
        line = line.strip()
        if line:
            plain_all.append(f"doc{index}\t{line}")
(OUT / "documents_lines.txt").write_text("\n".join(plain_all), encoding="utf-8")

cands = collect_candidates(documents, site)
print(f"candidates={len(cands)}")
for c in cands[:20]:
    print(f"  {c.issue}期 {c.value} anchor={c.anchor!r} pos={c.position}")

hits = [line for line in plain_all if f"{ISSUE}期" in line]
print(f"lines with {ISSUE}期: {len(hits)}")
for line in hits[:20]:
    print("  ", line[:200])
(OUT / "issue_hits.txt").write_text("\n".join(hits), encoding="utf-8")
