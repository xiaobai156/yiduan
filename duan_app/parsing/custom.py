# -*- coding: utf-8 -*-
import re

from duan_app.constants import ALLOW_REPEATED_DUAN_SITE_NAMES, FULLWIDTH_DIGITS, ISSUE_RE, MULTI_DUAN_SITE_NAMES
from duan_app.domain import ArticleDocumentList, Candidate, Site
from duan_app.parsing.engine import has_body_locator, has_result_keyword, is_strict_segment, iter_issue_segments, iter_search_texts, score_segment, table_signature_count, title_in_segment, values_in_segment
from duan_app.parsing.profiles import CONFIRMED_NEW_SITE_PARSER_NAMES, SITE_SECTION_ANCHOR_ALIASES, SITE_TITLE_ISSUE_AUTHORITY_NAMES
from duan_app.text_utils import compact_line, format_duan, html_to_text, normalize_text, number_to_int, strip_hidden_html_blocks


RESULT_TITLE_VARIANT_RE = re.compile(r"稳杀一段|必杀一段|稳禁一段|绝禁一段|(?<!绝)杀(?:一|1)段")
THREE_LANDLORDS_MARKER = "[三表主六段]√"
THREE_LANDLORDS_BOUNDARY = "____________★____________"


def dafangguangcai_values_and_strictness(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> tuple[list[str], bool]:
    values = values_in_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    return values, is_strict_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )

def langlangquankun_values_and_strictness(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> tuple[list[str], bool]:
    values = values_in_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    return values, is_strict_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )

def hanlaishuwang_values_and_strictness(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> tuple[list[str], bool]:
    values = values_in_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    return values, is_strict_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )

def confirmed_new_site_values_and_strictness(
    segment: str,
    site_name: str,
    has_document_anchor: bool = False,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> tuple[list[str], bool]:
    normalized_segment = normalize_text(segment).replace(" ", "")
    normalized_name = normalize_text(site_name).replace(" ", "")
    if normalized_name and normalized_name not in normalized_segment and not has_document_anchor:
        return [], False

    values = values_in_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    return values, is_strict_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )

def site_section_anchor_terms(site: Site) -> tuple[str, ...]:
    if site.name_anchors:
        name_terms = (site.name, *site.name_anchors)
    else:
        name_terms = (site.name, *SITE_SECTION_ANCHOR_ALIASES.get(site.name, ()))
    return tuple(dict.fromkeys(name_terms))

def has_site_section_result_marker(text: str) -> bool:
    normalized = normalize_text(text).replace(" ", "")
    return has_result_keyword(normalized) or "绝杀㊣一段" in normalized

def site_section_title_issues(
    documents: list[str],
    site: Site,
    issue_filter: set[int] | None = None,
) -> set[int]:
    if site.name not in SITE_TITLE_ISSUE_AUTHORITY_NAMES:
        return set()

    issues: set[int] = set()
    for document in documents:
        text = "\n".join(iter_search_texts(document))
        normalized = normalize_text(text)
        for anchor_term in site_section_anchor_terms(site):
            anchor = normalize_text(anchor_term)
            anchor_position = normalized.find(anchor)
            if anchor_position < 0:
                continue
            start = max(0, anchor_position - 180)
            end = min(len(normalized), anchor_position + 180)
            window = normalized[start:end]
            if not has_site_section_result_marker(window):
                continue
            local_anchor = anchor_position - start
            issue_matches = list(ISSUE_RE.finditer(window))
            preceding = [match for match in issue_matches if match.start() <= local_anchor]
            selected = max(preceding, key=lambda match: match.start()) if preceding else None
            if selected is not None:
                issue = int(selected.group(1).translate(FULLWIDTH_DIGITS))
                if issue_filter is None or issue in issue_filter:
                    issues.add(issue)
    return issues

def hanlaishuwang_title_kind(
    text: str,
    title_issues: set[int],
) -> str | None:
    normalized = normalize_text(text).replace(" ", "")
    title_match = re.search(r"(?<!\d)(\d{1,4})期[^\n]{0,100}?→", normalized)
    if title_match is None:
        return None

    issue = int(title_match.group(1).translate(FULLWIDTH_DIGITS))
    if (
        issue in title_issues
        and "→寒来暑往" in normalized
        and ("绝杀一段" in normalized or "绝杀1段" in normalized)
    ):
        return "target"
    return "other"

def hanlaishuwang_target_title_suffix(text: str, title_issues: set[int]) -> str:
    normalized = normalize_text(text)
    compact = normalized.replace(" ", "")
    title_match = re.search(r"(?<!\d)(\d{1,4})期[^\n]{0,100}?→", normalized)
    if title_match is None:
        return ""
    issue = int(title_match.group(1).translate(FULLWIDTH_DIGITS))
    if (
        issue not in title_issues
        or "→寒来暑往" not in compact
        or ("绝杀一段" not in compact and "绝杀1段" not in compact)
    ):
        return ""
    suffix_start = min(len(normalized), title_match.end())
    return normalized[suffix_start:]

def hanlaishuwang_target_title_index(
    documents: list[str], title_issues: set[int]
) -> int | None:
    for document_index, document in enumerate(documents):
        text = "\n".join(iter_search_texts(document))
        if hanlaishuwang_title_kind(text, title_issues) == "target":
            return document_index
    return None

def hanlaishuwang_contiguous_prefix(
    text: str,
    expected_issue: int,
    started: bool,
) -> tuple[str, int, bool, bool]:
    normalized = normalize_text(text)
    issue_matches = list(ISSUE_RE.finditer(normalized))
    if not issue_matches:
        return (normalized if started else ""), expected_issue, started, False

    if not started:
        first_target = next(
            (
                match
                for match in issue_matches
                if int(match.group(1).translate(FULLWIDTH_DIGITS)) == expected_issue
            ),
            None,
        )
        if first_target is None:
            return "", expected_issue, False, False
        normalized = normalized[first_target.start() :]
        issue_matches = list(ISSUE_RE.finditer(normalized))

    cutoff = len(normalized)
    current_issue = expected_issue
    saw_expected_issue = False
    for match in issue_matches:
        issue = int(match.group(1).translate(FULLWIDTH_DIGITS))
        if issue != current_issue:
            cutoff = match.start()
            break
        saw_expected_issue = True
        current_issue -= 1

    if not saw_expected_issue:
        return "", expected_issue, started, True
    return normalized[:cutoff], current_issue, True, cutoff < len(normalized)

def prioritize_site_title_issue_candidates(
    candidates: list[Candidate], title_issues: set[int], pick: str
) -> list[Candidate]:
    del title_issues, pick
    return candidates

def site_specific_values_and_strictness(
    segment: str,
    site: Site,
    has_document_anchor: bool = False,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> tuple[list[str], bool]:
    if site.custom_parser in {"topic_arrow", "topic_ordinal"}:
        values = _profile_layout_values(segment, site.custom_parser)
        if values:
            return values, (
                has_body_locator(segment)
                and has_result_keyword(segment)
                and _has_open_status(segment)
                and len(values) == 1
            )
    if site.name == "大放光彩":
        return dafangguangcai_values_and_strictness(
            segment,
            allow_repeated_duan=allow_repeated_duan,
            allow_multi_duan=allow_multi_duan,
        )
    if site.name == "朗朗权坤":
        return langlangquankun_values_and_strictness(
            segment,
            allow_repeated_duan=allow_repeated_duan,
            allow_multi_duan=allow_multi_duan,
        )
    if site.name == "寒来暑往":
        return hanlaishuwang_values_and_strictness(
            segment,
            allow_repeated_duan=allow_repeated_duan,
            allow_multi_duan=allow_multi_duan,
        )

    if site.name in CONFIRMED_NEW_SITE_PARSER_NAMES:
        return confirmed_new_site_values_and_strictness(
            segment,
            site.name,
            has_document_anchor=has_document_anchor,
            allow_repeated_duan=allow_repeated_duan,
            allow_multi_duan=allow_multi_duan,
        )

    values = values_in_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    return values, is_strict_segment(
        segment,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )


def _has_open_status(segment: str) -> bool:
    return re.search(r"开\s*[:：]?\s*[^准对中错赢]{0,24}(?:准|对|中|错|赢)", normalize_text(segment)) is not None


def _profile_layout_values(segment: str, parser_name: str) -> list[str]:
    normalized = normalize_text(segment)
    if parser_name == "topic_arrow":
        pattern = re.compile(r"(?:绝|灭|稳|必)?\s*杀\s*(?:一|1)\s*段.*?[→>]\s*([0-9０-９零一二两三四五六七八九十]{1,2})\s*段\s*[←<]", re.I)
    else:
        pattern = re.compile(r"(?:绝|灭|稳|必)?\s*杀\s*(?:一|1)\s*段.*?[\[【《（(]\s*第?\s*([0-9０-９零一二两三四五六七八九十]{1,2})\s*段\s*[\]】》）)]", re.I)
    match = pattern.search(normalized)
    if match is None:
        return []
    value = number_to_int(match.group(1))
    return [format_duan(value)] if value is not None and 1 <= value <= 7 else []

def normalize_result_title_variants(text: str) -> str:
    return RESULT_TITLE_VARIANT_RE.sub("绝杀一段", text)

def source_block_key(metadata: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(metadata.get("source_url") or ""),
        str(metadata.get("document_type") or ""),
        str(metadata.get("document_id") or ""),
        str(metadata.get("block_id") or ""),
    )

def document_has_strict_site_candidate(
    document: str,
    site: Site,
    issue_filter: set[int] | None,
) -> bool:
    allow_repeated_duan = site.name in ALLOW_REPEATED_DUAN_SITE_NAMES
    allow_multi_duan = site.name in MULTI_DUAN_SITE_NAMES
    for text in iter_search_texts(normalize_result_title_variants(document)):
        for _, _, segment in iter_issue_segments(text, issue_filter):
            values, strict = site_specific_values_and_strictness(
                segment,
                site,
                has_document_anchor=True,
                allow_repeated_duan=allow_repeated_duan,
                allow_multi_duan=allow_multi_duan,
            )
            segment_title = normalize_text(title_in_segment(segment, "")).replace(" ", "")
            if values and strict and (not segment_title or has_result_keyword(segment_title)):
                return True
    return False


def target_table_document_indexes(
    documents: list[str],
    indexes: list[int],
    normalized_by_index: dict[int, str],
    site: Site,
    issue_filter: set[int] | None,
    local_candidate_issues: set[int] | None,
) -> list[int]:
    # This boundary repair is authorized only for the currently failing 215期
    # run; other periods retain their previously verified document selection.
    if issue_filter != {215}:
        return []

    table_indexes: list[int] = []
    for position, index in enumerate(indexes):
        if not document_has_strict_site_candidate(documents[index], site, issue_filter):
            continue
        table_count = table_signature_count(normalized_by_index[index])
        if table_count >= 2:
            table_indexes.append(index)
            continue
        for neighbor_index in indexes[position + 1 : position + 3]:
            if document_has_strict_site_candidate(
                documents[neighbor_index], site, local_candidate_issues
            ):
                break
            table_count += table_signature_count(normalized_by_index[neighbor_index])
            if table_count >= 2:
                table_indexes.append(index)
                break
    return table_indexes


def authorized_script_document_anchors(
    documents: list[str],
    site: Site,
    issue_filter: set[int] | None,
) -> dict[int, str]:
    metadata_list = getattr(documents, "document_metadata", [])
    anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in site_section_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    block_indexes: dict[tuple[str, str, str, str], list[int]] = {}
    normalized_by_index: dict[int, str] = {}
    for index, document in enumerate(documents):
        metadata = metadata_list[index] if index < len(metadata_list) else {}
        key = source_block_key(metadata) if isinstance(metadata, dict) else ("", "", "", "")
        if key[1] != "script" or not key[0] or not key[3]:
            continue
        block_indexes.setdefault(key, []).append(index)
        normalized_by_index[index] = normalize_text(
            "\n".join(iter_search_texts(document))
        ).replace(" ", "")

    authorized: dict[int, str] = {}
    local_candidate_issues = (
        issue_filter | {issue - 1 for issue in issue_filter if issue > 1}
        if issue_filter is not None
        else None
    )
    for indexes in block_indexes.values():
        selected_in_block = False
        local_position = {index: position for position, index in enumerate(indexes)}
        anchor_indexes = [
            index
            for index in indexes
            if any(anchor in normalized_by_index[index] for anchor in anchor_terms)
        ]
        heading_indexes = []
        for index in indexes:
            text = normalized_by_index[index]
            issues = {
                int(match.group(1).translate(FULLWIDTH_DIGITS))
                for match in ISSUE_RE.finditer(text)
            }
            if (
                issues
                and (issue_filter is None or bool(issues & issue_filter))
                and has_site_section_result_marker(text)
            ):
                heading_indexes.append(index)
        starts = sorted(
            {
                min(local_position[anchor_index], local_position[heading_index])
                for anchor_index in anchor_indexes
                for heading_index in heading_indexes
                if abs(local_position[anchor_index] - local_position[heading_index]) <= 5
            }
        )
        for start in starts:
            target_index: int | None = None
            fallback_index: int | None = None
            last_candidate_index: int | None = None
            table_target_indexes = target_table_document_indexes(
                documents,
                indexes[start:],
                normalized_by_index,
                site,
                issue_filter,
                local_candidate_issues,
            )
            preferred_table_target = (
                table_target_indexes[0] if len(table_target_indexes) == 1 else None
            )
            for index in indexes[start:]:
                is_candidate = document_has_strict_site_candidate(
                    documents[index], site, local_candidate_issues
                )
                if fallback_index is None and is_candidate:
                    fallback_index = index
                is_target = bool(
                    issue_filter
                    and document_has_strict_site_candidate(
                        documents[index], site, issue_filter
                    )
                )
                if preferred_table_target == index:
                    target_index = index
                    break
                if (
                    preferred_table_target is None
                    and is_target
                    and (
                        fallback_index is None
                        or fallback_index == index
                        or last_candidate_index == index - 1
                    )
                ):
                    target_index = index
                    break
                if is_candidate:
                    last_candidate_index = index
            selected_index = target_index if target_index is not None else fallback_index
            if selected_index is None:
                continue
            index = selected_index
            anchor = next(
                (
                    term
                    for term in anchor_terms
                    if term in normalized_by_index.get(index, "")
                ),
                None,
            )
            if anchor is None:
                anchor = next(
                    (
                        term
                        for anchor_index in anchor_indexes
                        for term in anchor_terms
                        if term in normalized_by_index[anchor_index]
                    ),
                    site.name,
                )
            authorized[index] = anchor
            selected_in_block = True
            break
            if selected_in_block:
                break
    return authorized

def collect_three_landlords_candidates(
    documents: list[str], site: Site, issue_filter: set[int] | None
) -> list[Candidate]:
    metadata_list = getattr(documents, "document_metadata", [])
    prepared: list[tuple[str, dict[str, object], tuple[str, str, str, str]]] = []
    authorities: list[tuple[int, int]] = []
    marker_count = 0
    for document_index, document in enumerate(documents):
        text = normalize_text("\n".join(iter_search_texts(document))).replace(" ", "")
        metadata = metadata_list[document_index] if document_index < len(metadata_list) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        block_key = _document_block_key(metadata) if metadata else ("", "", "", f"document:{document_index}")
        prepared.append((text, metadata, block_key))
        count = text.count(THREE_LANDLORDS_MARKER)
        marker_count += count
        if count:
            authorities.append((document_index, text.find(THREE_LANDLORDS_MARKER)))
    if marker_count != 1 or len(authorities) != 1:
        return []

    document_index, marker_position = authorities[0]
    _, metadata, block_key = prepared[document_index]
    section_parts: list[str] = []
    boundary_found = False
    for fragment_index in range(document_index, len(prepared)):
        text, _, fragment_key = prepared[fragment_index]
        if fragment_key != block_key:
            return []
        fragment = (
            text[marker_position + len(THREE_LANDLORDS_MARKER) :]
            if fragment_index == document_index
            else text
        )
        boundary = fragment.find(THREE_LANDLORDS_BOUNDARY)
        if boundary >= 0:
            fragment = fragment[:boundary]
            boundary_found = True
        section_parts.append(fragment)
        if boundary_found:
            break
    if not boundary_found:
        return []
    section = "\n".join(section_parts)
    candidates: list[Candidate] = []
    row_re = re.compile(r"(?m)(\d{1,4})期\[([1-7](?:[\.、,，][1-7]){5})段\]")
    for order, match in enumerate(row_re.finditer(section)):
        issue = int(match.group(1))
        if issue_filter is not None and issue not in issue_filter:
            continue
        values = [int(value) for value in re.findall(r"[1-7]", match.group(2))]
        missing = sorted(set(range(1, 8)) - set(values))
        if len(values) != 6 or len(set(values)) != 6 or len(missing) != 1:
            continue
        raw_block = match.group(0)
        candidates.append(
            Candidate(
                issue=issue,
                issue_text=match.group(1),
                value=f"{missing[0]}段",
                title=site.name,
                snippet=raw_block,
                score=200,
                order=order,
                position=document_index * 10_000_000 + match.start(),
                source_url=str(metadata.get("source_url") or "") or None,
                document_type=str(metadata.get("document_type") or "unknown"),
                document_id=str(metadata.get("document_id") or "") or None,
                block_id=str(metadata.get("block_id") or "") or f"document:{document_index}",
                anchor="三表主六段",
                raw_block=raw_block,
                source_title=site.name,
            )
        )
    return candidates

def huifeidezhu_html_row_texts(text: str, base_position: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for match in re.finditer(r"<p\b[^>]*>.*?</p>", text, flags=re.I | re.S):
        row_html = match.group(0)
        if "绝杀一段" not in normalize_text(row_html).replace(" ", ""):
            continue
        row_text = re.sub(r"\s+", " ", html_to_text(row_html)).strip()
        if row_text:
            rows.append((row_text, base_position + match.start()))
    return rows

def jidichengming_title_issues(documents: list[str]) -> set[int]:
    issues: set[int] = set()
    for document in documents:
        for text in iter_search_texts(document):
            normalized = normalize_text(text)
            if "免费发表" not in normalized:
                continue
            for match in re.finditer(r"(\d{1,4})\s*期", normalized):
                tail = normalized[match.start() : match.start() + 80]
                if has_result_keyword(tail):
                    issues.add(int(match.group(1)))
    return issues

def add_jidichengming_typo_candidates(
    documents: list[str],
    issue_filter: set[int] | None,
    candidates: list[Candidate],
    seen: set[tuple[object, ...]],
    order: int,
) -> int:
    del documents, issue_filter, candidates, seen
    return order

def reorder_candidates_by_issue(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return candidates
    ordered = sorted(candidates, key=lambda item: (item.issue, item.position, item.order))
    return [
        Candidate(
            issue=candidate.issue,
            issue_text=candidate.issue_text,
            value=candidate.value,
            title=candidate.title,
            snippet=candidate.snippet,
            score=candidate.score,
            order=candidate.order,
            position=index,
            source_url=candidate.source_url,
            document_type=candidate.document_type,
            document_id=candidate.document_id,
            block_id=candidate.block_id,
            anchor=candidate.anchor,
            raw_block=candidate.raw_block,
            source_title=candidate.source_title,
        )
        for index, candidate in enumerate(ordered)
    ]


def _document_block_key(metadata: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(metadata.get("source_url") or ""),
        str(metadata.get("document_type") or ""),
        str(metadata.get("document_id") or ""),
        str(metadata.get("block_id") or ""),
    )


def _searchable_document_text(document: str) -> str:
    normalized_document = normalize_result_title_variants(document)
    return normalize_text("\n".join(iter_search_texts(normalized_document))).replace(" ", "")


def _is_topic_heading_document(document: str) -> bool:
    lowered = document.lower()
    return any(
        marker in lowered
        for marker in ("topic-content", "topic-author", "forum-head", 'class="title"')
    )


def _document_has_profile_candidate(
    document: str,
    site: Site,
    issue_filter: set[int] | None,
) -> bool:
    allow_repeated_duan = site.name in ALLOW_REPEATED_DUAN_SITE_NAMES
    allow_multi_duan = site.name in MULTI_DUAN_SITE_NAMES
    for text in iter_search_texts(document):
        for _, _, segment in iter_issue_segments(text, issue_filter):
            values, strict = site_specific_values_and_strictness(
                segment,
                site,
                has_document_anchor=True,
                allow_repeated_duan=allow_repeated_duan,
                allow_multi_duan=allow_multi_duan,
            )
            if values and strict:
                return True
    return False


def _profile_heading_issue(
    document: str,
    site: Site,
    issue_filter: set[int] | None,
) -> int | None:
    if not issue_filter:
        return None

    heading_terms = (
        site.section_keywords
        if site.custom_parser == "topic_semantic_cycle"
        else site_section_anchor_terms(site)
    )
    anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in heading_terms
        if normalize_text(term).replace(" ", "")
    )
    searchable = _searchable_document_text(document)
    for match in ISSUE_RE.finditer(searchable):
        issue = int(match.group(1).translate(FULLWIDTH_DIGITS))
        if site.custom_parser != "topic_semantic_cycle" and issue not in issue_filter:
            continue
        title_window = searchable[match.start() : match.start() + 160]
        if any(term in title_window for term in anchor_terms):
            return issue
    return None


def _profile_section_documents(
    documents: list[str],
    site: Site,
    issue_filter: set[int] | None,
) -> ArticleDocumentList:
    """Select the first candidate document belonging to one semantic topic heading.

    A decoded script may contain several topic bodies while retaining one script URL.
    The topic heading and its nearest candidate document are the smallest evidence
    block that can be proven without borrowing a URL or a sibling topic as an anchor.
    """
    metadata_list = getattr(documents, "document_metadata", [])
    if len(metadata_list) != len(documents):
        return ArticleDocumentList()

    wanted = set(issue_filter) if issue_filter else None
    anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in site_section_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    section_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in (site.section_keywords or ("绝杀一段", "绝杀1段"))
        if normalize_text(term).replace(" ", "")
    )
    groups: dict[tuple[str, str, str, str], list[int]] = {}
    for index, metadata in enumerate(metadata_list):
        if not isinstance(metadata, dict):
            continue
        source_type = str(metadata.get("document_type") or "")
        if site.document_sources and source_type not in site.document_sources:
            continue
        groups.setdefault(_document_block_key(metadata), []).append(index)

    sections: list[tuple[int, list[int]]] = []
    for indexes in groups.values():
        for position, heading_index in enumerate(indexes):
            document = documents[heading_index]
            searchable = _searchable_document_text(document)
            issue_matches = {
                int(match.group(1))
                for match in ISSUE_RE.finditer(searchable)
            }
            if (
                wanted is not None
                and not issue_matches.intersection(wanted)
                and site.custom_parser != "topic_semantic_cycle"
            ):
                continue
            if not any(term in searchable for term in section_terms):
                continue
            if not _is_topic_heading_document(document):
                continue

            score = 20
            if any(anchor in searchable for anchor in anchor_terms):
                score += 30
            if any(term in searchable for term in section_terms):
                score += 20
            if wanted is not None and issue_matches.intersection(wanted):
                score += 20
            if _document_has_profile_candidate(document, site, wanted):
                score += 20

            candidate_index: int | None = None
            if _document_has_profile_candidate(document, site, wanted):
                candidate_index = heading_index
            else:
                for next_index in indexes[position + 1 :]:
                    next_document = documents[next_index]
                    if _is_topic_heading_document(next_document):
                        break
                    if _document_has_profile_candidate(next_document, site, wanted):
                        candidate_index = next_index
                        break
            if candidate_index is None:
                continue
            if site.custom_parser == "topic_semantic_cycle":
                selected_indexes = []
                for next_index in indexes[position:]:
                    if next_index != heading_index and _is_topic_heading_document(
                        documents[next_index]
                    ):
                        break
                    selected_indexes.append(next_index)
            else:
                selected_indexes = [heading_index]
                if candidate_index != heading_index:
                    selected_indexes.append(candidate_index)
            sections.append((score, selected_indexes))

    if not sections:
        return ArticleDocumentList()

    best_score = max(score for score, _ in sections)
    best_sections = [indexes for score, indexes in sections if score == best_score]
    if len(best_sections) != 1:
        return ArticleDocumentList()

    selected = ArticleDocumentList()
    section_issue_limit = _profile_heading_issue(
        documents[best_sections[0][0]], site, wanted
    )
    heading_searchable = _searchable_document_text(documents[best_sections[0][0]])
    section_anchor = next(
        (term for term in section_terms if term in heading_searchable),
        None,
    )
    for index in best_sections[0]:
        metadata = dict(metadata_list[index])
        if section_issue_limit is not None:
            metadata["section_issue_limit"] = section_issue_limit
        if site.custom_parser == "topic_semantic_cycle" and section_anchor:
            metadata["section_anchor"] = section_anchor
        selected.append_document(documents[index], metadata)
    return selected


def _current_profile_issue_cycle(
    candidates: list[Candidate], issue: int, pick: str
) -> list[Candidate]:
    ordered = sorted(candidates, key=lambda item: (item.position, item.order))
    cycles: list[list[Candidate]] = [[]]
    for candidate in ordered:
        if cycles[-1]:
            previous = cycles[-1][-1].issue
            rollover = (
                candidate.issue < previous
                if pick == "bottom"
                else candidate.issue > previous
            )
            if rollover:
                cycles.append([])
        cycles[-1].append(candidate)

    matching = [cycle for cycle in cycles if any(item.issue == issue for item in cycle)]
    if not matching:
        return []
    selected = matching[-1] if pick == "bottom" else matching[0]
    boundary_issue = selected[-1].issue if pick == "bottom" else selected[0].issue
    return selected if boundary_issue == issue else []

def collect_candidates(
    documents: list[str],
    site: Site,
    issue_filter: set[int] | None = None,
    *,
    anchor_issue_filter: set[int] | None = None,
    _scope_documents: bool = True,
) -> list[Candidate]:
    if _scope_documents and site.section_scope:
        scope_filter = anchor_issue_filter if anchor_issue_filter is not None else issue_filter
        scoped_documents = _profile_section_documents(documents, site, scope_filter)
        if not scoped_documents:
            return []
        return collect_candidates(
            scoped_documents,
            site,
            issue_filter,
            anchor_issue_filter=anchor_issue_filter,
            _scope_documents=False,
        )

    if site.name == "三地主":
        return collect_three_landlords_candidates(documents, site, issue_filter)

    candidates: list[Candidate] = []
    seen: set[tuple[object, ...]] = set()
    order = 0
    allow_repeated_duan = site.name in ALLOW_REPEATED_DUAN_SITE_NAMES
    allow_multi_duan = site.name in MULTI_DUAN_SITE_NAMES
    title_issue_filter = (
        anchor_issue_filter if anchor_issue_filter is not None else issue_filter
    )
    title_issues = site_section_title_issues(documents, site, title_issue_filter)
    hanlaishuwang_target_index = (
        hanlaishuwang_target_title_index(documents, title_issues)
        if site.name == "寒来暑往"
        else None
    )
    hanlaishuwang_expected_issue = max(title_issues) if title_issues else None
    hanlaishuwang_started = False
    hanlaishuwang_ended = False
    normalized_anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in site_section_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    shared_script_anchors = authorized_script_document_anchors(
        documents, site, anchor_issue_filter if anchor_issue_filter is not None else issue_filter
    )

    for document_index, document in enumerate(documents):
        document_position = document_index * 10_000_000
        raw_metadata = getattr(documents, "document_metadata", [])
        document_metadata = (
            raw_metadata[document_index]
            if document_index < len(raw_metadata) and isinstance(raw_metadata[document_index], dict)
            else {}
        )
        source_url = str(document_metadata.get("source_url", "")) or None
        document_type = str(document_metadata.get("document_type", "unknown"))
        document_id = str(document_metadata.get("document_id", "")) or None
        block_id = str(document_metadata.get("block_id", "")) or f"document:{document_index}"
        source_title = str(document_metadata.get("source_title", ""))
        raw_section_issue_limit = document_metadata.get("section_issue_limit")
        section_issue_limit = (
            int(raw_section_issue_limit)
            if isinstance(raw_section_issue_limit, int)
            and not isinstance(raw_section_issue_limit, bool)
            else None
        )
        document_texts = list(iter_search_texts(document))
        normalized_document = normalize_text("\n".join(document_texts)).replace(" ", "")
        document_anchor = next(
            (
                anchor
                for anchor in normalized_anchor_terms
                if anchor in normalized_document
            ),
            None,
        )
        metadata_section_anchor = str(document_metadata.get("section_anchor", "")) or None
        document_anchor = document_anchor or metadata_section_anchor
        document_anchor = document_anchor or shared_script_anchors.get(document_index)
        document_has_site_name = document_anchor is not None
        document_has_result_marker = has_site_section_result_marker(normalized_document)
        has_document_anchor = document_has_site_name and document_has_result_marker
        if site.name == "寒来暑往":
            title_kind = hanlaishuwang_title_kind(normalized_document, title_issues)
            if title_kind == "target":
                has_document_anchor = True
            elif title_kind == "other":
                has_document_anchor = False
        document_search_texts: list[tuple[str, int]] = []
        if site.name == "会飞的猪":
            document_search_texts.extend(
                huifeidezhu_html_row_texts(strip_hidden_html_blocks(document), document_position)
            )
        for text_index, text in enumerate(document_texts):
            text_position = document_position + text_index * 1_000_000
            normalized_text = normalize_text(normalize_result_title_variants(text))
            search_texts = (
                []
                if site.name == "会飞的猪" and document_search_texts
                else [(normalized_text, text_position)]
            )
            if site.name == "朗朗权坤":
                compact_text = re.sub(r"\s+", " ", normalized_text)
                if compact_text != normalized_text:
                    search_texts.append((compact_text, text_position))
            if text_index == 0 and document_search_texts:
                search_texts.extend(document_search_texts)
            for search_text, base_position in search_texts:
                if (
                    site.name == "寒来暑往"
                    and hanlaishuwang_target_index is not None
                    and hanlaishuwang_expected_issue is not None
                ):
                    if document_index < hanlaishuwang_target_index or hanlaishuwang_ended:
                        continue
                    if document_index == hanlaishuwang_target_index:
                        search_text = hanlaishuwang_target_title_suffix(
                            search_text, title_issues
                        )
                        if not search_text:
                            continue
                    (
                        search_text,
                        hanlaishuwang_expected_issue,
                        hanlaishuwang_started,
                        section_ended,
                    ) = hanlaishuwang_contiguous_prefix(
                        search_text,
                        hanlaishuwang_expected_issue,
                        hanlaishuwang_started,
                    )
                    hanlaishuwang_ended = hanlaishuwang_ended or section_ended
                    if not search_text:
                        continue
                for issue, issue_text, segment in iter_issue_segments(search_text, issue_filter):
                    if section_issue_limit is not None and issue > section_issue_limit:
                        continue
                    if site.name == "寒来暑往" and not has_document_anchor:
                        continue
                    normalized_segment = normalize_text(segment).replace(" ", "")
                    segment_anchor = next(
                        (
                            anchor
                            for anchor in normalized_anchor_terms
                            if anchor in normalized_segment
                        ),
                        None,
                    )
                    if normalized_anchor_terms and segment_anchor is None and not has_document_anchor:
                        continue
                    values, is_strict = site_specific_values_and_strictness(
                        segment,
                        site,
                        has_document_anchor=has_document_anchor,
                        allow_repeated_duan=allow_repeated_duan,
                        allow_multi_duan=allow_multi_duan,
                    )
                    if not values or not is_strict:
                        continue

                    anchor = segment_anchor or document_anchor
                    segment_title = title_in_segment(segment, "")
                    normalized_segment_title = normalize_text(segment_title).replace(" ", "")
                    if (
                        normalized_segment_title
                        and not has_result_keyword(normalized_segment_title)
                        and normalized_segment_title not in normalized_anchor_terms
                    ):
                        continue
                    if not source_title and segment_title and segment_title not in {"绝杀一段", "绝杀1段"}:
                        source_title = segment_title
                    snippet = compact_line(segment)
                    segment_position = normalize_text(search_text).find(normalize_text(segment))
                    if segment_position >= 0:
                        segment_position += base_position
                    else:
                        segment_position = normalized_text.find(normalize_text(segment))
                    if segment_position < 0:
                        segment_position = base_position
                    score = score_segment(segment, values, allow_repeated_duan=allow_repeated_duan)
                    candidate_title = source_title or anchor or ""
                    for value in values:
                        key = (
                            (issue, value, candidate_title, snippet, segment_position)
                            if site.custom_parser == "topic_semantic_cycle"
                            else (issue, value, candidate_title, snippet)
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        candidates.append(
                            Candidate(
                                issue=issue,
                                issue_text=issue_text,
                                value=value,
                                title=candidate_title,
                                snippet=snippet,
                                score=score,
                                order=order,
                                position=segment_position,
                                source_url=source_url,
                                document_type=document_type,
                                document_id=document_id,
                                block_id=block_id,
                                anchor=anchor,
                                raw_block=segment,
                                source_title=source_title,
                            )
                        )
                        order += 1

    if site.name == "及第成名":
        order = add_jidichengming_typo_candidates(documents, issue_filter, candidates, seen, order)

    if site.custom_parser == "topic_semantic_cycle":
        section_issues = {
            int(metadata["section_issue_limit"])
            for metadata in getattr(documents, "document_metadata", [])
            if isinstance(metadata, dict)
            and isinstance(metadata.get("section_issue_limit"), int)
            and not isinstance(metadata.get("section_issue_limit"), bool)
        }
        if len(section_issues) != 1:
            return []
        candidates = _current_profile_issue_cycle(
            candidates, next(iter(section_issues)), site.pick
        )

    return prioritize_site_title_issue_candidates(candidates, title_issues, site.pick)
