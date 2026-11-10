# -*- coding: utf-8 -*-
"""封存 精品赐码（314 期，站方段值未公开）。

只动该站在各文件中的记录：sites.json / site_profiles.json / slow_sites.json /
recent_10_cache.json / archived_sites.json / 314期-段-失败.txt。
成功 TXT 不改动。所有写入走临时文件 + os.replace 原子替换，并保留原 BOM 与换行风格。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
RESULT_DIR = PROJECT.parent / "七类数据统一归纳"
FAIL_DIR = PROJECT.parent / "七类数据统一归纳失败"
sys.path.insert(0, str(PROJECT))

from duan_app.persistence.outputs import build_failure_stats_lines, safe_write_text  # noqa: E402

PERIOD = 314
TZ = timezone(timedelta(hours=8))

# 站点名 → 取证结论（写入 archived_sites.json 的 reason）
REASONS = {
    "精品赐码": (
        "314期失败清单处置：站方标题已改为『314期：【精品赐码★绝杀①段 ★重金铲庄】』，正文最后一行是 "
        "『314期: 绝杀①段【？？？？？段】 开:00准』，段值被 5 个问号遮蔽（需打赏金币可见）；"
        "其上 311→2段、312→5段、313→4段 均为明文。浏览器实开与项目抓取通道结果一致，"
        "判定为无数据（段值未公开），非解析异常；用户点名封存并停止抓取"
    ),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_like(path: Path, data) -> bytes:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = b"\r\n" in raw[:4096]
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if crlf:
        text = text.replace("\n", "\r\n")
    text += "\r\n" if crlf else "\n"
    return (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=path.suffix, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def parse_failure(line: str) -> dict:
    """从失败行抽取 期数/方向/阶段/原因。"""
    import re

    period = re.search(r"期数:\s*(\d+)", line)
    direction = re.search(r"方向:\s*(\w+)", line)
    stage = re.search(r"阶段:\s*([^\s]+)", line)
    reason = re.search(r"原因:\s*(.+)$", line)
    return {
        "period": int(period.group(1)) if period else PERIOD,
        "direction": direction.group(1) if direction else "bottom",
        "stage": stage.group(1) if stage else "指定期数校验",
        "reason": reason.group(1).strip() if reason else "",
    }


def main() -> int:
    now = datetime.now(TZ).replace(microsecond=0).isoformat()
    sites_path = PROJECT / "sites.json"
    profiles_path = PROJECT / "site_profiles.json"
    slow_path = PROJECT / "slow_sites.json"
    arch_path = PROJECT / "archived_sites.json"
    cache_path = PROJECT / "recent_10_cache.json"
    fail_txt = FAIL_DIR / f"{PERIOD}期-段-失败.txt"
    succ_txt = RESULT_DIR / f"{PERIOD}期-段.txt"

    sites = read_json(sites_path)
    profiles = read_json(profiles_path)
    slow = read_json(slow_path)
    arch = read_json(arch_path)
    cache = read_json(cache_path)

    fail_lines_all = [l for l in fail_txt.read_text(encoding="utf-8-sig").splitlines() if l.strip().startswith("失败 ")]
    duplicated = [e["site"]["name"] for e in arch["sites"] if e.get("site", {}).get("name") in REASONS]
    if duplicated:
        raise SystemExit(f"这些站点已在 archived_sites.json 中：{duplicated}")
    success_hash_before = hashlib.sha256(succ_txt.read_bytes()).hexdigest()

    snapshots = {}
    for path in (sites_path, profiles_path, slow_path, arch_path, cache_path, fail_txt):
        snapshots[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    # 失败 TXT 不在 git 里，留一份改前副本，便于回滚
    (AUDIT / f"{fail_txt.name}.before").write_bytes(fail_txt.read_bytes())

    entries = []
    for name, reason in REASONS.items():
        target = next((s for s in sites if s.get("name") == name), None)
        if target is None:
            raise SystemExit(f"站点不存在于 sites.json：{name}")
        profile = next((p for p in profiles["sites"] if p.get("name") == name), None)
        record = next((c for c in cache["sites"] if c.get("name") == name), None)
        raw_fail = next((l for l in fail_lines_all if f"失败 {name} " in l), "")
        entries.append(
            {
                "archived_at": now,
                "reason": reason,
                "last_failure": parse_failure(raw_fail),
                "raw_failure_line": raw_fail,
                "site": target,
                "profile": profile,
                "cache": record,
                "slow_site": slow.get(target.get("url", "")),
            }
        )

    removed_urls = [e["site"].get("url", "") for e in entries]
    names = list(REASONS)

    # 1) sites.json
    sites = [s for s in sites if s.get("name") not in REASONS]
    atomic_write(sites_path, dump_like(sites_path, sites))

    # 2) site_profiles.json
    profiles["sites"] = [p for p in profiles["sites"] if p.get("name") not in REASONS]
    atomic_write(profiles_path, dump_like(profiles_path, profiles))

    # 3) slow_sites.json
    for url in removed_urls:
        slow.pop(url, None)
    atomic_write(slow_path, dump_like(slow_path, slow))

    # 4) archived_sites.json
    arch["sites"].extend(entries)
    atomic_write(arch_path, dump_like(arch_path, arch))

    # 5) recent_10_cache.json
    cache["sites"] = [c for c in cache["sites"] if c.get("name") not in REASONS]
    records = cache["sites"]

    def seq_len(rec):
        return sum(1 for value in (rec.get("fingerprint") or {}).values() if str(value).strip())

    cache["_meta"]["source_sites_hash"] = hashlib.sha256(sites_path.read_bytes()).hexdigest()
    cache["_meta"]["summary"] = {
        "site_count": len(records),
        "ok_count": sum(1 for r in records if r.get("status") == "ok"),
        "audit_count": sum(1 for r in records if r.get("status") == "audit"),
        "error_count": sum(1 for r in records if r.get("status") == "error"),
        "no_candidates_count": sum(1 for r in records if r.get("status") == "no_candidates"),
        "full_10_count": sum(1 for r in records if seq_len(r) == 10),
    }
    cache["updated_at"] = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    atomic_write(cache_path, dump_like(cache_path, cache))

    # 6) 失败 TXT：删掉该站，保留其余失败并重建分类统计
    kept_fail = [l for l in fail_lines_all if not any(f"失败 {n} " in l for n in names)]
    remaining = [l.strip() for l in kept_fail if l.strip()]
    stats = build_failure_stats_lines(remaining)
    head = "\n".join(remaining) + "\n" if remaining else ""
    text = head + "\n".join(stats) + "\n"
    safe_write_text(fail_txt, text)

    success_hash_after = hashlib.sha256(succ_txt.read_bytes()).hexdigest()

    print(f"archived_at={now}")
    print(f"sites={len(sites)} profiles={len(profiles['sites'])} archived={len(arch['sites'])} cache={len(records)}")
    print(f"cache_summary={json.dumps(cache['_meta']['summary'], ensure_ascii=False)}")
    print(f"fail_lines_removed={len(fail_lines_all) - len(remaining)} remaining={len(remaining)}")
    print(f"success_txt_unchanged={success_hash_before == success_hash_after}")
    print("snapshot_sha256_before=" + json.dumps(snapshots, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
