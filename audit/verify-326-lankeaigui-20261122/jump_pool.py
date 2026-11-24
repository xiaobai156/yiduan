"""配置地址每次渲染跳到哪个域名：确认跳转域名是否固定（决定能不能写死真实地址）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

CONFIG = "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"
for i in range(3):
    page = render_page_text(CONFIG, 40, False)
    real = getattr(page, "source_url", "")
    rows = [l.strip() for l in html_to_text(page).splitlines() if "期:[杀一段]" in l]
    print(f"第{i+1}次 -> {real}  html={len(page)} 数据行={len(rows)}")
