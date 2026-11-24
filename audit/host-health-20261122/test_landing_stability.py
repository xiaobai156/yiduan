"""只读：对 7 站的落地地址各连开 5 次，测「是否原地不跳」+ 内容是否与配置地址一致。
只写本目录 evidence，不改任何配置。"""
from __future__ import annotations

import hashlib
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
TARGETS = ["夹谷笑过", "没有之后", "天朗气清", "巷议街谈", "六合联盟", "高温凯子", "悠闲自在"]
sites = {s.name: s for s in load_sites_config(ROOT / "sites.json")}


def digest(text: str) -> str:
    rows = [l.strip() for l in text.splitlines() if "段" in l and "期" in l]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()[:12]


def probe(name: str):
    s = sites[name]
    out = {"name": name, "cfg_url": s.url}
    # 1) 配置地址渲染一次，取最新落地 + 内容摘要
    try:
        p0 = render_page_text(s.url, 40, False)
        t0 = html_to_text(p0)
        out["cfg_land"] = p0.source_url
        out["cfg_sha"] = digest(t0)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:110]
        return out
    # 2) 拿这个落地地址连开 5 次
    land = p0.source_url
    runs = []
    for _ in range(5):
        try:
            p = render_page_text(land, 40, False)
            t = html_to_text(p)
            runs.append({
                "land": p.source_url,
                "stayed": p.source_url.rstrip("/") == land.rstrip("/"),
                "sha": digest(t),
            })
        except Exception as exc:
            runs.append({"land": "", "stayed": False, "sha": "", "err": type(exc).__name__})
    out["runs"] = runs
    out["stayed_all"] = all(r["stayed"] for r in runs)
    out["same_content"] = all(r["sha"] == out["cfg_sha"] for r in runs if r["sha"])
    return out


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(probe, TARGETS))

(HERE / "landing_stability.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"{'站点':<8} {'原地不跳':<8} {'内容一致':<8} 5 次落地")
for r in results:
    if "error" in r:
        print(f"{r['name']:<8} ERROR {r['error']}")
        continue
    lands = [x["land"].replace("https://", "").split("/")[0] if x["land"] else "ERR" for x in r["runs"]]
    print(f"{r['name']:<8} {'是' if r['stayed_all'] else '否':<8} {'是' if r['same_content'] else '否':<8} "
          f"{' | '.join(lands)}")
