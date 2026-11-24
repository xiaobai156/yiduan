"""只读全量体检：对每个站点走生产渲染通道，记录配置主机 vs 落地主机、数据行数、是否含当前期。
只写 audit/host-health-20261122/ 下的证据文件，不碰任何正式输出与缓存。"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from duan_app.config import load_sites_config
from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
BASE = cache["base_period"]
prev = {s["name"]: s for s in cache["sites"]}
sites = load_sites_config(ROOT / "sites.json")


def topic_of(u: str) -> str:
    m = re.search(r"/topic/(\d+)\.json|/topic/(\d+)\.html", urlparse(u).path)
    return (m.group(1) or m.group(2)) if m else ""


def check(site):
    cfg_host = urlparse(site.url).hostname or ""
    row = {"name": site.name, "cfg": cfg_host, "url": site.url,
           "cfg_topic": topic_of(site.url), "pick": site.pick}
    try:
        page = render_page_text(site.url, 40, False)
        text = html_to_text(page)
        land = urlparse(page.source_url)
        row.update({
            "ok": True, "land": land.hostname or "", "land_url": page.source_url,
            "land_topic": topic_of(page.source_url),
            "same_host": (land.hostname or "") == cfg_host,
            "rows": sum(1 for l in text.splitlines() if "期" in l and "段" in l),
            "has_base": f"{BASE}期" in text,
            "len": len(text),
        })
    except Exception as exc:
        row.update({"ok": False, "err": f"{type(exc).__name__}: {exc}"[:120],
                    "land": "", "land_url": "", "land_topic": "",
                    "same_host": False, "rows": 0, "has_base": False, "len": 0})
    return row


with ThreadPoolExecutor(max_workers=8) as pool:
    rows = list(pool.map(check, sites))

rows.sort(key=lambda r: (r["ok"], r["same_host"], r["has_base"], -r["rows"]))
(HERE / "render_all.json").write_text(
    json.dumps({"base_period": BASE, "scanned_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "sites": rows},
               ensure_ascii=False, indent=2), encoding="utf-8")

fail = [r for r in rows if not r["ok"]]
jump = [r for r in rows if r["ok"] and not r["same_host"]]
topic_mismatch = [r for r in jump if r["cfg_topic"] and r["land_topic"] and r["cfg_topic"] != r["land_topic"]]
no_base = [r for r in rows if r["ok"] and not r["has_base"] and BASE in (BASE,)]

print(f"扫描 {len(rows)} 站 | 渲染失败 {len(fail)} | 发生跳转 {len(jump)} | 跳转后 topic 不一致 {len(topic_mismatch)} | 页面无{BASE}期 {len(no_base)}")
print("\n## 渲染失败（配置地址打不开）")
for r in fail:
    print(f"  {r['name']:<10} {r['cfg']:<42} {r['err']}")
print("\n## 跳转后 topic 不一致（危险：可能抓到别的帖）")
for r in topic_mismatch:
    print(f"  {r['name']:<10} {r['cfg_topic']} -> {r['land_topic']}  {r['land']}")
print("\n## 页面里完全没有当期 {BASE} 期".format())
for r in no_base:
    print(f"  {r['name']:<10} {r['land'] or r['cfg']:<42} 行数={r['rows']}")
