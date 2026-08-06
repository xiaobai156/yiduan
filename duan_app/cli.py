# -*- coding: utf-8 -*-
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from duan_app.config import default_failure_result_dir, default_result_dir, load_sites_config, resolve_failure_path
from duan_app.crawl_service import process_site, should_recheck_result
from duan_app.domain import Site, SiteResult
from duan_app.persistence.cache import write_recent_cache_file
from duan_app.persistence.outputs import build_failure_stats, build_output_lines, count_output_lines, format_progress_line, is_slow_site, load_slow_site_memory, parse_issue_range, update_slow_site_memory, write_result_files
from duan_app.parsing.profiles import load_site_profiles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="抓取指定期数里的绝杀一段/杀几段内容，并分别输出成功和失败 txt。"
    )
    # 指定期数：运行时可用 -i 修改，例如 python duan_crawler.py -i 120；默认抓 120期。
    parser.add_argument("-i", "--issues", default="125", help="期数，例如：120 或 094-120")
    parser.add_argument("--success", help="成功结果 txt；不填则自动生成到数据统一归纳：120期-段.txt")
    parser.add_argument("--fail", help="失败结果 txt；不填则自动生成到数据统一归纳：120期-段-失败.txt")
    parser.add_argument("--timeout", type=int, default=20, help="单个请求超时秒数")
    parser.add_argument("--delay", type=float, default=0.2, help="提交每个网站任务之间暂停秒数")
    parser.add_argument("--workers", type=int, default=8, help="并发抓取数量，调大更快，调小更稳")
    parser.add_argument("--max-recheck", type=int, default=10, help="打开失败后最多低速复查几个网站；-1 表示全部复查")
    parser.add_argument("--sites", default="sites.json", help="站点配置 JSON，默认 sites.json")
    parser.add_argument("--slow-sites", default="slow_sites.json", help="慢站记忆 JSON，默认 slow_sites.json")
    parser.add_argument("--recent-cache", default="recent_10_cache.json", help="近10期重复检测缓存 JSON")
    parser.add_argument("--no-recent-cache", action="store_true", help="本次运行不刷新近10期缓存")
    parser.add_argument("--quiet-ok", action="store_true", help="不打印每条成功明细，只保留进度和最终文件")
    parser.add_argument("--allow-insecure", action="store_true", help="允许不校验证书，仅在明确需要时使用")
    parser.add_argument("--verify-ssl", action="store_true", help="兼容旧参数；默认已校验证书")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    verify_ssl = not args.allow_insecure or args.verify_ssl

    try:
        issues, issue_width, issues_label = parse_issue_range(args.issues)
    except Exception as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2

    output_dir = Path(__file__).resolve().parent.parent
    result_dir = default_result_dir(output_dir)
    failure_result_dir = default_failure_result_dir(output_dir)
    sites_path = Path(args.sites)
    if not sites_path.is_absolute():
        sites_path = output_dir / sites_path
    slow_sites_path = Path(args.slow_sites)
    if not slow_sites_path.is_absolute():
        slow_sites_path = output_dir / slow_sites_path
    recent_cache_path = Path(args.recent_cache)
    if not recent_cache_path.is_absolute():
        recent_cache_path = output_dir / recent_cache_path

    try:
        sites = load_sites_config(sites_path)
        load_site_profiles(output_dir / "site_profiles.json", sites)
    except Exception as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2

    slow_memory = load_slow_site_memory(slow_sites_path)
    wanted_issues = set(issues)
    workers = max(1, min(args.workers, len(sites)))
    results: list[SiteResult | None] = [None] * len(sites)
    success_path = Path(args.success).resolve() if args.success else result_dir / f"{issues_label}期-段.txt"
    fail_path = resolve_failure_path(args.fail, failure_result_dir, issues_label)
    show_ok_details = not args.quiet_ok

    def current_counts() -> tuple[int, int]:
        return count_output_lines(results, wanted_issues)

    def print_ok_details(result: SiteResult) -> None:
        if not show_ok_details:
            return
        for match in result.matches:
            if match.issue not in wanted_issues:
                continue
            issue_text = f"{match.issue:0{issue_width}d}期"
            print(f"  OK {match.value} {issue_text} {match.title or result.site.name}")
            print(f"     {match.snippet}")

    site_entries = list(enumerate(sites, start=1))
    normal_entries = [(index, site) for index, site in site_entries if not is_slow_site(site, slow_memory)]
    slow_entries = [(index, site) for index, site in site_entries if is_slow_site(site, slow_memory)]

    def run_entries(entries: list[tuple[int, Site]], worker_count: int, delay: float, timeout: int, label: str) -> None:
        if not entries:
            return

        print(f"{label}：{len(entries)} 个网站，并发 {worker_count}，超时 {timeout} 秒")
        started_at = time.monotonic()
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {}
            for group_index, (index, site) in enumerate(entries, start=1):
                future = executor.submit(
                    process_site,
                    index,
                    site,
                    timeout,
                    verify_ssl,
                    wanted_issues,
                    issues_label,
                )
                future_map[future] = (index, site)
                if delay and group_index < len(entries):
                    time.sleep(delay)

            for done_count, future in enumerate(as_completed(future_map), start=1):
                index, site = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:
                    fail_line = f"{issues_label}期 {site.name} {site.url} 解析失败：{type(exc).__name__}: {exc}"
                    result = SiteResult(index, site, [], fail_line, f"FAIL 解析失败：{type(exc).__name__}: {exc}")
                results[index - 1] = result
                current_success_count, current_fail_count = current_counts()

                print(
                    format_progress_line(
                        done_count,
                        len(entries),
                        current_success_count,
                        current_fail_count,
                        time.monotonic() - started_at,
                        site,
                    )
                )
                print_ok_details(result)

    print(f"站点配置：{sites_path}")
    print(f"慢站记忆：{slow_sites_path}")
    print(f"并发抓取：{workers} 个任务")
    print(f"最终结果：{success_path} / {fail_path}")
    run_entries(normal_entries, workers, args.delay, args.timeout, "普通抓取")
    if slow_entries:
        slow_workers = max(1, min(2, workers, len(slow_entries)))
        slow_delay = max(args.delay, 1.0)
        slow_timeout = args.timeout + 10
        print(f"\n慢站自动降速：{len(slow_entries)} 个")
        run_entries(slow_entries, slow_workers, slow_delay, slow_timeout, "慢站抓取")

    recheck_indexes = [index for index, result in enumerate(results) if should_recheck_result(result)]
    skipped_recheck_count = 0
    if args.max_recheck >= 0 and len(recheck_indexes) > args.max_recheck:
        skipped_recheck_count = len(recheck_indexes) - args.max_recheck
        recheck_indexes = recheck_indexes[: args.max_recheck]
    if recheck_indexes:
        recheck_timeout = args.timeout
        print(f"\n低速复查打开失败网站：{len(recheck_indexes)} 个，超时 {recheck_timeout} 秒")
        if skipped_recheck_count:
            print(f"另有 {skipped_recheck_count} 个打开失败未复查，可用 --max-recheck 调大，或用 -1 全部复查")
        recheck_started_at = time.monotonic()
        for position, result_index in enumerate(recheck_indexes, start=1):
            site = sites[result_index]
            time.sleep(1.5)
            result = process_site(
                result_index + 1,
                site,
                recheck_timeout,
                verify_ssl,
                wanted_issues,
                issues_label,
            )
            results[result_index] = result
            current_success_count, current_fail_count = current_counts()
            print(
                format_progress_line(
                    position,
                    len(recheck_indexes),
                    current_success_count,
                    current_fail_count,
                    time.monotonic() - recheck_started_at,
                    site,
                )
            )
            print_ok_details(result)

    success_lines, fail_lines, all_ranking_counts = build_output_lines(results, wanted_issues, issue_width)
    write_result_files(success_path, fail_path, success_lines, fail_lines, all_ranking_counts)
    update_slow_site_memory(slow_sites_path, results)
    failure_stats = build_failure_stats(fail_lines)

    cache_summary = None
    if not args.no_recent_cache:
        try:
            cache_summary = write_recent_cache_file(
                recent_cache_path,
                sites_path,
                results,
            )
        except Exception as exc:
            print(f"缓存更新未完成：{exc}", file=sys.stderr)
            return 1

    print(f"\n完成：成功 {len(success_lines)} 条，失败 {len(fail_lines)} 条")
    if failure_stats:
        print("失败统计：" + "；".join(f"{reason} {count}个" for reason, count in sorted(failure_stats.items(), key=lambda item: (-item[1], item[0]))))
    print(f"成功结果：{success_path}")
    if fail_lines:
        print(f"失败结果：{fail_path}")
    else:
        print("失败结果：无失败，不生成失败 txt")
    if cache_summary is not None:
        print(
            "近10期缓存："
            f"{recent_cache_path}；"
            f"站点 {cache_summary['site_count']}；"
            f"完整10期 {cache_summary['full_10_count']}；"
            f"需审核 {cache_summary['audit_count']}；"
            f"错误 {cache_summary['error_count']}"
        )
    return 0
