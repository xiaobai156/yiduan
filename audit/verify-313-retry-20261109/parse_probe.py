"""313 期非 API 站点解析复现：collect_documents → collect_candidates，看指定期候选与越界原因。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀段_解耦版")
sys.path.insert(0, str(PROJECT))

from duan_app.config import load_sites_config  # noqa: E402
from duan_app.crawl_service import collect_candidates  # noqa: E402
from duan_app.documents import collect_documents  # noqa: E402
from duan_app.text_utils import compact_line  # noqa: E402

PERIOD = 313
OUT = Path(__file__).with_name("raw")


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "六合联盟"
    sites = load_sites_config(PROJECT / "sites.json")
    site = next(s for s in sites if s.name == name)
    print(f"site={site.name} pick={site.pick} url={site.url}")
    documents, errors = collect_documents(
        site.url,
        20,
        True,
        page_attempts=6,
        cache_bust_first=False,
        issue_filter={PERIOD},
        site_name=site.name,
        pick=site.pick,
        api_url=getattr(site, "api_url", None),
    )
    print(f"documents={len(documents)} errors={errors}")
    OUT.mkdir(parents=True, exist_ok=True)
    for index, document in enumerate(documents, start=1):
        (OUT / f"doc_{index}.txt").write_text(document, encoding="utf-8")
        print(f"  doc{index}: {len(document)} chars, head={compact_line(document, 100)!r}")

    candidates = collect_candidates(documents, site, anchor_issue_filter={PERIOD})
    print(f"candidates={len(candidates)}")
    for candidate in candidates:
        if getattr(candidate, "issue", None) == PERIOD:
            print("  MATCH:", json.dumps(candidate.__dict__, ensure_ascii=False, default=str)[:600])
    near = [c for c in candidates if abs(getattr(c, "issue", 0) - PERIOD) <= 3]
    print(f"near-period candidates={len(near)}")
    for candidate in near[:12]:
        print("  near:", getattr(candidate, "issue", None), repr(getattr(candidate, "value", None)),
              compact_line(str(getattr(candidate, "snippet", "")), 120))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
