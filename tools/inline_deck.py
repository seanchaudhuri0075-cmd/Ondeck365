#!/usr/bin/env python3
"""Fold every external asset into one self-contained HTML file.

`index.html` keeps its `src="assets/..."` references: it is the diffable
build, and the standing test runs against it. This produces a SECOND file
alongside it with every image and video as a data: URI, so the deck travels
as a single document.

  python3 tools/inline_deck.py out/secret

Base64 costs 4 bytes per 3, so expect the payload to grow by a third. The
tool prints the before/after breakdown rather than leaving it to be guessed.
"""
import base64, mimetypes, os, re, sys

MIME = {".mp4": "video/mp4", ".webp": "image/webp", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}


def main(out_dir):
    src = os.path.join(out_dir, "index.html")
    dst = os.path.join(out_dir, "index.standalone.html")
    html = open(src, encoding="utf-8").read()
    refs = sorted(set(re.findall(r'(?:src|poster)="(assets/[^"]+)"', html)))
    rows, before = [], len(html.encode())
    for rel in refs:
        path = os.path.join(out_dir, rel)
        raw = open(path, "rb").read()
        ext = os.path.splitext(rel)[1].lower()
        mime = MIME.get(ext) or mimetypes.guess_type(rel)[0] or "application/octet-stream"
        b64 = base64.b64encode(raw).decode("ascii")
        html = html.replace(f'"{rel}"', f'"data:{mime};base64,{b64}"')
        rows.append((rel, len(raw), len(b64)))
    open(dst, "w", encoding="utf-8").write(html)
    after = len(html.encode())
    left = re.findall(r'(?:src|poster)="(?!data:)([^"]+)"', html)
    by = {}
    for rel, r, e in rows:
        k = os.path.splitext(rel)[1].lower()
        a, b, c = by.get(k, (0, 0, 0))
        by[k] = (a + 1, b + r, c + e)
    print(f"{'type':>6}{'files':>7}{'on disk':>16}{'base64':>16}{'growth':>9}")
    for k, (n, r, e) in sorted(by.items(), key=lambda x: -x[1][1]):
        print(f"{k:>6}{n:>7}{r:>16,}{e:>16,}{e / r:>8.2f}x")
    tr = sum(r for _, r, _ in rows); te = sum(e for _, _, e in rows)
    print(f"{'TOTAL':>6}{len(rows):>7}{tr:>16,}{te:>16,}{te / tr:>8.2f}x")
    print()
    print(f"index.html            {before:>14,} bytes  {before / 1048576:8.2f} MB")
    print(f"index.standalone.html {after:>14,} bytes  {after / 1048576:8.2f} MB")
    print(f"remaining non-data src/poster refs: {len(left)}  {left[:5]}")
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
