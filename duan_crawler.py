# -*- coding: utf-8 -*-
"""正式兼容入口；业务实现位于 duan_app。"""

from duan_app import *  # noqa: F401,F403
from duan_app.cli import build_parser, main  # noqa: F401
from duan_app.documents import collect_documents as _collect_documents
from duan_app.fetcher import fetch_page_text, fetch_text, render_page_text


def collect_documents(*args, **kwargs):
    """保持外部验证器替换入口网络函数的兼容行为。"""
    kwargs.setdefault("fetch_text_fn", fetch_text)
    kwargs.setdefault("fetch_page_text_fn", fetch_page_text)
    kwargs.setdefault("render_page_text_fn", render_page_text)
    return _collect_documents(*args, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
