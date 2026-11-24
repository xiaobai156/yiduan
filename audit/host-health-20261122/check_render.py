"""对指定站点走项目渲染通道，看落地主机是否与配置一致、正文有没有数据行。"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
sites = load_sites_config(ROOT / "sites.json")
names = sys.argv[1:]
for name in names:
    site = next((s for s in sites if s.name == name), None)
    if site is None:
        print(f"{name}: 不在 sites.json")
        continue
    start = time.time()
    try:
        page = render_page_text(site.url, 40, False)
        text = html_to_text(page)
        cfg_host = urlparse(site.url).hostname
        land = urlparse(page.source_url)
        rows = sum(1 for l in text.splitlines() if "期" in l and "段" in l)
        print(f"{name}: {time.time()-start:.1f}s 配置主机={cfg_host} 落地={land.hostname} "
              f"同主机={land.hostname == cfg_host} 数据行={rows} 长度={len(text)}")
        print(f"   落地URL={page.source_url}")
    except Exception as exc:
        print(f"{name}: {time.time()-start:.1f}s FAIL {type(exc).__name__}: {exc}")
