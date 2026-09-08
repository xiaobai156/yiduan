# -*- coding: utf-8 -*-
import base64
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from duan_app.constants import DECODE_B64_RE, ISSUE_RE, PAGE_DATA_RE, STRDECODE_RE
from duan_app.domain import ArticleDocumentList, ArticlePayloadUnavailableError, ArticleRecordError
from duan_app.parsing.engine import has_result_keyword
from duan_app.text_utils import normalize_text


def decode_base64_payload(payload: str) -> str | None:
    try:
        padded = payload + ("=" * (-len(payload) % 4))
        raw = base64.b64decode(padded)
    except Exception:
        return None

    for encoding in ("utf-8", "gb18030", "big5"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None

def decode_embedded_base64_blocks(text: str) -> list[str]:
    decoded: list[str] = []
    for regex in (STRDECODE_RE, DECODE_B64_RE, PAGE_DATA_RE):
        for match in regex.finditer(text):
            decoded_text = decode_base64_payload(match.group(2))
            if decoded_text:
                decoded.append(decoded_text)
    return decoded

class _HtmlNode:
    def __init__(self, tag: str = "#root", attrs: list[tuple[str, str | None]] | None = None) -> None:
        self.tag = tag
        self.attrs = {str(key).lower(): str(value or "") for key, value in (attrs or [])}
        self.children: list[_HtmlNode | str] = []

    def text_content(self) -> str:
        return "".join(
            child if isinstance(child, str) else child.text_content()
            for child in self.children
        )


class _HtmlTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _HtmlNode()
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _HtmlNode(tag, attrs)
        self.stack[-1].children.append(node)
        if tag.lower() not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(_HtmlNode(tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag.lower() == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _find_target_html_nodes(text: str, target_id: str) -> list[tuple[_HtmlNode, str]]:
    parser = _HtmlTreeParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise ArticleRecordError(f"动态页面HTML解析失败：{exc}") from exc

    target = str(target_id).strip()
    id_attributes = {
        "id",
        "data-id",
        "data-record-id",
        "data-article-id",
        "article-id",
        "articleid",
        "record-id",
        "recordid",
    }
    found: list[tuple[_HtmlNode, str]] = []

    def visit(node: _HtmlNode, path: str) -> None:
        for key, value in node.attrs.items():
            if key in id_attributes and value.strip() == target:
                found.append((node, path))
                break
        child_index = 0
        for child in node.children:
            if isinstance(child, _HtmlNode):
                visit(child, f"{path}.{child.tag}[{child_index}]")
                child_index += 1

    visit(parser.root, "$html")
    return found


def _target_html_document(text: str, target_id: str) -> tuple[str, dict[str, object]]:
    nodes = _find_target_html_nodes(text, target_id)
    if not nodes:
        raise ArticleRecordError(f"页面未包含目标记录ID块[{target_id}]")
    if len(nodes) > 1:
        raise ArticleRecordError(f"页面找到多个目标记录ID块[{target_id}]：{len(nodes)}个")
    node, path = nodes[0]
    nested_identity_attributes = {
        "data-id",
        "data-record-id",
        "data-article-id",
        "article-id",
        "articleid",
        "record-id",
        "recordid",
    }

    def has_nested_other_record(current: _HtmlNode, is_root: bool = False) -> bool:
        for key, value in current.attrs.items():
            if not is_root and key in nested_identity_attributes and value.strip() and value.strip() != target_id:
                return True
        return any(
            isinstance(child, _HtmlNode) and has_nested_other_record(child)
            for child in current.children
        )

    if has_nested_other_record(node, is_root=True):
        raise ArticleRecordError(f"目标记录块包含其他记录ID[{target_id}]")
    body = node.text_content().strip()
    if not body:
        raise ArticlePayloadUnavailableError(f"目标记录ID块为空[{target_id}]")
    return body, {
        "record_id": target_id,
        "record_path": path,
        "article_count": 1,
    }


def add_document_with_decoded(
    text: str,
    documents: list[str],
    seen: set[str],
    *,
    source_url: str | None = None,
    document_type: str = "unknown",
    document_id: str | None = None,
    block_id: str | None = None,
    source_title: str = "",
) -> None:
    queue = [text]
    index = 0
    while index < len(queue):
        current = queue[index]
        index += 1
        if not current:
            continue
        key = str(hash(current))
        if key in seen:
            continue
        seen.add(key)
        if isinstance(documents, ArticleDocumentList):
            documents.append_document(
                current,
                {
                    "source_url": source_url or "",
                    "document_type": document_type,
                    "document_id": document_id,
                    "block_id": block_id,
                    "source_title": source_title,
                },
            )
        else:
            documents.append(current)
        queue.extend(decode_embedded_base64_blocks(current))

def article_admin_api_url(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/article/admin/([^/?#]+)", parsed.path)
    if not match:
        return None
    return urljoin(url, f"/api/proxy/manager-articles/{match.group(1)}")

def article_manager_api_url(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/article/(?:manager|lottery)/([^/?#]+)", parsed.path)
    if not match:
        return None
    return urljoin(url, f"/api/proxy/manager-articles/{match.group(1)}")

def legacy_article_admin_api_url(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/article/admin/([^/?#]+)", parsed.path)
    if not match:
        return None
    return urljoin(url, f"/api/proxy/admin-articles/{match.group(1)}")

def is_article_admin_url(url: str) -> bool:
    return re.search(r"/article/admin/[^/?#]+", urlparse(url).path) is not None

def is_article_manager_url(url: str) -> bool:
    return re.search(r"/article/(?:manager|lottery)/[^/?#]+", urlparse(url).path) is not None

ARTICLE_ID_FIELDS = ("id", "articleId", "article_id")

ARTICLE_RECORD_FIELDS = {"authorNickname", "title", "html"}

def article_record_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/article/(?:admin|manager|lottery)/([^/?#]+)", parsed.path)
    return match.group(1).strip() if match else None

def article_record_identifiers(record: dict[str, object]) -> set[str]:
    return {
        str(record[key]).strip()
        for key in ARTICLE_ID_FIELDS
        if key in record and isinstance(record[key], (str, int)) and str(record[key]).strip()
    }

def iter_article_record_nodes(value: object, path: str = "$"):
    if isinstance(value, dict):
        identifiers = article_record_identifiers(value)
        if identifiers and ARTICLE_RECORD_FIELDS.intersection(value):
            yield value, path
        for key, nested in value.items():
            child_path = f"{path}.{key}" if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)) else f"{path}[{key!r}]"
            yield from iter_article_record_nodes(nested, child_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from iter_article_record_nodes(nested, f"{path}[{index}]")

def extract_article_record(
    text: str, target_id: str
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise ArticlePayloadUnavailableError("接口不是结构化JSON")

    records = list(iter_article_record_nodes(payload))
    if not records:
        raise ArticlePayloadUnavailableError("接口未返回文章记录")
    matches = [
        (record, path)
        for record, path in records
        if target_id in article_record_identifiers(record)
    ]
    if not matches:
        raise ArticleRecordError(f"未找到目标记录ID[{target_id}]")
    if len(matches) > 1:
        raise ArticleRecordError(f"找到多个目标记录ID[{target_id}]：{len(matches)}个")
    record, record_path = matches[0]
    return record, {
        "record_id": target_id,
        "record_path": record_path,
        "article_count": len(records),
    }

def decode_article_field(record: dict[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ArticleRecordError(f"目标记录缺少{field_name}字段")
    return decode_base64_payload(value) or value

def validate_article_record(
    record: dict[str, object], target_id: str, site_name: str, pick: str
) -> dict[str, object]:
    if article_record_identifiers(record) != {target_id}:
        raise ArticleRecordError(f"记录ID字段冲突[{article_record_identifiers(record)}]")
    author = record.get("authorNickname")
    if not isinstance(author, str) or normalize_text(author) != normalize_text(site_name):
        raise ArticleRecordError(f"作者校验失败[{author!r}]")
    title = decode_article_field(record, "title")
    body = decode_article_field(record, "html")
    if not ISSUE_RE.search(normalize_text(title)) or not has_result_keyword(title):
        raise ArticleRecordError("标题未通过期数和数据关键词校验")
    sections = record.get("formSections")
    if not isinstance(sections, list):
        raise ArticleRecordError("栏目字段缺失")
    main_sections = [
        section
        for section in sections
        if isinstance(section, dict)
        and section.get("type") == "mainarticle"
        and isinstance(section.get("name"), str)
        and section["name"].strip()
    ]
    if len(main_sections) != 1:
        raise ArticleRecordError(f"主栏目校验失败[{len(main_sections)}个]")
    if pick not in {"top", "bottom"}:
        raise ArticleRecordError(f"方向校验失败[{pick}]")
    if not has_result_keyword(body):
        raise ArticleRecordError("正文未找到目标数据关键词")
    return {
        "author": author,
        "title": title,
        "column": main_sections[0]["name"],
        "pick": pick,
        "target_field": "html",
    }

def article_record_document(
    record: dict[str, object], validated: dict[str, object]
) -> str:
    return "\n".join(
        [
            str(validated["author"]),
            str(validated["title"]),
            decode_article_field(record, "html"),
        ]
    )

def iter_article_json_documents(
    text: str, target_id: str, site_name: str, pick: str
):
    record, metadata = extract_article_record(text, target_id)
    validated = validate_article_record(record, target_id, site_name, pick)
    yield article_record_document(record, validated), {**metadata, **validated}

def add_article_json_documents(
    article_json: str,
    documents: list[str],
    seen_docs: set[str],
    *,
    target_id: str | None = None,
    site_name: str | None = None,
    pick: str | None = None,
    source_url: str | None = None,
) -> None:
    if not target_id or not site_name or not pick:
        raise ArticleRecordError("动态接口缺少强制记录ID、站名或方向")
    for article_document, metadata in iter_article_json_documents(
        article_json, target_id, site_name, pick
    ):
        add_document_with_decoded(
            article_document,
            documents,
            seen_docs,
            source_url=source_url,
            document_type="api",
            document_id=target_id,
            block_id=str(metadata.get("record_path", "")),
            source_title=str(metadata.get("title", "")),
        )
        metadata = {**metadata, "source_url": source_url or ""}
        if isinstance(documents, ArticleDocumentList):
            documents.article_audit.append(metadata)

def dynamic_document_has_target_id(text: str, target_id: str) -> bool:
    if target_id in text:
        return True
    return any(target_id in decoded for decoded in decode_embedded_base64_blocks(text))

def add_dynamic_article_document(
    text: str,
    documents: list[str],
    seen_docs: set[str],
    target_id: str,
    site_name: str | None = None,
    pick: str | None = None,
    *,
    source_url: str | None = None,
    document_type: str = "browser",
) -> None:
    json_source = next(
        (
            candidate
            for candidate in [text, *decode_embedded_base64_blocks(text)]
            if candidate.lstrip().startswith("{") or candidate.lstrip().startswith("[")
        ),
        None,
    )
    if json_source is not None:
        record, metadata = extract_article_record(json_source, target_id)
        validated = (
            validate_article_record(record, target_id, site_name, pick)
            if site_name and pick
            else {}
        )
        if isinstance(documents, ArticleDocumentList):
            documents.article_audit.append(
                {
                    **metadata,
                    **validated,
                    "source_url": source_url or "",
                    "document_type": document_type,
                }
            )
        add_document_with_decoded(
            "\n".join(
                decode_article_field(record, field_name)
                for field_name in ("authorNickname", "title", "html")
            ),
            documents,
            seen_docs,
            source_url=source_url,
            document_type=document_type,
            document_id=target_id,
            block_id=str(metadata.get("record_path", "")),
            source_title=str(validated.get("title", "")),
        )
        return
    scoped_text = ""
    metadata: dict[str, object] = {}
    last_error: ArticleRecordError | None = None
    for html_source in [text, *decode_embedded_base64_blocks(text)]:
        try:
            scoped_text, metadata = _target_html_document(html_source, target_id)
            break
        except ArticleRecordError as exc:
            last_error = exc
    if not scoped_text:
        if last_error is not None:
            raise last_error
        raise ArticleRecordError(f"页面未包含目标记录ID块[{target_id}]")
    if site_name and normalize_text(site_name) not in normalize_text(scoped_text):
        raise ArticleRecordError(f"目标记录块未包含站名锚点[{site_name}]")
    if pick not in {None, "top", "bottom"}:
        raise ArticleRecordError(f"页面方向校验失败[{pick}]")
    if not has_result_keyword(scoped_text):
        raise ArticlePayloadUnavailableError("目标记录块未包含目标数据关键词")
    if isinstance(documents, ArticleDocumentList):
        documents.article_audit.append(
            {
                **metadata,
                "source_url": source_url or "",
                "document_type": document_type,
            }
        )
    add_document_with_decoded(
        scoped_text,
        documents,
        seen_docs,
        source_url=source_url,
        document_type=document_type,
        document_id=target_id,
        block_id=str(metadata.get("record_path", "")),
    )
