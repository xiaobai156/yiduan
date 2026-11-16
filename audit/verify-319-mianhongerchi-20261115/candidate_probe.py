# -*- coding: utf-8 -*-
"""319 期 面红耳赤 候选取证：按来源/区块列出全部候选，判断 319 该取哪个区块。

背景：页面为 lz-string JS 空壳，正文由 upload/script/11/*.js 渲染；decode 后出现两个
互相冲突的期号区块：
  A) 314→319 递增（314 开鼠31 与历史一致），末行 319期【6段】开0000准（未开奖）
  B) 319→328 递增且全部已开奖（未来期不可能有开奖结果）
失败原因正是 bottom 窗口取了 B 区块尾部 [326,327,328]。
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


def main() -> int:
    sites = load_sites_config(PROJECT / "sites.json")
    site = next(s for s in sites if s.name == NAME)
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
    candidates = collect_candidates(documents, site, anchor_issue_filter={PERIOD})
    print(f"candidates={len(candidates)}")
    for candidate in candidates:
        print(
            json.dumps(
                {
                    "issue": getattr(candidate, "issue", None),
                    "value": getattr(candidate, "value", None),
                    "score": getattr(candidate, "score", None),
                    "order": getattr(candidate, "order", None),
                    "position": getattr(candidate, "position", None),
                    "doc_type": getattr(candidate, "document_type", None),
                    "source_url": getattr(candidate, "source_url", None),
                    "block_id": getattr(candidate, "block_id", None),
                    "anchor": getattr(candidate, "anchor", None),
                    "snippet": compact_line(str(getattr(candidate, "snippet", "")), 80),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
