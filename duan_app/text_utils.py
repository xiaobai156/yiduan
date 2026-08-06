# -*- coding: utf-8 -*-
import gzip
import html
import re
import zlib
from html.parser import HTMLParser

from duan_app.constants import BLOCK_TAGS, CHAR_TRANS, CHINESE_NUMBERS, FULLWIDTH_DIGITS, HIDDEN_HTML_TAGS


class PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in HIDDEN_HTML_TAGS:
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if normalized_tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in HIDDEN_HTML_TAGS:
            self.hidden_depth = max(0, self.hidden_depth - 1)
            return
        if self.hidden_depth:
            return
        if normalized_tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data and not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)

def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.translate(FULLWIDTH_DIGITS).translate(CHAR_TRANS)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n+ *", "\n", text)
    return text.strip()

def compact_line(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", normalize_text(text))
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text

def number_to_int(value: str) -> int | None:
    value = normalize_text(value).strip()
    value = value.translate(FULLWIDTH_DIGITS)
    if value.isdigit():
        return int(value)
    if value in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[value]
    if len(value) == 2 and value.startswith("十") and value[1] in CHINESE_NUMBERS:
        return 10 + CHINESE_NUMBERS[value[1]]
    if len(value) == 2 and value.endswith("十") and value[0] in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[value[0]] * 10
    if len(value) == 3 and value[1] == "十":
        left = CHINESE_NUMBERS.get(value[0])
        right = CHINESE_NUMBERS.get(value[2])
        if left is not None and right is not None:
            return left * 10 + right
    return None

def format_duan(value: int) -> str:
    return f"{value}段"

def is_valid_duan_value(value: int | None) -> bool:
    return value is not None and 1 <= value <= 7

def strip_hidden_html_blocks(document: str) -> str:
    cleaned = document or ""
    for tag in HIDDEN_HTML_TAGS:
        cleaned = re.sub(
            rf"<{tag}\b[^>]*>.*?</{tag}\s*>",
            " ",
            cleaned,
            flags=re.I | re.S,
        )
    return cleaned

def looks_like_html(document: str) -> bool:
    return re.search(r"</?[a-zA-Z][^>]*>", document or "") is not None

def html_to_text(document: str) -> str:
    parser = PlainTextParser()
    cleaned = strip_hidden_html_blocks(document)
    try:
        parser.feed(cleaned)
        parser.close()
    except Exception:
        return normalize_text(re.sub(r"<[^>]+>", " ", cleaned))
    return normalize_text(parser.text())

def decode_bytes(raw: bytes, headers) -> str:
    encodings: list[str] = []
    charset = headers.get_content_charset() if headers else None
    if charset:
        encodings.append(charset)

    head = raw[:4096].decode("ascii", errors="ignore")
    meta = re.search(r"charset\s*=\s*([a-zA-Z0-9_-]+)", head, re.I)
    if meta:
        encodings.append(meta.group(1))

    encodings.extend(["utf-8", "gb18030", "big5"])
    used: set[str] = set()
    for encoding in encodings:
        key = encoding.lower()
        if key in used:
            continue
        used.add(key)
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            continue
    return raw.decode("utf-8", errors="ignore")

def decompress_bytes(raw: bytes, headers) -> bytes:
    encoding = (headers.get("Content-Encoding", "") if headers else "").lower()
    if "gzip" in encoding or raw.startswith(b"\x1f\x8b"):
        return gzip.decompress(raw)
    if "deflate" in encoding:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw
