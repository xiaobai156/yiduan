# -*- coding: utf-8 -*-
import json
import hashlib
import re
from dataclasses import replace
from pathlib import Path

from duan_app.config import topic_key_from_url
from duan_app.constants import CANDIDATE_WINDOW_LIMIT
from duan_app.domain import Site


SITE_SPECIFIC_PARSER_NAMES = {
    "大放光彩",
    "朗朗权坤",
    "寒来暑往",
    "澳门招财猫",
    "凉秋瑾言",
    "金刚护体",
    "忧烟殇往",
    "海晏河清",
    "会飞的猪",
    "女神绝杀",
    "杨进心水",
    "创世奇彩",
    "南天财柱",
    "英雄豪杰",
    "争战夺宝",
    "福星王子",
    "六合料王",
    "翩翩少年",
    "力钧势敌",
    "夏意正浓",
    "追彩少年",
    "传真神彩",
    "高人彩经",
    "蓝田生玉",
    "青翠欲滴",
    "彩民推荐",
    "素雪怜影",
    "节节胜利",
    "丰硕成果",
    "及第成名",
    "蛇口蜂针",
    "探囊取物",
    "澳门杀肖",
    "昙花一现",
    "名扬天下",
    "没有之后",
    "眉头眼尾",
    "恭喜发财",
    "大手大脚",
    "秋月春风",
    "淋漓尽精",
    "逍遥浪子",
    "狂犬吠日",
    "暗香疏影",
    "倚靠窗畔",
    "敢拼敢博",
    "寻宝先生",
    "玄机码王",
    "天机神料",
    "彩事顺意",
    "天上人间",
    "金刚财子",
    "披金执锐",
    "自知者明",
    "最佳女主",
}

CONFIRMED_NEW_SITE_PARSER_NAMES = {
    "澳门招财猫",
    "凉秋瑾言",
    "金刚护体",
    "忧烟殇往",
    "海晏河清",
    "会飞的猪",
    "女神绝杀",
    "杨进心水",
    "创世奇彩",
    "南天财柱",
    "英雄豪杰",
    "争战夺宝",
    "福星王子",
    "六合料王",
    "翩翩少年",
    "力钧势敌",
    "夏意正浓",
    "追彩少年",
    "传真神彩",
    "高人彩经",
    "蓝田生玉",
    "青翠欲滴",
    "彩民推荐",
    "素雪怜影",
    "节节胜利",
    "丰硕成果",
    "及第成名",
    "蛇口蜂针",
    "探囊取物",
    "澳门杀肖",
    "昙花一现",
    "名扬天下",
    "没有之后",
    "眉头眼尾",
    "恭喜发财",
    "大手大脚",
    "秋月春风",
    "淋漓尽精",
    "逍遥浪子",
    "狂犬吠日",
    "暗香疏影",
    "倚靠窗畔",
    "敢拼敢博",
    "寻宝先生",
    "玄机码王",
    "天机神料",
    "彩事顺意",
    "天上人间",
    "金刚财子",
    "披金执锐",
    "自知者明",
    "最佳女主",
}

SITE_SECTION_ANCHOR_ALIASES = {
    "澳门招财猫": ("招财猫",),
    "淋漓尽精": ("澳门任我发",),
    "雷锋": ("26064c.com", "26064d.com"),
    "赛马会第一版": ("877730c.com", "877730d.com"),
    "赛马会第二版": ("877730c.com", "877730d.com"),
    "白虎": ("73448b.com", "73448c.com"),
    "三地主": ("土地公", "三表主六段"),
}

SITE_TITLE_ISSUE_AUTHORITY_NAMES = {"寒来暑往", "澳门招财猫", "力钧势敌"}


def _is_url_like_anchor(value: object) -> bool:
    text = str(value).strip()
    if not text:
        return False
    return bool(
        re.search(r"(?:https?://|www\.)", text, re.I)
        or re.search(r"(?<![\w-])[\w-]+\.(?:com|net|org|cc|cn|xyz|work|site)(?![\w-])", text, re.I)
    )


def stable_site_id(site: Site) -> str:
    source = f"{site.name}|{topic_key_from_url(site.url) or site.url}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def load_site_profiles(path: Path, sites: list[Site]) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"站点专属解析档案读取失败：{path}，{exc}") from exc
    raw_profiles = payload.get("sites") if isinstance(payload, dict) else None
    if not isinstance(raw_profiles, list):
        raise ValueError(f"站点专属解析档案格式不对：{path}")

    profiles: dict[str, dict[str, object]] = {}
    for position, profile in enumerate(raw_profiles, start=1):
        if not isinstance(profile, dict):
            raise ValueError(f"站点专属解析档案第 {position} 项必须是对象")
        name = str(profile.get("name", "")).strip()
        if not name:
            raise ValueError(f"站点专属解析档案第 {position} 项缺少 name")
        if name in profiles:
            raise ValueError(f"站点专属解析档案目录名重复：{name}")
        profiles[name] = profile

    site_by_name = {site.name: site for site in sites}
    missing = sorted(set(site_by_name) - set(profiles))
    extra = sorted(set(profiles) - set(site_by_name))
    if missing:
        raise ValueError("缺少专属解析档案：" + "、".join(missing))
    if extra:
        raise ValueError("存在无正式站点的专属解析档案：" + "、".join(extra))

    for name, site in site_by_name.items():
        profile = profiles[name]
        if str(profile.get("url", "")) != site.url:
            raise ValueError(f"站点专属解析档案 URL 不一致：{name}")
        if str(profile.get("pick", "")) != site.pick:
            raise ValueError(f"站点专属解析档案方向不一致：{name}")
        if str(profile.get("site_id", "")) != stable_site_id(site):
            raise ValueError(f"站点专属解析档案稳定 ID 不一致：{name}")
        anchors = profile.get("name_anchors")
        if not isinstance(anchors, list) or not any(str(anchor).strip() for anchor in anchors):
            raise ValueError(f"站点专属解析档案缺少名称锚点：{name}")
        candidate_window = profile.get("candidate_window", 0)
        if not isinstance(candidate_window, (int, float, str)):
            raise ValueError(f"站点专属解析档案候选窗口无效：{name}")
        if int(candidate_window) != CANDIDATE_WINDOW_LIMIT:
            raise ValueError(f"站点专属解析档案候选窗口不一致：{name}")
        dynamic = any(
            marker in site.url.lower()
            for marker in ("/article/admin/", "/article/manager/", "/article/lottery/")
        )
        if bool(profile.get("record_id_required")) != dynamic:
            raise ValueError(f"站点专属解析档案文章 ID 边界不一致：{name}")
    return profiles


def apply_site_profiles(
    sites: list[Site], profiles: dict[str, dict[str, object]]
) -> list[Site]:
    """Attach validated semantic profile data without letting URL text become an anchor."""
    configured: list[Site] = []
    for site in sites:
        profile = profiles.get(site.name)
        if profile is None:
            raise ValueError(f"缺少站点专属解析档案：{site.name}")

        raw_name_anchors = profile.get("name_anchors", [])
        name_anchors = tuple(
            str(anchor).strip()
            for anchor in raw_name_anchors
            if str(anchor).strip() and not _is_url_like_anchor(anchor)
        )
        section_keywords = tuple(
            str(keyword).strip()
            for keyword in profile.get("section_keywords", [])
            if str(keyword).strip()
        )
        document_sources = tuple(
            str(source).strip()
            for source in profile.get("document_sources", [])
            if str(source).strip()
        )
        custom_parser = str(profile.get("custom_parser", "")).strip() or None
        section_scope = bool(profile.get("section_scope", False))
        configured.append(
            replace(
                site,
                name_anchors=name_anchors,
                section_keywords=section_keywords,
                document_sources=document_sources,
                custom_parser=custom_parser,
                section_scope=section_scope,
            )
        )
    return configured
