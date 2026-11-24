"""只读体检：按主机名分组，测 TLS 握手 + HTTP 状态，看哪些配置地址已失效或被跳转。"""
from __future__ import annotations

import json
import re
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sites = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))

groups: dict[tuple[str, int, str], list[str]] = {}
for s in sites:
    p = urlparse(s["url"])
    scheme = p.scheme or "https"
    port = p.port or (443 if scheme == "https" else 80)
    groups.setdefault((p.hostname or "", port, scheme), []).append(s["name"])


def probe(key):
    host, port, scheme = key
    names = groups[key]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    out = {"host": host, "port": port, "scheme": scheme, "sites": names}
    try:
        sock = socket.create_connection((host, port), timeout=8)
        if scheme == "https":
            sock = ctx.wrap_socket(sock, server_hostname=host)
        out["tls"] = "ok"
        sock.settimeout(10)
        sock.sendall(
            f"GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\nAccept: */*\r\n\r\n".encode()
        )
        buf = b""
        while len(buf) < 8192:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        sock.close()
        head = buf.decode("utf-8", "replace")
        status = re.match(r"HTTP/\d\.\d (\d{3})", head)
        out["status"] = status.group(1) if status else "?"
        loc = re.search(r"(?im)^location:\s*(\S+)", head)
        out["location"] = loc.group(1) if loc else ""
    except Exception as exc:
        out["tls"] = out.get("tls", "fail")
        out["status"] = "CONNFAIL"
        out["location"] = f"{type(exc).__name__}: {exc}"[:120]
    return out


with ThreadPoolExecutor(max_workers=24) as pool:
    results = list(pool.map(probe, list(groups)))

results.sort(key=lambda r: (r["status"] == "200", r["host"]))
Path("audit/host-health-20261122/hosts.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

bad = [r for r in results if r["status"] != "200"]
print(f"主机数={len(results)} 站点数={len(sites)} 非200={len(bad)}")
print("\n== 非 200 ==")
for r in bad:
    print(f"{r['status']:>9} {r['host']}:{r['port']} 站点={','.join(r['sites'])} {r['location'][:70]}")
