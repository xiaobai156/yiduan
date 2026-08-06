import base64
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import duan_crawler as crawler


TARGET_ID = "target-record"
BAIT_ID = "bait-record"


def encoded(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def article_record(record_id: str, name: str, issue: int, value: int) -> dict[str, object]:
    body = f"{issue}期 [绝杀一段] 杀 [{value}段] 开 准"
    return {
        "id": record_id,
        "authorNickname": name,
        "title": encoded(f"<p>{issue}期:[绝杀一段]目标标题</p>"),
        "html": encoded(f"<p>{body}</p>"),
        "formSections": [{"id": "column-1", "name": "主条目", "type": "mainarticle", "sortOrder": 1}],
    }


def article_json(*records: dict[str, object]) -> str:
    return json.dumps({"data": list(records)}, ensure_ascii=False)


def test_nested_json_selects_exact_id_and_ignores_bait() -> None:
    payload = article_json(
        article_record(TARGET_ID, "目标站", 200, 2),
        article_record(BAIT_ID, "诱饵站", 200, 7),
    )

    record, metadata = crawler.extract_article_record(payload, TARGET_ID)

    assert record["id"] == TARGET_ID
    assert metadata["record_path"] == "$.data[0]"
    assert metadata["article_count"] == 2
    assert "7段" not in (crawler.decode_base64_payload(record["html"]) or "")


def test_missing_id_fails_closed() -> None:
    with pytest.raises(crawler.ArticleRecordError, match="未找到目标记录ID"):
        crawler.extract_article_record(article_json(article_record(BAIT_ID, "诱饵站", 200, 7)), TARGET_ID)


def test_duplicate_id_fails_closed() -> None:
    with pytest.raises(crawler.ArticleRecordError, match="找到多个目标记录ID"):
        crawler.extract_article_record(
            article_json(
                article_record(TARGET_ID, "目标站", 200, 2),
                article_record(TARGET_ID, "目标站", 199, 3),
            ),
            TARGET_ID,
        )


def test_title_author_column_and_body_must_be_one_record() -> None:
    record = article_record(TARGET_ID, "错误作者", 200, 2)
    with pytest.raises(crawler.ArticleRecordError, match="作者校验失败"):
        crawler.validate_article_record(record, TARGET_ID, "目标站", "bottom")


def test_scoped_document_contains_only_target_record_fields() -> None:
    payload = article_json(
        article_record(TARGET_ID, "目标站", 200, 2),
        article_record(BAIT_ID, "诱饵站", 200, 7),
    )
    documents = crawler.ArticleDocumentList()

    crawler.add_article_json_documents(
        payload,
        documents,
        set(),
        target_id=TARGET_ID,
        site_name="目标站",
        pick="bottom",
        source_url="https://example.test/api/target",
    )

    assert len(documents) == 1
    assert "2段" in documents[0]
    assert "7段" not in documents[0]
    assert documents.article_audit[0]["record_id"] == TARGET_ID
    assert documents.article_audit[0]["record_path"] == "$.data[0]"


def test_dynamic_page_fallback_requires_target_id() -> None:
    with pytest.raises(crawler.ArticleRecordError, match="页面未包含目标记录ID"):
        crawler.add_dynamic_article_document(
            "<html><body>200期 [绝杀一段] 杀 [7段] 开 准</body></html>",
            [],
            set(),
            TARGET_ID,
        )


def test_article_404_browser_fallback_keeps_id_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://example.test/article/admin/target-record?url=x"

    def api_404(*args: object, **kwargs: object) -> str:
        raise HTTPError(str(args[0]), 404, "missing", {}, None)

    monkeypatch.setattr(crawler, "fetch_text", api_404)
    monkeypatch.setattr(crawler, "fetch_page_text", lambda *args, **kwargs: "<html>shell</html>")
    monkeypatch.setattr(
        crawler,
        "render_page_text",
        lambda *args, **kwargs: (
            "<html><body><div data-record-id='target-record'>"
            "目标站 200期 [绝杀一段] 杀 [2段] 开 准"
            "</div></body></html>"
        ),
    )

    documents, _ = crawler.collect_documents(
        url,
        5,
        True,
        issue_filter={200},
        site_name="目标站",
        pick="bottom",
    )

    assert len(documents) == 1
    assert "目标站" in documents[0]
    assert "200期" in documents[0]


def test_empty_article_api_browser_fallback_keeps_id_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/article/admin/target-record?url=x"
    monkeypatch.setattr(crawler, "fetch_text", lambda *args, **kwargs: "{}")
    monkeypatch.setattr(crawler, "fetch_page_text", lambda *args, **kwargs: "<html>shell</html>")
    monkeypatch.setattr(
        crawler,
        "render_page_text",
        lambda *args, **kwargs: (
            "<html><body><div data-record-id='target-record'>"
            "目标站 200期 [绝杀一段] 杀 [2段] 开 准"
            "</div></body></html>"
        ),
    )

    documents, script_errors = crawler.collect_documents(
        url,
        5,
        True,
        issue_filter={200},
        site_name="目标站",
        pick="bottom",
    )

    assert len(documents) == 1
    assert len(script_errors) == 2


def test_cache_conflict_is_reported_by_period() -> None:
    previous = {
        "sites": [{
            "name": "目标站",
            "url": "https://example.test/topic",
            "sequence": [{"period": 200, "values": ["2段"]}],
        }]
    }
    current = [{
        "name": "目标站",
        "url": "https://example.test/topic",
        "sequence": [{"period": 200, "values": ["7段"]}],
    }]

    conflicts = crawler.compare_recent_cache_records(previous, current)

    assert conflicts == [{
        "name": "目标站",
        "url": "https://example.test/topic",
        "period": 200,
        "old_values": ["2段"],
        "new_values": ["7段"],
        "reason": "历史缓存与实时结果冲突",
    }]


def test_cache_article_id_conflict_is_reported() -> None:
    previous = {
        "sites": [{
            "name": "目标站",
            "url": "https://example.test/topic",
            "article_records": [{"record_id": "old-record"}],
            "sequence": [{"period": 200, "values": ["2段"]}],
        }]
    }
    current = [{
        "name": "目标站",
        "url": "https://example.test/topic",
        "article_records": [{"record_id": "new-record"}],
        "sequence": [{"period": 200, "values": ["2段"]}],
    }]

    conflicts = crawler.compare_recent_cache_records(previous, current)

    assert conflicts[0]["reason"] == "历史缓存与实时文章ID冲突"
    assert conflicts[0]["period"] is None


def test_cache_conflict_dry_run_does_not_affect_realtime_cache_update(tmp_path: Path) -> None:
    sites_path = tmp_path / "sites.json"
    cache_path = tmp_path / "recent_10_cache.json"
    sites_path.write_text(
        json.dumps([{"name": "目标站", "url": "https://example.test/topic", "pick": "bottom"}], ensure_ascii=False),
        encoding="utf-8",
    )
    original = {
        "sites": [{
            "name": "目标站",
            "url": "https://example.test/topic",
            "sequence": [{"period": 200, "values": ["2段"]}],
        }]
    }
    cache_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    site = crawler.Site("目标站", "https://example.test/topic", "bottom")
    result = crawler.SiteResult(
        1,
        site,
        [],
        None,
        "OK",
        cache_record={
            "name": "目标站",
            "url": "https://example.test/topic",
            "status": "ok",
            "period_count": 1,
            "sequence": [{"period": 200, "values": ["7段"]}],
        },
    )

    summary = crawler.write_recent_cache_file(cache_path, sites_path, [result], dry_run=True)

    assert summary["site_count"] == 1
    assert json.loads(cache_path.read_text(encoding="utf-8")) == original
