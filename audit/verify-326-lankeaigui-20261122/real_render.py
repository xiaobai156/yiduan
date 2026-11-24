"""用项目自己的浏览器通道渲染，看真实落地地址与正文是否出现。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

EV = Path(__file__).resolve().parent / "evidence"

for label, url in (
    ("配置地址", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"),
    ("上次落地", "https://pltltcuu.gn117-jsg9x-qcxxsa.work:17455/topic/350479.html"),
):
    try:
        page = render_page_text(url, 40, False)
    except Exception as exc:  # noqa: BLE001
        print(f"{label} {url}\n  FAIL {type(exc).__name__}: {exc}")
        continue
    real = getattr(page, "source_url", url)
    plain = html_to_text(page)
    rows = [l.strip() for l in plain.splitlines() if "期:[杀一段]" in l]
    print(f"{label}\n  配置 {url}\n  实际 {real}\n  html={len(page)} 数据行={len(rows)}")
    if rows:
        print("  末三行:", rows[-3:])
        (EV / f"render_{label}.txt").write_text("\n".join(rows[-12:]), encoding="utf-8")
