# -*- coding: utf-8 -*-
import re


SCRIPT_SRC_RE = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*([\"']?)([^\"'\s>]+)\1", re.I
)

IFRAME_SRC_RE = re.compile(
    r"<iframe\b[^>]*\bsrc\s*=\s*(\\?[\"']?)([^\"'\s>\\]+)\1", re.I
)

STRDECODE_RE = re.compile(r"strdecode\s*\(\s*([\"'])([^\"']+)\1\s*\)", re.I)

DECODE_B64_RE = re.compile(r"decodeB64\s*\(\s*([\"'])([^\"']+)\1\s*\)", re.I)

PAGE_DATA_RE = re.compile(r"__PAGE_DATA__\s*=\s*([\"'])([^\"']+)\1", re.I)

ISSUE_RE = re.compile(r"(?<!\d)([0-9０-９]{1,4})\s*期")

FULLWIDTH_DIGITS = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "⓪": "0",
        "①": "1",
        "②": "2",
        "③": "3",
        "④": "4",
        "⑤": "5",
        "⑥": "6",
        "⑦": "7",
        "⑧": "8",
        "⑨": "9",
        "⑩": "10",
        "⒈": "1",
        "⒉": "2",
        "⒊": "3",
        "⒋": "4",
        "⒌": "5",
        "⒍": "6",
        "⒎": "7",
        "⒏": "8",
        "⒐": "9",
    }
)

CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

CHAR_TRANS = str.maketrans(
    {
        "【": "[",
        "】": "]",
        "［": "[",
        "］": "]",
        "〔": "[",
        "〕": "]",
        "〖": "[",
        "〗": "]",
        "（": "(",
        "）": ")",
        "：": ":",
        "開": "开",
        "　": " ",
        "\xa0": " ",
    }
)

NUMBER_TOKEN = r"[0-9０-９零一二两三四五六七八九十]{1,2}"

KILL_DUAN_RE = re.compile(rf"(?<![\[【绝灭])杀\s*({NUMBER_TOKEN})\s*段")

DIRECT_KILL_BRACKET_DUAN_RE = re.compile(
    rf"\d{{2,4}}\s*期\s*杀\s*[\[【《{{『]\s*({NUMBER_TOKEN})\s*段\s*[\]】》}}』][^\n]{{0,24}}?开\s*[:：]?\s*[^准对中错赢]{{0,24}}(?:准|对|中|错|赢)",
    re.I,
)

BRACKET_DUAN_RE = re.compile(
    rf"(?:(?:绝|灭|稳)\s*)?杀\s*(?:一|1)\s*段\s*[\[【《{{『]\s*({NUMBER_TOKEN})\s*段\s*[\]】》}}』]"
)

MULTI_DUAN_VALUE_RE = re.compile(
    r"\d{2,4}\s*期\s*[\[【《{『]\s*([1-7](?:\s*[\.、,，]\s*[1-7]){1,8}\s*段)\s*[\]】》}』]",
    re.I,
)

ANY_BRACKET_DUAN_RE = re.compile(rf"[\[【《{{『]\s*({NUMBER_TOKEN})\s*段\s*[\]】》}}』]")

REPEATED_DUAN_RE = re.compile(r"[『「\[\【《]?\s*([1-7])\1{4}\s*段\s*[』」\]\】》]?", re.I)

SITE_REPEATED_DUAN_RE = re.compile(r"[『「\[\【《]?\s*([1-7])\1{2,4}\s*段\s*[』」\]\】》]?", re.I)

RESULT_KEYWORD_RE = re.compile(r"(?:绝|灭|稳|必)?\s*杀\s*(?:一|1)\s*段", re.I)

WENJIN_DUAN_RE = re.compile(r"稳\s*禁\s*(?:一|1)\s*段", re.I)

BODY_LOCATOR_RE = re.compile(r"\d{2,4}\s*期[^\n]{0,80}?(?:绝|灭|稳|必)?\s*杀\s*(?:一|1)\s*段", re.I)

WENJIN_BODY_LOCATOR_RE = re.compile(r"\d{2,4}\s*期[^\n]{0,80}?稳\s*禁\s*(?:一|1)\s*段", re.I)

OPEN_STATUS_RE = re.compile(r"开\s*[:：]?\s*[^准对中错赢]{0,24}(准|对|中|错|赢)")

TABLE_SEGMENT_RE = re.compile(r"[1-7]\s*段\s*[:：\-—–]{1,2}\s*(?:\d{2}[\.\-、,\s]*){2,}", re.I)

STRICT_BRACKET_VALUE_RE = re.compile(
    rf"(?:(?:绝|灭|稳)\s*)?杀\s*(?:一|1)\s*段[^\n]{{0,36}}?[『「\[\【《(]?\s*({NUMBER_TOKEN})\s*段\s*[』」\]\】》)]?[^\n]{{0,28}}?开\s*[:：]?\s*[^准对中错赢]{{0,24}}(?:准|对|中|错|赢)",
    re.I,
)

WENJIN_BRACKET_VALUE_RE = re.compile(
    rf"稳\s*禁\s*(?:一|1)\s*段[^\n]{{0,36}}?[『「\[\【《(]?\s*({NUMBER_TOKEN})\s*段\s*[』」\]\】》)]?[^\n]{{0,28}}?开\s*[:：]?\s*[^准对中错赢]{{0,24}}(?:准|对|中|错|赢)",
    re.I,
)

STRICT_KILL_VALUE_RE = re.compile(
    rf"(?:(?:绝|灭|稳)\s*)?杀\s*(?:一|1)\s*段[^\n]{{0,24}}?杀\s*({NUMBER_TOKEN})\s*段[^\n]{{0,24}}?开\s*[:：]?\s*[^准对中错赢]{{0,24}}(?:准|对|中|错|赢)",
    re.I,
)

STRICT_REPEATED_VALUE_RE = re.compile(
    r"(?:(?:绝|灭|稳)\s*)?杀\s*(?:一|1)\s*段[^\n]{0,36}?[『「\[\【《(]?\s*([1-7])\1{4}\s*段\s*[』」\]\】》)]?[^\n]{0,28}?开\s*[:：]?\s*[^准对中错赢]{0,24}(?:准|对|中|错|赢)",
    re.I,
)

TITLE_BRACKET_RE = re.compile(
    r"期\s*[:：]?\s*[^0-9A-Za-z\u4e00-\u9fff]{0,12}[\[【《]\s*([^\]】》]{2,30})\s*[\]】》]"
)

TITLE_PLAIN_RE = re.compile(
    r"期\s*[:：]?\s*[^0-9A-Za-z\u4e00-\u9fff]{0,12}((?:(?:绝|灭|稳)\s*)?杀\s*(?:一|1)\s*段)"
)

REMOTE_RESET_ERRNOS = {10053, 10054, 10060, 10061}

FETCH_ATTEMPTS = 5

RETRY_BASE_DELAY = 0.7

RETRY_MAX_DELAY = 4.0

TRANSIENT_HTTP_CODES = {502, 503, 504, 520, 521, 522, 523, 524}

CURL_SSL_EXIT_CODES = {35, 51, 58, 60}

WARNED_WRITE_PATHS: set[str] = set()

DEFAULT_RESULT_DIR_NAME = "七类数据统一归纳"

DEFAULT_FAILURE_RESULT_DIR_NAME = "七类数据统一归纳失败"

CANDIDATE_STRICT_THRESHOLD = 30

CANDIDATE_WINDOW_LIMIT = 3

MISS_RETRY_REASONS = ("无期数", "无定位", "无结果词")

ALLOW_REPEATED_DUAN_SITE_NAMES = {"澳门曾夫人", "宝马"}

MULTI_DUAN_SITE_NAMES = {"三地主"}

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "p",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
    "ol",
}

HIDDEN_HTML_TAGS = {"script", "style", "noscript", "template"}

TRUSTED_EXTERNAL_SCRIPT_HOST_SUFFIXES = (
    ".cosds.ahsccn.com",
    ".cosds.aohjifv.com",
)
