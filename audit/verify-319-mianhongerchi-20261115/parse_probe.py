# -*- coding: utf-8 -*-
"""319 期 面红耳赤 失败核查：项目抓取通道取正文，核对 bottom 窗口候选期数。

页面为 lz-string JS 空壳（raw 2711B，正文由 upload/script/11/*.js 渲染），
直接 html_to_text 得到空文本，必须走项目 documents 通道。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from duan_app.config import load_sites_config  # noqa: E402
from duan_app.crawl_service import collect_candidates  # noqa: E402
from duan_app.documents import collect_documents  # noqa: E402
from duan_app.text_utils import compact_line  # noqa: E402

PERIOD = 319
NAME = "面红耳赤"
OUT = Path(__file__).resolve().parent / "evidence"


def main() -> int:
    sites = load_sites_config(PROJECT / "sites.json")
    site = next(s for s in sites if s.name == NAME)
    print(f"site={site.name} pick={site.pick} url={site.url}")
    documents, errors = collect_documents(
        site.url,
        25,
        False,
        page_attempts=6,
        cache_bust_first=True,
        issue_filter={PERIOD},
        site_name=site.name,
        pick=site.pick,
        api_url=getattr(site, "api_url", None),
    )
    print(f"documents={len(documents)} errors={errors}")
    OUT.mkdir(parents=True, exist_ok=True)
    for index, document in enumerate(documents, start=1):
        (OUT / f"doc_{index}.txt").write_text(document, encoding="utf-8")
        print(f"  doc{index}: {len(document)} chars head={compact_line(document, 120)!r}")

    candidates = collect_candidates(documents, site, anchor_issue_filter={PERIOD})
    print(f"candidates={len(candidates)}")
    for candidate in candidates:
        if getattr(candidate, "issue", None) == PERIOD:
            print("  MATCH:", json.dumps(candidate.__dict__, ensure_ascii=False, default=str)[:800])
    issues = sorted({getattr(c, "issue", None) for c in candidates if isinstance(getattr(c, "issue", None), int)})
    print("issues:", issues[:20], "..." if len(issues) > 20 else "", "max:", issues[-1] if issues else None)
    for candidate in candidates[-4:]:
        print(
            "  tail:",
            getattr(candidate, "issue", None),
            repr(getattr(candidate, "value", None)),
            compact_line(str(getattr(candidate, "snippet", "")), 100),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
