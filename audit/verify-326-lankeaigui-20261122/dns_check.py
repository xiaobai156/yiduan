"""看页内自报的易记域名/备用域名原文，并核对 DNS 与证书。"""
import re
import socket
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from duan_app.fetcher import render_page_text

page = render_page_text("https://255560.com/topic/350479.html", 40, False)
html = str(page)
hits = set(re.findall(r"[0-9A-Za-z][0-9A-Za-z.-]{2,30}\.(?:com|net|cc|xyz|work|cyou|top|site)(?::\d+)?", html))
print("页内域名候选:", sorted(hits)[:30])
for m in re.finditer(r"(易记|备用|收藏|防劫持)[^<>\n]{0,60}", html):
    print("  ", m.group(0)[:80])
for host in ("255560.com", "255560b.com", "zdwcig.iyo4d-81klf-udwkqg.work"):
    try:
        ip = socket.gethostbyname(host)
    except Exception as exc:
        ip = f"DNSFAIL {exc}"
    print(f"{host} -> {ip}")
