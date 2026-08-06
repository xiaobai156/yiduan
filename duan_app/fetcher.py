# -*- coding: utf-8 -*-
import ssl
import subprocess
import time
import warnings
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from duan_app.constants import FETCH_ATTEMPTS, REMOTE_RESET_ERRNOS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, TRANSIENT_HTTP_CODES
from duan_app.text_utils import compact_line, decode_bytes, decompress_bytes, normalize_text


def is_remote_reset_error(exc: BaseException | str) -> bool:
    if isinstance(exc, URLError) and exc.reason:
        return is_remote_reset_error(exc.reason)

    winerror = getattr(exc, "winerror", None)
    errno = getattr(exc, "errno", None)
    if winerror in REMOTE_RESET_ERRNOS or errno in REMOTE_RESET_ERRNOS:
        return True

    message = str(exc)
    return any(str(code) in message for code in REMOTE_RESET_ERRNOS)

def build_ssl_contexts(verify_ssl: bool):
    if verify_ssl:
        return [None]

    contexts = [ssl._create_unverified_context()]
    try:
        compat = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        compat.check_hostname = False
        compat.verify_mode = ssl.CERT_NONE
        try:
            compat.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                compat.minimum_version = ssl.TLSVersion.TLSv1
        except (AttributeError, ValueError):
            pass
        legacy_server_connect = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
        if isinstance(legacy_server_connect, int):
            compat.options |= legacy_server_connect
        contexts.append(compat)
    except Exception:
        pass
    return contexts

class CurlFetchError(RuntimeError):
    def __init__(self, exit_code: int, message: str):
        self.exit_code = exit_code
        super().__init__(f"curl exit {exit_code}: {message.strip()}")

def is_transient_http_error(exc: BaseException) -> bool:
    return isinstance(exc, HTTPError) and exc.code in TRANSIENT_HTTP_CODES

def is_ssl_handshake_text(text: str) -> bool:
    lowered = text.lower()
    return (
        "ssl/tls" in lowered
        or "schannel" in lowered
        or "handshake" in lowered
        or "tlsv1" in lowered
        or "wrong version number" in lowered
        or "certificate" in lowered
    )

def curl_fetch_text(url: str, timeout: int, verify_ssl: bool) -> str:
    command = [
        "curl",
        "--location",
        "--silent",
        "--show-error",
        "--fail",
        "--compressed",
        "--http1.1",
        "--connect-timeout",
        str(max(5, min(timeout, 15))),
        "--max-time",
        str(max(timeout, 20)),
        "--retry",
        "2",
        "--retry-delay",
        "1",
        "--retry-connrefused",
        "--retry-all-errors",
        "-A",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "-H",
        "Cache-Control: no-cache",
        url,
    ]
    if not verify_ssl:
        command[6:6] = ["--insecure", "--ssl-no-revoke"]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(timeout + 10, 30),
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"curl超时：{url}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="ignore")
        raise CurlFetchError(completed.returncode, stderr)
    return decode_bytes(completed.stdout, None)

def fetch_text(url: str, timeout: int, verify_ssl: bool) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "close",
    }
    contexts = build_ssl_contexts(verify_ssl)
    last_error: Exception | None = None

    for attempt in range(FETCH_ATTEMPTS):
        for context in contexts:
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=timeout, context=context) as response:
                    raw = decompress_bytes(response.read(), response.headers)
                    return decode_bytes(raw, response.headers)
            except HTTPError as exc:
                if is_transient_http_error(exc):
                    last_error = exc
                    continue
                raise
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
        if attempt == FETCH_ATTEMPTS - 1:
            break
        delay = min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt))
        if last_error is not None and is_remote_reset_error(last_error):
            delay += min(2.0, attempt * 0.5)
        time.sleep(delay)

    if last_error is not None:
        try:
            return curl_fetch_text(url, timeout, verify_ssl)
        except Exception as curl_error:
            if is_ssl_handshake_text(str(curl_error)) or isinstance(curl_error, CurlFetchError):
                raise curl_error
            raise last_error
    raise URLError("打开失败")

def is_placeholder_document(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {"", "0", "1", "ok", "OK"}

def cache_busted_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_={time.time_ns()}"

def fetch_page_text(
    url: str,
    timeout: int,
    verify_ssl: bool,
    attempts: int = 6,
    cache_bust_first: bool = False,
) -> str:
    last_text = ""
    for attempt in range(max(1, attempts)):
        next_url = cache_busted_url(url) if cache_bust_first or attempt > 0 else url
        text = fetch_text(next_url, timeout, verify_ssl)
        if not is_placeholder_document(text):
            return text
        last_text = text
        time.sleep(1.0 + attempt * 0.5)
    raise URLError(f"页面返回空壳内容：{compact_line(last_text, 40)}")

def render_page_text(url: str, timeout: int, verify_ssl: bool) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("浏览器渲染不可用：缺少 playwright") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(ignore_https_errors=not verify_ssl)
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=max(timeout, 10) * 1000)
            return page.content()
        finally:
            browser.close()
