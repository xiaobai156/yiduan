# -*- coding: utf-8 -*-
import html
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse

from duan_app.constants import FULLWIDTH_DIGITS, IFRAME_SRC_RE, ISSUE_RE, SCRIPT_SRC_RE, TRUSTED_EXTERNAL_SCRIPT_HOST_SUFFIXES
from duan_app.domain import ArticleDocumentList, ArticlePayloadUnavailableError, ArticleRecordError, Site
from duan_app.dynamic_articles import add_article_json_documents, add_document_with_decoded, add_dynamic_article_document, article_admin_api_url, article_manager_api_url, article_record_id_from_url, is_article_admin_url, is_article_manager_url, legacy_article_admin_api_url
from duan_app.fetcher import fetch_page_text, fetch_text, render_page_text
from duan_app.parsing.custom import collect_candidates
from duan_app.selection import find_matches_from_candidates
from duan_app.text_utils import html_to_text, normalize_text


def documents_have_strict_context(
    documents: list[str],
    issue_filter: set[int] | None,
    site_name: str | None,
    pick: str | None,
) -> bool:
    if not issue_filter or not site_name or not pick:
        return False
    site = Site(site_name, "", pick)
    candidates = collect_candidates(documents, site, issue_filter=issue_filter)
    if find_matches_from_candidates(candidates, issue_filter, site):
        return True
    normalized_site = normalize_text(site_name).replace(" ", "")
    has_name_anchor = any(
        normalized_site in normalize_text(document).replace(" ", "")
        for document in documents
    )
    if has_name_anchor:
        return False
    # This helper only decides whether a dynamic page needs another render pass.
    # Dynamic records have already passed the strict ID/author checks before reaching here.
    return bool(find_matches_from_candidates(
        [
            candidate
            for document in documents
            for candidate in collect_candidates(
                [document.replace(site_name, "")],
                Site("", "", pick),
                issue_filter=issue_filter,
            )
        ],
        issue_filter,
        Site("", "", pick),
    ))

def should_fetch_script(script_url: str, root_url: str) -> bool:
    parsed = urlparse(script_url)
    root = urlparse(root_url)
    path = parsed.path.lower()
    same_host = parsed.hostname == root.hostname
    if not same_host:
        hostname = (parsed.hostname or "").lower()
        trusted_content_script = (
            hostname.endswith(TRUSTED_EXTERNAL_SCRIPT_HOST_SUFFIXES)
            and "/upload/script/" in path
            and path.endswith(".js")
        )
        return trusted_content_script
    return (
        "/upload/script/" in path
        or path.endswith("/script.js")
        or path.endswith("view_content.php")
        or re.search(r"/htm/bbs/top\d+\.js$", path) is not None
    )

def should_fetch_frame(frame_url: str, root_url: str) -> bool:
    parsed = urlparse(frame_url)
    root = urlparse(root_url)
    if parsed.hostname != root.hostname:
        return False

    path = parsed.path.lower()
    return "/main/bbs/" in path or "/htm/bbs/" in path

def xiaoyao_detail_urls(
    listing_html: str,
    base_url: str,
    issue_filter: set[int] | None,
) -> list[str]:
    matches: list[tuple[int, str]] = []
    seen_issues: set[int] = set()
    for match in re.finditer(
        r"<a\b[^>]*\bhref\s*=\s*([\"']?)([^\"'\s>]+)\1[^>]*>(.*?)</a>",
        listing_html,
        flags=re.I | re.S,
    ):
        title = normalize_text(html_to_text(match.group(3))).replace(" ", "")
        issue_match = ISSUE_RE.search(title)
        if (
            issue_match is None
            or "逍遥浪子" not in title
            or "绝杀一段" not in title
            or "实力见证" not in title
        ):
            continue
        issue = int(issue_match.group(1).translate(FULLWIDTH_DIGITS))
        detail_url = urljoin(base_url, html.unescape(match.group(2)))
        if urlparse(detail_url).hostname != urlparse(base_url).hostname:
            continue
        if issue in seen_issues:
            continue
        seen_issues.add(issue)
        matches.append((issue, detail_url))
    return [url for _, url in matches]

def collect_documents(
    url: str,
    timeout: int,
    verify_ssl: bool,
    page_attempts: int = 6,
    cache_bust_first: bool = False,
    issue_filter: set[int] | None = None,
    site_name: str | None = None,
    pick: str | None = None,
    api_url: str | None = None,
    fetch_text_fn=None,
    fetch_page_text_fn=None,
    render_page_text_fn=None,
) -> tuple[list[str], list[str]]:
    fetch_text_impl = fetch_text if fetch_text_fn is None else fetch_text_fn
    fetch_page_text_impl = fetch_page_text if fetch_page_text_fn is None else fetch_page_text_fn
    render_page_text_impl = render_page_text if render_page_text_fn is None else render_page_text_fn
    documents: ArticleDocumentList = ArticleDocumentList()
    seen_docs: set[str] = set()
    script_errors: list[str] = []
    script_urls: list[str] = []
    seen_scripts: set[str] = set()
    frame_urls: list[str] = []
    seen_frames: set[str] = set()

    article_mode = is_article_admin_url(url)
    manager_mode = is_article_manager_url(url)
    dynamic_record_id = article_record_id_from_url(url) if article_mode or manager_mode else None
    if (article_mode or manager_mode) and not dynamic_record_id:
        raise ArticleRecordError("动态详情页URL缺少记录ID")
    dynamic_api_url = (
        api_url
        or (article_manager_api_url(url) if manager_mode else article_admin_api_url(url))
    )
    should_render_article_page = False
    api_blocked = False

    if (article_mode or manager_mode) and dynamic_api_url:
        try:
            add_article_json_documents(
                fetch_text_impl(dynamic_api_url, timeout, verify_ssl),
                documents,
                seen_docs,
                target_id=dynamic_record_id,
                site_name=site_name,
                pick=pick,
                source_url=dynamic_api_url,
            )
            return documents, script_errors
        except ArticlePayloadUnavailableError as exc:
            script_errors.append(f"{dynamic_api_url} ({exc})")
            should_render_article_page = True
        except ArticleRecordError:
            raise
        except HTTPError as exc:
            script_errors.append(f"{dynamic_api_url} ({exc})")
            if exc.code == 404:
                should_render_article_page = True
            else:
                api_blocked = True
        except Exception as exc:
            script_errors.append(f"{dynamic_api_url} ({exc})")
            api_blocked = True

        if article_mode and not api_url and not api_blocked:
            legacy_api_url = legacy_article_admin_api_url(url)
            if legacy_api_url and legacy_api_url != dynamic_api_url:
                try:
                    add_article_json_documents(
                        fetch_text_impl(legacy_api_url, timeout, verify_ssl),
                        documents,
                        seen_docs,
                        target_id=dynamic_record_id,
                        site_name=site_name,
                        pick=pick,
                        source_url=legacy_api_url,
                    )
                    return documents, script_errors
                except ArticlePayloadUnavailableError as legacy_exc:
                    script_errors.append(f"{legacy_api_url} ({legacy_exc})")
                    should_render_article_page = True
                except ArticleRecordError:
                    raise
                except HTTPError as legacy_exc:
                    script_errors.append(f"{legacy_api_url} ({legacy_exc})")
                    if legacy_exc.code == 404:
                        should_render_article_page = True
                    else:
                        api_blocked = True
                except Exception as legacy_exc:
                    script_errors.append(f"{legacy_api_url} ({legacy_exc})")
                    api_blocked = True

        if api_blocked:
            return documents, script_errors

    page_html = fetch_page_text_impl(url, timeout, verify_ssl, page_attempts, cache_bust_first)
    if article_mode or manager_mode:
        try:
            add_dynamic_article_document(
                page_html,
                documents,
                seen_docs,
                dynamic_record_id or "",
                site_name,
                pick,
                source_url=url,
                document_type="page",
            )
        except ArticlePayloadUnavailableError as exc:
            script_errors.append(f"{url} ({exc})")
            should_render_article_page = True
        except ArticleRecordError as exc:
            if "目标记录ID" in str(exc) and "未包含" in str(exc):
                should_render_article_page = True
            else:
                script_errors.append(f"{url} ({exc})")
            should_render_article_page = True
    else:
        add_document_with_decoded(
            page_html,
            documents,
            seen_docs,
            source_url=url,
            document_type="page",
            block_id="page",
        )

    if site_name == "逍遥浪子":
        for detail_url in xiaoyao_detail_urls(page_html, url, issue_filter):
            try:
                detail_html = fetch_text_impl(detail_url, timeout, verify_ssl)
            except Exception as exc:
                script_errors.append(f"{detail_url} ({exc})")
            else:
                add_document_with_decoded(
                    detail_html,
                    documents,
                    seen_docs,
                    source_url=detail_url,
                    document_type="detail",
                    block_id=detail_url,
                )

    if (
        (article_mode or manager_mode)
        and (should_render_article_page or not documents_have_strict_context(documents, issue_filter, site_name, pick))
    ):
        try:
            rendered_html = render_page_text_impl(url, timeout, verify_ssl)
        except Exception as exc:
            script_errors.append(f"{url} 浏览器渲染失败：{exc}")
        else:
            try:
                add_dynamic_article_document(
                    rendered_html,
                    documents,
                    seen_docs,
                    dynamic_record_id or "",
                    site_name,
                    pick,
                    source_url=url,
                    document_type="browser",
                )
            except ArticleRecordError as exc:
                script_errors.append(f"{url} 浏览器结果校验失败：{exc}")

    script_index = 0
    frame_index = 0
    while True:
        for document in documents:
            for _, src in SCRIPT_SRC_RE.findall(document):
                full_url = urljoin(url, html.unescape(src))
                if full_url not in seen_scripts and should_fetch_script(full_url, url):
                    seen_scripts.add(full_url)
                    script_urls.append(full_url)

            for _, src in IFRAME_SRC_RE.findall(document):
                full_url = urljoin(url, html.unescape(src))
                if full_url not in seen_frames and should_fetch_frame(full_url, url):
                    seen_frames.add(full_url)
                    frame_urls.append(full_url)

        if script_index < len(script_urls):
            next_url = script_urls[script_index]
            script_index += 1
        elif frame_index < len(frame_urls):
            next_url = frame_urls[frame_index]
            frame_index += 1
        else:
            break

        try:
            nested_text = fetch_text_impl(next_url, timeout, verify_ssl)
        except Exception as exc:
            script_errors.append(f"{next_url} ({exc})")
            continue
        if article_mode or manager_mode:
            add_dynamic_article_document(
                nested_text,
                documents,
                seen_docs,
                dynamic_record_id or "",
                site_name,
                pick,
                source_url=next_url,
                document_type="iframe" if frame_index > 0 and script_index >= len(script_urls) else "script",
            )
        else:
            add_document_with_decoded(
                nested_text,
                documents,
                seen_docs,
                source_url=next_url,
                document_type="iframe" if frame_index > 0 and script_index >= len(script_urls) else "script",
                block_id=next_url,
            )

    return documents, script_errors
