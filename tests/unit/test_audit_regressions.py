import json
from pathlib import Path

import pytest

from duan_app.documents import xiaoyao_detail_urls
from duan_app.domain import ArticleDocumentList, Candidate, Site
from duan_app.dynamic_articles import add_dynamic_article_document
from duan_app.parsing.custom import collect_candidates, prioritize_site_title_issue_candidates
from duan_app.persistence.cache import build_recent_cache_record, write_recent_cache_file
from duan_app.selection import find_matches_from_candidates


def candidate(issue: int, value: str, position: int, order: int) -> Candidate:
    return Candidate(issue, str(issue), value, "测试站", "片段", 100, order, position)


def test_generic_candidates_require_the_real_site_anchor() -> None:
    site = Site("本站目录", "https://example.test/topic/1.html", "top")
    documents = ["其他栏目 202期 [绝杀一段] 杀 [2段] 开 准"]

    assert collect_candidates(documents, site, {202}) == []


def test_title_issue_metadata_cannot_rewrite_page_position() -> None:
    candidates = [
        candidate(214, "2段", 10, 0),
        candidate(213, "3段", 20, 1),
        candidate(212, "4段", 30, 2),
        candidate(211, "5段", 40, 3),
    ]

    prioritized = prioritize_site_title_issue_candidates(candidates, {213}, "top")

    assert [item.position for item in prioritized] == [10, 20, 30, 40]


def test_jidichengming_does_not_synthesize_the_requested_issue() -> None:
    site = Site("及第成名", "https://example.test/topic/1.html", "top")
    document = "免费发表 211期 绝杀一段；210期；220期 及第成名 [绝杀一段] 杀 [3段] 开 准"

    candidates = collect_candidates([document], site, {211})

    assert all(item.issue != 211 for item in candidates)


def test_xiaoyao_source_collection_does_not_filter_by_requested_issue() -> None:
    listing = "".join(
        f'<a href="topic/{issue}.html">{issue}期【逍遥浪子】绝杀一段☆实力见证</a>'
        for issue in (214, 213, 212, 211)
    )

    urls = xiaoyao_detail_urls(listing, "https://example.test/home", {211})

    assert urls == [f"https://example.test/topic/{issue}.html" for issue in (214, 213, 212, 211)]


def test_anchor_state_does_not_cross_document_boundaries() -> None:
    site = Site("暗香疏影", "https://example.test/topic/1.html", "top")
    documents = [
        "暗香疏影 绝杀一段",
        "202期 [绝杀一段] 杀 [2段] 开 准",
    ]

    assert collect_candidates(documents, site, {202}) == []


def test_multi_duan_inference_requires_explicit_site_result_format() -> None:
    site = Site("三地主", "https://example.test/topic/1.html", "top")
    document = "三地主 202期 [1,2,3,4,5,6段]"

    assert collect_candidates([document], site, {202}) == []


def test_sandizhu_uses_only_unique_authoritative_six_segment_section() -> None:
    site = Site("三地主", "https://example.test/topic/1.html", "top")
    document = (
        "三地主\n[三表主六段]√\n"
        "215期[2.5.3.1.4.6段]\n"
        "214期[1.2.3.4.6.7段]\n"
        "____________★____________\n"
        "215期[1.2.3.4.5.6段]"
    )

    candidates = collect_candidates([document], site, {214, 215, 999})

    assert [(item.issue, item.value) for item in candidates] == [(215, "7段"), (214, "5段")]


@pytest.mark.parametrize(
    "document",
    [
        "三地主\n[三表主六段]√\n215期[1.2.3.4.5段]",
        "三地主\n[三表主六段]√\n215期[1.2.3.4.5.6段]\n[三表主六段]√\n215期[1.2.3.4.5.7段]",
    ],
)
def test_sandizhu_rejects_invalid_or_duplicate_authoritative_section(document: str) -> None:
    site = Site("三地主", "https://example.test/topic/1.html", "top")

    assert collect_candidates([document], site, {215}) == []


def test_conflict_candidates_cannot_create_a_cache_value(tmp_path: Path) -> None:
    site = Site("冲突站", "https://example.test/topic/1.html", "top")
    candidates: list[Candidate] = []
    for order, issue in enumerate(range(202, 192, -1)):
        position = order
        candidates.extend(
            [
                candidate(issue, "2段", position, order * 2),
                candidate(issue, "5段", position, order * 2 + 1),
            ]
        )

    assert find_matches_from_candidates(candidates, {202}, site) == []
    record = build_recent_cache_record(1, site, [], [], candidates)
    assert record["status"] == "error"
    assert record["sequence"] == []

    sites_path = tmp_path / "sites.json"
    cache_path = tmp_path / "recent_10_cache.json"
    sites_path.write_text(
        json.dumps([{"name": site.name, "url": site.url, "pick": site.pick}], ensure_ascii=False),
        encoding="utf-8",
    )
    result = type("Result", (), {"cache_record": record})()
    write_recent_cache_file(cache_path, sites_path, [result])
    payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    assert payload["sites"][0]["status"] == "error"


def test_candidate_keeps_source_evidence_and_real_anchor() -> None:
    site = Site("证据站", "https://example.test/topic/1.html", "top")
    documents = ArticleDocumentList()
    documents.append_document(
        "证据站 202期 [绝杀一段] 杀 [2段] 开 准",
        {
            "source_url": "https://example.test/topic/1.html",
            "document_type": "page",
            "document_id": "page-1",
            "block_id": "body-1",
        },
    )

    matches = collect_candidates(documents, site, {202})

    assert len(matches) == 1
    assert matches[0].source_url == "https://example.test/topic/1.html"
    assert matches[0].document_type == "page"
    assert matches[0].document_id == "page-1"
    assert matches[0].block_id == "body-1"
    assert matches[0].anchor == "证据站"
    assert "2段" in matches[0].raw_block


def test_dynamic_html_fallback_scopes_target_record_and_rejects_duplicate_target() -> None:
    target_html = (
        "<html><body>"
        "<div data-record-id='target'>目标站 202期 [绝杀一段] 杀 [2段] 开 准</div>"
        "<div data-record-id='bait'>诱饵站 202期 [绝杀一段] 杀 [7段] 开 准</div>"
        "</body></html>"
    )
    documents = ArticleDocumentList()
    add_dynamic_article_document(
        target_html,
        documents,
        set(),
        "target",
        "目标站",
        "top",
        source_url="https://example.test/article/admin/target",
        document_type="browser",
    )

    assert len(documents) == 1
    assert "2段" in documents[0]
    assert "7段" not in documents[0]
    assert documents.article_audit[0]["record_id"] == "target"

    duplicate = target_html.replace(
        "</body>",
        "<div data-record-id='target'>目标站 201期 [绝杀一段] 杀 [3段] 开 准</div></body>",
    )
    with pytest.raises(ValueError, match="多个目标记录ID块"):
        add_dynamic_article_document(duplicate, [], set(), "target", "目标站", "top")


def test_cache_records_current_sites_identity_hash(tmp_path: Path) -> None:
    site = Site("哈希站", "https://example.test/topic/1.html", "top")
    sites_path = tmp_path / "sites.json"
    cache_path = tmp_path / "recent_10_cache.json"
    sites_path.write_text(
        json.dumps([{"name": site.name, "url": site.url, "pick": site.pick}], ensure_ascii=False),
        encoding="utf-8",
    )
    record = {
        "index": 1,
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "latest_period": 202,
        "sequence": [{"period": 202, "values": ["2段"]}],
        "period_count": 1,
        "is_consecutive": True,
        "status": "audit",
        "notes": ["仅抓到1期"],
        "error": None,
        "script_error_count": 0,
        "article_records": [],
    }
    result = type("Result", (), {"cache_record": record})()

    write_recent_cache_file(cache_path, sites_path, [result], preserve_conflicting_records=True)
    payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    assert payload["source_sites"] == str(sites_path.resolve())
    assert len(payload["source_sites_hash"]) == 64
