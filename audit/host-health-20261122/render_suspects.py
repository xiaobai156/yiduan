"""把原始 TLS 探测失败的主机，用项目浏览器渲染通道复核一遍（这才是生产真实路径）。"""
from __future__ import annotations

import json
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
sites = {s.name: s for s in load_sites_config(ROOT / "sites.json")}
hosts = json.loads((HERE / "hosts.json").read_text(encoding="utf-8"))
suspects = [r for r in hosts if r["status"] != "200"]

targets = []
for r in suspects:
    for name in r["sites"]:
        if name in sites:
            targets.append((name, sites[name].url))


def check(item):
    name, url = item
    cfg = urlparse(url).hostname
    try:
        page = render_page_text(url, 40, False)
        text = html_to_text(page)
        land = urlparse(page.source_url)
        rows = sum(1 for l in text.splitlines() if "期" in l and "段" in l)
        return {
            "name": name, "cfg": cfg, "land": land.hostname,
            "same": land.hostname == cfg, "rows": rows,
            "has326": "326期" in text, "ok": True, "land_url": page.source_url,
        }
    except Exception as exc:
        return {"name": name, "cfg": cfg, "land": "", "same": False, "rows": 0,
                "has326": False, "ok": False, "err": f"{type(exc).__name__}: {exc}"[:110]}


with ThreadPoolExecutor(max_workers=6) as pool:
    out = list(pool.map(check, targets))

out.sort(key=lambda r: (r["ok"], r["same"], -r["rows"]))
(HERE / "render_suspects.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
ok = [r for r in out if r["ok"]]
print(f"复核 {len(out)} 站：渲染成功 {len(ok)}，失败 {len(out)-len(ok)}")
print("\n== 渲染失败 ==")
for r in out:
    if not r["ok"]:
        print(f"  {r['name']:<8} {r['cfg']} -> {r['err']}")
print("\n== 渲染成功但落地主机不同（跳转）==")
for r in ok:
    if not r["same"]:
        print(f"  {r['name']:<8} {r['cfg']} -> {r['land']} 行数={r['rows']} 含326={r['has326']}")
print("\n== 渲染成功且同主机，但行数异常少 ==")
for r in ok:
    if r["same"] and r["rows"] < 20:
        print(f"  {r['name']:<8} {r['land']} 行数={r['rows']} 含326={r['has326']}")
