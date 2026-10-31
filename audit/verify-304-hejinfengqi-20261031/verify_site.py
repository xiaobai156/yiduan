# -*- coding: utf-8 -*-
"""304 期失败站 禾尽风起 现场验证：直接取原始响应，判断异常 vs 无数据。

只读网络，不写缓存、不写正式 TXT。
"""
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from duan_app.fetcher import fetch_text  # noqa: E402

SITE = {
    "name": "禾尽风起",
    "url": "https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a47ecaa57dc857ae1bf570e?url=txbb",
    "api_url": "https://herymche.x6l2j-h6kfu-qdresg.work:29466/api/proxy/manager-articles/6a47ecaa57dc857ae1bf570e",
}


def show(label: str, text: str) -> None:
    print(f"--- {label}: len={len(text)}")
    periods = re.findall(r"(30[0-9])\s*[期期]?", text)
    uniq = sorted({int(p) for p in periods}, reverse=True)
    print(f"    期数出现(300-309): {uniq}")
    for kw in ("304", "303", "302", "杀", "绝杀", "段"):
        print(f"    count({kw!r})={text.count(kw)}")
    idx = text.find("304")
    if idx >= 0:
        print("    304 上下文:", repr(text[max(0, idx - 120): idx + 200]))
    else:
        print("    未出现 304")


def main() -> int:
    for label, url in (("API", SITE["api_url"]), ("PAGE", SITE["url"])):
        try:
            text = fetch_text(url, 25, True)
        except Exception as exc:  # noqa: BLE001
            print(f"--- {label}: FETCH ERROR {type(exc).__name__}: {exc}")
            continue
        show(label, text)
        out = PROJECT / "audit" / "verify-304-hejinfengqi-20261031" / f"{label.lower()}_raw.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"    saved={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
