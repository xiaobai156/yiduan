# -*- coding: utf-8 -*-
import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import cast

from duan_app.domain import Candidate, Site, SiteResult
from duan_app.parsing.custom import collect_candidates
from duan_app.persistence.outputs import safe_write_text
from duan_app.selection import ordered_candidate_groups, values_for_cache_issue


@contextmanager
def _cache_file_lock(cache_path: Path, timeout: float = 60.0):
    lock_path = cache_path.with_name(cache_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"近10期缓存锁等待超时：{cache_path}") from exc
                    time.sleep(0.1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def build_recent_cache_record(
    index: int,
    site: Site,
    documents: list[str],
    script_errors: list[str],
    candidates: list[Candidate] | None = None,
    error: str | None = None,
    window: int = 10,
    max_search: int = 30,
) -> dict[str, object]:
    article_records = list(getattr(documents, "article_audit", []))
    base_record: dict[str, object] = {
        "index": index,
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "latest_period": None,
        "sequence": [],
        "period_count": 0,
        "is_consecutive": False,
        "status": "error" if error else "no_candidates",
        "notes": ["抓取或解析异常"] if error else ["无候选数据"],
        "error": error,
        "script_error_count": len(script_errors),
        "article_records": article_records,
    }
    if error:
        return base_record

    if candidates is None:
        candidates = collect_candidates(documents, site)
    groups = ordered_candidate_groups(candidates, site.pick)
    if not groups:
        return base_record

    latest_candidate = (
        min(groups, key=lambda item: (item.position, item.order))
        if site.pick == "top"
        else max(groups, key=lambda item: (item.position, item.order))
    )
    latest_period = latest_candidate.issue
    sequence: list[dict[str, object]] = []
    min_period = max(1, latest_period - max_search)
    values_by_issue: dict[int, set[str]] = {}
    for candidate in groups:
        if min_period <= candidate.issue <= latest_period:
            values_by_issue.setdefault(candidate.issue, set()).add(candidate.value)
    for issue, values in sorted(values_by_issue.items()):
        if len(values) > 1:
            values_text = "、".join(sorted(values))
            return {
                **base_record,
                "latest_period": latest_period,
                "status": "error",
                "notes": [f"同期高可信候选冲突[{values_text}]"],
                "error": f"{issue}期同期高可信候选冲突[{values_text}]",
            }

    period = latest_period
    while period >= min_period and len(sequence) < window:
        values = values_for_cache_issue(groups, period, site.pick)
        if len(values) > 1:
            values_text = "、".join(values)
            return {
                **base_record,
                "latest_period": latest_period,
                "status": "error",
                "notes": [f"同期高可信候选冲突[{values_text}]"],
                "error": f"同期高可信候选冲突[{values_text}]",
            }
        if values:
            sequence.append({"period": period, "values": values})
        period -= 1

    seq_for_check = [
        (int(cast(int | str, item["period"])), tuple(cast(list[str], item["values"])))
        for item in sequence
    ]
    notes: list[str] = []
    if len(sequence) < window:
        notes.append(f"仅抓到{len(sequence)}期")
    if sequence and not is_consecutive_period_values(seq_for_check):
        notes.append("期数不连续")
    if script_errors:
        notes.append(f"脚本/接口错误{len(script_errors)}个")

    return {
        "index": index,
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "latest_period": latest_period,
        "sequence": sequence,
        "period_count": len(sequence),
        "is_consecutive": is_consecutive_period_values(seq_for_check) if sequence else False,
        "status": "ok" if not notes else "audit",
        "notes": notes,
        "error": None,
        "script_error_count": len(script_errors),
        "article_records": article_records,
    }


def mark_cache_record_failed(record: dict[str, object], reason: str) -> dict[str, object]:
    updated = dict(record)
    notes = [str(note) for note in record.get("notes", []) if str(note)]
    note = f"本次实时判定失败：{reason}"
    if note not in notes:
        notes.append(note)
    updated["status"] = "error"
    updated["notes"] = notes
    updated["error"] = reason
    return updated


def is_consecutive_period_values(sequence: list[tuple[int, tuple[str, ...]]]) -> bool:
    if len(sequence) < 2:
        return True
    return all(
        sequence[index][0] == sequence[index - 1][0] - 1
        for index in range(1, len(sequence))
    )

def cache_record_key(record: dict[str, object]) -> tuple[str, str]:
    return str(record.get("name", "")), str(record.get("url", ""))

def cache_sequence_map(record: dict[str, object]) -> dict[int, list[str]]:
    fingerprint = record.get("fingerprint")
    if isinstance(fingerprint, dict):
        result: dict[int, list[str]] = {}
        for raw_period, raw_value in fingerprint.items():
            try:
                period = int(raw_period)
            except (TypeError, ValueError):
                continue
            if isinstance(raw_value, list):
                values = [str(value) for value in raw_value if str(value).strip()]
            else:
                value = str(raw_value).strip()
                values = [value] if value else []
            if values:
                result[period] = values
        return result

    sequence = record.get("sequence")
    if not isinstance(sequence, list):
        return {}
    result: dict[int, list[str]] = {}
    for item in sequence:
        if not isinstance(item, dict):
            continue
        try:
            period = int(item["period"])
        except (KeyError, TypeError, ValueError):
            continue
        values = item.get("values")
        if isinstance(values, list):
            result[period] = [str(value) for value in values]
    return result

def cache_site_id(index: int, url: str) -> str:
    patterns = (
        (r"/topic/(\d+)\.html", "topic"),
        (r"/article/(?:admin|manager|lottery)/([0-9a-fA-F]+)", "article"),
        (r"[?&]tid=(\d+)", "tid"),
        (r"[?&]id=(\d+)", "id"),
        (r"/(?:bbs|art_[^/]+)/(\d+)", "page"),
    )
    for pattern, kind in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return f"s{index:03d}_{kind}_{match.group(1)}"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"s{index:03d}_url_{digest}"

def cache_record_for_storage(record: dict[str, object]) -> dict[str, object]:
    index = int(cast(int | str, record.get("index") or 0))
    url = str(record.get("url") or "")
    fingerprint: dict[str, str] = {}
    for period, values in sorted(cache_sequence_map(record).items(), reverse=True):
        if len(values) != 1:
            raise ValueError(f"近10期缓存存在非单值结果：{record.get('name', '')} {period}期")
        fingerprint[str(period)] = values[0]

    stored: dict[str, object] = {
        "id": cache_site_id(index, url),
        "name": str(record.get("name") or ""),
        "url": url,
        "pick": str(record.get("pick") or "top"),
        "fingerprint": fingerprint,
        "status": str(record.get("status") or "error"),
    }
    notes = record.get("notes")
    if isinstance(notes, list) and notes:
        stored["notes"] = [str(note) for note in notes]
    error = record.get("error")
    if error:
        stored["error"] = str(error)
    script_error_count = int(cast(int | str, record.get("script_error_count") or 0))
    if script_error_count:
        stored["script_error_count"] = script_error_count
    article_records = record.get("article_records")
    if isinstance(article_records, list) and article_records:
        stored["article_records"] = article_records
    return stored

def build_cache_payload(
    records: list[dict[str, object]],
    sites_path: Path,
    *,
    base_period: int,
    window: int = 10,
    max_search: int = 30,
) -> tuple[dict[str, object], dict[str, object]]:
    resolved_sites_path = sites_path.resolve()
    try:
        source_sites_hash = hashlib.sha256(resolved_sites_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"站点配置读取失败，禁止写入近10期缓存：{exc}") from exc

    summary: dict[str, object] = {
        "site_count": len(records),
        "ok_count": sum(1 for record in records if record.get("status") == "ok"),
        "audit_count": sum(1 for record in records if record.get("status") == "audit"),
        "error_count": sum(1 for record in records if record.get("status") == "error"),
        "no_candidates_count": sum(1 for record in records if record.get("status") == "no_candidates"),
        "full_10_count": sum(1 for record in records if len(cache_sequence_map(record)) == window),
    }
    payload = {
        "base_period": base_period,
        "periods": window,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sites": [cache_record_for_storage(record) for record in records],
        "_meta": {
            "format": "duan_recent_10_cache.v2",
            "source_sites": str(resolved_sites_path),
            "source_sites_hash": source_sites_hash,
            "max_search": max_search,
            "summary": summary,
        },
    }
    return payload, summary

def cache_article_id(record: dict[str, object]) -> str | None:
    article_records = record.get("article_records")
    if not isinstance(article_records, list) or len(article_records) != 1:
        return None
    article_record = article_records[0]
    if not isinstance(article_record, dict):
        return None
    value = article_record.get("record_id")
    return str(value) if value else None

def compare_recent_cache_records(
    previous_payload: dict[str, object], current_records: list[dict[str, object]]
) -> list[dict[str, object]]:
    previous_sites = previous_payload.get("sites")
    if not isinstance(previous_sites, list):
        return []
    previous_by_key = {
        cache_record_key(record): record
        for record in previous_sites
        if isinstance(record, dict)
    }
    conflicts: list[dict[str, object]] = []
    for current in current_records:
        if not isinstance(current, dict):
            continue
        previous = previous_by_key.get(cache_record_key(current))
        if previous is None:
            continue
        old_article_id = cache_article_id(previous)
        new_article_id = cache_article_id(current)
        if old_article_id and new_article_id and old_article_id != new_article_id:
            conflicts.append(
                {
                    "name": current.get("name", ""),
                    "url": current.get("url", ""),
                    "period": None,
                    "old_values": [old_article_id],
                    "new_values": [new_article_id],
                    "reason": "历史缓存与实时文章ID冲突",
                }
            )
        old_sequence = cache_sequence_map(previous)
        new_sequence = cache_sequence_map(current)
        for period in sorted(set(old_sequence) & set(new_sequence), reverse=True):
            if old_sequence[period] == new_sequence[period]:
                continue
            conflicts.append(
                {
                    "name": current.get("name", ""),
                    "url": current.get("url", ""),
                    "period": period,
                    "old_values": old_sequence[period],
                    "new_values": new_sequence[period],
                    "reason": "历史缓存与实时结果冲突",
                }
            )
    return conflicts

def _write_recent_cache_file_unlocked(
    cache_path: Path,
    sites_path: Path,
    results: list[SiteResult | None],
    *,
    base_period: int | None = None,
    dry_run: bool = False,
    preserve_conflicting_records: bool = False,
) -> dict[str, object]:
    del preserve_conflicting_records
    expected_count = None
    if sites_path.exists():
        raw_sites = json.loads(sites_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw_sites, list):
            expected_count = len(raw_sites)
    if expected_count is not None and len(results) != expected_count:
        raise ValueError(f"近10期缓存未刷新：结果数量 {len(results)} 与站点数量 {expected_count} 不一致")
    missing_indexes = [index + 1 for index, result in enumerate(results) if result is None or result.cache_record is None]
    if missing_indexes:
        preview = "、".join(str(index) for index in missing_indexes[:10])
        raise ValueError(f"近10期缓存未刷新：缺少站点结果 {preview}")

    records = [
        result.cache_record
        for result in results
        if result is not None and result.cache_record is not None
    ]
    if cache_path.exists():
        try:
            json.loads(cache_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise ValueError(f"近10期缓存读取失败，禁止覆盖：{exc}") from exc
    if base_period is None:
        periods = [period for record in records for period in cache_sequence_map(record)]
        base_period = max(periods, default=0)
    payload, summary = build_cache_payload(records, sites_path, base_period=base_period)
    if not dry_run:
        safe_write_text(cache_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return summary


def write_recent_cache_file(
    cache_path: Path,
    sites_path: Path,
    results: list[SiteResult | None],
    *,
    base_period: int | None = None,
    dry_run: bool = False,
    preserve_conflicting_records: bool = False,
) -> dict[str, object]:
    with _cache_file_lock(cache_path):
        return _write_recent_cache_file_unlocked(
            cache_path,
            sites_path,
            results,
            base_period=base_period,
            dry_run=dry_run,
            preserve_conflicting_records=preserve_conflicting_records,
        )
