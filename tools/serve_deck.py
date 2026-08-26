#!/usr/bin/env python3
"""Static server with Range support, for reviewing a multi-file deck locally.

Python's http.server answers a Range request with 200 and the whole file. The
real media origin (Cloudflare/R2) answers 206 — verified on HenHouse — and that
difference is exactly what `preload="none"` plus an IntersectionObserver is
judged on: with 206 the browser streams the first chunk and starts playing, with
200 it downloads the whole clip first. Reviewing on a 200-only server would
misrepresent how the published deck loads.

  python3 tools/serve_deck.py out/venus-hestia 8912
"""
import os, re, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


class RangeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, directory=None, **k):
        super().__init__(*a, directory=directory, **k)

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()
        a, b = m.group(1), m.group(2)
        if a == "":                                  # suffix range: last N bytes
            start, end = max(0, size - int(b)), size - 1
        else:
            start = int(a)
            end = int(b) if b else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._limit = end - start + 1
        return f

    def copyfile(self, src, dst):
        if not hasattr(self, "_limit"):
            return super().copyfile(src, dst)
        left = self._limit
        del self._limit
        while left > 0:
            chunk = src.read(min(1 << 20, left))
            if not chunk:
                break
            dst.write(chunk)
            left -= len(chunk)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    root = os.path.abspath(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8912
    h = lambda *a, **k: RangeHandler(*a, directory=root, **k)
    print(f"serving {root} on http://127.0.0.1:{port}/  (Range: 206 supported)")
    HTTPServer(("127.0.0.1", port), h).serve_forever()
