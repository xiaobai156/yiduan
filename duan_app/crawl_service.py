# -*- coding: utf-8 -*-
import time
from urllib.error import HTTPError, URLError

from duan_app.constants import MISS_RETRY_REASONS
from duan_app.documents import collect_documents
from duan_app.domain import Candidate, Site, SiteResult
from duan_app.fetcher import CurlFetchError
from duan_app.parsing.custom import collect_candidates
from duan_app.persistence.cache import build_recent_cache_record, mark_cache_record_failed
from duan_app.persistence.outputs import classify_open_error, failure_reason_from_line, format_failure_line, is_network_retry_reason
from duan_app.selection import candidate_window, find_matches_from_candidates, ordered_candidate_groups
from duan_app.validation import diagnose_issue_reasons, explicit_failure_reason, issue_numbers_in_documents, refine_missing_issue_reason, source_failure_reason, summarize_issue_reasons


def _nearby_document_issues(documents: list[str], wanted_issues: set[int]) -> list[int]:
    found = issue_numbers_in_documents(documents)
    if not found:
        return []
    if found & wanted_issues:
        return sorted(found & wanted_issues)
    target = min(wanted_issues) if wanted_issues else 0
    return sorted(sorted(found, key=lambda issue: (abs(issue - target), issue))[:3])


def _validation_failure_context(
    candidates: list[Candidate],
    documents: list[str],
    wanted_issues: set[int],
    pick: str,
    reason: str,
) -> tuple[str, list[int], str]:
    groups = ordered_candidate_groups(candidates, pick)
    if groups:
        window = candidate_window(groups, pick)
        actual_issues = list(dict.fromkeys(candidate.issue for candidate in window))
        side = "顶部" if pick == "top" else "尾部"
        location = f"{side}最新{len(window)}个有效候选"
        if "组内无指定期数" in reason:
            actual_text = "、".join(f"{issue}期" for issue in actual_issues)
            target_text = "、".join(f"{issue}期" for issue in sorted(wanted_issues))
            reason = f"{location}期数为[{actual_text}]，不含指定{target_text}"
        return location, actual_issues, reason

    if "专属锚点" in reason:
        location = "目标URL内已抓取文档（专属栏目锚点缺失）"
    else:
        location = "目标URL内已抓取文档（未形成高可信候选）"
    return location, _nearby_document_issues(documents, wanted_issues), reason


def process_site(
    index: int,
    site: Site,
    timeout: int,
    verify_ssl: bool,
    wanted_issues: set[int],
    issues_label: str,
) -> SiteResult:
    search_issues = wanted_issues

    try:
        script_errors: list[str] = []
        issue_reasons: dict[int, str] = {}
        matches: list[Candidate] = []
        documents: list[str] = []
        candidates: list[Candidate] = []
        reason = ""
        retry_count = site.retry
        page_attempts = max(6, site.retry + 4)
        site_verify_ssl = verify_ssl and not site.allow_insecure

        for attempt in range(retry_count + 1):
            documents, script_errors = collect_documents(
                site.url,
                timeout,
                site_verify_ssl,
                page_attempts=page_attempts,
                cache_bust_first=site.cache_bust or attempt > 0,
                issue_filter=search_issues,
                site_name=site.name,
                pick=site.pick,
                api_url=site.api_url,
            )
            candidates = collect_candidates(
                documents, site, anchor_issue_filter=search_issues
            )
            matches = find_matches_from_candidates(candidates, search_issues, site)
            if any(match.issue in wanted_issues for match in matches):
                break

            issue_reasons = diagnose_issue_reasons(documents, wanted_issues, site, candidates)
            reason = summarize_issue_reasons(issue_reasons, wanted_issues)
            reason = refine_missing_issue_reason(reason, documents, wanted_issues)
            if not any(item in reason for item in MISS_RETRY_REASONS):
                break
            if attempt < retry_count:
                time.sleep(1.5 + attempt)
    except (HTTPError, URLError, TimeoutError, OSError, CurlFetchError) as exc:
        reason = classify_open_error(exc)
        fail_line = format_failure_line(
            site,
            wanted_issues,
            stage="抓取",
            location="目标URL",
            reason=f"打开失败[{reason}]：{exc}",
        )
        cache_record = build_recent_cache_record(index, site, [], [], error=f"{type(exc).__name__}: {exc}")
        return SiteResult(index, site, [], fail_line, f"FAIL 打开失败[{reason}]：{exc}", cache_record=cache_record)
    except Exception as exc:
        fail_line = format_failure_line(
            site,
            wanted_issues,
            stage="解析",
            location="目标URL的抓取结果",
            reason=f"解析失败：{type(exc).__name__}: {exc}",
        )
        cache_record = build_recent_cache_record(index, site, [], [], error=f"{type(exc).__name__}: {exc}")
        return SiteResult(index, site, [], fail_line, f"FAIL 解析失败：{type(exc).__name__}: {exc}", cache_record=cache_record)

    if any(match.issue in wanted_issues for match in matches):
        if site.confirm:
            try:
                first_values = {
                    match.issue: match.value
                    for match in matches
                    if match.issue in wanted_issues
                }
                confirm_documents, _ = collect_documents(
                    site.url,
                    timeout,
                    site_verify_ssl,
                    page_attempts=page_attempts,
                    cache_bust_first=True,
                    issue_filter=search_issues,
                    site_name=site.name,
                    pick=site.pick,
                    api_url=site.api_url,
                )
                confirm_candidates = collect_candidates(
                    confirm_documents, site, anchor_issue_filter=search_issues
                )
                confirm_matches = find_matches_from_candidates(confirm_candidates, search_issues, site)
                confirm_values = {
                    match.issue: match.value
                    for match in confirm_matches
                    if match.issue in wanted_issues
                }
                if confirm_values != first_values:
                    fail_line = format_failure_line(
                        site,
                        wanted_issues,
                        stage="二次确认",
                        location="目标期首次结果与二次抓取结果",
                        reason=f"二次确认结果冲突[首次{first_values}，确认{confirm_values}]",
                        actual_issues=sorted(set(first_values) | set(confirm_values)),
                    )
                    cache_record = build_recent_cache_record(
                        index,
                        site,
                        [],
                        script_errors,
                        error="二次确认结果冲突",
                    )
                    return SiteResult(
                        index,
                        site,
                        [],
                        fail_line,
                        "MISS 二次确认结果冲突",
                        issue_reasons,
                        cache_record,
                    )
                if confirm_values:
                    matches = confirm_matches
                    documents = confirm_documents
                    candidates = confirm_candidates
                    issue_reasons = diagnose_issue_reasons(confirm_documents, wanted_issues, site, confirm_candidates)
            except Exception as exc:
                fail_line = format_failure_line(
                    site,
                    wanted_issues,
                    stage="二次确认",
                    location="目标URL的二次抓取结果",
                    reason=f"二次确认失败：{type(exc).__name__}: {exc}",
                )
                cache_record = build_recent_cache_record(
                    index,
                    site,
                    [],
                    script_errors,
                    error=f"二次确认失败：{type(exc).__name__}: {exc}",
                )
                return SiteResult(
                    index,
                    site,
                    [],
                    fail_line,
                    f"MISS 二次确认失败：{type(exc).__name__}: {exc}",
                    issue_reasons,
                    cache_record,
                )
        matched_issues = {match.issue for match in matches if match.issue in wanted_issues}
        if wanted_issues - matched_issues:
            issue_reasons = diagnose_issue_reasons(documents, wanted_issues, site, candidates)
        cache_record = build_recent_cache_record(index, site, documents, script_errors, candidates)
        return SiteResult(index, site, matches, None, "OK", issue_reasons, cache_record)

    source_reason = source_failure_reason(documents, script_errors)
    reason = explicit_failure_reason(source_reason or reason or summarize_issue_reasons(issue_reasons, wanted_issues))
    reason = refine_missing_issue_reason(reason, documents, wanted_issues)
    if script_errors and not source_reason:
        reason += f"；另有 {len(script_errors)} 个脚本加载失败"
    location, actual_issues, reason = _validation_failure_context(
        candidates, documents, wanted_issues, site.pick, reason
    )
    fail_line = format_failure_line(
        site,
        wanted_issues,
        stage="校验",
        location=location,
        reason=reason,
        actual_issues=actual_issues,
    )
    cache_record = mark_cache_record_failed(
        build_recent_cache_record(index, site, documents, script_errors, candidates),
        reason,
    )
    return SiteResult(index, site, [], fail_line, f"MISS {reason}", issue_reasons, cache_record)

def should_recheck_result(result: SiteResult | None) -> bool:
    if result is None:
        return False
    if not result.fail_line:
        return False
    return is_network_retry_reason(failure_reason_from_line(result.fail_line))
