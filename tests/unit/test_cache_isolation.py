import json
from pathlib import Path

import duan_crawler as crawler


def cache_record(index: int, site: crawler.Site, value: str) -> dict[str, object]:
    return {
        "index": index,
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "latest_period": 202,
        "sequence": [{"period": 201, "values": [value]}],
        "period_count": 10,
        "is_consecutive": True,
        "status": "ok",
        "notes": [],
        "error": None,
        "script_error_count": 0,
        "article_records": [],
    }


def site_result(index: int, site: crawler.Site, value: str, cache_value: str) -> crawler.SiteResult:
    candidate = crawler.Candidate(202, "202", value, f"{site.name} 202期", "", 100, index, index)
    return crawler.SiteResult(
        index,
        site,
        [candidate],
        None,
        "OK",
        cache_record=cache_record(index, site, cache_value),
    )


def test_cache_update_keeps_live_records_without_changing_realtime_output(tmp_path: Path) -> None:
    conflict_site = crawler.Site("冲突站", "https://example.test/conflict", "top")
    normal_site = crawler.Site("正常站", "https://example.test/normal", "bottom")
    results = [
        site_result(1, conflict_site, "2段", "2段"),
        site_result(2, normal_site, "5段", "5段"),
    ]
    sites_path = tmp_path / "sites.json"
    cache_path = tmp_path / "recent_10_cache.json"
    sites_path.write_text("[{}, {}]", encoding="utf-8")
    previous_normal = cache_record(2, normal_site, "5段")
    previous_normal["notes"] = ["旧记录"]
    cache_path.write_text(
        json.dumps(
            {"sites": [cache_record(1, conflict_site, "7段"), previous_normal]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = crawler.write_recent_cache_file(
        cache_path,
        sites_path,
        results,
        dry_run=True,
        preserve_conflicting_records=True,
    )
    success_lines, failure_lines, _ = crawler.build_output_lines(results, {202}, 3)
    crawler.write_recent_cache_file(
        cache_path,
        sites_path,
        results,
        preserve_conflicting_records=True,
    )

    assert success_lines == ["2段 冲突站 202期", "5段 正常站 202期"]
    assert failure_lines == []
    assert summary["site_count"] == 2

    refreshed = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    records = {record["name"]: record for record in refreshed["sites"]}
    assert records["冲突站"]["sequence"][0]["values"] == ["2段"]
    assert records["正常站"]["notes"] == []


def test_failed_single_period_record_cannot_reuse_old_success_cache(tmp_path: Path) -> None:
    site = crawler.Site("失败站", "https://example.test/failed", "bottom")
    failed_record = cache_record(1, site, "2段")
    failed_record.update(
        {
            "status": "error",
            "sequence": [],
            "period_count": 0,
            "error": "215期实时判定失败",
        }
    )
    failed_result = crawler.SiteResult(1, site, [], "失败行", "MISS", cache_record=failed_record)
    sites_path = tmp_path / "sites.json"
    cache_path = tmp_path / "recent_10_cache.json"
    sites_path.write_text("[{}]", encoding="utf-8")
    cache_path.write_text(
        json.dumps({"sites": [cache_record(1, site, "7段")]}, ensure_ascii=False),
        encoding="utf-8",
    )

    crawler.write_recent_cache_file(cache_path, sites_path, [failed_result])

    refreshed = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    record = refreshed["sites"][0]
    assert record["status"] == "error"
    assert record["sequence"] == []
    assert record["error"] == "215期实时判定失败"
