"""看落地域名有几个、是否都能直接拿到原帖（不跳转）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import fetch_page_text, render_page_text
from duan_app.text_utils import html_to_text

CONFIG = "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"
SEEN = "https://pltltcuu.gn117-jsg9x-qcxxsa.work:17455/topic/350479.html"
NEW = "https://pdvlvrkg.jjd8j-niebw-pusitw.work:17466/topic/350479.html"

for label, url in (("配置", CONFIG), ("上次落地", SEEN), ("本次落地", NEW)):
    rows = []
    try:
        page = render_page_text(url, 40, False)
        plain = html_to_text(page)
        rows = [l.strip() for l in plain.splitlines() if "期:[杀一段]" in l]
        print(f"{label}: render ok html={len(page)} 数据行={len(rows)} 实际={getattr(page,'source_url',url)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: render FAIL {type(exc).__name__}: {exc}")
    try:
        raw = fetch_page_text(url, 30, False, attempts=2, cache_bust_first=True)
        print(f"        curl len={len(raw)} topic-content={'topic-content' in raw}")
    except Exception as exc:  # noqa: BLE001
        print(f"        curl FAIL {type(exc).__name__}: {exc}")

# 渲染页里出现的自有域名
page = render_page_text(SEEN, 40, False)
hosts = sorted(set(re.findall(r"https?://([a-z0-9.\-]+\.(?:work|xyz|com|cc|net))", str(page))))
print("\n渲染页内出现域名(前20):", hosts[:20])
