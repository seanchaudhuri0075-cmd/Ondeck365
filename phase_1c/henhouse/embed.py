"""Fold the HenHouse build into one self-contained HTML file.

DEDUPE FIRST, same as deck 7. Six brochure spreads and one gallery board are
each shown on mobile as two crop windows over ONE asset (rule 31), so those
seven assets are referenced three times apiece: the desktop <img> plus two
mobile halves. An `<img src="data:...">` cannot share bytes with another
element -- every attribute carries its own copy -- but a CSS custom property
can be referenced any number of times while appearing once. So each half moves
from an oversized <img> to `background-image: var(--aN)`.

The crop maths is exact, not approximate. For a window whose visible fraction
is vw, the emitted <img> carries width = 100/vw % and left = -l/vw * 100 %. A
percentage background-position places the image's p% point at the container's
p% point, i.e. offset = p*(Wc - Wi); substituting Wi = Wc/vw gives

    p = -left% / (width% - 100)

computed straight from the style already emitted, with no re-derivation from
the model.

The desktop shape keeps a real <img> with a literal data: src, because the
editor parses with DOMParser and finds media through img elements. An asset
driving crop halves therefore appears twice -- once as that img, once in the
shared property -- and that is the floor while img elements are required.

VIDEO IS DIFFERENT AND CANNOT BE DEDUPED. A <video> needs its bytes in a src
attribute and <source> is banned by the spec, so an asset used on two slides
is inlined twice. Slides 29 and 30 show the same two ads, which alone costs
7.09 MB of the finished file.
"""
from __future__ import annotations

import base64, os, re, sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "out" / "henhouse"
ASSETS = OUT / "assets"
SRC = OUT / "index.html"
DST = OUT / "henhouse_deck_embedded.html"
# Route B diagnostic: same document, video ELEMENTS intact (poster, autoplay,
# muted, loop, playsinline, preload, and the shape's --ar) but no media bytes.
# Isolates decode/memory pressure from snap behaviour without introducing an
# external reference, which the iOS file:// sandbox would not load anyway.
# NOT A DELIVERABLE -- see NOTES 2026-08-24. Never to the editor, R2, or a client.
DIAG = OUT / "henhouse_DIAGNOSTIC_no-video-bytes_DO-NOT-SHIP.html"
# Multi-file variant for HTTPS hosting: images inlined, the 5 unique videos
# left as relative assets/ references. Only viable over http(s) -- the iOS
# file:// sandbox will not fetch a sibling file. Over HTTPS preload="none"
# genuinely defers the fetch until the element nears playback.
MULTI = OUT / "multifile"

# ---- crop-half dedupe: OFF for this deck ------------------------------------
# The shared-property technique (a crop half painted from `background-image:
# var(--aN)` with the asset inlined once into :root) saves 1.87 MB raw here.
# It is disabled because Deck Editor v14 rewrites `src`/`poster` on img/video
# and does NOT rewrite `url(data:)` inside a <style> block. Live evidence:
# published Old Spice still carries 15 such properties holding 3.45 MB of a
# 3.51 MB file -- 98.3% of the published deck never reached R2, while its 39
# img/poster srcs were rewritten correctly. HenHouse would have shipped 2.49 MB
# the same way. With dedupe off, every crop half is a real <img> with a literal
# data: src, so the editor enumerates and externalises all of them.
# The input file grows by 2.49 MB; the PUBLISHED deck gets smaller, because
# those bytes move to the CDN instead of riding along in the CSS.
# Re-enable when the editor rewrites url(data:) inside <style>.
DEDUPE_CROP_HALVES = False

MIME = {".webp": "image/webp", ".svg": "image/svg+xml", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


@lru_cache(maxsize=None)
def data_uri(name: str) -> str:
    p = ASSETS / name
    return (f"data:{MIME[p.suffix.lower()]};base64,"
            + base64.b64encode(p.read_bytes()).decode("ascii"))


HALF = re.compile(
    r'<div class="sh im cropped split" data-role="split" style="([^"]*)">'
    r'<span class="cropw"><img src="assets/([^"]+)"[^>]*?'
    r'style="width:([0-9.]+)%;height:([0-9.]+)%;left:(-?[0-9.]+)%;top:(-?[0-9.]+)%">'
    r'</span></div>')


def main(diagnostic: bool = False, external_video: bool = False) -> None:
    doc = SRC.read_text()
    before = Counter(re.findall(r'\b(?:src|poster)="assets/([^"]+)"', doc))

    # 1. Only assets driving MORE THAN ONE half gain from a shared property; a
    #    solo half plus the desktop <img> is two copies either way.
    half_count = Counter(m.group(2) for m in HALF.finditer(doc))
    shared = ([n for n, k in half_count.items() if k > 1]
              if DEDUPE_CROP_HALVES else [])
    var_of = {name: f"--a{i}" for i, name in enumerate(shared)}

    def half(m: re.Match) -> str:
        style, name = m.group(1), m.group(2)
        if name not in var_of:
            return m.group(0)
        w, h = float(m.group(3)), float(m.group(4))
        left, top = float(m.group(5)), float(m.group(6))
        px = 0.0 if abs(w - 100.0) < 1e-9 else -left / (w - 100.0) * 100.0
        py = 0.0 if abs(h - 100.0) < 1e-9 else -top / (h - 100.0) * 100.0
        return (f'<div class="sh im cropped split" data-role="split" style="{style}">'
                f'<span class="cropw" style="background-image:var({var_of[name]});'
                f'background-size:{w:.4f}% {h:.4f}%;'
                f'background-position:{px:.4f}% {py:.4f}%;'
                f'background-repeat:no-repeat"></span></div>')

    doc, n_halves = HALF.subn(half, doc)

    props = "\n".join(f"  {var_of[n]}:url({data_uri(n)});" for n in shared)
    doc = doc.replace("<style>", "<style>\n:root{\n" + props + "\n}\n", 1)

    # 2. Every remaining img and video keeps a literal src, one copy each.
    seen = Counter()

    def sub(m: re.Match) -> str:
        name = m.group(2)
        if external_video and name.endswith(".mp4"):
            return f'{m.group(1)}="assets/{name}"'      # relative, resolved over HTTPS
        if diagnostic and name.endswith(".mp4"):
            # strip the attribute entirely: no bytes AND no external reference,
            # which the iOS file:// sandbox would refuse to load in any case
            return ""
        seen[name] += 1
        return f'{m.group(1)}="{data_uri(name)}"'

    # poster= carries bytes exactly as src= does
    doc, n_src = re.subn(r'\b(src|poster)="assets/([^"]+)"', sub, doc)

    # ---- spec assertions ----------------------------------------------------
    if not external_video:
        assert "assets/" not in doc, "a folder reference survived"
    else:
        stray = [r for r in re.findall(r'(?:src|poster)="assets/([^"]+)"', doc)
                 if not r.endswith(".mp4")]
        assert not stray, f"non-video folder references survived: {stray[:3]}"
    for bad in ("srcset", "<picture", "<source"):
        assert bad not in doc, f"banned markup present: {bad}"
    assert "document.createElement" not in doc and "innerHTML" not in doc, \
        "runtime DOM construction present"
    n_sec = len(re.findall(r'<section class="slide"', doc))
    assert n_sec == 52, f"expected 52 sections, found {n_sec}"
    ids = re.findall(r'<section class="slide" id="s(\d+)"', doc)
    assert [int(i) for i in ids] == list(range(1, 53)), "section ids not 1..52"
    assert len(re.findall(r'<li class="rail-item"', doc)) == 52, "rail labels lost"
    imgs = re.findall(r"<img\b[^>]*>", doc)
    assert all(re.search(r'\ssrc="data:', i) for i in imgs), "an <img> lost its literal src"
    vids = re.findall(r"<video\b[^>]*>", doc)
    if diagnostic:
        # the elements must survive intact, only the media is gone
        assert all('src="' not in v for v in vids), "a diagnostic <video> kept a src"
        for attr in ('poster="data:', "autoplay", "muted", "loop", "playsinline",
                     'preload="none"'):
            assert all(attr in v for v in vids), f"a <video> lost {attr}"
    elif external_video:
        assert all(re.search(r'\ssrc="assets/[^"]+\.mp4"', v) for v in vids), \
            "a <video> lost its relative src"
        for attr in ('poster="data:', "autoplay", "muted", "loop", "playsinline",
                     'preload="none"'):
            assert all(attr in v for v in vids), f"a <video> lost {attr}"
    else:
        assert all(re.search(r'\ssrc="data:', v) for v in vids), "a <video> lost its literal src"

    if external_video:
        import shutil
        MULTI.mkdir(parents=True, exist_ok=True)
        (MULTI / "assets").mkdir(exist_ok=True)
        target = MULTI / "index.html"
        target.write_text(doc)
        (MULTI / ".nojekyll").write_text("")
        for vn in sorted({n for n in re.findall(r'src="assets/([^"]+)"', doc)}):
            shutil.copy2(ASSETS / vn, MULTI / "assets" / vn)
    else:
        target = DIAG if diagnostic else DST
        target.write_text(doc)

    raw_before = sum(os.path.getsize(ASSETS / n) * k for n, k in before.items())
    raw_after = sum(os.path.getsize(ASSETS / n) * k for n, k in seen.items()) \
        + sum(os.path.getsize(ASSETS / n) for n in shared)
    print(f"crop halves rewritten to shared properties : {n_halves}")
    print(f"assets given a shared property             : {len(shared)}")
    print(f"src attributes inlined literally           : {n_src}")
    print(f"sections / rail labels                     : {n_sec} / 52")
    print()
    print(f"unique asset bytes                         : "
          f"{sum(os.path.getsize(ASSETS / n) for n in before)/1e6:8.2f} MB")
    print(f"raw bytes inlined, naive                   : {raw_before/1e6:8.2f} MB")
    print(f"raw bytes inlined, after dedupe            : {raw_after/1e6:8.2f} MB")
    print(f"  recovered                                : "
          f"{(raw_before-raw_after)/1e6:8.2f} MB")
    print()
    dup = {k: v for k, v in seen.items() if v > 1}
    for n, k in sorted(dup.items(), key=lambda kv: -os.path.getsize(ASSETS / kv[0]) * (kv[1] - 1)):
        print(f"  still x{k}: {n:<26} {os.path.getsize(ASSETS/n)/1e6:5.2f} MB each"
              f"{'   <- video, cannot be shared' if n.endswith('.mp4') else ''}")
    print()
    print(f"wrote {target.name}  {target.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main(diagnostic="--diagnostic" in sys.argv,
         external_video="--external-video" in sys.argv)
