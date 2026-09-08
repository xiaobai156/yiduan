# -*- coding: utf-8 -*-

from duan_app.constants import CANDIDATE_STRICT_THRESHOLD, CANDIDATE_WINDOW_LIMIT
from duan_app.domain import Candidate, Site
from duan_app.parsing.custom import collect_candidates


def pick_nearest_candidate(candidates: list[Candidate], pick: str) -> Candidate | None:
    if not candidates:
        return None

    if pick == "top":
        return min(candidates, key=lambda item: (item.position, item.order))
    return max(candidates, key=lambda item: (item.position, item.order))

def candidate_group_key(candidate: Candidate) -> tuple[int, str]:
    return (candidate.issue, candidate.value)

def ordered_candidate_groups(candidates: list[Candidate], pick: str = "top") -> list[Candidate]:
    ordered = sorted(candidates, key=lambda item: (item.position, item.order))
    groups: list[Candidate] = []
    seen: set[tuple[int, str]] = set()
    scan_order = ordered if pick == "top" else reversed(ordered)
    for candidate in scan_order:
        key = candidate_group_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        groups.append(candidate)
    if pick == "bottom":
        groups.reverse()
    return groups

def cache_value_sort_key(value: str) -> tuple[int, str]:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return (int(digits) if digits else 999, str(value))

def values_for_cache_issue(groups: list[Candidate], issue: int, pick: str) -> list[str]:
    issue_groups = [candidate for candidate in groups if candidate.issue == issue]
    if not issue_groups:
        return []

    anchor_position = (
        min(candidate.position for candidate in issue_groups)
        if pick == "top"
        else max(candidate.position for candidate in issue_groups)
    )
    values = {
        candidate.value
        for candidate in issue_groups
        if candidate.position == anchor_position
    }
    return sorted(values, key=cache_value_sort_key)

def strict_candidate_window_required(candidates: list[Candidate]) -> bool:
    if len(candidates) > CANDIDATE_STRICT_THRESHOLD:
        return True

    issue_counts: dict[int, int] = {}
    for candidate in candidates:
        issue_counts[candidate.issue] = issue_counts.get(candidate.issue, 0) + 1
        if issue_counts[candidate.issue] > 1:
            return True
    return False

def candidate_window(candidates: list[Candidate], pick: str) -> list[Candidate]:
    if pick == "top":
        return candidates[:CANDIDATE_WINDOW_LIMIT]
    return candidates[-CANDIDATE_WINDOW_LIMIT:]

def scoped_candidates(
    candidates: list[Candidate], wanted_issues: set[int], pick: str
) -> tuple[list[Candidate], str]:
    groups = ordered_candidate_groups(candidates, pick)
    if not groups:
        return [], ""

    window = candidate_window(groups, pick)
    if not any(candidate.issue in wanted_issues for candidate in window):
        side = "顶部" if pick == "top" else "尾部"
        return [], f"{side}最新{CANDIDATE_WINDOW_LIMIT}组内无指定期数"

    return window, ""

def candidate_window_issue_reasons(
    candidates: list[Candidate], wanted_issues: set[int], pick: str
) -> dict[int, str]:
    groups = ordered_candidate_groups(candidates, pick)
    if not groups:
        return {}

    window = candidate_window(groups, pick)
    window_issues = {candidate.issue for candidate in window}
    side = "顶部" if pick == "top" else "尾部"
    return {
        issue: f"{side}最新{CANDIDATE_WINDOW_LIMIT}组内无指定期数"
        for issue in wanted_issues
        if issue not in window_issues
    }

def candidate_conflict_issue_reasons(candidates: list[Candidate], wanted_issues: set[int]) -> dict[int, str]:
    values_by_issue: dict[int, set[str]] = {}
    for candidate in candidates:
        if candidate.issue not in wanted_issues:
            continue
        values_by_issue.setdefault(candidate.issue, set()).add(candidate.value)

    reasons: dict[int, str] = {}
    for issue, values in values_by_issue.items():
        if len(values) <= 1:
            continue
        values_text = "、".join(sorted(values, key=cache_value_sort_key))
        reasons[issue] = f"同一期高可信候选冲突[{values_text}]"
    return reasons

def find_matches_from_candidates(candidates: list[Candidate], wanted_issues: set[int], site: Site) -> list[Candidate]:
    # Parsers supply the authoritative candidates. Never discard conflict evidence
    # through the direction window; ambiguous sources also fail closed.
    conflict_reasons = candidate_conflict_issue_reasons(candidates, wanted_issues)
    candidates, reason = scoped_candidates(candidates, wanted_issues, site.pick)
    if reason or not candidates:
        return []

    picked: dict[int, Candidate] = {}
    for issue in wanted_issues:
        if issue in conflict_reasons:
            continue
        issue_candidates = [candidate for candidate in candidates if candidate.issue == issue]
        if not issue_candidates:
            continue

        if site.pick == "top":
            picked[issue] = min(issue_candidates, key=lambda item: (item.position, item.order))
        else:
            picked[issue] = max(issue_candidates, key=lambda item: (item.position, item.order))

    return [picked[issue] for issue in sorted(picked)]

def find_matches(documents: list[str], wanted_issues: set[int], site: Site) -> list[Candidate]:
    return find_matches_from_candidates(collect_candidates(documents, site), wanted_issues, site)
