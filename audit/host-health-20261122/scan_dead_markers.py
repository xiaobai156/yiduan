"""只读：检查各站渲染文本里是否出现帖子已删除/下架/不存在/无权限等失效标记。"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MARKERS = ["已删除", "已下架", "不存在", "无权限", "已封禁", "帖子ID", "内容已被", "404", "抱歉", "无权访问"]
sites = load_sites_config(ROOT / "sites.json")


def check(site):
    try:
        text = html_to_text(render_page_text(site.url, 40, False))
        hits = [m for m in MARKERS if m in text]
        return {"name": site.name, "len": len(text), "marks": hits}
    except Exception as exc:
        return {"name": site.name, "len": 0, "marks": [], "err": f"{type(exc).__name__}"}


with ThreadPoolExecutor(max_workers=8) as pool:
    rows = list(pool.map(check, sites))

hit = [r for r in rows if r["marks"]]
(HERE / "dead_markers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"扫描 {len(rows)} 站，出现失效标记 {len(hit)} 站")
for r in hit:
    print(f"  {r['name']:<10} len={r['len']:<7} {r['marks']}")
