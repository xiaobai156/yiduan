"""310 期 六合料王：直接抓 API 原始记录，查看真实标题与正文尾部（只读）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀段_解耦版")
sys.path.insert(0, str(PROJECT))

from duan_app.fetcher import fetch_text  # noqa: E402
from duan_app.dynamic_articles import (  # noqa: E402
    article_record_identifiers,
    iter_article_record_nodes,
    decode_article_field,
    decode_base64_payload,
)
from duan_app.constants import ISSUE_RE, STRDECODE_RE  # noqa: E402
from duan_app.parsing.engine import has_result_keyword  # noqa: E402

API = "https://uqdccnri.oy2bh-swrfr-gvzxkk.work:29499/api/proxy/manager-articles/6a0331f5e09a39d316b223b4"
TARGET_ID = "6a0331f5e09a39d316b223b4"
OUT = Path(__file__).with_name("documents")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = fetch_text(API, 20, True)
    (OUT / "api_raw.json").write_text(raw, encoding="utf-8")
    print("raw bytes:", len(raw))
    payload = json.loads(raw)
    records = list(iter_article_record_nodes(payload))
    print("records:", len(records))
    for record, path in records:
        ids = article_record_identifiers(record)
        print("record", path, "ids=", ids)
        if TARGET_ID not in ids:
            continue
        for field in ("authorNickname", "title", "html"):
            try:
                value = decode_article_field(record, field)
            except Exception as exc:  # noqa: BLE001
                print(f"  {field}: <error {exc}>")
                continue
            (OUT / f"field_{field}.txt").write_text(value, encoding="utf-8")
            lines = value.splitlines()
            print(f"  {field}: {len(value)} chars, {len(lines)} lines")
            print("    first:", repr(lines[0][:120]) if lines else None)
            print("    ISSUE_RE:", sorted({m.group(1) for m in ISSUE_RE.finditer(value)})[:5])
            print("    has_result_keyword:", has_result_keyword(value))
        sections = record.get("formSections")
        print("  formSections:", json.dumps(sections, ensure_ascii=False)[:300] if sections else None)
        title = decode_article_field(record, "title")
        body = decode_article_field(record, "html")
        print("\nTITLE repr:", repr(title[:200]))
        print("TITLE normalized check:", ISSUE_RE.search(title) is not None, has_result_keyword(title))
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        print("\nBODY lines:", len(body_lines))
        for line in body_lines[-15:]:
            print("  ", line[:180])
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
