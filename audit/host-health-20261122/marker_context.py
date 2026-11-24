"""把命中失效标记的原文行打出来，排除「404期」这类误报。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
sites = {s.name: s for s in load_sites_config(ROOT / "sites.json")}
MARKERS = ["已删除", "已下架", "不存在", "无权限", "已封禁", "内容已被", "无权访问"]

for name in sys.argv[1:]:
    s = sites[name]
    try:
        text = html_to_text(render_page_text(s.url, 40, False))
    except Exception as exc:
        print(f"{name}: FAIL {type(exc).__name__}")
        continue
    print(f"\n=== {name} len={len(text)} ===")
    found = False
    for line in text.splitlines():
        line = line.strip()
        if any(m in line for m in MARKERS):
            print(f"   {line[:110]}")
            found = True
    if not found:
        print("   无失效标记")
