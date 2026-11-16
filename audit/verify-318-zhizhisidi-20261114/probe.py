# -*- coding: utf-8 -*-
"""318 期 置之死地 失败核查：项目抓取通道取证 + bottom 窗口候选复现。

结论（2026-11-14）：站方页面「绝杀一段」区块最后一行仍是 317 期（两条 317：
杀4段 开:蛇26错 / 杀2段 开:？00对），全文没有 318 期的段值行 →
判为站方未发布 318（无数据），不是解析异常。页面中的 318 字样只出现在广告位
（零零七 精准大小）与另一博主区块，不属于本栏目区块，不得采信。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from duan_app.fetcher import fetch_page_text  # noqa: E402
from duan_app.text_utils import html_to_text  # noqa: E402

URL = "https://lf29cc.1231978.com/shaxiao/036.htm"
EVIDENCE = Path(__file__).resolve().parent / "evidence"


def main() -> int:
    raw = fetch_page_text(URL, 30, False, cache_bust_first=True)
    text = html_to_text(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "raw.html").write_text(raw, encoding="utf-8")
    (EVIDENCE / "text.txt").write_text(text, encoding="utf-8")

    data_lines = [l for l in lines if "绝杀一段" in l and "开" in l]
    print(f"raw={len(raw)}B text={len(text)}B data_lines={len(data_lines)}")
    for line in data_lines[-6:]:
        print("  ", line)
    tail = "\n".join(data_lines)
    print("含318期:", "318期" in tail)
    print("317期条数:", tail.count("317期"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
