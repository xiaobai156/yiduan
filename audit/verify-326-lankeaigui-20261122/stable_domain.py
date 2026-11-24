"""渲染页里找「永久/易记/备用域名/本站网址」等稳定入口提示。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

CONFIG = "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"
page = render_page_text(CONFIG, 40, False)
EV = Path(__file__).resolve().parent / "evidence"
(EV / "rendered_head.txt").write_text(html_to_text(page)[:1200], encoding="utf-8")

plain = html_to_text(page)
for kw in ("永久", "易记", "备用", "网址", "域名", "收藏"):
    for line in plain.splitlines():
        s = line.strip()
        if kw in s and 3 <= len(s) <= 120:
            print(f"[{kw}] {s}")
