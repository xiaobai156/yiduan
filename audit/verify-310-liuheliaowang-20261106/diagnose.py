"""310 期 六合料王 解析失败诊断（只读，不写正式输出/缓存）。

失败原因：ArticleRecordError: 标题未通过期数和数据关键词校验。
本脚本复用正式抓取通道 collect_documents，把每个 document 落到隔离目录，
并打印标题校验与正文尾部数据行，用于区分「站方把关键词写成 ①」与「真的没有 310 数据」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀段_解耦版")
sys.path.insert(0, str(PROJECT))

from duan_app.config import load_sites_config  # noqa: E402
from duan_app.documents import collect_documents  # noqa: E402
from duan_app.parsing.engine import has_result_keyword  # noqa: E402
from duan_app.constants import ISSUE_RE  # noqa: E402

TARGET = "六合料王"
PERIOD = 310
OUT = Path(__file__).with_name("documents")


def main() -> int:
    sites = load_sites_config(PROJECT / "sites.json")
    site = next((s for s in sites if s.name == TARGET), None)
    if site is None:
        raise SystemExit(f"sites.json 没有 {TARGET}")
    print("site:", site.name, site.url, site.pick, "api_url=", getattr(site, "api_url", None))

    documents, script_errors = collect_documents(
        site.url,
        20,
        True,
        page_attempts=max(6, site.retry + 4),
        cache_bust_first=site.cache_bust,
        issue_filter={PERIOD},
        site_name=site.name,
        pick=site.pick,
        api_url=site.api_url,
    )
    print("documents:", len(documents), "script_errors:", script_errors)
    OUT.mkdir(parents=True, exist_ok=True)
    for index, document in enumerate(documents, start=1):
        (OUT / f"doc{index}.txt").write_text(document, encoding="utf-8")
        lines = document.splitlines()
        print(f"\n--- doc{index}: {len(document)} chars, {len(lines)} lines ---")
        for line in lines[:6]:
            print("  HEAD:", line[:160])
        for line in lines[-12:]:
            print("  TAIL:", line[:160])
        joined = "\n".join(lines)
        print("  has_result_keyword(all):", has_result_keyword(joined))
        print("  ISSUE_RE hits:", sorted({m.group(1) for m in ISSUE_RE.finditer(joined)}))
        for line in lines:
            if f"{PERIOD}期" in line:
                print("  310 line:", line[:200])
    print("\nOUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
