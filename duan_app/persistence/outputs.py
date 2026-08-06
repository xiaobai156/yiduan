# -*- coding: utf-8 -*-
import json
import re
import ssl
import time
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from duan_app.constants import CURL_SSL_EXIT_CODES
from duan_app.domain import Site, SiteResult
from duan_app.fetcher import CurlFetchError, is_remote_reset_error, is_ssl_handshake_text
from duan_app.text_utils import normalize_text


FAILURE_REASON_DETAILS = {
    "无期数": "抓取内容中未发现指定期数",
    "无定位": "已发现指定期数，但同一期内容未发现“杀/绝杀一段”等目标定位词",
    "段位表": "指定期附近只识别到段位表，未识别到目标开奖结果",
    "无结果词": "已发现指定期数，但同一期内容未发现目标结果词",
    "无开字": "指定期内容缺少开奖表达中的“开”字，无法证明是已开奖结果",
    "无对错": "指定期内容缺少准、错、对等结果状态，无法证明结果语义",
    "段数越界": "指定期内容出现1段至7段之外的值",
    "表干扰": "指定期附近的段值来自段位表干扰，不是目标结果",
    "无段数": "指定期目标内容中未找到合法的1段至7段结果",
    "数量错": "指定期目标内容中合法段值不是唯一一个",
    "不合规": "严格校验未通过：检测到指定期、目标词、开奖状态和单个合法段值，但未能证明它们属于同一目标栏目和区块",
}


def specific_failure_reason(reason: str) -> str:
    cleaned = str(reason).strip(" ；;\r\n\t")
    return FAILURE_REASON_DETAILS.get(cleaned, cleaned or "未找到符合严格规则的结果")


def format_issue_list(issues: set[int] | list[int] | tuple[int, ...]) -> str:
    ordered = list(dict.fromkeys(int(issue) for issue in issues))
    return "、".join(f"{issue}期" for issue in ordered) if ordered else "未读取"


def format_failure_line(
    site: Site,
    wanted_issues: set[int],
    *,
    stage: str,
    location: str,
    reason: str,
    actual_issues: set[int] | list[int] | tuple[int, ...] = (),
) -> str:
    target_text = format_issue_list(sorted(wanted_issues))
    actual_text = format_issue_list(actual_issues)
    return (
        f"失败 {site.name} {site.url} 方向:{site.pick} 位置:{location} "
        f"期数:{target_text} 实际期数:{actual_text} 阶段:{stage} "
        f"原因:{specific_failure_reason(reason)}"
    )


def format_failure_output_line(
    site: Site,
    wanted_issues: set[int],
    *,
    stage: str,
    reason: str,
) -> str:
    target_text = "、".join(str(int(issue)) for issue in sorted(wanted_issues)) or "未读取"
    output_stage = "指定期数校验" if stage == "校验" else stage
    return (
        f"失败 {site.name} {site.url} 方向: {site.pick} 期数: {target_text} "
        f"阶段: {output_stage} 原因: {specific_failure_reason(reason)}"
    )


def ensure_failure_line_format(result: SiteResult, wanted_issues: set[int]) -> str:
    line = result.fail_line or ""
    required_fields = ("方向: ", "期数: ", "阶段: ", "原因: ")
    if (
        line.startswith("失败 ")
        and all(field in line for field in required_fields)
        and "位置:" not in line
        and "实际期数:" not in line
    ):
        return line

    if "打开失败" in line:
        stage = "抓取"
    elif "二次确认" in line:
        stage = "二次确认"
    elif "近10期缓存冲突" in line:
        stage = "缓存校验"
    elif "解析失败" in line:
        stage = "解析"
    else:
        stage = "校验"

    stage_match = re.search(r"(?:^|\s)阶段:\s*([^\s]+)", line)
    if stage_match:
        stage = stage_match.group(1)
    reason_match = re.search(r"(?:^|\s)原因:\s*(.*)$", line)
    tail = line.partition(result.site.url)[2].strip() if result.site.url in line else line.strip()
    reason = reason_match.group(1).strip() if reason_match else (tail or "未找到符合严格规则的结果")
    return format_failure_output_line(
        result.site,
        wanted_issues,
        stage=stage,
        reason=reason,
    )


def parse_issue_range(value: str) -> tuple[list[int], int, str]:
    raw = normalize_text(value).replace("，", ",")
    raw = raw.replace("~", "-").replace("至", "-").replace("到", "-")
    pieces = [piece.strip() for piece in re.split(r"[,、\s]+", raw) if piece.strip()]
    issues: set[int] = set()
    width = 3

    for piece in pieces:
        range_match = re.fullmatch(r"(\d{1,4})-(\d{1,4})", piece)
        if range_match:
            left, right = range_match.groups()
            start, end = int(left), int(right)
            width = max(width, len(left), len(right))
            step = 1 if start <= end else -1
            issues.update(range(start, end + step, step))
            continue

        single_match = re.fullmatch(r"\d{1,4}", piece)
        if single_match:
            width = max(width, len(piece))
            issues.add(int(piece))
            continue

        raise ValueError(f"期数格式不对：{piece}，例子：120 或 094-120")

    if not issues:
        raise ValueError("期数不能为空")

    ordered = sorted(issues)
    if len(ordered) == 1:
        label = f"{ordered[0]:0{width}d}"
    else:
        label = f"{ordered[0]:0{width}d}-{ordered[-1]:0{width}d}"
    return ordered, width, label

def default_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    host_name = parsed.hostname.split(".")[0] if parsed.hostname else "site"

    topic_match = re.search(r"/topic/(\d+)\.html", parsed.path)
    if topic_match:
        return f"{host_name}_topic_{topic_match.group(1)}"

    query = parse_qs(parsed.query)
    if "tid" in query and query["tid"]:
        return f"{host_name}_tid_{query['tid'][0]}"

    return host_name

def duan_sort_value(value: str) -> int:
    match = re.search(r"(\d+)\s*段", value)
    return int(match.group(1)) if match else 999

def build_ranking_lines(counts: dict[str, int], title: str = "排行") -> list[str]:
    if not counts:
        return ["", title, "合计 0条"]

    lines = ["", title, f"合计 {sum(counts.values())}条"]
    ordered = sorted(counts.items(), key=lambda item: (-item[1], duan_sort_value(item[0]), item[0]))
    rank = 0
    last_count: int | None = None
    for value, count in ordered:
        if count != last_count:
            rank += 1
            last_count = count
        lines.append(f"第{rank}名 {value} {count}条")
    return lines

def classify_open_error(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, CurlFetchError):
        message = str(exc)
        if exc.exit_code in CURL_SSL_EXIT_CODES or is_ssl_handshake_text(message):
            return "SSL握手失败"
        http_match = re.search(r"returned error:\s*(\d{3})", message, re.I)
        if http_match:
            return f"HTTP {http_match.group(1)}"
        return "curl连接失败"

    if isinstance(exc, TimeoutError):
        return "超时"

    if isinstance(exc, URLError) and exc.reason:
        reason = exc.reason
        if isinstance(reason, BaseException):
            return classify_open_error(reason)
        reason_text = str(reason)
    else:
        reason_text = str(exc)

    if is_remote_reset_error(exc):
        return "远端断开"
    if isinstance(exc, ssl.SSLError) or "SSL" in reason_text or "_ssl" in reason_text or is_ssl_handshake_text(reason_text):
        return "SSL握手失败"
    if "timed out" in reason_text.lower() or "超时" in reason_text:
        return "超时"
    if "10013" in reason_text or "权限" in reason_text:
        return "访问被拦截"
    return "未知打开失败"

def failure_reason_from_line(line: str) -> str:
    match = re.search(r"打开失败\[([^\]]+)\]", line)
    if match:
        return match.group(1)

    if "解析失败" in line:
        return "解析失败"
    if "候选冲突" in line:
        return "候选冲突"
    if "近10期缓存冲突" in line:
        return "近10期缓存历史冲突"
    if "未找到符合严格规则的结果" in line:
        return "未找到符合严格规则的结果"
    if "严格校验未通过" in line:
        return "严格校验未通过"
    if "最近" in line and "期不符" in line:
        return "期数不符"
    if (
        "组内无指定期数" in line
        or ("个有效候选期数为[" in line and "不含指定" in line)
        or "不是最后一条专属历史边界行" in line
        or "不是第一条专属历史边界行" in line
    ):
        return "方向范围外"
    if "接口403拒绝访问" in line:
        return "接口403拒绝访问"
    if "接口404不存在" in line:
        return "接口404不存在"
    if "帖子不存在" in line:
        return "帖子不存在"

    detailed_reasons = {
        "抓取内容中未发现指定期数": "指定期数缺失",
        "未发现“杀/绝杀一段”等目标定位词": "目标定位词缺失",
        "只识别到段位表": "段位表干扰",
        "未发现目标结果词": "目标结果词缺失",
        "缺少开奖表达中的“开”字": "开奖表达不完整",
        "缺少准、错、对等结果状态": "结果状态缺失",
        "出现1段至7段之外的值": "段数越界",
        "来自段位表干扰": "段位表干扰",
        "未找到合法的1段至7段结果": "合法段值缺失",
        "合法段值不是唯一一个": "段值数量错误",
        "未找到专属锚点": "专属锚点缺失",
    }
    for detail, category in detailed_reasons.items():
        if detail in line:
            return category

    pieces = line.split()
    tail = pieces[-1] if pieces else line
    for reason in ("未更新", "无期数", "无定位", "段位表", "无结果词", "无开字", "无对错", "段数越界", "表干扰", "无段数", "数量错", "不合规"):
        if reason in tail:
            return reason
    if "脚本加载失败" in line:
        return "脚本加载失败"
    return f"未分类失败[{tail or '无详细内容'}]"

def build_failure_stats(fail_lines: list[str]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for line in fail_lines:
        reason = failure_reason_from_line(line)
        stats[reason] = stats.get(reason, 0) + 1
    return stats

def is_network_retry_reason(reason: str) -> bool:
    return (
        reason in {"远端断开", "SSL握手失败", "超时", "curl连接失败"}
        or reason.startswith("HTTP 5")
    )

def build_failure_stats_lines(fail_lines: list[str]) -> list[str]:
    stats = build_failure_stats(fail_lines)
    if not stats:
        return ["", "失败分类统计", "无失败"]

    ordered = sorted(stats.items(), key=lambda item: (-item[1], item[0]))
    return ["", "失败分类统计"] + [f"{reason} {count}条" for reason, count in ordered]

def format_progress_line(
    done_count: int,
    total_count: int,
    success_count: int,
    fail_count: int,
    elapsed_seconds: float,
    site: Site,
) -> str:
    percent = int(done_count * 100 / total_count) if total_count else 0
    return (
        f"[进度 {done_count}/{total_count} {percent}% "
        f"成功 {success_count} 失败 {fail_count} "
        f"用时 {elapsed_seconds:.1f}s] 当前: {site.name}"
    )

def safe_write_text(path: Path, text: str) -> Path:
    temp_path = path.with_name(path.name + f".writing-{time.time_ns()}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8-sig")
        temp_path.replace(path)
        return path
    except PermissionError:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise PermissionError(f"结果文件被占用，请关闭后重试：{path}")

def load_slow_site_memory(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(url): item for url, item in data.items() if isinstance(item, dict)}

def is_slow_site(site: Site, memory: dict[str, dict[str, object]]) -> bool:
    item = memory.get(site.url, {})
    streak = item.get("fail_streak", 0)
    try:
        return int(cast(int | str | float, streak)) >= 2
    except (TypeError, ValueError):
        return False

def update_slow_site_memory(path: Path, results: list[SiteResult | None]) -> None:
    memory = load_slow_site_memory(path)
    for result in results:
        if result is None:
            continue

        item = memory.get(result.site.url, {})
        item["name"] = result.site.name
        item["pick"] = result.site.pick

        if result.matches:
            item["fail_streak"] = 0
            item["last_status"] = "OK"
        elif result.fail_line:
            reason = failure_reason_from_line(result.fail_line)
            if is_network_retry_reason(reason):
                try:
                    item["fail_streak"] = int(cast(int | str | float, item.get("fail_streak", 0))) + 1
                except (TypeError, ValueError):
                    item["fail_streak"] = 1
            else:
                item["fail_streak"] = 0
            item["last_status"] = reason
        else:
            continue

        memory[result.site.url] = item

    safe_write_text(
        path,
        json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

def build_output_lines(
    results: list[SiteResult | None],
    wanted_issues: set[int],
    issue_width: int,
) -> tuple[list[str], list[str], dict[str, int]]:
    success_lines: list[str] = []
    fail_lines: list[str] = []
    ranking_counts: dict[str, int] = {}

    for result in results:
        if result is None:
            continue
        if result.matches:
            matches_by_issue = {match.issue: match for match in result.matches}
            for issue in sorted(wanted_issues):
                match = matches_by_issue.get(issue)
                if match is None:
                    reason = result.issue_reasons.get(issue, "未找到符合严格规则的结果")
                    fail_lines.append(
                        format_failure_output_line(
                            result.site,
                            {issue},
                            stage="校验",
                            reason=reason,
                        )
                    )
                    continue

                success_lines.append(f"{match.value} {match.title or result.site.name}")
                ranking_counts[match.value] = ranking_counts.get(match.value, 0) + 1
        elif result.fail_line:
            fail_lines.append(ensure_failure_line_format(result, wanted_issues))

    return success_lines, fail_lines, ranking_counts

def count_output_lines(results: list[SiteResult | None], wanted_issues: set[int]) -> tuple[int, int]:
    success_count = 0
    fail_count = 0

    for result in results:
        if result is None:
            continue
        if result.matches:
            matched_issues = {match.issue for match in result.matches}
            for issue in wanted_issues:
                if issue in matched_issues:
                    success_count += 1
                else:
                    fail_count += 1
        elif result.fail_line:
            fail_count += 1

    return success_count, fail_count

def write_result_files(success_path: Path, fail_path: Path, success_lines: list[str], fail_lines: list[str], ranking_counts: dict[str, int]) -> None:
    success_output_lines = success_lines + build_ranking_lines(ranking_counts)
    if fail_lines:
        separated_fail_lines: list[str] = []
        for index, line in enumerate(fail_lines):
            separated_fail_lines.append(line)
            if index < len(fail_lines) - 1:
                separated_fail_lines.append("")
        fail_output_lines = separated_fail_lines + build_failure_stats_lines(fail_lines)
        safe_write_text(fail_path, "\n".join(fail_output_lines) + "\n")
    else:
        try:
            fail_path.unlink(missing_ok=True)
        except OSError as exc:
            raise OSError(f"无法删除旧失败文件，请关闭后重试：{fail_path}") from exc
    safe_write_text(success_path, "\n".join(success_output_lines) + ("\n" if success_output_lines else ""))
