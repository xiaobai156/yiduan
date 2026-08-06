# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from duan_app.config import load_sites_config
from duan_app.documents import collect_documents
from duan_app.domain import ArticleDocumentList, Candidate, Site
from duan_app.parsing.custom import (
    collect_candidates,
    has_site_section_result_marker,
    site_section_anchor_terms,
)
from duan_app.parsing.engine import iter_search_texts
from duan_app.selection import (
    candidate_conflict_issue_reasons,
    candidate_window,
    find_matches_from_candidates,
    ordered_candidate_groups,
)
from duan_app.text_utils import compact_line, normalize_text


FAILURE_LINE_RE = re.compile(
    r"^失败\s+(?P<name>.*?)\s+(?P<url>https?://\S+)\s+方向:(?P<pick>top|bottom)\b",
    re.M,
)

RESULT_TITLE_VARIANTS = (
    "稳杀一段",
    "必杀一段",
    "稳禁一段",
    "绝禁一段",
)
RESULT_TITLE_VARIANT_RE = re.compile(
    "|".join(re.escape(variant) for variant in RESULT_TITLE_VARIANTS)
)
VALIDATION_SITE_ALIASES = {
    "雷锋": ("26064c.com",),
    "赛马会第一版": ("877730c.com",),
    "赛马会第二版": ("877730c.com",),
    "白虎": ("73448b.com", "73448c.com"),
    "三地主": ("土地公", "三表主六段"),
}


def normalize_result_title_variants(text: str) -> str:
    normalized = RESULT_TITLE_VARIANT_RE.sub("绝杀一段", text)
    return re.sub(r"(?<!绝)杀(?:一|1)段", "绝杀一段", normalized)


def searchable_compact(text: str) -> str:
    return normalize_text("\n".join(iter_search_texts(text))).replace(" ", "")


def validation_anchor_terms(site: Site) -> tuple[str, ...]:
    return (*site_section_anchor_terms(site), *VALIDATION_SITE_ALIASES.get(site.name, ()))


def source_block_key(metadata: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(metadata.get("source_url", "")),
        str(metadata.get("document_type", "")),
        str(metadata.get("document_id", "")),
        str(metadata.get("block_id", "")),
    )


def with_same_script_block_anchor(
    documents: ArticleDocumentList, site: Site
) -> tuple[ArticleDocumentList, list[tuple[str, str, str, str]]]:
    anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in validation_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    anchored_blocks: set[tuple[str, str, str, str]] = set()
    for document, metadata in zip(documents, documents.document_metadata):
        key = source_block_key(metadata)
        normalized = searchable_compact(document)
        if (
            key[1] == "script"
            and key[0]
            and key[3]
            and any(anchor in normalized for anchor in anchor_terms)
            and has_site_section_result_marker(normalized)
        ):
            anchored_blocks.add(key)

    isolated = ArticleDocumentList()
    for document, metadata in zip(documents, documents.document_metadata):
        key = source_block_key(metadata)
        normalized = searchable_compact(document)
        if key in anchored_blocks and not any(anchor in normalized for anchor in anchor_terms):
            document = f"{site.name}\n{document}"
        isolated.append_document(document, metadata)
    return isolated, sorted(anchored_blocks)


def with_local_script_topic_section(
    documents: ArticleDocumentList, site: Site, issue: int
) -> tuple[ArticleDocumentList, list[tuple[str, str, str, str]]]:
    anchor_terms = tuple(
        normalize_text(term).replace(" ", "")
        for term in validation_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    block_indexes: dict[tuple[str, str, str, str], list[int]] = {}
    for index, metadata in enumerate(documents.document_metadata):
        key = source_block_key(metadata)
        if key[1] == "script" and key[0] and key[3]:
            block_indexes.setdefault(key, []).append(index)

    selected_indexes: set[int] = set()
    selected_blocks: set[tuple[str, str, str, str]] = set()
    issue_text = f"{issue}期"
    for key, indexes in block_indexes.items():
        normalized_by_index = {
            index: searchable_compact(documents[index])
            for index in indexes
        }
        local_positions = {index: position for position, index in enumerate(indexes)}
        anchor_indexes = [
            index
            for index in indexes
            if any(anchor in normalized_by_index[index] for anchor in anchor_terms)
        ]
        heading_indexes = [
            index
            for index in indexes
            if issue_text in normalized_by_index[index]
            and has_site_section_result_marker(normalized_by_index[index])
        ]
        starts = sorted(
            {
                min(local_positions[anchor], local_positions[heading])
                for anchor in anchor_indexes
                for heading in heading_indexes
                if abs(local_positions[anchor] - local_positions[heading]) <= 5
            }
        )
        for start in starts:
            end = len(indexes)
            for position in range(start, end):
                index = indexes[position]
                candidate_document = normalize_result_title_variants(documents[index])
                local_candidates = collect_candidates(
                    [f"{site.name}\n{candidate_document}"],
                    site,
                    {issue, issue - 1},
                )
                if not local_candidates:
                    continue
                selected_indexes.add(index)
                selected_blocks.add(key)
                break
            if key in selected_blocks:
                break

    isolated = ArticleDocumentList()
    for index, (document, metadata) in enumerate(
        zip(documents, documents.document_metadata)
    ):
        if index in selected_indexes or str(metadata.get("document_type", "")) == "script":
            continue
        candidate_document = normalize_result_title_variants(document)
        normalized = searchable_compact(candidate_document)
        if (
            any(anchor in normalized for anchor in anchor_terms)
            and issue_text in normalized
            and has_site_section_result_marker(normalized)
            and collect_candidates([candidate_document], site, {issue, issue - 1})
        ):
            isolated.append_document(candidate_document, metadata)
    for index in sorted(selected_indexes):
        isolated.append_document(
            f"{site.name}\n{normalize_result_title_variants(documents[index])}",
            documents.document_metadata[index],
        )
    return isolated, sorted(selected_blocks)


def candidate_summary(candidate) -> dict[str, object]:
    return {
        "issue": candidate.issue,
        "value": candidate.value,
        "source_url": candidate.source_url,
        "document_type": candidate.document_type,
        "block_id": candidate.block_id,
        "anchor": candidate.anchor,
        "raw_block": compact_line(candidate.raw_block, 260),
    }


def evidence_documents(
    documents: ArticleDocumentList, site: Site, issue: int
) -> list[dict[str, object]]:
    anchors = tuple(
        normalize_text(term).replace(" ", "")
        for term in validation_anchor_terms(site)
        if normalize_text(term).replace(" ", "")
    )
    evidence: list[dict[str, object]] = []
    issue_text = f"{issue}期"
    for index, (document, metadata) in enumerate(
        zip(documents, documents.document_metadata)
    ):
        normalized = searchable_compact(document)
        has_anchor = any(anchor in normalized for anchor in anchors)
        has_target = issue_text in normalized and has_site_section_result_marker(normalized)
        if not has_anchor and not has_target:
            continue
        positions = [
            position
            for position in (
                normalized.find(issue_text),
                *(normalized.find(anchor) for anchor in anchors),
            )
            if position >= 0
        ]
        position = min(positions) if positions else 0
        evidence.append(
            {
                "index": index,
                "has_anchor": has_anchor,
                "has_target": has_target,
                "source_key": list(source_block_key(metadata)),
                "snippet": compact_line(
                    normalized[max(0, position - 100) : position + 420], 520
                ),
            }
        )
    return evidence


def three_landlords_candidates(
    documents: ArticleDocumentList, site: Site, issue_filter: set[int]
) -> list[Candidate]:
    if site.name != "三地主":
        return []
    marker = "[三表主六段]√"
    authorities: list[tuple[int, str]] = []
    for index, document in enumerate(documents):
        searchable = normalize_text("\n".join(iter_search_texts(document)))
        if marker in searchable.replace(" ", ""):
            authorities.append((index, searchable))
    if len(authorities) != 1:
        return []

    document_index, text = authorities[0]
    compact = text.replace(" ", "")
    marker_position = compact.find(marker)
    section_start = marker_position + len(marker)
    next_marker = compact.find("____________★____________", section_start)
    section = compact[section_start : next_marker if next_marker >= 0 else len(compact)]
    metadata = documents.document_metadata[document_index]
    candidates: list[Candidate] = []
    row_re = re.compile(
        r"(?m)(\d{1,4})期\[([1-7](?:[\.、,，][1-7]){5})段\]"
    )
    for order, match in enumerate(row_re.finditer(section)):
        issue = int(match.group(1))
        if issue not in issue_filter:
            continue
        values = [int(value) for value in re.findall(r"[1-7]", match.group(2))]
        if len(values) != 6 or len(set(values)) != 6:
            continue
        missing = sorted(set(range(1, 8)) - set(values))
        if len(missing) != 1:
            continue
        candidates.append(
            Candidate(
                issue=issue,
                issue_text=match.group(1),
                value=f"{missing[0]}段",
                title=site.name,
                snippet=match.group(0),
                score=200,
                order=order,
                position=match.start(),
                source_url=str(metadata.get("source_url", "")) or None,
                document_type=str(metadata.get("document_type", "unknown")),
                document_id=str(metadata.get("document_id", "")) or None,
                block_id=str(metadata.get("block_id", "")) or None,
                anchor="三表主六段",
                raw_block=match.group(0),
            )
        )
    return candidates


def validate_site(site: Site, issue: int, timeout: int) -> dict[str, object]:
    result: dict[str, object] = {
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "target_issue": issue,
    }
    try:
        documents, errors = collect_documents(
            site.url,
            timeout,
            True,
            page_attempts=max(6, site.retry + 4),
            cache_bust_first=True,
            issue_filter={issue, issue - 1},
            site_name=site.name,
            pick=site.pick,
            api_url=site.api_url,
        )
        formal_candidates = collect_candidates(
            documents, site, anchor_issue_filter={issue}
        )
        formal_matches = find_matches_from_candidates(formal_candidates, {issue}, site)
        isolated_documents, anchored_blocks = with_local_script_topic_section(
            documents, site, issue
        )
        isolated_candidates = (
            three_landlords_candidates(documents, site, {issue, issue - 1, issue - 2, 999})
            if site.name == "三地主"
            else collect_candidates(isolated_documents, site)
        )
        target_matches = find_matches_from_candidates(isolated_candidates, {issue}, site)
        adjacent_matches = find_matches_from_candidates(isolated_candidates, {issue - 1}, site)
        nonexistent_matches = find_matches_from_candidates(isolated_candidates, {999}, site)
        groups = ordered_candidate_groups(isolated_candidates, site.pick)
        window = candidate_window(groups, site.pick)
        conflicts = candidate_conflict_issue_reasons(isolated_candidates, {issue, issue - 1})
        result.update(
            {
                "status": "validated" if len(target_matches) == 1 and issue not in conflicts else "failed",
                "document_count": len(documents),
                "fetch_errors": errors,
                "evidence_documents": evidence_documents(documents, site, issue),
                "formal_matches": [candidate_summary(item) for item in formal_matches],
                "anchored_script_blocks": [list(key) for key in anchored_blocks],
                "target_matches": [candidate_summary(item) for item in target_matches],
                "all_target_candidates": [
                    candidate_summary(item)
                    for item in isolated_candidates
                    if item.issue == issue
                ],
                "adjacent_matches": [candidate_summary(item) for item in adjacent_matches],
                "nonexistent_matches": [candidate_summary(item) for item in nonexistent_matches],
                "direction_window": [candidate_summary(item) for item in window],
                "conflicts": conflicts,
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure", type=Path, required=True)
    parser.add_argument("--sites", type=Path, default=Path("sites.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--issue", type=int, default=215)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    failure_text = args.failure.read_text(encoding="utf-8-sig")
    requested = {
        match.group("name"): (match.group("url"), match.group("pick"))
        for match in FAILURE_LINE_RE.finditer(failure_text)
    }
    configured = {site.name: site for site in load_sites_config(args.sites)}
    missing = sorted(set(requested) - set(configured))
    identity_mismatches = sorted(
        name
        for name, (url, pick) in requested.items()
        if name in configured
        and (configured[name].url != url or configured[name].pick != pick)
    )
    if missing or identity_mismatches:
        raise SystemExit(
            f"失败清单身份不一致：missing={missing}, mismatches={identity_mismatches}"
        )

    results: list[dict[str, object]] = []
    selected = [configured[name] for name in requested]
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(selected)))) as executor:
        futures = {
            executor.submit(validate_site, site, args.issue, args.timeout): site
            for site in selected
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{len(results)}/{len(selected)} {result['name']} "
                f"{result['pick']} {result['status']}"
            )

    results.sort(key=lambda item: selected.index(configured[str(item["name"])]))
    payload = {
        "schema": "duan_215_failure_validation.v1",
        "issue": args.issue,
        "site_count": len(selected),
        "validated_count": sum(item.get("status") == "validated" for item in results),
        "failed_count": sum(item.get("status") == "failed" for item in results),
        "error_count": sum(item.get("status") == "error" for item in results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"SUMMARY sites={payload['site_count']} validated={payload['validated_count']} "
        f"failed={payload['failed_count']} errors={payload['error_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
