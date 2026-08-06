from duan_app.domain import ArticleDocumentList, Site
from duan_app.parsing.custom import collect_candidates

from verification.validate_215_failure_sites import (
    normalize_result_title_variants,
    three_landlords_candidates,
    with_local_script_topic_section,
    with_same_script_block_anchor,
)


def documents(data_block: str = "target-script") -> ArticleDocumentList:
    result = ArticleDocumentList()
    anchor_metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": "target-script",
    }
    result.append_document("测试站 215期:[绝杀一段]", anchor_metadata)
    result.append_document(
        "215期:[绝杀一段][1段]开:鼠00准\n214期:[绝杀一段][6段]开:兔04准",
        {**anchor_metadata, "block_id": data_block},
    )
    return result


def test_same_script_block_can_share_anchor_without_crossing_sources() -> None:
    site = Site("测试站", "https://example.test/topic/1.html", "top")

    isolated, blocks = with_same_script_block_anchor(documents(), site)
    candidates = collect_candidates(isolated, site)

    assert blocks == [
        (
            "https://example.test/upload/script/target.js",
            "script",
            "None",
            "target-script",
        )
    ]
    assert [(item.issue, item.value) for item in candidates] == [
        (215, "1段"),
        (214, "6段"),
    ]


def test_different_script_blocks_cannot_borrow_anchor() -> None:
    site = Site("测试站", "https://example.test/topic/1.html", "top")

    isolated, _ = with_same_script_block_anchor(documents("other-script"), site)

    assert collect_candidates(isolated, site) == []


def test_nonexistent_period_is_not_created() -> None:
    site = Site("测试站", "https://example.test/topic/1.html", "top")
    isolated, _ = with_same_script_block_anchor(documents(), site)

    assert [item for item in collect_candidates(isolated, site) if item.issue == 999] == []


def test_local_topic_section_ignores_far_old_content_in_same_script() -> None:
    site = Site("测试站", "https://example.test/topic/1.html", "top")
    source = documents()
    metadata = dict(source.document_metadata[0])
    for index in range(12):
        source.append_document(f"无关片段{index}", metadata)
    source.append_document("215期:[绝杀一段][7段]开:鼠00准", metadata)

    isolated, _ = with_local_script_topic_section(source, site, 215)
    candidates = collect_candidates(isolated, site)

    assert [(item.issue, item.value) for item in candidates] == [
        (215, "1段"),
        (214, "6段"),
    ]


def test_supported_title_variants_are_normalized_only_inside_verified_section() -> None:
    assert normalize_result_title_variants("215期:[稳禁一段][2段]开:鼠00准") == (
        "215期:[绝杀一段][2段]开:鼠00准"
    )


def test_three_landlords_uses_only_unique_six_value_section() -> None:
    site = Site("三地主", "https://example.test/", "top")
    source = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/content.js",
        "document_type": "script",
        "block_id": "content.js",
    }
    source.append_document(
        "[三表主六段]√\n215期[2.5.3.1.4.6段]\n214期[1.2.4.6.7.3段]"
        "\n____________★____________\n215期[1.2.3.4.5.6段]",
        metadata,
    )

    candidates = three_landlords_candidates(source, site, {215, 214, 999})

    assert [(item.issue, item.value) for item in candidates] == [
        (215, "7段"),
        (214, "5段"),
    ]


def test_three_landlords_rejects_invalid_or_duplicate_authority() -> None:
    site = Site("三地主", "https://example.test/", "top")
    invalid = ArticleDocumentList()
    invalid.append_document("[三表主六段]√\n215期[1.2.3.4.5段]", {})
    assert three_landlords_candidates(invalid, site, {215}) == []

    invalid.append_document("[三表主六段]√\n215期[1.2.3.4.5.6段]", {})
    assert three_landlords_candidates(invalid, site, {215}) == []
