# -*- coding: utf-8 -*-
import re

from duan_app.constants import BODY_LOCATOR_RE, FULLWIDTH_DIGITS, ISSUE_RE, MULTI_DUAN_VALUE_RE, OPEN_STATUS_RE, RESULT_KEYWORD_RE, SITE_REPEATED_DUAN_RE, STRICT_BRACKET_VALUE_RE, STRICT_KILL_VALUE_RE, STRICT_REPEATED_VALUE_RE, TABLE_SEGMENT_RE, TITLE_BRACKET_RE, TITLE_PLAIN_RE, WENJIN_BODY_LOCATOR_RE, WENJIN_BRACKET_VALUE_RE, WENJIN_DUAN_RE
from duan_app.text_utils import format_duan, html_to_text, is_valid_duan_value, looks_like_html, normalize_text, number_to_int, strip_hidden_html_blocks


def iter_search_texts(document: str):
    cleaned = strip_hidden_html_blocks(document)
    if looks_like_html(cleaned):
        text = html_to_text(cleaned)
        if text:
            yield text
        return

    raw_text = normalize_text(cleaned)
    if raw_text:
        yield raw_text

def has_invalid_duan_value(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> bool:
    normalized = normalize_text(segment)
    no_space = normalized.replace(" ", "")
    has_target_keyword = (
        "绝杀一段" in no_space
        or "绝杀1段" in no_space
        or "灭杀一段" in no_space
        or "灭杀1段" in no_space
        or "稳杀一段" in no_space
        or "稳杀1段" in no_space
        or "必杀一段" in no_space
        or "必杀1段" in no_space
        or "杀一段" in no_space
        or "杀1段" in no_space
        or "[杀一段]" in no_space
        or "[杀1段]" in no_space
        or RESULT_KEYWORD_RE.search(normalized) is not None
        or WENJIN_DUAN_RE.search(normalized) is not None
        or (allow_multi_duan and MULTI_DUAN_VALUE_RE.search(normalized) is not None)
    )
    if not has_target_keyword:
        return False

    strict_repeated_present = STRICT_REPEATED_VALUE_RE.search(normalized) is not None
    if SITE_REPEATED_DUAN_RE.search(normalized) and not allow_repeated_duan and not strict_repeated_present:
        return True
    if allow_repeated_duan or strict_repeated_present:
        normalized = SITE_REPEATED_DUAN_RE.sub(" ", normalized)

    regexes = (
        STRICT_BRACKET_VALUE_RE,
        WENJIN_BRACKET_VALUE_RE,
        STRICT_KILL_VALUE_RE,
    )
    for regex in regexes:
        for match in regex.finditer(normalized):
            value = number_to_int(match.group(1))
            if not is_valid_duan_value(value):
                return True
    return False

def values_in_segment(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> list[str]:
    normalized = normalize_text(segment)
    no_space = normalized.replace(" ", "")
    values: list[str] = []

    if has_invalid_duan_value(
        normalized,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    ):
        return values

    for match in STRICT_REPEATED_VALUE_RE.finditer(normalized):
        value = int(match.group(1))
        item = format_duan(value)
        if item not in values:
            values.append(item)
    if values:
        return values

    if allow_multi_duan:
        for match in MULTI_DUAN_VALUE_RE.finditer(normalized):
            raw_values: list[str] = []
            for raw_value in re.findall(r"[1-7]", match.group(1)):
                item = format_duan(int(raw_value))
                if item not in raw_values:
                    raw_values.append(item)
            if len(raw_values) == 6:
                missing_values = [
                    format_duan(value)
                    for value in range(1, 8)
                    if format_duan(value) not in raw_values
                ]
                return missing_values
            if raw_values:
                return raw_values

    if has_result_keyword(normalized) and OPEN_STATUS_RE.search(normalized):
        if allow_repeated_duan:
            for match in STRICT_REPEATED_VALUE_RE.finditer(normalized):
                value = int(match.group(1))
                item = format_duan(value)
                if item not in values:
                    values.append(item)
            if values:
                return values

        for regex in (STRICT_BRACKET_VALUE_RE, WENJIN_BRACKET_VALUE_RE, STRICT_KILL_VALUE_RE):
            for match in regex.finditer(normalized):
                value = number_to_int(match.group(1))
                if value is None or not is_valid_duan_value(value):
                    continue
                item = format_duan(value)
                if item not in values:
                    values.append(item)
            if values:
                return values

    if allow_repeated_duan:
        for match in SITE_REPEATED_DUAN_RE.finditer(normalized):
            value = int(match.group(1))
            item = format_duan(value)
            if item not in values:
                values.append(item)
        if values:
            return values

    if (
        "绝杀一段" not in no_space
        and "绝杀1段" not in no_space
        and "灭杀一段" not in no_space
        and "灭杀1段" not in no_space
        and "稳杀一段" not in no_space
        and "稳杀1段" not in no_space
        and "杀一段" not in no_space
        and "杀1段" not in no_space
        and "[杀一段]" not in no_space
        and "[杀1段]" not in no_space
    ):
        return values

    if allow_repeated_duan:
        for match in SITE_REPEATED_DUAN_RE.finditer(normalized):
            value = int(match.group(1))
            item = format_duan(value)
            if item not in values:
                values.append(item)

    return values

def has_result_keyword(text: str) -> bool:
    normalized = normalize_text(text)
    no_space = normalized.replace(" ", "")
    return (
        "绝杀一段" in no_space
        or "绝杀1段" in no_space
        or "灭杀一段" in no_space
        or "灭杀1段" in no_space
        or "稳杀一段" in no_space
        or "稳杀1段" in no_space
        or "必杀一段" in no_space
        or "必杀1段" in no_space
        or "[杀一段]" in no_space
        or "[杀1段]" in no_space
        or RESULT_KEYWORD_RE.search(normalized) is not None
        or WENJIN_DUAN_RE.search(normalized) is not None
    )

def table_signature_count(text: str) -> int:
    normalized = normalize_text(text)
    return len(TABLE_SEGMENT_RE.findall(normalized))

def has_body_locator(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        BODY_LOCATOR_RE.search(normalized) is not None
        or WENJIN_BODY_LOCATOR_RE.search(normalized) is not None
    )

def trim_segment(text: str, limit: int = 220) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return normalized

    if len(normalized) > limit:
        normalized = normalized[:limit]

    status_match = OPEN_STATUS_RE.search(normalized)
    if status_match:
        normalized = normalized[: status_match.end()]

    table_match = TABLE_SEGMENT_RE.search(normalized)
    if table_match and table_match.start() > 0:
        normalized = normalized[: table_match.start()]

    return normalized.strip()

def title_in_segment(segment: str, fallback: str) -> str:
    normalized = normalize_text(segment)
    match = TITLE_BRACKET_RE.search(normalized)
    if match:
        title = re.sub(r"\s+", "", match.group(1))
        return title

    match = TITLE_PLAIN_RE.search(normalized)
    if match:
        return re.sub(r"\s+", "", match.group(1))

    return fallback

def strict_value_count_ok(values: list[str], allow_multi_duan: bool = False) -> bool:
    if allow_multi_duan:
        return bool(values)
    return len(values) == 1

def is_strict_segment(
    segment: str,
    allow_repeated_duan: bool = False,
    allow_multi_duan: bool = False,
) -> bool:
    normalized = normalize_text(segment)
    values = values_in_segment(
        normalized,
        allow_repeated_duan=allow_repeated_duan,
        allow_multi_duan=allow_multi_duan,
    )
    if allow_multi_duan and MULTI_DUAN_VALUE_RE.search(normalized) is not None:
        return (
            has_body_locator(normalized)
            and has_result_keyword(normalized)
            and OPEN_STATUS_RE.search(normalized) is not None
            and strict_value_count_ok(values, allow_multi_duan=True)
        )
    return (
        has_body_locator(normalized)
        and has_result_keyword(normalized)
        and OPEN_STATUS_RE.search(normalized) is not None
        and strict_value_count_ok(values)
    )

def score_segment(segment: str, values: list[str], allow_repeated_duan: bool = False) -> int:
    normalized = normalize_text(segment)
    score = 0
    if has_result_keyword(normalized):
        score += 80
    if (
        STRICT_BRACKET_VALUE_RE.search(normalized)
        or WENJIN_BRACKET_VALUE_RE.search(normalized)
        or STRICT_KILL_VALUE_RE.search(normalized)
    ):
        score += 90
    if allow_repeated_duan and STRICT_REPEATED_VALUE_RE.search(normalized):
        score += 85
    if allow_repeated_duan and SITE_REPEATED_DUAN_RE.search(normalized):
        score += 60
    if "开" in normalized:
        score += 25
    if OPEN_STATUS_RE.search(normalized):
        score += 55
    if table_signature_count(normalized) >= 2:
        score -= 120
    score += len(values) * 5
    score -= min(len(normalized), 360) // 80
    return score

def iter_issue_focus_texts(text: str, wanted_issues: set[int] | None = None):
    normalized = normalize_text(text)
    if not normalized:
        return

    compact = re.sub(r"\s+", " ", normalized)
    matches = [
        match
        for match in ISSUE_RE.finditer(compact)
        if wanted_issues is None or int(match.group(1).translate(FULLWIDTH_DIGITS)) in wanted_issues
    ]
    yielded: set[str] = set()
    for match in matches:
        start = max(0, match.start() - 120)
        end = min(len(compact), match.start() + 520)
        window = compact[start:end].strip()
        if window and window not in yielded:
            yielded.add(window)
            yield window, start

def iter_issue_segments(text: str, wanted_issues: set[int] | None = None):
    normalized = normalize_text(text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        line_matches = list(ISSUE_RE.finditer(line))
        for match_index, match in enumerate(line_matches):
            issue = int(match.group(1).translate(FULLWIDTH_DIGITS))
            if wanted_issues is None or issue in wanted_issues:
                next_start = (
                    line_matches[match_index + 1].start()
                    if match_index + 1 < len(line_matches)
                    else len(line)
                )
                segment = trim_segment(line[match.start() : next_start].strip(), limit=180)
                yield issue, match.group(1), segment

def issue_guard_set(wanted_issues: set[int]) -> set[int]:
    return set(wanted_issues)
