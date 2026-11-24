"""按用户授权，把 7 个跳转站的 URL 改成已实测稳定的落地地址。
同步 sites.json / site_profiles.json / recent_10_cache.json（url + source_sites_hash）。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from duan_app.domain import Site
from duan_app.parsing.profiles import stable_site_id
from duan_app.persistence.outputs import safe_write_text

HERE = Path(__file__).resolve().parent
SWAPS = {
    "夹谷笑过": "https://srnurztl.19o0y-m8cdt-fxekxw.work:17488/topic/702079.html",
    "没有之后": "https://jmqmlqdu.rjx9m-5ewz5-mwaciw.work:17488/topic/350521.html",
    "天朗气清": "https://lirbervs.ziovj-yrlm2-byxpig.work:17466/topic/371410.html",
    "巷议街谈": "https://iotwbmqb.wasbo-ehfv0-qyqhdl.work:17466/topic/462301.html",
    "六合联盟": "https://iotwbmqb.wasbo-ehfv0-qyqhdl.work:17466/topic/500604.html",
    "高温凯子": "https://pltltcuu.gn117-jsg9x-qcxxsa.work:17455/topic/678627.html",
    "悠闲自在": "https://pdvlvrkg.jjd8j-niebw-pusitw.work:17466/topic/573876.html",
}

def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

sp, pp, cp = ROOT / "sites.json", ROOT / "site_profiles.json", ROOT / "recent_10_cache.json"
raw = load(sp)
sites = raw["sites"] if isinstance(raw, dict) else raw
prof = load(pp)
cache = load(cp)
site_by = {s["name"]: s for s in sites}
prof_by = {p["name"]: p for p in prof["sites"]}
cache_by = {c["name"]: c for c in cache["sites"]}

report = []
for name, new in SWAPS.items():
    s = site_by[name]
    p = prof_by[name]
    c = cache_by.get(name)
    old = s["url"]
    assert p["url"] == old, f"{name} profile url 不一致"
    old_id = p["site_id"]
    new_id = stable_site_id(Site(name, new, s["pick"]))
    assert old_id == new_id, f"{name} site_id 会变，拒绝改"
    s["url"] = new
    p["url"] = new
    if c is not None and c.get("url") == old:
        c["url"] = new
    report.append((name, old, new))

safe_write_text(sp, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
safe_write_text(pp, json.dumps(prof, ensure_ascii=False, indent=2) + "\n")
cache["_meta"]["source_sites_hash"] = hashlib.sha256(sp.resolve().read_bytes()).hexdigest()
safe_write_text(cp, json.dumps(cache, ensure_ascii=False, indent=2) + "\n")

for name, old, new in report:
    print(f"{name}: {old}\n    -> {new}")
print(f"\nsource_sites_hash -> {cache['_meta']['source_sites_hash'][:12]}…")
