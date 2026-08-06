import pytest

from duan_app.domain import ArticleDocumentList, Site
from duan_app.parsing.custom import collect_candidates


def decoded_documents(
    anchor_text: str,
    data_text: str,
    *,
    block_id: str = "script-block",
    data_block_id: str | None = None,
) -> ArticleDocumentList:
    documents = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": block_id,
    }
    documents.append_document(anchor_text, metadata)
    data_metadata = dict(metadata)
    if data_block_id is not None:
        data_metadata["block_id"] = data_block_id
    documents.append_document(data_text, data_metadata)
    return documents


def test_same_script_block_shares_anchor_across_decoded_documents() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "top")
    documents = decoded_documents(
        "解耦站 213期:[绝杀一段]",
        "213期:[绝杀一段][2段]开:猴35准",
    )

    candidates = collect_candidates(documents, site, {213})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(213, "2段")]
    assert candidates[0].block_id == "script-block"


def test_decoded_documents_from_different_blocks_do_not_share_anchor() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "top")
    documents = decoded_documents(
        "解耦站 213期:[绝杀一段]",
        "213期:[绝杀一段][2段]开:猴35准",
        data_block_id="other-script-block",
    )

    assert collect_candidates(documents, site, {213}) == []


def test_same_script_block_authorizes_only_first_local_strict_data_document() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "top")
    documents = decoded_documents(
        "解耦站 215期:[绝杀一段]",
        "215期:[绝杀一段][2段]开:猴35准",
    )
    metadata = dict(documents.document_metadata[0])
    for index in range(12):
        documents.append_document(f"无关脚本内容{index}", metadata)
    documents.append_document("215期:[绝杀一段][7段]开:猴35准", metadata)

    candidates = collect_candidates(documents, site, {215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "2段")]


def test_target_issue_selects_its_local_script_section_but_keeps_section_history() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = decoded_documents(
        "解耦站 220期:[绝杀一段]",
        "220期:[绝杀一段][7段]开:猴35准",
    )
    metadata = dict(documents.document_metadata[0])
    documents.append_document("解耦站 215期:[绝杀一段]", metadata)
    documents.append_document(
        "215期:[绝杀一段][2段]开:猴35准\n214期:[绝杀一段][3段]开:猴35准",
        metadata,
    )

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [
        (215, "2段"),
        (214, "3段"),
    ]


def test_target_heading_does_not_skip_local_previous_issue_for_far_target_bait() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = decoded_documents(
        "解耦站 215期:[绝杀一段]",
        "214期:[绝杀一段][3段]开:猴35准\n213期:[绝杀一段][4段]开:猴35准",
    )
    metadata = dict(documents.document_metadata[0])
    for index in range(12):
        documents.append_document(f"无关脚本内容{index}", metadata)
    documents.append_document("215期:[绝杀一段][7段]开:猴35准", metadata)

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [
        (214, "3段"),
        (213, "4段"),
    ]


def test_target_issue_document_precedes_historical_document_in_same_script_block() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": "script-block",
    }
    documents.append_document("解耦站 215期:[绝杀一段]", metadata)
    documents.append_document("214期:[绝杀一段][3段]开:猴35准", metadata)
    documents.append_document("215期:[绝杀一段][2段]开:猴35准", metadata)

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "2段")]


def test_target_table_document_is_preferred_over_future_range_in_same_script_block() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": "script-block",
    }
    documents.append_document("解耦站 215期:[绝杀一段]", metadata)
    documents.append_document(
        "215期:[绝杀一段][2段]开:猴35准\n216期:[绝杀一段][3段]开:猴35准\n217期:[绝杀一段][4段]开:猴35准",
        metadata,
    )
    documents.append_document(
        "215期:[绝杀一段][1段]开:0000中\n"
        "1段:01 02 03 04 05 06 07\n"
        "2段:08 09 10 11 12 13 14",
        metadata,
    )

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "1段")]


def test_target_row_followed_by_split_table_document_is_preferred() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": "script-block",
    }
    documents.append_document("解耦站 215期:[绝杀一段]", metadata)
    documents.append_document(
        "215期:[绝杀一段][2段]开:猴35准\n216期:[绝杀一段][3段]开:猴35准\n217期:[绝杀一段][4段]开:猴35准",
        metadata,
    )
    documents.append_document("215期:[绝杀一段][1段]开:0000中", metadata)
    documents.append_document("1段--01.02.03.04.05.06.07", metadata)
    documents.append_document("2段--08.09.10.11.12.13.14", metadata)

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "1段")]


def test_target_issue_with_zero_open_placeholder_keeps_valid_segment_candidate() -> None:
    site = Site("解耦站", "https://example.test/topic/1.html", "bottom")
    documents = ArticleDocumentList()
    metadata = {
        "source_url": "https://example.test/upload/script/target.js",
        "document_type": "script",
        "document_id": None,
        "block_id": "script-block",
    }
    documents.append_document("解耦站 215期:[绝杀一段]", metadata)
    documents.append_document("214期:[绝杀一段][3段]开:猴35准", metadata)
    documents.append_document("215期:[绝杀一段][1段]开:0000中", metadata)

    candidates = collect_candidates(documents, site, anchor_issue_filter={215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "1段")]


@pytest.mark.parametrize(
    ("title", "value"),
    [("稳杀一段", "2段"), ("必杀一段", "3段"), ("稳禁一段", "5段")],
)
def test_supported_result_title_variants_require_strict_data(
    title: str, value: str
) -> None:
    site = Site("变体站", "https://example.test/topic/1.html", "top")
    document = f"变体站 213期:{title}[{value}]开:猴35准"

    candidates = collect_candidates([document], site, {213})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(213, value)]


def test_result_title_variant_without_open_status_is_rejected() -> None:
    site = Site("变体站", "https://example.test/topic/1.html", "top")
    document = "变体站 213期:稳杀一段[2段]"

    assert collect_candidates([document], site, {213}) == []


@pytest.mark.parametrize(
    ("site_name", "alias"),
    [
        ("雷锋", "26064c.com"),
        ("雷锋", "26064d.com"),
        ("赛马会第一版", "877730c.com"),
        ("赛马会第一版", "877730d.com"),
        ("赛马会第二版", "877730c.com"),
        ("赛马会第二版", "877730d.com"),
        ("白虎", "73448b.com"),
    ],
)
def test_verified_site_alias_can_anchor_adjacent_decoded_data(
    site_name: str, alias: str
) -> None:
    site = Site(site_name, "https://example.test/topic/1.html", "top")
    documents = decoded_documents(
        f"{alias} 215期:[绝杀一段]",
        "215期:[稳杀一段][2段]开:猴35准",
    )

    candidates = collect_candidates(documents, site, {215})

    assert [(candidate.issue, candidate.value) for candidate in candidates] == [(215, "2段")]
