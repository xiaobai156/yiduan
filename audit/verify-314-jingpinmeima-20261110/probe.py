# -*- coding: utf-8 -*-
"""314 期 精品赐码 单站取证：抓原文 + 打印底部区块尾部行。"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from duan_app.fetcher import fetch_page_text  # noqa: E402
from duan_app.text_utils import html_to_text  # noqa: E402

URL = "https://88888020827.897657.xyz/bbs/topic.php?id=19260"

OUT = Path(__file__).resolve().parent / "evidence"
OUT.mkdir(exist_ok=True)


def main() -> int:
    raw = fetch_page_text(URL, timeout=30, verify_ssl=False, attempts=3)
    print(f"raw_bytes={len(raw.encode('utf-8'))}")
    (OUT / "raw.html").write_text(raw, encoding="utf-8")

    text = html_to_text(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    (OUT / "text.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"lines={len(lines)}")
    print("--- head 6 ---")
    for line in lines[:6]:
        print(repr(line[:160]))
    print("--- tail 14 ---")
    for line in lines[-14:]:
        print(repr(line[:200]))
    hit = [l for l in lines if "314期" in l]
    print(f"--- 314期 命中 {len(hit)} ---")
    for line in hit[:5]:
        print(repr(line[:200]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
