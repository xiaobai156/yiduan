"""把蓝可爱鬼的 URL 换成用户指定地址（sites.json / site_profiles.json / 缓存 url 字段 + source_sites_hash）。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from duan_app.parsing.profiles import stable_site_id
from duan_app.domain import Site
from duan_app.persistence.outputs import safe_write_text

NAME = "蓝可爱鬼"
OLD = "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html"
NEW = "https://bbrqhvww.4eylv-8gp30-jpndzw.work:17488/topic/350479.html"

def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

# 1) sites.json
sp = ROOT / "sites.json"
raw = load(sp)
sites = raw["sites"] if isinstance(raw, dict) else raw
hit = next(x for x in sites if x["name"] == NAME)
assert hit["url"] == OLD, hit["url"]
hit["url"] = NEW
safe_write_text(sp, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
print(f"sites.json: {OLD} -> {NEW}")

# 2) site_profiles.json
pp = ROOT / "site_profiles.json"
prof = load(pp)
pr = next(x for x in prof["sites"] if x["name"] == NAME)
assert pr["url"] == OLD
new_site = Site(NEW, hit["pick"], NAME)
pr["url"] = NEW
pr["site_id"] = stable_site_id(new_site)
safe_write_text(pp, json.dumps(prof, ensure_ascii=False, indent=2) + "\n")
print(f"site_profiles.json: url 更新, site_id={pr['site_id']}")

# 3) recent_10_cache.json
cp = ROOT / "recent_10_cache.json"
cache = load(cp)
rec = next(x for x in cache["sites"] if x["name"] == NAME)
if rec.get("url") == OLD:
    rec["url"] = NEW
meta = cache["_meta"]
new_hash = hashlib.sha256(sp.resolve().read_bytes()).hexdigest()
meta["source_sites_hash"] = new_hash
safe_write_text(cp, json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
print(f"cache: url 更新, source_sites_hash={new_hash[:12]}…")
