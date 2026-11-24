"""跳转类站点：核对落地页 topic 身份是否与配置一致（同帖才算可用）。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "render_suspects.json").read_text(encoding="utf-8"))
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from duan_app.config import load_sites_config

urls = {s.name: s.url for s in load_sites_config(ROOT / "sites.json")}

def topic_of(u: str) -> str:
    m = re.search(r"/topic/(\d+)\.html", urlparse(u).path)
    return m.group(1) if m else ""

print("站点\t配置topic\t落地topic\t一致")
for r in data:
    if not r["ok"] or r["same"]:
        continue
    cfg_t = topic_of(urls[r["name"]])
    land_t = topic_of(r["land_url"])
    print(f"{r['name']}\t{cfg_t}\t{land_t}\t{cfg_t == land_t}")
