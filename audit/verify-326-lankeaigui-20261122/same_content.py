"""比对两个入口渲染出的正文尾部 303 行是否完全相同（真等价性判据）。"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

URLS = {
    "现配置": "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html",
    "255560": "https://255560.com/topic/350479.html",
}
tails = {}
for label, url in URLS.items():
    try:
        page = render_page_text(url, 40, False)
        text = html_to_text(page)
        rows = [l.strip() for l in text.splitlines() if "期:[杀一段]" in l]
        head = [l.strip() for l in text.splitlines() if "蓝可爱鬼" in l][:2]
        digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()[:12]
        tails[label] = rows
        print(f"{label}: rows={len(rows)} sha={digest} land={page.source_url}")
        print(f"   首行={rows[0] if rows else ''}")
        print(f"   末行={rows[-1] if rows else ''}")
        print(f"   标题锚={head}")
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__}: {exc}")
a, b = tails.get("现配置"), tails.get("255560")
if a and b:
    print(f"\n完全相同={a == b} 差异行数={sum(1 for x, y in zip(a, b) if x != y)} len={len(a)}/{len(b)}")
