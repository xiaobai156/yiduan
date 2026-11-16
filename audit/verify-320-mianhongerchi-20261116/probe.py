"""320 期 面红耳赤 取证探针（只读，不写任何正式文件）。

复现结论：
  1) 生产路径 collect_candidates(documents, site, anchor_issue_filter={320})
     只拿到 10 个候选（319=5段 起 328=3段），全部来自带作者锚点的区块 B；
  2) 去掉站点锚点要求后共 367 个候选，成绩表区块 A 在尾部给出
     314=7段 … 319=6段(开虎05准，已被开奖证实)、320=3段(开0000未开奖)；
  3) 所以 bottom 窗口 [326,327,328] 是模板占位造成的 MISS，320 实际值 3段 在两块一致。

用法：python audit/verify-320-mianhongerchi-20261116/probe.py
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

PERIOD = 320
SITE = "面红耳赤"


def main() -> int:
    sites = load_sites_config(PROJECT / "sites.json")
    profiles = load_site_profiles(PROJECT / "site_profiles.json", sites)
    if profiles is not None:
        sites = apply_site_profiles(sites, profiles)
    site = next(s for s in sites if s.name == SITE)

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
    print(f"\n[生产路径] 候选 {len(production)} 个（只有带作者锚点的区块 B）")
    for candidate in production:
        print(f"  {candidate.issue} {candidate.value} order={candidate.order} "
              f"pos={candidate.position} anchor={candidate.anchor} | {candidate.snippet}")

    anchorless = collect_candidates(documents, Site("", "", site.pick))
    print(f"\n[去锚点] 候选 {len(anchorless)} 个")
    for candidate in anchorless:
        if 314 <= candidate.issue <= PERIOD:
            print(f"  {candidate.issue} {candidate.value} pos={candidate.position} | {candidate.snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
