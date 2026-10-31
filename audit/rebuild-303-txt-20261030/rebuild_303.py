# -*- coding: utf-8 -*-
"""从 recent_10_cache.json 重建指定期成功 TXT（只读缓存，不联网、不写缓存）。

用法: py -3.10 rebuild_303.py 303
"""
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
CACHE = PROJECT / "recent_10_cache.json"
SITES = PROJECT / "sites.json"
OUT_DIR = PROJECT.parent / "七类数据统一归纳"


def duan_sort_value(value: str) -> int:
    match = re.search(r"(\d+)\s*段", value)
    return int(match.group(1)) if match else 999


def build_ranking_lines(counts: Counter) -> list[str]:
    if not counts:
        return ["", "内容\t次数\t排名"]
    lines = ["", "内容\t次数\t排名"]
    ordered = sorted(counts.items(), key=lambda item: (-item[1], duan_sort_value(item[0]), item[0]))
    rank = 0
    last = None
    for value, count in ordered:
        if count != last:
            rank += 1
            last = count
        lines.append(f"{value}\t{count}\t{rank}")
    return lines


def main() -> int:
    period = int(sys.argv[1]) if len(sys.argv) > 1 else 303
    key = str(period)
    payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
    sites = payload["sites"]
    declared_sites = len(json.loads(SITES.read_text(encoding="utf-8-sig")))

    rows: list[tuple[str, str]] = []
    missing: list[str] = []
    bad_value: list[str] = []
    for record in sites:
        name = str(record.get("name") or "")
        fp = record.get("fingerprint") or {}
        value = fp.get(key)
        if not value:
            missing.append(f"{name} [{record.get('status')}] {record.get('error') or ''}".strip())
            continue
        value = str(value).strip()
        if not re.fullmatch(r"[1-7]段", value):
            bad_value.append(f"{name} -> {value}")
            continue
        rows.append((value, name))

    names = [name for _, name in rows]
    dup_names = [n for n, c in Counter(names).items() if c > 1]

    lines = [f"{value} {name}" for value, name in rows]
    counts = Counter(value for value, _ in rows)
    output = lines + build_ranking_lines(counts)
    text = "\n".join(output) + ("\n" if output else "")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{period:03d}期-段.txt"
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", suffix=".txt", dir=str(OUT_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    print(f"cache_base_period={payload['base_period']} updated_at={payload['updated_at']}")
    print(f"sites_in_cache={len(sites)} sites_json={declared_sites}")
    print(f"period={period} rows={len(rows)} missing={len(missing)} bad_value={len(bad_value)} dup_names={len(dup_names)}")
    print(f"ranking={dict(sorted(counts.items(), key=lambda kv: duan_sort_value(kv[0])))}")
    print(f"written={target} total_lines={len(output)}")
    for item in missing[:20]:
        print("  MISSING:", item)
    for item in bad_value[:10]:
        print("  BADVALUE:", item)
    for item in dup_names[:10]:
        print("  DUPNAME:", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
