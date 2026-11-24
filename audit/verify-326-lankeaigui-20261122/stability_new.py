"""新地址连开 5 次：落地是否稳定（是否无需跳转）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from duan_app.fetcher import render_page_text
from duan_app.text_utils import html_to_text

NEW = "https://bbrqhvww.4eylv-8gp30-jpndzw.work:17488/topic/350479.html"
for i in range(5):
    try:
        page = render_page_text(NEW, 40, False)
        rows = sum(1 for l in html_to_text(page).splitlines() if "期:[杀一段]" in l)
        land = page.source_url
        print(f"{i+1}: rows={rows} 原地={land.rstrip('/') == NEW.rstrip('/')} land={land}")
    except Exception as exc:
        print(f"{i+1}: FAIL {type(exc).__name__}: {exc}")
