"""313 期失败三站：原始抓取诊断（只读，不写正式输出/缓存）。

用法：python probe.py <alias>
alias: lianmeng / tiantian / jueSha
输出包含：抓取通道、字节数、指定期附近的原始行、以及解析器看到的候选值。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀段_解耦版")
sys.path.insert(0, str(PROJECT))

from duan_app.config import load_sites_config  # noqa: E402
from duan_app.fetcher import fetch_page_text, fetch_text  # noqa: E402
from duan_app.text_utils import html_to_text  # noqa: E402

PERIOD = 313
OUT = Path(__file__).with_name("raw")
ALIASES = {
    "lianmeng": "六合联盟",
    "tiantian": "天天向上",
    "juesha": "绝杀一合",
}


def context_lines(lines: list[str], needle: str, before: int = 6, after: int = 25) -> None:
    hits = [i for i, line in enumerate(lines) if needle in line]
    print(f"  needle {needle!r}: {len(hits)} hit(s)")
    for index in hits[:6]:
        lo, hi = max(0, index - before), min(len(lines), index + after)
        print(f"  --- around line {index} ---")
        for i in range(lo, hi):
            print(f"   {i:4d}| {lines[i][:200]}")


def main() -> int:
    alias = sys.argv[1] if len(sys.argv) > 1 else "lianmeng"
    name = ALIASES[alias]
    sites = load_sites_config(PROJECT / "sites.json")
    site = next(s for s in sites if s.name == name)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"site={site.name} pick={site.pick} url={site.url} api={getattr(site, 'api_url', None)}")

    api = getattr(site, "api_url", None)
    if api:
        raw = fetch_text(api, 20, True)
        (OUT / f"{alias}_api.json").write_text(raw, encoding="utf-8")
        print(f"api bytes={len(raw)}")
        from duan_app.dynamic_articles import (
            decode_article_field,
            iter_article_record_nodes,
        )

        payload = json.loads(raw)
        for record, path in iter_article_record_nodes(payload):
            print("record", path)
            for field in ("authorNickname", "title", "html"):
                try:
                    value = decode_article_field(record, field)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {field}: <{exc}>")
                    continue
                text = html_to_text(value) if "<" in value else value
                (OUT / f"{alias}_{field}.txt").write_text(text, encoding="utf-8")
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                print(f"  {field}: {len(value)} chars -> {len(lines)} text lines")
                if field == "title":
                    print("    title text:", repr(lines[0][:160]) if lines else None)
                context_lines(lines, f"{PERIOD}期", before=2, after=8)
    else:
        html = fetch_page_text(site.url, 20, True, attempts=6, cache_bust_first=True)
        (OUT / f"{alias}_page.html").write_text(html, encoding="utf-8")
        print(f"page bytes={len(html)}")
        text = html_to_text(html)
        (OUT / f"{alias}_text.txt").write_text(text, encoding="utf-8")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        print(f"text lines={len(lines)}")
        for line in lines[:5]:
            print("  HEAD:", line[:160])
        context_lines(lines, f"{PERIOD}期", before=2, after=20)
        print("  --- all 1-7段-ish lines containing 段 ---")
        for line in lines:
            if re.search(r"[1-7１-７一二三四五六七]\s*段", line):
                print("   ", line[:160])
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
