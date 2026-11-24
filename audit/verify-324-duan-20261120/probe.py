"""324 期失败清单取证探针（只读，不写任何正式文件）。

用法：
  python audit/verify-324-duan-20261120/probe.py                 # 全部 4 站
  python audit/verify-324-duan-20261120/probe.py 动地惊天 记得善良
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
from duan_app.text_utils import html_to_text  # noqa: E402

PERIOD = 324
DEFAULT_TARGETS = ["面红耳赤", "动地惊天", "记得善良", "娇生惯养"]
EVIDENCE = Path(__file__).resolve().parent / "evidence"


def load_sites():
    sites = load_sites_config(PROJECT / "sites.json")
    profiles = load_site_profiles(PROJECT / "site_profiles.json", sites)
    if profiles is not None:
        sites = apply_site_profiles(sites, profiles)
    return sites


def dump_candidates(title, candidates, low, high):
    print(f"\n[{title}] 候选 {len(candidates)} 个")
    for candidate in candidates:
        if low <= candidate.issue <= high:
            print(f"  {candidate.issue} {candidate.value} order={candidate.order} "
                  f"pos={candidate.position} anchor={candidate.anchor} | {candidate.snippet}")


def main(argv):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    targets = argv or DEFAULT_TARGETS
    sites = load_sites()

    for name in targets:
        site = next(s for s in sites if s.name == name)
        print("=" * 100)
        print(f"site={site.name} url={site.url} pick={site.pick}")
        try:
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
        except Exception as exc:
            print(f"  抓取异常：{type(exc).__name__}: {exc}")
            continue
        print(f"  documents={len(documents)} script_errors={errors}")

        production = collect_candidates(documents, site, anchor_issue_filter={PERIOD})
        dump_candidates("生产路径", production, PERIOD - 12, PERIOD + 8)

        anchorless = collect_candidates(documents, Site("", "", site.pick))
        dump_candidates("去锚点", anchorless, PERIOD - 12, PERIOD + 8)

        # 关键上下文：正文里所有带当期的行
        hits = []
        for doc_index, text in enumerate(documents):
            plain = html_to_text(text) if "<" in text else text
            lines = [line.strip() for line in plain.splitlines() if line.strip()]
            for line_pos, line in enumerate(lines):
                if f"{PERIOD}期" in line or f"{PERIOD} 期" in line:
                    hits.append((doc_index, line_pos, line))
        print(f"\n[正文含{PERIOD}期的行] {len(hits)} 行")
        for doc_index, line_pos, line in hits[:40]:
            print(f"  doc{doc_index}:L{line_pos} {line[:120]}")

        # 落证据：正文末 25 行 + 含当期行的文档
        if documents:
            tail = []
            for doc_index, text in enumerate(documents):
                plain = html_to_text(text) if "<" in text else text
                lines = [line.strip() for line in plain.splitlines() if line.strip()]
                for line_pos, line in enumerate(lines):
                    if f"{PERIOD}期" in line:
                        start = max(0, line_pos - 4)
                        tail.append(f"--- doc{doc_index} 附近 ---")
                        tail.extend(lines[start:line_pos + 2])
            out = EVIDENCE / f"{name}-{PERIOD}-tail.txt"
            out.write_text("\n".join(tail[:400]), encoding="utf-8")
            print(f"  [saved] {out.name} ({len(tail)} lines)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
