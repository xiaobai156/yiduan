# -*- coding: utf-8 -*-
import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import duan_crawler as crawler


DEFAULT_CASES_PATH = Path(__file__).with_name("failed_site_cases.json")


@dataclass(frozen=True)
class FailedSiteCase:
    name: str
    url: str
    pick: str
    issues: tuple[int, ...]
    api_url: str | None = None


def load_cases(path: Path) -> list[FailedSiteCase]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise ValueError("失败站点清单必须是数组，或包含 cases 数组")

    cases: list[FailedSiteCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("失败站点清单存在非对象项目")
        name = str(raw_case.get("name", "")).strip()
        url = str(raw_case.get("url", "")).strip()
        pick = crawler.normalize_pick(raw_case.get("pick", ""))
        raw_issues = raw_case.get("issues", raw_case.get("periods"))
        if raw_issues is None:
            raw_issues = [raw_case.get("period")]
        if isinstance(raw_issues, (str, int)):
            raw_issues = [raw_issues]
        if not name or not url or pick not in {"top", "bottom"} or not isinstance(raw_issues, list):
            raise ValueError(f"失败站点配置不完整：{raw_case}")
        typed_issues = cast(list[str | int], raw_issues)
        issues = tuple(sorted({int(issue) for issue in typed_issues if int(issue) > 0}, reverse=True))
        if not issues:
            raise ValueError(f"失败站点没有有效期数：{name}")
        api_url = str(raw_case["api_url"]).strip() if raw_case.get("api_url") else None
        cases.append(FailedSiteCase(name, url, pick, issues, api_url))
    return cases


def _ordered_values(candidates: list[crawler.Candidate], issues: tuple[int, ...]) -> dict[int, list[str]]:
    values: dict[int, list[str]] = {issue: [] for issue in issues}
    for candidate in candidates:
        if candidate.issue in values and candidate.value not in values[candidate.issue]:
            values[candidate.issue].append(candidate.value)
    return {issue: items for issue, items in values.items() if items}


def _anchor_hits(site: crawler.Site, documents: list[str]) -> list[str]:
    text = "".join(
        text
        for document in documents
        for text in crawler.iter_search_texts(document)
    )
    compact = crawler.normalize_text(text).replace(" ", "")
    return [
        term
        for term in crawler.site_section_anchor_terms(site)
        if crawler.normalize_text(term).replace(" ", "") in compact
    ]


def _keyword_hit(documents: list[str]) -> bool:
    return any(
        crawler.has_result_keyword(text) or crawler.WENJIN_DUAN_RE.search(text)
        for document in documents
        for text in crawler.iter_search_texts(document)
    )


def _hanlaishuwang_title_match(text: str, issue_set: set[int]) -> re.Match[str] | None:
    normalized = crawler.normalize_text(text)
    title_match = re.search(r"(?<!\d)(\d{1,4})期[^\n]{0,100}?→", normalized)
    if title_match is None:
        return None
    issue = int(title_match.group(1).translate(crawler.FULLWIDTH_DIGITS))
    title_compact = normalized[title_match.start() :].replace(" ", "")
    if (
        issue not in issue_set
        or "→寒来暑往" not in title_compact
        or ("绝杀一段" not in title_compact and "绝杀1段" not in title_compact)
    ):
        return None
    return title_match


def _hanlaishuwang_contiguous_prefix(
    text: str,
    expected_issue: int,
    started: bool,
) -> tuple[str, int, bool, bool]:
    normalized = crawler.normalize_text(text)
    issue_matches = list(crawler.ISSUE_RE.finditer(normalized))
    if not issue_matches:
        return (normalized if started else ""), expected_issue, started, False
    if not started:
        target_match = next(
            (
                match
                for match in issue_matches
                if int(match.group(1).translate(crawler.FULLWIDTH_DIGITS)) == expected_issue
            ),
            None,
        )
        if target_match is None:
            return "", expected_issue, False, False
        normalized = normalized[target_match.start() :]
        issue_matches = list(crawler.ISSUE_RE.finditer(normalized))

    current_issue = expected_issue
    cutoff = len(normalized)
    saw_expected = False
    for match in issue_matches:
        issue = int(match.group(1).translate(crawler.FULLWIDTH_DIGITS))
        if issue != current_issue:
            cutoff = match.start()
            break
        current_issue -= 1
        saw_expected = True
    if not saw_expected:
        return "", expected_issue, started, True
    return normalized[:cutoff], current_issue, True, cutoff < len(normalized)


def _hanlaishuwang_candidates(
    case: FailedSiteCase,
    documents: list[str],
) -> list[crawler.Candidate]:
    wanted_issues = set(case.issues)
    target_index: int | None = None
    title_suffix: dict[int, str] = {}
    for document_index, document in enumerate(documents):
        for text in crawler.iter_search_texts(document):
            title_match = _hanlaishuwang_title_match(text, wanted_issues)
            if title_match is None:
                continue
            target_index = document_index
            normalized = crawler.normalize_text(text)
            title_suffix[document_index] = normalized[title_match.end() :]
            break
        if target_index is not None:
            break
    if target_index is None:
        return []

    expected_issue = max(wanted_issues)
    started = False
    ended = False
    candidates: list[crawler.Candidate] = []
    order = 0
    for document_index, document in enumerate(documents):
        if document_index < target_index or ended:
            continue
        for text_index, text in enumerate(crawler.iter_search_texts(document)):
            if document_index == target_index:
                text = title_suffix.get(document_index, "")
                if not text:
                    continue
            text, expected_issue, started, section_ended = _hanlaishuwang_contiguous_prefix(
                text,
                expected_issue,
                started,
            )
            ended = ended or section_ended
            if not text:
                continue
            base_position = document_index * 10_000_000 + text_index * 1_000_000
            for issue, issue_text, segment in crawler.iter_issue_segments(text, wanted_issues):
                values = crawler.values_in_segment(segment)
                if not values or not crawler.is_strict_segment(segment):
                    continue
                segment_position = crawler.normalize_text(text).find(crawler.normalize_text(segment))
                if segment_position < 0:
                    segment_position = 0
                score = crawler.score_segment(segment, values)
                for value in values:
                    candidates.append(
                        crawler.Candidate(
                            issue=issue,
                            issue_text=issue_text,
                            value=value,
                            title=case.name,
                            snippet=crawler.compact_line(segment),
                            score=score,
                            order=order,
                            position=base_position + segment_position,
                        )
                    )
                    order += 1
    return candidates


def extract_candidates(
    case: FailedSiteCase,
    documents: list[str],
) -> tuple[list[crawler.Candidate], str]:
    if case.name == "寒来暑往":
        return _hanlaishuwang_candidates(case, documents), "寒来暑往独立专属解析"
    return [], "未配置独立验证解析"


def analyze_documents(
    case: FailedSiteCase,
    documents: list[str],
    script_errors: list[str],
) -> dict[str, object]:
    site = crawler.Site(case.name, case.url, case.pick, api_url=case.api_url)
    wanted_issues = set(case.issues)
    candidates, parser_name = extract_candidates(case, documents)
    scoped, window_reason = crawler.scoped_candidates(candidates, wanted_issues, site.pick)
    matches = crawler.find_matches_from_candidates(candidates, wanted_issues, site)
    conflicts = crawler.candidate_conflict_issue_reasons(scoped, wanted_issues)
    scoped_values = _ordered_values(scoped, case.issues)
    all_values = _ordered_values(candidates, case.issues)
    duplicate_values: dict[int, dict[str, int]] = {}
    for issue in case.issues:
        counts = Counter(candidate.value for candidate in scoped if candidate.issue == issue)
        repeated = {value: count for value, count in counts.items() if count > 1}
        if repeated:
            duplicate_values[issue] = repeated

    window_issues = {candidate.issue for candidate in scoped}
    missing_window_issues = [issue for issue in case.issues if issue not in window_issues]
    direction_passed = not window_reason and not missing_window_issues
    anchor_hits = _anchor_hits(site, documents)
    keyword_passed = _keyword_hit(documents)
    number_rows = {
        issue: {
            "count": len(scoped_values.get(issue, [])),
            "passed": len(scoped_values.get(issue, [])) == 1,
        }
        for issue in case.issues
    }
    number_count_passed = all(row["passed"] for row in number_rows.values())
    period_present = any(candidate.issue in wanted_issues for candidate in candidates)

    failure_reasons: list[str] = []
    if script_errors:
        failure_reasons.append("原始内容加载异常：" + "；".join(script_errors[:3]))
    if parser_name == "未配置独立验证解析":
        failure_reasons.append(parser_name)
    if not anchor_hits:
        failure_reasons.append("站名/栏目锚点未命中")
    if not keyword_passed:
        failure_reasons.append("数据关键词未命中")
    if window_reason:
        failure_reasons.append(window_reason)
    if missing_window_issues:
        missing_text = "、".join(f"{issue}期" for issue in missing_window_issues)
        failure_reasons.append(f"指定期数不在{case.pick}方向最新{crawler.CANDIDATE_WINDOW_LIMIT}组内：{missing_text}")
    for issue, reason in conflicts.items():
        failure_reasons.append(f"{issue}期 {reason}")
    if duplicate_values:
        failure_reasons.append(f"同期重复候选：{duplicate_values}")
    if not number_count_passed:
        failure_reasons.append("号码数量不是每期唯一一个")
    if not period_present:
        failure_reasons.append("未抓到指定期数候选")
    if period_present and not matches and not conflicts:
        failure_reasons.append("有指定期数候选，但未形成唯一有效结果")

    return {
        "case": case,
        "parser": parser_name,
        "passed": not failure_reasons,
        "period_present": period_present,
        "actual_values": scoped_values,
        "all_candidate_values": all_values,
        "direction": {
            "pick": case.pick,
            "window_issues": sorted(window_issues, reverse=True),
            "passed": direction_passed,
        },
        "anchor": {"passed": bool(anchor_hits), "hits": anchor_hits},
        "keyword": {"passed": keyword_passed},
        "number_count": {"passed": number_count_passed, "by_issue": number_rows},
        "conflicts": conflicts,
        "duplicates": duplicate_values,
        "failure_reasons": failure_reasons,
        "document_count": len(documents),
        "candidate_count": len(candidates),
        "script_error_count": len(script_errors),
    }


def validate_case(case: FailedSiteCase, timeout: int = 30) -> dict[str, object]:
    try:
        documents, script_errors = crawler.collect_documents(
            case.url,
            timeout,
            True,
            page_attempts=6,
            issue_filter=set(case.issues),
            site_name=case.name,
            pick=case.pick,
            api_url=case.api_url,
        )
    except Exception as exc:
        documents = []
        script_errors = [f"{type(exc).__name__}: {exc}"]
    return analyze_documents(case, documents, script_errors)


def _yes_no(value: bool) -> str:
    return "通过" if value else "失败"


def format_report(report: dict[str, object]) -> str:
    case = report["case"]
    assert isinstance(case, FailedSiteCase)
    actual_values = cast(dict[object, list[str]], report["actual_values"])
    actual_text = "；".join(
        f"{issue}期={','.join(values)}" for issue, values in actual_values.items()
    ) or "无"
    number_count = cast(dict[str, object], report["number_count"])
    by_issue = cast(dict[object, dict[str, object]], number_count["by_issue"])
    count_text = "；".join(
        f"{issue}期{row['count']}个" for issue, row in by_issue.items()
    )
    lines = [
        f"验证站点：{case.name}",
        f"网址：{case.url}",
        f"方向：{case.pick}；指定期数：{','.join(f'{issue}期' for issue in case.issues)}",
        f"验证解析：{report['parser']}",
        f"最终结果：{'通过' if report['passed'] else '失败'}",
        f"是否抓到指定期数：{'是' if report['period_present'] else '否'}",
        f"实际号码：{actual_text}",
        f"{case.pick}方向最新{crawler.CANDIDATE_WINDOW_LIMIT}组：{_yes_no(cast(bool, cast(dict[str, object], report['direction'])['passed']))}",
        f"锚点：{_yes_no(cast(bool, cast(dict[str, object], report['anchor'])['passed']))}；关键词：{_yes_no(cast(bool, cast(dict[str, object], report['keyword'])['passed']))}",
        f"号码数量：{_yes_no(cast(bool, number_count['passed']))}（{count_text or '无'}）",
        f"同期冲突：{report['conflicts'] or '无'}；重复号码：{report['duplicates'] or '无'}",
        f"原始文档：{report['document_count']}；候选：{report['candidate_count']}；加载异常：{report['script_error_count']}",
        f"失败原因：{'；'.join(cast(list[str], report['failure_reasons'])) or '无'}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只验证失败站点清单，不更新缓存或结果 TXT。")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="失败站点清单 JSON")
    parser.add_argument("--case", action="append", help="只验证指定站名或网址，可重复")
    parser.add_argument("--timeout", type=int, default=30, help="单站请求超时秒数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    cases = load_cases(Path(args.cases))
    if args.case:
        selected = [case for case in cases if case.name in args.case or case.url in args.case]
        if not selected:
            print("没有匹配的失败站点清单项。", file=sys.stderr)
            return 2
        cases = selected

    reports = [validate_case(case, max(1, args.timeout)) for case in cases]
    for index, report in enumerate(reports):
        if index:
            print("\n" + "=" * 60)
        print(format_report(report))
    print(f"\n独立验证完成：{sum(bool(report['passed']) for report in reports)}/{len(reports)} 通过")
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
