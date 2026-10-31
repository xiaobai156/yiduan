# -*- coding: utf-8 -*-
"""封存 禾尽风起（304 期，无数据/发帖时序）。

只动本站在各文件中的记录：sites.json / site_profiles.json / slow_sites.json /
recent_10_cache.json / archived_sites.json / 304期-段-失败.txt。
成功 TXT 不改动。所有写入走临时文件 + os.replace 原子替换，并保留原 BOM 与换行风格。
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
RESULT_DIR = PROJECT.parent / "七类数据统一归纳"
FAIL_DIR = PROJECT.parent / "七类数据统一归纳失败"

NAME = "禾尽风起"
PERIOD = 304
URL = "https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a47ecaa57dc857ae1bf570e?url=txbb"
TZ = timezone(timedelta(hours=8))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_like(path: Path, data) -> bytes:
    """按原文件的 BOM 与换行风格序列化。"""
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


def snapshot(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, AUDIT / f"{path.name}.before")


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

    target = next((s for s in sites if s.get("name") == NAME), None)
    if target is None:
        raise SystemExit(f"站点不存在于 sites.json：{NAME}")
    profile = next((p for p in profiles["sites"] if p.get("name") == NAME), None)
    cache_record = next((c for c in cache["sites"] if c.get("name") == NAME), None)
    slow_entry = slow.get(URL)
    success_hash_before = hashlib.sha256(succ_txt.read_bytes()).hexdigest() if succ_txt.exists() else None

    for path in (sites_path, profiles_path, slow_path, arch_path, cache_path, fail_txt):
        snapshot(path)

    entry = {
        "archived_at": now,
        "reason": (
            "304期失败清单处置：站方发帖时序缺数据（标题已改为304期，正文期号只到300/301/302/303，"
            "304期正文行未发布）。2026-10-31 现场取证：API 209091 字节，title/html base64 解码后正文 143643 字节内 "
            "'304' 出现 0 次，尾部顺序 302期→303期→303期(站方重复行)→段位表页脚；页面为 Next.js SPA 空壳无正文。"
            "判定为无数据而非解析异常，用户点名封存并停止抓取"
        ),
        "last_failure": {
            "period": PERIOD,
            "direction": target.get("pick", "bottom"),
            "stage": "指定期数校验",
            "reason": "尾部最新3个有效候选期数为[302期、303期]，不含指定304期",
        },
        "site": target,
        "profile": profile,
        "cache": cache_record,
        "slow_site": slow_entry,
    }

    # 1) sites.json
    sites = [s for s in sites if s.get("name") != NAME]
    atomic_write(sites_path, dump_like(sites_path, sites))

    # 2) site_profiles.json
    profiles["sites"] = [p for p in profiles["sites"] if p.get("name") != NAME]
    atomic_write(profiles_path, dump_like(profiles_path, profiles))

    # 3) slow_sites.json
    slow.pop(URL, None)
    atomic_write(slow_path, dump_like(slow_path, slow))

    # 4) archived_sites.json
    arch["sites"].append(entry)
    atomic_write(arch_path, dump_like(arch_path, arch))

    # 5) recent_10_cache.json
    cache["sites"] = [c for c in cache["sites"] if c.get("name") != NAME]
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

    # 6) 失败 TXT：删掉该站记录；无剩余失败则删除文件本身
    removed_lines = 0
    if fail_txt.exists():
        lines = fail_txt.read_text(encoding="utf-8-sig").splitlines()
        kept = []
        for line in lines:
            if line.strip().startswith("失败 ") and NAME in line:
                removed_lines += 1
                continue
            kept.append(line)
        remaining = [l for l in kept if l.strip().startswith("失败 ")]
        if remaining:
            text = "\n".join(kept).rstrip("\n") + "\n"
            atomic_write(fail_txt, text.encode("utf-8"))
        else:
            fail_txt.unlink()

    print(f"archived_at={now}")
    print(f"sites={len(sites)} profiles={len(profiles['sites'])} archived={len(arch['sites'])} cache={len(records)}")
    print(f"cache_summary={json.dumps(cache['_meta']['summary'], ensure_ascii=False)}")
    print(f"failure_lines_removed={removed_lines} fail_txt_exists={fail_txt.exists()}")
    print(f"success_txt_hash_before={success_hash_before}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
