"""323 期 面红耳赤 取证探针（只读，不写任何正式文件）。

该站连续多期同一模式：同一脚本里塞了两套冲突区块
  A) 无作者锚点的成绩表：每天续写一行当期，末行是当期真实值（未开奖，开0000）；
  B) 带「作者:面红耳赤」的模板块：把 319-328 甚至更远的未来期全部标成「已开奖」。

bottom 窗口取的是 B 的尾部 [326,327,328]，因此生产路径必然 MISS。

用法：python audit/verify-323-mianhongerchi-20261119/probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from duan_app.config import load_sites_config  # noqa: E402
from duan_app.documents import collect_documents  # noqa: E402
from duan_app.domain import Site  # noqa: E402
from duan_app.parsing.custom import collect_candidates  # noqa: E402
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles  # noqa: E402

PERIOD = 323
SITE = "面红耳赤"
EVIDENCE = Path(__file__).resolve().parent / "evidence"


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    sites = load_sites_config(PROJECT / "sites.json")
    profiles = load_site_profiles(PROJECT / "site_profiles.json", sites)
    if profiles is not None:
        sites = apply_site_profiles(sites, profiles)
    site = next(s for s in sites if s.name == SITE)
    print(f"site={site.name} url={site.url} pick={site.pick}")

    documents, errors = collect_documents(
        site.url,
        25,
        False,
        page_attempts=6,
        cache_bust_first=True,
        issue_filter={PERIOD},
        site_name=site.name,
        pick=site.pick,
        api_url=site.api_url,
    )
    print(f"documents={len(documents)} script_errors={errors}")

    production = collect_candidates(documents, site, anchor_issue_filter={PERIOD})
    print(f"\n[生产路径] 候选 {len(production)} 个（应全来自带作者锚点的区块 B）")
    for candidate in production:
        print(f"  {candidate.issue} {candidate.value} order={candidate.order} "
              f"pos={candidate.position} anchor={candidate.anchor} | {candidate.snippet}")

    anchorless = collect_candidates(documents, Site("", "", site.pick))
    print(f"\n[去锚点] 候选 {len(anchorless)} 个")
    for candidate in anchorless:
        if PERIOD - 12 <= candidate.issue <= PERIOD + 8:
            print(f"  {candidate.issue} {candidate.value} pos={candidate.position} | {candidate.snippet}")

    # 落证据：只存命中三个关键块的文档（documents 是纯字符串列表）
    saved: dict[str, int] = {}
    for doc_index, text in enumerate(documents):
        if f"{PERIOD}期" not in text:
            continue
        if "class=\"title\"" in text and "title_block" not in saved:
            name = "title_block.txt"
        elif "作者:面红耳赤" in text and "blockB_author_anchor" not in saved:
            name = "blockB_author_anchor.txt"
        elif "1段：" in text and "开0000" in text and "blockA_score_table_tail" not in saved:
            name = "blockA_score_table_tail.txt"
        else:
            continue
        (EVIDENCE / name).write_text(text, encoding="utf-8")
        saved[name] = doc_index
        print(f"[saved] {name} <- doc {doc_index} ({len(text)} chars)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
