# -*- coding: utf-8 -*-
"""Record real responses once, then replay them through old and modular crawlers."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = ROOT.parent / "杀段_修复版"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical_url(url: str) -> str:
    parts = urlsplit(str(url))
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "_"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def serialize_error(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, HTTPError):
        return {
            "type": "HTTPError",
            "url": exc.url,
            "code": exc.code,
            "message": exc.msg,
        }
    if isinstance(exc, URLError):
        return {"type": "URLError", "reason": str(exc.reason)}
    if isinstance(exc, TimeoutError):
        return {"type": "TimeoutError", "message": str(exc)}
    if isinstance(exc, OSError):
        return {"type": "OSError", "errno": exc.errno, "message": str(exc)}
    if exc.__class__.__name__ == "CurlFetchError":
        return {
            "type": "CurlFetchError",
            "exit_code": int(getattr(exc, "exit_code", 1)),
            "message": str(exc),
        }
    return {"type": "RuntimeError", "message": f"{type(exc).__name__}: {exc}"}


def raise_recorded_error(payload: dict[str, object], target: ModuleType) -> None:
    error_type = str(payload.get("type", "RuntimeError"))
    message = str(payload.get("message", "recorded failure"))
    if error_type == "HTTPError":
        raise HTTPError(
            str(payload.get("url", "")),
            int(payload.get("code", 500)),
            message,
            {},
            None,
        )
    if error_type == "URLError":
        raise URLError(str(payload.get("reason", message)))
    if error_type == "TimeoutError":
        raise TimeoutError(message)
    if error_type == "OSError":
        raise OSError(payload.get("errno"), message)
    if error_type == "CurlFetchError":
        raise target.CurlFetchError(int(payload.get("exit_code", 1)), message)
    raise RuntimeError(message)


class ResponseStore:
    def __init__(self, directory: Path, *, record: bool) -> None:
        self.directory = directory
        self.blob_directory = directory / "blobs"
        self.record = record
        self.events: dict[str, list[dict[str, object]]] = {}
        self.cursors: dict[str, int] = {}
        self._master_lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        if record:
            if directory.exists():
                shutil.rmtree(directory)
            self.blob_directory.mkdir(parents=True)
        else:
            payload = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            self.events = {
                str(key): list(value)
                for key, value in payload.get("events", {}).items()
                if isinstance(value, list)
            }

    def _lock_for(self, key: str) -> threading.Lock:
        with self._master_lock:
            return self._key_locks.setdefault(key, threading.Lock())

    @staticmethod
    def key(kind: str, url: str) -> str:
        return f"{kind}|{canonical_url(url)}"

    def record_call(self, kind: str, url: str, callback) -> str:
        key = self.key(kind, url)
        with self._lock_for(key):
            try:
                text = callback()
            except Exception as exc:
                event = {"status": "error", "error": serialize_error(exc)}
                self.events.setdefault(key, []).append(event)
                raise
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            blob_path = self.blob_directory / f"{digest}.txt.gz"
            if not blob_path.exists():
                with gzip.open(blob_path, "wt", encoding="utf-8", newline="") as output:
                    output.write(text)
            self.events.setdefault(key, []).append(
                {"status": "ok", "sha256": digest, "length": len(text)}
            )
            return text

    def replay_call(self, kind: str, url: str, target: ModuleType) -> str:
        key = self.key(kind, url)
        with self._lock_for(key):
            index = self.cursors.get(key, 0)
            events = self.events.get(key, [])
            if index >= len(events):
                raise RuntimeError(f"回放缺少请求：{key}，调用序号 {index + 1}")
            self.cursors[key] = index + 1
            event = events[index]
        if event.get("status") == "error":
            error = event.get("error")
            if not isinstance(error, dict):
                raise RuntimeError(f"回放异常记录损坏：{key}")
            raise_recorded_error(error, target)
        digest = str(event["sha256"])
        with gzip.open(self.blob_directory / f"{digest}.txt.gz", "rt", encoding="utf-8", newline="") as source:
            return source.read()

    def save(self) -> None:
        payload = {
            "schema": "duan_response_recording.v1",
            "events": self.events,
            "summary": {
                "request_keys": len(self.events),
                "request_count": sum(len(events) for events in self.events.values()),
            },
        }
        (self.directory / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def reset(self) -> None:
        self.cursors = {}

    def usage(self) -> dict[str, object]:
        missing = {
            key: len(events) - self.cursors.get(key, 0)
            for key, events in self.events.items()
            if len(events) != self.cursors.get(key, 0)
        }
        return {
            "used_count": sum(self.cursors.values()),
            "recorded_count": sum(len(events) for events in self.events.values()),
            "unconsumed": missing,
        }


def patch_recording(baseline: ModuleType, store: ResponseStore) -> None:
    real_fetch = baseline.fetch_text
    real_render = baseline.render_page_text
    baseline.fetch_text = lambda url, timeout, verify_ssl: store.record_call(
        "fetch", url, lambda: real_fetch(url, timeout, verify_ssl)
    )
    baseline.render_page_text = lambda url, timeout, verify_ssl: store.record_call(
        "render", url, lambda: real_render(url, timeout, verify_ssl)
    )


def patch_baseline_replay(baseline: ModuleType, store: ResponseStore) -> None:
    baseline.fetch_text = lambda url, timeout, verify_ssl: store.replay_call("fetch", url, baseline)
    baseline.render_page_text = lambda url, timeout, verify_ssl: store.replay_call("render", url, baseline)


def patch_modular_replay(store: ResponseStore) -> tuple[ModuleType, ModuleType, ModuleType]:
    import duan_app.crawl_service as crawl_service
    import duan_app.documents as documents
    import duan_app.fetcher as fetcher

    def replay_fetch(url, timeout, verify_ssl):
        return store.replay_call("fetch", url, fetcher)

    def replay_render(url, timeout, verify_ssl):
        return store.replay_call("render", url, fetcher)
    fetcher.fetch_text = replay_fetch
    documents.fetch_text = replay_fetch
    documents.render_page_text = replay_render
    return crawl_service, documents, fetcher


def run_sites(module: ModuleType, sites: list[object], issue: int, workers: int) -> list[object]:
    results: list[object | None] = [None] * len(sites)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(sites)))) as pool:
        futures = {
            pool.submit(module.process_site, index, site, 20, True, {issue}, str(issue)): index
            for index, site in enumerate(sites, start=1)
        }
        for future in as_completed(futures):
            index = futures[future]
            results[index - 1] = future.result()
    return [result for result in results if result is not None]


def serialize_results(results: list[object]) -> list[dict[str, object]]:
    return [asdict(result) for result in results]


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 7, 31, 12, 0, 0)
        return value if tz is None else value.replace(tzinfo=tz)


def subset_cache(source: Path, target: Path, site_names: set[str]) -> None:
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    payload["sites"] = [record for record in payload.get("sites", []) if record.get("name") in site_names]
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["site_count"] = len(payload["sites"])
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")


def artifact_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def build_artifacts(
    label: str,
    module: ModuleType,
    results: list[object],
    sites: list[object],
    issue: int,
    directory: Path,
) -> tuple[dict[str, bytes | None], str | None]:
    directory.mkdir(parents=True, exist_ok=True)
    sites_path = directory.parent / "sites.json"
    if not sites_path.exists():
        sites_path.write_text(
            json.dumps([module.site_to_dict(site) for site in sites], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8-sig",
        )
    cache_path = directory / "recent_10_cache.json"
    subset_cache(ROOT / "recent_10_cache.json", cache_path, {site.name for site in sites})
    slow_path = directory / "slow_sites.json"
    shutil.copy2(ROOT / "slow_sites.json", slow_path)
    success_path = directory / "success.txt"
    failure_path = directory / "failure.txt"

    success_lines, failure_lines, ranking = module.build_output_lines(results, {issue}, 3)
    module.write_result_files(success_path, failure_path, success_lines, failure_lines, ranking)
    module.update_slow_site_memory(slow_path, results)
    cache_error = None
    try:
        module.write_recent_cache_file(
            cache_path,
            sites_path,
            results,
            preserve_conflicting_records=True,
        )
    except ValueError as exc:
        cache_error = str(exc)

    artifacts = {
        "success": artifact_bytes(success_path),
        "failure": artifact_bytes(failure_path),
        "cache": artifact_bytes(cache_path),
        "slow": artifact_bytes(slow_path),
    }
    (directory / "result-objects.json").write_text(
        json.dumps(serialize_results(results), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifacts, cache_error


def compare_artifacts(old: dict[str, bytes | None], new: dict[str, bytes | None]) -> list[str]:
    return sorted(name for name in set(old) | set(new) if old.get(name) != new.get(name))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="杀段新旧版本同源响应回放验收")
    parser.add_argument("--issue", type=int, default=202)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="0 表示全部站点")
    parser.add_argument("--recording", default="tests/fixtures/full-replay")
    parser.add_argument("--output", default="verification_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline = load_module("duan_baseline", BASELINE_ROOT / "duan_crawler.py")
    import duan_app
    import duan_app.persistence.cache as modular_cache

    baseline_sites = baseline.load_sites_config(BASELINE_ROOT / "sites.json")
    modular_sites = duan_app.load_sites_config(ROOT / "sites.json")
    if args.limit > 0:
        baseline_sites = baseline_sites[: args.limit]
        modular_sites = modular_sites[: args.limit]
    if [site.name for site in baseline_sites] != [site.name for site in modular_sites]:
        raise RuntimeError("新旧站点顺序不一致")

    recording_path = ROOT / args.recording
    store = ResponseStore(recording_path, record=True)
    patch_recording(baseline, store)
    recorded_results = run_sites(baseline, baseline_sites, args.issue, args.workers)
    store.save()

    replay_store = ResponseStore(recording_path, record=False)
    patch_baseline_replay(baseline, replay_store)
    baseline.time.sleep = lambda *_args, **_kwargs: None
    old_results = run_sites(baseline, baseline_sites, args.issue, args.workers)
    old_usage = replay_store.usage()

    replay_store.reset()
    crawl_service, _documents, fetcher = patch_modular_replay(replay_store)
    fetcher.time.sleep = lambda *_args, **_kwargs: None
    new_results = run_sites(crawl_service, modular_sites, args.issue, args.workers)
    new_usage = replay_store.usage()

    baseline.datetime = FrozenDateTime
    modular_cache.datetime = FrozenDateTime
    output_root = ROOT / args.output
    if output_root.exists():
        shutil.rmtree(output_root)
    old_artifacts, old_cache_error = build_artifacts(
        "old", baseline, old_results, baseline_sites, args.issue, output_root / "old"
    )
    new_artifacts, new_cache_error = build_artifacts(
        "new", duan_app, new_results, modular_sites, args.issue, output_root / "new"
    )

    recorded_serialized = serialize_results(recorded_results)
    old_serialized = serialize_results(old_results)
    new_serialized = serialize_results(new_results)
    different_artifacts = compare_artifacts(old_artifacts, new_artifacts)
    accepted = (
        recorded_serialized == old_serialized
        and old_serialized == new_serialized
        and old_cache_error == new_cache_error
        and not different_artifacts
        and not old_usage["unconsumed"]
        and not new_usage["unconsumed"]
    )
    report = {
        "accepted": accepted,
        "issue": args.issue,
        "site_count": len(baseline_sites),
        "recording_summary": {
            "request_keys": len(replay_store.events),
            "request_count": sum(len(events) for events in replay_store.events.values()),
        },
        "baseline_record_replay_equal": recorded_serialized == old_serialized,
        "old_new_results_equal": old_serialized == new_serialized,
        "old_cache_error": old_cache_error,
        "new_cache_error": new_cache_error,
        "different_artifacts": different_artifacts,
        "old_replay_usage": old_usage,
        "new_replay_usage": new_usage,
    }
    (output_root / "parity-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
