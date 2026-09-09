"""Retry only identities in one failure TXT; preserve unrelated records."""
import copy
import json
import re
import sys
import argparse
import hashlib
from datetime import datetime
from pathlib import Path

from duan_app.config import default_result_dir, load_sites_config
from duan_app.crawl_service import process_site
from duan_app.parsing.profiles import apply_site_profiles, load_site_profiles
from duan_app.persistence.outputs import build_failure_stats_lines, build_ranking_lines, safe_write_text
from duan_app.persistence.transaction import capture, commit_updates


FAILURE = re.compile(
    r"^失败\s+(.+?)\s+(https?://\S+)\s+方向:\s*(top|bottom)\s+"
    r"期数:\s*([1-9]\d*)期?\s+阶段:\s*.+?\s+原因:\s*.+$"
)
SUCCESS = re.compile(r"^([1-7]段)\s+([^\d\s][^\r\n]*?)\s*$")


def refresh_cache_record(record):
    fingerprint = record.get("fingerprint")
    periods = sorted(int(period) for period, value in fingerprint.items() if str(value).strip())
    consecutive = all(periods[index] == periods[index - 1] + 1 for index in range(1, len(periods)))
    removable = ("同期高可信候选冲突", "本次实时判定失败", "定向重抓恢复", "仅抓到", "期数不连续", "脚本/接口错误")
    notes = [str(note) for note in record.get("notes", []) if str(note) and not str(note).startswith(removable)]
    if len(periods) < 10:
        notes.append(f"仅抓到{len(periods)}期")
    if not consecutive:
        notes.append("期数不连续")
    script_errors = int(record.get("script_error_count") or 0)
    if script_errors:
        notes.append(f"脚本/接口错误{script_errors}个")
    record["notes"] = list(dict.fromkeys(notes))
    record["status"] = "ok" if not record["notes"] else "audit"
    record.pop("error", None)


def parse_failures(text):
    records = []
    for number, line in enumerate(text.splitlines(keepends=True)):
        if line.strip().startswith("失败 "):
            match = FAILURE.fullmatch(line.strip())
            if not match:
                raise ValueError(f"第 {number + 1} 行失败记录格式不完整，停止重抓")
            name, url, pick, period = match.groups()
            records.append((number, (name, url, pick), int(period)))
    periods = {record[2] for record in records}
    if len(periods) > 1:
        raise ValueError("只允许单期失败 TXT；检测到混合期数")
    return records


def merge_success(text, values):
    """Keep existing data lines verbatim; insert recovered sites above ranking."""
    lines = text.splitlines(keepends=True)
    body = [line for line in lines if not re.fullmatch(r"(?:内容\s+次数\s+排名|排行|\d+段\s+\d+\s+\d+|合计\s+\d+条)", line.strip())]
    newline = "\r\n" if "\r\n" in text else "\n"
    existing = {}
    for line in body:
        match = SUCCESS.fullmatch(line.strip())
        if match:
            value, name = match.groups()
            existing.setdefault(name, []).append(value)
    accepted = {}
    for name, value in values.items():
        if name in existing and existing[name] != [value]:
            continue  # A conflicting existing success must never be overwritten.
        accepted[name] = value
    added = {name: value for name, value in accepted.items() if name not in existing}
    if not added:
        return text, accepted
    while body and not body[-1].strip():
        body.pop()
    if body and not body[-1].endswith(("\n", "\r")):
        body[-1] += newline
    body.extend(f"{value} {name}{newline}" for name, value in added.items())
    counts = {}
    for line in body:
        match = SUCCESS.fullmatch(line.strip())
        if match:
            value = match.group(1)
            counts[value] = counts.get(value, 0) + 1
    return "".join(body) + newline.join(build_ranking_lines(counts)) + newline, accepted


def merge_failures(text, records, recovered):
    removed = {number for number, identity, _ in records if identity in recovered}
    if not removed:
        return text
    lines = text.splitlines(keepends=True)
    body = []
    for number, line in enumerate(lines):
        if number in removed:
            continue
        if line.strip() in {"失败分类统计", "无失败"} or re.fullmatch(r".+ \d+条", line.strip()):
            continue
        body.append(line)
    remaining = [line.strip() for line in body if line.strip().startswith("失败 ")]
    newline = "\r\n" if "\r\n" in text else "\n"
    return "".join(body).rstrip("\r\n") + newline.join(build_failure_stats_lines(remaining)) + newline


def retry(fail_path, success_path, sites, *, timeout=20, verify_ssl=True,
          cache_path=None, sites_path=None, processor=None):
    processor = processor or process_site
    if fail_path.resolve() == success_path.resolve():
        raise ValueError("成功和失败 TXT 不能是同一个文件")
    paths = [fail_path, success_path] + ([cache_path] if cache_path is not None else [])
    before = capture(paths)
    text = before[fail_path.resolve()].decode("utf-8-sig")
    records = parse_failures(text)
    if not records:
        return 0, 0
    period = records[0][2]
    filename = re.fullmatch(r"(\d+)期-段-失败\.txt", fail_path.name)
    if filename and int(filename.group(1)) != period:
        raise ValueError("失败 TXT 文件名与内容期数不一致")
    if not re.fullmatch(rf"0*{period}期-段\.txt", success_path.name):
        raise ValueError("成功 TXT 文件名与失败记录期数不一致")
    configured = {(site.name, site.url, site.pick): (i, site) for i, site in enumerate(sites, 1)}
    targets = list(dict.fromkeys(identity for _, identity, _ in records))
    cache = None
    if cache_path is not None and not cache_path.exists():
        raise FileNotFoundError(f"近10期缓存不存在，停止删除失败记录：{cache_path}")
    if cache_path is not None and cache_path.exists():
        if cache_path.resolve() in {fail_path.resolve(), success_path.resolve()}:
            raise ValueError("缓存与 TXT 路径不能相同")
        cache = json.loads(before[cache_path.resolve()].decode("utf-8-sig"))
        if not isinstance(cache, dict) or not isinstance(cache.get("sites"), list):
            raise ValueError("缓存格式错误，停止重抓")
        meta = cache.get("_meta")
        if not isinstance(meta, dict) or meta.get("format") not in {"duan_recent_10_cache.v1", "duan_recent_10_cache.v2"}:
            raise ValueError("缓存版本不受支持，停止重抓")
        if sites_path is None:
            raise ValueError("缺少 sites.json 路径，停止缓存更新")
        if Path(str(meta.get("source_sites", ""))).resolve() != sites_path.resolve():
            raise ValueError("缓存来源路径与 sites.json 不一致，停止重抓")
        expected_hash = hashlib.sha256(sites_path.read_bytes()).hexdigest()
        if str(meta.get("source_sites_hash", "")).lower() != expected_hash.lower():
            raise ValueError("缓存配置哈希不一致，停止重抓")
        if any(not isinstance(item, dict) or not isinstance(item.get("fingerprint"), dict)
               for item in cache["sites"]):
            raise ValueError("缓存不是 fingerprint 格式，停止重抓")
        if int(cache.get("periods", 0)) != 10:
            raise ValueError("缓存窗口不是10期，停止重抓")
        meta_summary = meta.get("summary")
        if not isinstance(meta_summary, dict) or int(meta_summary.get("site_count", -1)) != len(cache["sites"]):
            raise ValueError("缓存摘要站点数不一致，停止重抓")
    values, successful = {}, {}
    for position, identity in enumerate(targets, 1):
        name, url, pick = identity
        entry = configured.get(identity)
        if entry is None:
            print(f"[{position}/{len(targets)}] 保留失败 {name}：未配置、已封存或身份不一致")
            continue
        index, site = entry
        try:
            result = processor(index, site, timeout, verify_ssl, {period}, str(period))
            matches = [match for match in result.matches if match.issue == period]
            if (result.site != site or result.fail_line or len(matches) != 1
                    or not re.fullmatch(r"[1-7]段", matches[0].value)):
                print(f"[{position}/{len(targets)}] 保留失败 {name}：{result.status}")
                continue
            values[name] = matches[0].value
            successful[identity] = matches[0].value
            print(f"[{position}/{len(targets)}] 校验成功 {name} {matches[0].value}")
        except Exception as exc:
            print(f"[{position}/{len(targets)}] 保留失败 {name}：{type(exc).__name__}: {exc}")
    success_text = (before[success_path.resolve()] or b"").decode("utf-8-sig")
    merged_success, accepted = merge_success(success_text, values)
    recovered = {identity: value for identity, value in successful.items() if identity[0] in accepted}
    if not recovered:
        return 0, len(targets)
    updates = {}
    if merged_success != success_text:
        updates[success_path] = merged_success
    if cache is not None:
        updated = copy.deepcopy(cache)
        for identity, value in recovered.items():
            matches = [item for item in updated["sites"]
                       if (item.get("name"), item.get("url"), item.get("pick")) == identity]
            if len(matches) > 1:
                raise ValueError(f"缓存站点身份重复：{identity[0]}；停止写入")
            if matches:
                matches[0]["fingerprint"][str(period)] = value
                matches[0]["status"] = "ok"
                matches[0].pop("error", None)
                notes = [str(note) for note in matches[0].get("notes", []) if str(note)]
                matches[0]["notes"] = [note for note in notes if "本次实时判定失败" not in note] or ["定向重抓恢复"]
            else:
                raise ValueError(f"缓存缺少目标站点：{identity[0]}；停止删除失败记录")
        for item in updated["sites"]:
            if isinstance(item, dict):
                refresh_cache_record(item)
        updated["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = updated["_meta"]["summary"]
        summary["site_count"] = len(updated["sites"])
        for status in ("ok", "audit", "error", "no_candidates"):
            summary[f"{status}_count"] = sum(1 for item in updated["sites"] if item.get("status") == status)
        summary["full_10_count"] = sum(
            1 for item in updated["sites"]
            if len(item.get("fingerprint", {})) == 10
        )
        if updated != cache:
            updates[cache_path] = json.dumps(updated, ensure_ascii=False, indent=2) + "\n"
    updates[fail_path] = merge_failures(text, records, recovered)
    commit_updates(before, updates)
    return len(recovered), len(targets) - len(recovered)


def run(args):
    try:
        root = Path(__file__).resolve().parent.parent
        fail_path = Path(args.retry_fail).resolve()
        records = parse_failures(fail_path.read_text(encoding="utf-8-sig"))
        if not records:
            print("失败 TXT 无失败站点，无需重抓")
            return 0
        period = records[0][2]
        # The period comes from the selected TXT, never the normal CLI default.
        sites_path = Path(args.sites)
        if not sites_path.is_absolute():
            sites_path = root / sites_path
        sites = load_sites_config(sites_path)
        profiles = load_site_profiles(root / "site_profiles.json", sites)
        sites = apply_site_profiles(sites, profiles)
        success_path = Path(args.success).resolve() if args.success else default_result_dir(root) / f"{period:03d}期-段.txt"
        cache_path = Path(args.recent_cache)
        if not cache_path.is_absolute():
            cache_path = root / cache_path
        ok, failed = retry(fail_path, success_path, sites, sites_path=sites_path, timeout=args.timeout,
                           verify_ssl=not args.allow_insecure or args.verify_ssl,
                           cache_path=None if args.no_recent_cache else cache_path)
        print(f"失败 TXT 重抓完成：恢复 {ok} 站，保留失败 {failed} 站")
        return 1 if failed else 0
    except Exception as exc:
        print(f"重抓未完成：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="只重抓失败 TXT 中的站点")
    parser.add_argument("retry_fail")
    parser.add_argument("--success")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--recent-cache", default="recent_10_cache.json")
    parser.add_argument("--no-recent-cache", action="store_true")
    parser.add_argument("--allow-insecure", action="store_true")
    parser.add_argument("--verify-ssl", action="store_true")
    parser.add_argument("--sites", default="sites.json")
    raise SystemExit(run(parser.parse_args()))
