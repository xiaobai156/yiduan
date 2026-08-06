# -*- coding: utf-8 -*-
"""
杀段数据跨站重复检测
检测逻辑：优先取近 N 期（默认10期），不足 N 期也参与检测。
两个站点按共同拥有的具体期号对齐比较，连续 3-5 期一致为疑似重复，
连续 6 期及以上一致为重复。

用法：
  py -3 period_repetition_checker.py --period 152
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from duan_crawler import Site


def build_search_periods(base_period: int, window: int, max_search: int) -> set[int]:
    total = window + max_search
    return {p for p in range(base_period, base_period - total, -1) if p > 0}


def get_period_data_map(matches, wanted_periods: set[int]) -> dict[int, tuple[str, ...]]:
    period_values: dict[int, list[str]] = {}
    for m in matches:
        if m.issue in wanted_periods:
            period_values.setdefault(m.issue, []).append(m.value)
    return {issue: tuple(sorted(set(vals))) for issue, vals in period_values.items()}


def build_sequence(data_map: dict[int, tuple[str, ...]], base_period: int, window: int, max_search: int) -> list[tuple[int, tuple[str, ...]]]:
    seq: list[tuple[int, tuple[str, ...]]] = []
    p = base_period
    limit = base_period - max_search
    while len(seq) < window and p >= limit:
        if p > 0 and p in data_map:
            seq.append((p, data_map[p]))
        p -= 1
    return seq


def is_consecutive_sequence(sequence: list[tuple[int, tuple[str, ...]]]) -> bool:
    if len(sequence) < 2:
        return True
    return all(sequence[index][0] == sequence[index - 1][0] - 1 for index in range(1, len(sequence)))


def find_matching_runs(
    a: list[tuple[int, tuple[str, ...]]],
    b: list[tuple[int, tuple[str, ...]]],
) -> list[list[tuple[int, tuple[str, ...]]]]:
    a_by_period = dict(a)
    b_by_period = dict(b)
    common_periods = sorted(set(a_by_period) & set(b_by_period), reverse=True)
    runs: list[list[tuple[int, tuple[str, ...]]]] = []
    current: list[tuple[int, tuple[str, ...]]] = []
    previous_period: int | None = None

    for period in common_periods:
        values_match = a_by_period[period] == b_by_period[period]
        is_next_period = previous_period is None or period == previous_period - 1
        if values_match and is_next_period:
            current.append((period, a_by_period[period]))
        else:
            if current:
                runs.append(current)
            current = [(period, a_by_period[period])] if values_match else []
        previous_period = period

    if current:
        runs.append(current)
    return runs


def classify_pair(
    a: list[tuple[int, tuple[str, ...]]],
    b: list[tuple[int, tuple[str, ...]]],
) -> tuple[str | None, list[tuple[int, tuple[str, ...]]] | None]:
    runs = find_matching_runs(a, b)
    if not runs:
        return None, None
    longest = max(runs, key=len)
    if len(longest) >= 6:
        return "duplicate", longest
    if len(longest) >= 3:
        return "suspect", longest
    return None, longest


def fmt_values(vals: tuple[str, ...]) -> str:
    return '、'.join(f'杀{v}' if str(v).endswith('段') else f'杀{v}段' for v in vals)


@dataclass
class SiteAnalysis:
    index: int
    site: Site
    sequence: list[tuple[int, tuple[str, ...]]]
    fail_line: str | None
    status: str
    audit_note: str | None = None


def cache_record_to_analysis(record: dict[str, object], base_period: int, window: int) -> SiteAnalysis:
    index = int(cast(str | int | float | None, record.get("index")) or 0)
    site = Site(
        str(record.get("name") or "").strip(),
        str(record.get("url") or "").strip(),
        str(record.get("pick") or "top").strip() or "top",
    )
    raw_sequence = record.get("sequence")
    parsed_sequence: list[tuple[int, tuple[str, ...]]] = []
    if isinstance(raw_sequence, list):
        for item in raw_sequence:
            if not isinstance(item, dict):
                continue
            try:
                period = int(cast(str | int | float, item.get("period")))
            except (TypeError, ValueError):
                continue
            raw_values = item.get("values")
            if not isinstance(raw_values, list):
                continue
            values = tuple(str(value) for value in raw_values if str(value).strip())
            if values:
                parsed_sequence.append((period, values))

    sequence_by_period = dict(parsed_sequence)
    min_period = max(base_period - window + 1, 1)
    sequence = [
        (period, sequence_by_period[period])
        for period in range(base_period, min_period - 1, -1)
        if period in sequence_by_period
    ]

    raw_notes = record.get("notes")
    notes = [str(note) for note in raw_notes] if isinstance(raw_notes, list) else []
    status_value = str(record.get("status") or "")
    error_value = str(record.get("error") or "").strip()

    if error_value or status_value in {"error", "no_candidates"} or not sequence:
        reason = error_value or "无基准窗口内缓存候选数据"
        fail_line = f'缓存 {site.name} {site.url} {reason}'
        return SiteAnalysis(index, site, [], fail_line, f'FAIL {reason}')

    audit_notes = list(notes)
    if len(sequence) < window and not any("仅" in note for note in audit_notes):
        audit_notes.append(f'仅有 {len(sequence)} 期数据（目标 {window} 期）')
    if sequence and not is_consecutive_sequence(sequence) and not any("不连续" in note for note in audit_notes):
        audit_notes.append('数据不是连续期数')

    status = f'OK 缓存 {len(sequence)} 期数据'
    if audit_notes:
        status += '；需审核：' + '；'.join(audit_notes)
    return SiteAnalysis(index, site, sequence, None, status, '；'.join(audit_notes) if audit_notes else None)


def load_sites_count(sites_path: Path) -> int:
    if not sites_path.exists():
        raise FileNotFoundError(f"站点配置不存在：{sites_path}")

    payload = json.loads(sites_path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and isinstance(payload.get("sites"), list):
        return len(payload["sites"])
    raise ValueError("站点配置格式错误：必须是站点列表或包含 sites 列表的对象")


def normalize_path_text(path_text: object, base_dir: Path) -> str:
    if not isinstance(path_text, str) or not path_text.strip():
        raise ValueError("source_sites 缺失或无效")
    path = Path(path_text.strip())
    if not path.is_absolute():
        path = base_dir / path
    return str(path.resolve()).casefold()


def get_cache_site_count(payload: dict[str, object]) -> int:
    summary = payload.get("summary")
    raw_site_count = summary.get("site_count") if isinstance(summary, dict) else payload.get("site_count")
    try:
        return int(cast(str | int | float, raw_site_count))
    except (TypeError, ValueError):
        raise ValueError("site_count 缺失或无效") from None


def validate_cache_integrity(
    payload: dict[str, object],
    raw_sites: list[object],
    cache_path: Path,
    sites_path: Path,
    requested_window: int,
    requested_max_search: int,
) -> None:
    if payload.get("schema") != "duan_recent_10_cache.v1":
        raise ValueError("拒绝使用近10期缓存：schema 不匹配")

    try:
        cache_window = int(cast(str | int | float, payload.get("window")))
    except (TypeError, ValueError):
        raise ValueError("拒绝使用近10期缓存：window 缺失或无效") from None
    if cache_window < requested_window:
        raise ValueError("拒绝使用近10期缓存：window 小于本次检测窗口")

    try:
        cache_max_search = int(cast(str | int | float, payload.get("max_search")))
    except (TypeError, ValueError):
        raise ValueError("拒绝使用近10期缓存：max_search 缺失或无效") from None
    if cache_max_search != requested_max_search:
        raise ValueError("拒绝使用近10期缓存：max_search 与本次参数不一致")

    expected_source = str(sites_path.resolve()).casefold()
    cache_source = normalize_path_text(payload.get("source_sites"), cache_path.parent)
    if cache_source != expected_source:
        raise ValueError("拒绝使用近10期缓存：source_sites 与本次 sites.json 不一致")
    cached_hash = payload.get("source_sites_hash")
    if not isinstance(cached_hash, str) or not cached_hash.strip():
        raise ValueError("拒绝使用近10期缓存：缺少 source_sites_hash，必须重新生成缓存")
    try:
        expected_hash = hashlib.sha256(sites_path.resolve().read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"拒绝使用近10期缓存：sites.json 读取失败：{exc}") from exc
    if cached_hash.strip().lower() != expected_hash:
        raise ValueError("拒绝使用近10期缓存：source_sites_hash 与本次 sites.json 不一致")

    sites_count = load_sites_count(sites_path)
    cache_site_count = get_cache_site_count(payload)
    if cache_site_count != sites_count:
        raise ValueError("拒绝使用近10期缓存：site_count 与 sites.json 站点数不一致")
    if len(raw_sites) != sites_count:
        raise ValueError("拒绝使用近10期缓存：sites 列表数量与 sites.json 站点数不一致")


def load_cache_analyses(
    cache_path: Path,
    sites_path: Path,
    base_period: int,
    window: int,
    max_search: int,
) -> tuple[list[SiteAnalysis], dict[str, object]]:
    if not cache_path.exists():
        raise FileNotFoundError(f"近10期缓存不存在：{cache_path}")

    payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("近10期缓存格式错误：顶层必须是对象")
    raw_sites = payload.get("sites")
    if not isinstance(raw_sites, list):
        raise ValueError("近10期缓存格式错误：缺少 sites 列表")
    validate_cache_integrity(payload, raw_sites, cache_path, sites_path, window, max_search)

    analyses = [
        cache_record_to_analysis(record, base_period, window)
        for record in raw_sites
        if isinstance(record, dict)
    ]
    return analyses, payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='杀段数据跨站重复检测（站点之间数据完全一致则判重复）')
    p.add_argument('--period', type=int, required=True, help='当前期数')
    p.add_argument('--window', type=int, default=10, help='往前看多少期，默认 10')
    p.add_argument('--max-search', type=int, default=30, help='不足最多往前替补多少期，默认 30')
    p.add_argument('--timeout', type=int, default=20, help='单个请求超时秒数')
    p.add_argument('--delay', type=float, default=0.05, help='提交任务间暂停秒数')
    p.add_argument('--workers', type=int, default=8, help='并发抓取数量')
    p.add_argument('--sites', default='sites.json', help='站点配置 JSON')
    p.add_argument('--recent-cache', default='recent_10_cache.json', help='近10期缓存 JSON')
    p.add_argument('--output', help='输出文件路径，不填则自动生成')
    p.add_argument('--verify-ssl', action='store_true', help='校验证书')
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    output_dir = Path(__file__).resolve().parent
    cache_path = Path(args.recent_cache)
    if not cache_path.is_absolute():
        cache_path = output_dir / cache_path
    sites_path = Path(args.sites)
    if not sites_path.is_absolute():
        sites_path = output_dir / sites_path

    try:
        ordered, cache_payload = load_cache_analyses(cache_path, sites_path, args.period, args.window, args.max_search)
    except Exception as exc:
        print(f'输入错误：{exc}', file=sys.stderr)
        return 2

    print(f'当前期数：{args.period}期')
    print(f'检测窗口：读取 recent_10_cache.json 近 {args.window} 期基准数据')
    print(f'缓存文件：{cache_path}；站点数：{len(ordered)}')
    if cache_payload.get("generated_at"):
        print(f'缓存生成时间：{cache_payload.get("generated_at")}')
    print('实时抓取：已禁用，本检测只使用缓存基准结果')
    print()
    for done, analysis in enumerate(ordered, start=1):
        print(f'[{done}/{len(ordered)}] {analysis.site.name} ({analysis.site.pick}) {analysis.status}')

    # ---- 跨站对比 ----
    sep = '=' * 60
    print(f'\n{sep}')
    print('跨站重复检测结果（按共同期号对齐，连续一致分级）')
    print(sep)

    valid = [a for a in ordered if a.sequence]
    duplicate_pairs = []
    suspect_pairs = []
    seen = set()
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            level, run = classify_pair(valid[i].sequence, valid[j].sequence)
            if level is None or run is None:
                continue
            key = tuple(sorted([valid[i].site.url, valid[j].site.url]))
            if key in seen:
                continue
            seen.add(key)
            if level == "duplicate":
                duplicate_pairs.append((valid[i], valid[j], run))
            elif level == "suspect":
                suspect_pairs.append((valid[i], valid[j], run))

    if not duplicate_pairs and not suspect_pairs:
        print('\n✅ 无连续3期及以上相同的疑似/重复网站')
    else:
        for a_i, a_j, run in duplicate_pairs:
            print(f'\n【重复拒收】{a_i.site.name} 与 {a_j.site.name}')
            print(f'  连续一致：{len(run)} 期')
            print('  对齐数据：')
            for period, vals in run:
                print(f'    {period}期：{fmt_values(vals)}')
        for a_i, a_j, run in suspect_pairs:
            print(f'\n【疑似重复-人工审核】{a_i.site.name} 与 {a_j.site.name}')
            print(f'  连续一致：{len(run)} 期')
            print('  对齐数据：')
            for period, vals in run:
                print(f'    {period}期：{fmt_values(vals)}')
        print(f'\n📊 重复拒收 {len(duplicate_pairs)} 组，疑似审核 {len(suspect_pairs)} 组')

    # ---- 失败统计 ----
    fails = [a for a in ordered if a.fail_line]
    if fails:
        print(f'\n{sep}')
        print('失败站点')
        print(sep)
        for a in fails:
            print(f'  {a.fail_line}')

    audits = [a for a in ordered if a.audit_note and not a.fail_line]
    if audits:
        print(f'\n{sep}')
        print('需要人工审核的抓取情况')
        print(sep)
        for a in audits:
            print(f'  目录：杀段 | 网站：{a.site.name} | URL：{a.site.url} | pick：{a.site.pick} | 问题：{a.audit_note}')

    success_count = len(ordered) - len(fails)
    print(f'\n{sep}')
    print(f'检测完成：总 {len(ordered)} 站，成功 {success_count}，失败 {len(fails)}，重复拒收 {len(duplicate_pairs)} 组，疑似审核 {len(suspect_pairs)} 组')

    # ---- 写文件 ----
    output_path = Path(args.output).resolve() if args.output else output_dir / f'{args.period}期重复检测结果.txt'
    lines: list[str] = []
    lines.append('杀段数据跨站重复检测结果')
    lines.append(f'当前期数：{args.period}期')
    lines.append(f'检测窗口：读取 recent_10_cache.json 近 {args.window} 期基准数据，按共同期号对齐')
    lines.append(f'缓存文件：{cache_path}')
    lines.append(f'站点数：{len(ordered)} ，成功：{success_count} ，失败：{len(fails)}')
    lines.append('')
    lines.append(sep)
    lines.append('检测结果')
    lines.append(sep)
    if not duplicate_pairs and not suspect_pairs:
        lines.append('')
        lines.append('无连续3期及以上相同的疑似/重复网站')
    else:
        for a_i, a_j, run in duplicate_pairs:
            lines.append('')
            lines.append(f'【重复拒收】{a_i.site.name} 与 {a_j.site.name}')
            lines.append(f'  连续一致：{len(run)} 期')
            lines.append('  对齐数据：')
            for period, vals in run:
                lines.append(f'    {period}期：{fmt_values(vals)}')
        for a_i, a_j, run in suspect_pairs:
            lines.append('')
            lines.append(f'【疑似重复-人工审核】{a_i.site.name} 与 {a_j.site.name}')
            lines.append(f'  连续一致：{len(run)} 期')
            lines.append('  对齐数据：')
            for period, vals in run:
                lines.append(f'    {period}期：{fmt_values(vals)}')
    if fails:
        lines.append('')
        lines.append(sep)
        lines.append('失败站点')
        lines.append(sep)
        for a in fails:
            lines.append(f'  {a.fail_line}')
    if audits:
        lines.append('')
        lines.append(sep)
        lines.append('需要人工审核的抓取情况')
        lines.append(sep)
        for a in audits:
            lines.append(f'  目录：杀段 | 网站：{a.site.name} | URL：{a.site.url} | pick：{a.site.pick} | 问题：{a.audit_note}')
    output_path.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8-sig')
    print(f'\n结果已保存：{output_path}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
