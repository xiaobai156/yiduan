# -*- coding: utf-8 -*-

from duan_app.constants import ALLOW_REPEATED_DUAN_SITE_NAMES, FULLWIDTH_DIGITS, ISSUE_RE, MULTI_DUAN_SITE_NAMES, MULTI_DUAN_VALUE_RE, OPEN_STATUS_RE
from duan_app.domain import Candidate, Site
from duan_app.parsing.custom import collect_candidates, site_section_anchor_terms
from duan_app.parsing.engine import has_body_locator, has_invalid_duan_value, has_result_keyword, iter_issue_segments, iter_search_texts, table_signature_count, values_in_segment
from duan_app.selection import candidate_conflict_issue_reasons, candidate_window_issue_reasons, scoped_candidates
from duan_app.text_utils import normalize_text


def new_issue_state() -> dict[str, bool]:
    return {
        "issue": False,
        "locator": False,
        "keyword": False,
        "open": False,
        "status": False,
        "value": False,
        "invalid": False,
        "single": False,
        "table": False,
    }

def update_issue_state(
    state: dict[str, bool],
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> None:
    normalized = normalize_text(segment)
    state["issue"] = True
    state["locator"] = state["locator"] or has_body_locator(normalized) or (
        allow_multi_duan and MULTI_DUAN_VALUE_RE.search(normalized) is not None
    )
    state["keyword"] = state["keyword"] or has_result_keyword(normalized) or (
        allow_multi_duan and MULTI_DUAN_VALUE_RE.search(normalized) is not None
    )
    state["open"] = state["open"] or ("开" in normalized)
    state["status"] = state["status"] or (OPEN_STATUS_RE.search(normalized) is not None) or (
        allow_multi_duan and MULTI_DUAN_VALUE_RE.search(normalized) is not None
    )
    state["invalid"] = state["invalid"] or has_invalid_duan_value(
        normalized,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    vals = values_in_segment(
        normalized,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    state["value"] = state["value"] or bool(vals)
    state["single"] = state["single"] or (len(vals) == 1) or (
        allow_multi_duan and len(vals) > 1
    )
    state["table"] = state["table"] or (table_signature_count(normalized) >= 2)

def reason_from_issue_state(state: dict[str, bool]) -> str:
    if not state["issue"]:
        return "无期数"
    if not state["locator"]:
        return "无定位"
    if not state["keyword"]:
        if state["table"]:
            return "段位表"
        return "无结果词"
    if not state["open"]:
        return "无开字"
    if not state["status"]:
        return "无对错"
    if state["invalid"]:
        return "段数越界"
    if not state["value"]:
        if state["table"]:
            return "表干扰"
        return "无段数"
    if not state["single"]:
        return "数量错"
    return "不合规"

def diagnose_issue_reasons(
    documents: list[str],
    wanted_issues: set[int],
    site: Site,
    candidates: list[Candidate] | None = None,
) -> dict[int, str]:
    states = {issue: new_issue_state() for issue in wanted_issues}
    allow_repeated_duan = site.name in ALLOW_REPEATED_DUAN_SITE_NAMES
    allow_multi_duan = site.name in MULTI_DUAN_SITE_NAMES
    if candidates is None:
        candidates = collect_candidates(documents, site)
    if not candidates and documents:
        anchor_terms = tuple(
            normalize_text(term).replace(" ", "")
            for term in site_section_anchor_terms(site)
            if normalize_text(term).replace(" ", "")
        )
        has_requested_issue = any(
            issue in wanted_issues
            for document in documents
            for text in iter_search_texts(document)
            for issue, _, _ in iter_issue_segments(text, wanted_issues)
        )
        has_anchor = any(
            anchor in normalize_text(document).replace(" ", "")
            for document in documents
            for anchor in anchor_terms
        )
        if has_requested_issue and anchor_terms and not has_anchor:
            return {issue: "未找到专属锚点" for issue in wanted_issues}
    scoped, scope_reason = scoped_candidates(candidates, wanted_issues, site.pick)
    conflict_reasons = candidate_conflict_issue_reasons(scoped, wanted_issues)
    window_reasons = candidate_window_issue_reasons(candidates, wanted_issues, site.pick)

    for document in documents:
        for text in iter_search_texts(document):
            for issue, _, segment in iter_issue_segments(text, wanted_issues):
                update_issue_state(
                    states[issue],
                    segment,
                    allow_repeated_duan=allow_repeated_duan,
                    allow_multi_duan=allow_multi_duan,
                )

    if scope_reason:
        return {
            issue: (
                conflict_reasons.get(issue)
                or ("段数越界" if states[issue]["invalid"] else None)
                or window_reasons.get(issue)
                or scope_reason
            )
            for issue in wanted_issues
        }

    return {
        issue: (
            conflict_reasons.get(issue)
            or ("段数越界" if state["invalid"] else None)
            or window_reasons.get(issue)
            or reason_from_issue_state(state)
        )
        for issue, state in states.items()
    }

def summarize_issue_reasons(issue_reasons: dict[int, str], wanted_issues: set[int]) -> str:
    ordered = sorted(wanted_issues)
    if len(ordered) == 1:
        return issue_reasons.get(ordered[0], "未找到符合严格规则的结果")
    parts = [f"{issue}期{issue_reasons.get(issue, '未找到符合严格规则的结果')}" for issue in ordered]
    return "；".join(parts)

def explicit_failure_reason(reason: str | None) -> str:
    cleaned = (reason or "").strip(" ；;\r\n\t")
    return cleaned or "未找到符合严格规则的结果"

def source_failure_reason(documents: list[str], script_errors: list[str]) -> str:
    for document in documents:
        normalized = normalize_text(document)
        if "帖子不存在" in normalized:
            return "帖子不存在"

    for error in script_errors:
        if "404" in error and "/api/proxy/" in error:
            return "接口404不存在"
        if "403" in error and "/api/proxy/" in error:
            return "接口403拒绝访问"
        if "HTTP Error 403" in error:
            return "接口403拒绝访问"
        if "HTTP Error 404" in error:
            return "接口404不存在"

    return ""

def issue_numbers_in_documents(documents: list[str]) -> set[int]:
    issues: set[int] = set()
    for document in documents:
        for text in iter_search_texts(document):
            for match in ISSUE_RE.finditer(normalize_text(text)):
                try:
                    issues.add(int(match.group(1).translate(FULLWIDTH_DIGITS)))
                except ValueError:
                    continue
    return issues

def refine_missing_issue_reason(reason: str, documents: list[str], wanted_issues: set[int]) -> str:
    return reason
