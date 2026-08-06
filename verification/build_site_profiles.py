# -*- coding: utf-8 -*-
"""Build deterministic site parsing profiles from the formal site registry."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def stable_site_id(name: str, url: str) -> str:
    topic = topic_key_from_url(url)
    source = f"{name}|{topic or url}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def topic_key_from_url(url: str) -> str | None:
    match = re.search(r"/topic/(\d+)\.html/?$", urlparse(url).path)
    return match.group(1) if match else None


def document_sources(name: str, url: str) -> list[str]:
    path = urlparse(url).path.lower()
    if "/article/admin/" in path or "/article/manager/" in path:
        return ["api", "page", "browser"]
    if name == "逍遥浪子":
        return ["page", "detail"]
    return ["page", "script", "iframe"]


def main() -> int:
    sites = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))
    profiles = []
    for site in sites:
        name = str(site["name"]).strip()
        url = str(site["url"]).strip()
        profiles.append(
            {
                "site_id": stable_site_id(name, url),
                "name": name,
                "url": url,
                "pick": site["pick"],
                "name_anchors": [name],
                "section_keywords": ["绝杀一段", "绝杀1段", "杀一段", "杀1段"],
                "value_keyword": "段",
                "candidate_window": 3,
                "value_min": 1,
                "value_max": 7,
                "document_sources": document_sources(name, url),
                "record_id_required": "/article/admin/" in url.lower()
                or "/article/manager/" in url.lower(),
                "custom_parser": name if name in {"逍遥浪子", "寒来暑往", "会飞的猪", "及第成名"} else None,
            }
        )
    payload = {"schema": "duan_site_profiles.v1", "sites": profiles}
    (ROOT / "site_profiles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {len(profiles)} 个站点专属档案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
