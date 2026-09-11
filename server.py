#!/usr/bin/env python3
"""
Holdings Scanner - local server
--------------------------------
Serves index.html and downloads the daily holdings files for you, so the
"Fetch latest" button works. Browsers can't download these files directly
from another website (CORS), which is why this small server exists.

    python server.py            # then open http://localhost:8000
    python server.py 9000       # use a different port
    python server.py --lan      # also open it from your phone on the same Wi-Fi
    python server.py --download data   # just save today's 14 files into ./data
                                       # (used by the GitHub Pages workflow)

Only the Python standard library is used - nothing to install.
Downloaded files are cached per day in ./cache/YYYY-MM-DD/.
"""
import datetime
import gzip
import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

SSGA = "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{t}.xlsx"

# Every fund maps to a list of candidate URLs, tried in order.
SOURCES = {t: [SSGA.format(t=t.lower())] for t in
           ["SPY", "DIA", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
            "XLP", "XLRE", "XLU", "XLV", "XLY"]}
# QQQ: the holdings table on https://www.invesco.com/qqq-etf/en/about.html is loaded
# from Invesco's data service (JSON). 46090E103 is QQQ's CUSIP.
QQQ_API = "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/{id}/holdings/fund?idType={kind}&productType=ETF"
SOURCES["QQQ"] = [
    QQQ_API.format(id="46090E103", kind="cusip"),
    QQQ_API.format(id="QQQ", kind="ticker"),
    "https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0"
    "?audienceType=Investor&action=download&ticker=QQQ",
]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

_lock = threading.Lock()


def _decode(body, encoding):
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        return zlib.decompress(body)
    return body


def _kind(body):
    """Return file type of a downloaded body, or None if it looks like an HTML error page."""
    if body[:2] == b"PK":
        return "xlsx"
    head = body[:400].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return None
    if head.startswith(b"{") or head.startswith(b"["):
        return "json"
    return "csv"


def download(ticker, refresh=False):
    day = datetime.date.today().isoformat()
    folder = os.path.join(CACHE, day)
    os.makedirs(folder, exist_ok=True)
    if not refresh:
        for ext in ("xlsx", "csv", "json"):
            path = os.path.join(folder, f"{ticker}.{ext}")
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    return fh.read(), ext, "cache"

    body, kind, url = fetch_remote(ticker)
    with _lock:
        with open(os.path.join(folder, f"{ticker}.{kind}"), "wb") as fh:
            fh.write(body)
    return body, kind, url


def fetch_remote(ticker):
    """Try each source URL for a fund; return (bytes, kind, url) or raise."""
    errors = []
    for url in SOURCES[ticker]:
        if "invesco" in url:
            extra = {"Referer": "https://www.invesco.com/qqq-etf/en/about.html",
                     "Origin": "https://www.invesco.com"}
        else:
            extra = {"Referer": "https://www.ssga.com/"}
        req = urllib.request.Request(url, headers=dict(HEADERS, **extra))
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = _decode(resp.read(), resp.headers.get("Content-Encoding", ""))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url} -> {exc}")
            continue
        kind = _kind(body)
        if not kind or len(body) < 200:
            errors.append(f"{url} -> returned a web page instead of a holdings file")
            continue
        return body, kind, url
    raise RuntimeError("; ".join(errors) or "no source configured")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")

    def _json(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/ping":
            return self._json(200, {"ok": True, "funds": list(SOURCES)})
        if path.startswith("/api/holdings/"):
            ticker = path.rsplit("/", 1)[-1].upper()
            if ticker not in SOURCES:
                return self._json(404, {"error": f"Unknown fund {ticker}"})
            try:
                body, kind, src = download(ticker, refresh="refresh=1" in query)
            except Exception as exc:  # report back to the page
                return self._json(502, {"error": str(exc)})
            ctype = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "csv": "text/csv", "json": "application/json"}[kind]
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-File-Kind", kind)
            self.send_header("X-Source", src)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("", "/"):
            self.path = "/index.html"
        return super().do_GET()


def download_all(folder):
    """Save every fund's file into `folder` plus a manifest.json the page reads."""
    os.makedirs(folder, exist_ok=True)
    manifest = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "files": {}, "errors": {}}
    for ticker in SOURCES:
        for ext in ("xlsx", "csv", "json"):          # drop yesterday's file, whatever its type
            old = os.path.join(folder, f"{ticker}.{ext}")
            if os.path.exists(old):
                os.remove(old)
        try:
            body, kind, url = fetch_remote(ticker)
        except Exception as exc:
            manifest["errors"][ticker] = str(exc)[:300]
            print(f"  {ticker:5} FAILED  {exc}")
            continue
        name = f"{ticker}.{kind}"
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(body)
        manifest["files"][ticker] = {"file": name, "source": url}
        print(f"  {ticker:5} ok      {len(body):>9,} bytes  {url}")
    with open(os.path.join(folder, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"{len(manifest['files'])} of {len(SOURCES)} files saved to {folder}")
    return 0 if manifest["files"] else 1


def lan_ip():
    """Best guess at this computer's address on the local network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("10.255.255.255", 1))
            return sk.getsockname()[0]
    except OSError:
        return None


def main():
    args = sys.argv[1:]
    if "--download" in args:
        i = args.index("--download")
        folder = args[i + 1] if i + 1 < len(args) else "data"
        sys.exit(download_all(folder))

    cloud_port = os.environ.get("PORT")          # set by hosts such as Render or Railway
    nums = [a for a in args if a.isdigit()]
    port = int(cloud_port or (nums[0] if nums else 8000))
    lan = "--lan" in args or bool(cloud_port)
    server = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"Holdings Scanner running at {url}  (Ctrl+C to stop)")
    if lan and not cloud_port:
        ip = lan_ip()
        print(f"On your phone (same Wi-Fi): http://{ip or '<this computer IP>'}:{port}")
    if "--no-browser" not in args and not cloud_port:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
