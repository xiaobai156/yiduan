# -*- coding: utf-8 -*-
"""用户指定写入：305 期 南辕北辙 = 1段（站方正文未发布该期，来源为用户指定）。

复用项目正式写盘链路：capture -> 校验缓存 -> merge_success/merge_failures -> commit_updates。
不抓取、不改配置、不动其他站点。
"""
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from duan_app.config import default_result_dir, load_sites_config  # noqa: E402
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles  # noqa: E402
from duan_app.retry_failed import (  # noqa: E402
    merge_failures,
    merge_success,
    parse_failures,
    refresh_cache_record,
)
from duan_app.persistence.transaction import capture, commit_updates  # noqa: E402
from period_repetition_checker import validate_cache_integrity  # noqa: E402

NAME = "南辕北辙"
VALUE = "1段"
PERIOD = 305
NOTE = "用户指定写入305期1段：站方正文未发布该期，无来源证据"

sites_path = (ROOT / "sites.json").resolve()
cache_path = (ROOT / "recent_10_cache.json").resolve()
success_path = (default_result_dir(ROOT) / f"{PERIOD}期-段.txt").resolve()
fail_path = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败\305期-段-失败.txt").resolve()

sites = apply_site_profiles(
    load_sites_config(sites_path),
    load_site_profiles(ROOT / "site_profiles.json", load_sites_config(sites_path)),
)
target = [site for site in sites if site.name == NAME]
if len(target) != 1:
    raise SystemExit(f"站点身份不唯一或缺失：{NAME}")
site = target[0]
if site.pick != "top":
    raise SystemExit(f"方向与失败记录不一致：{site.pick}")

before = capture([fail_path, success_path, cache_path, sites_path])
fail_text = before[fail_path].decode("utf-8-sig")
records = parse_failures(fail_text)
if len(records) != 1 or records[0][1] != (NAME, site.url, site.pick) or records[0][2] != PERIOD:
    raise SystemExit("失败 TXT 白名单与本轮目标不一致，停止写入")

cache = json.loads(before[cache_path].decode("utf-8-sig"))
meta = cache.get("_meta") or {}
if meta.get("format") != "duan_recent_10_cache.v2":
    raise SystemExit("缓存版本不支持")
if int(cache.get("periods", 0)) != 10:
    raise SystemExit("缓存窗口不是 10 期")
if Path(str(meta.get("source_sites"))).resolve() != sites_path:
    raise SystemExit("缓存来源路径不一致")
validate_cache_integrity(cache, cache["sites"], cache_path, sites_path, 10, 30)

success_text = before[success_path].decode("utf-8-sig")
merged_success, accepted = merge_success(success_text, {NAME: VALUE})
if accepted.get(NAME) != VALUE:
    raise SystemExit("成功 TXT 已存在冲突值，停止写入")

updated = copy.deepcopy(cache)
matches = [
    item
    for item in updated["sites"]
    if (item.get("name"), item.get("url"), item.get("pick")) == (NAME, site.url, site.pick)
]
if len(matches) != 1:
    raise SystemExit("缓存站点身份缺失或重复，停止写入")
record = matches[0]
record["fingerprint"][str(PERIOD)] = VALUE
window_periods = sorted((int(p) for p in record["fingerprint"]), reverse=True)[:10]
record["fingerprint"] = {str(p): record["fingerprint"][str(p)] for p in window_periods}
record["script_error_count"] = 0
refresh_cache_record(record)
record["notes"] = list(dict.fromkeys(list(record.get("notes") or []) + [NOTE]))
record["status"] = "audit" if record["notes"] else "ok"

updated["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
summary = updated["_meta"]["summary"]
summary["site_count"] = len(updated["sites"])
for status in ("ok", "audit", "error", "no_candidates"):
    summary[f"{status}_count"] = sum(1 for item in updated["sites"] if item.get("status") == status)
summary["full_10_count"] = sum(1 for item in updated["sites"] if len(item.get("fingerprint", {})) == 10)

merged_fail = merge_failures(fail_text, records, {(NAME, site.url, site.pick): VALUE})

updates = {}
if merged_success != success_text:
    updates[success_path] = merged_success
updates[cache_path] = json.dumps(updated, ensure_ascii=False, indent=2) + "\n"
updates[fail_path] = merged_fail
commit_updates(before, updates)
print("写入完成")
print("成功 TXT 站点行：", sum(1 for line in merged_success.splitlines() if line.strip().endswith(NAME)))
print("缓存记录：", json.dumps({k: record[k] for k in ("name", "status", "notes", "fingerprint")}, ensure_ascii=False))
print("摘要：", json.dumps(summary, ensure_ascii=False))
