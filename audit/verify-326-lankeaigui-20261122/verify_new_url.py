"""验证用户给的新地址：能否渲染出真实帖页、正文是否与现配置一致。"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

NEW = "https://bbrqhvww.4eylv-8gp30-jpndzw.work:17488/topic/350479.html"
OLD = "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"
BASE_SHA = "bc02a948d5da"

for label, url in (("新地址", NEW), ("现配置", OLD)):
    try:
        page = render_page_text(url, 40, False)
        text = html_to_text(page)
        rows = [l.strip() for l in text.splitlines() if "期:[杀一段]" in l]
        digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()[:12]
        title = [l.strip() for l in text.splitlines() if "蓝可爱鬼" in l][:2]
        print(f"{label}: rows={len(rows)} sha={digest} 与基线一致={digest == BASE_SHA}")
        print(f"   落地={page.source_url}")
        print(f"   锚点={title}")
        print(f"   末行={rows[-1] if rows else ''}")
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__}: {exc}")
