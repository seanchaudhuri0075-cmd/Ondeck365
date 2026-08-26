"""Fold the Old Spice build into one self-contained HTML file.

DEDUPE FIRST. The carousel renders each product unit as its own crop of the
SAME asset, so the document holds 78 image references over 29 unique assets —
inlining naively would embed 18.3MB of base64 where 6.8MB of distinct bytes
exist (2.70x).

An `<img src="data:...">` cannot share bytes with another element: each
attribute carries its own copy. A CSS custom property can be referenced by any
number of rules while appearing once. So the crop frames move from an oversized
<img> to a `background-image: var(--aN)`, with the asset inlined once into the
property. The maths is exact rather than approximate — for a crop whose visible
fraction is vw:

    img:        width = 100/vw %          left = -l/vw * 100 %
    background: background-size = 100/vw %   background-position = l/(l+r) %

because a percentage background-position places the image's p% point at the
container's p% point, i.e. offset = p*(Wc - Wi). Substituting Wi = Wc/vw gives
p = -left% / (width% - 100), which is computed straight from the emitted style.

The desktop shape image stays a real <img> with a literal data: src, because
the editor parses with DOMParser and finds media through img elements. So an
asset that also drives carousel cells appears twice — once as that img, once
in the shared property — and that is the floor while img elements are required.
"""
from __future__ import annotations

import base64, re, sys
from functools import lru_cache
from pathlib import Path

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")
ASSETS = OUT / "assets"
SRC = OUT / "index.html"
DST = OUT / "oldspice_deck_embedded.html"

MIME = {".webp": "image/webp", ".svg": "image/svg+xml", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


@lru_cache(maxsize=None)
def data_uri(name: str) -> str:
    p = ASSETS / name
    return (f"data:{MIME[p.suffix.lower()]};base64,"
            + base64.b64encode(p.read_bytes()).decode("ascii"))


CELL = re.compile(
    r'<div class="uf" style="--uar:([0-9.]+)"><img src="assets/([^"]+)"[^>]*?'
    r'style="width:([0-9.]+)%;height:([0-9.]+)%;left:(-?[0-9.]+)%;top:(-?[0-9.]+)%;"></div>')


def main() -> None:
    doc = SRC.read_text()

    # 1. Only assets driving MORE THAN ONE cell benefit from a shared property.
    #    A solo cell plus the desktop <img> is two copies whichever way it is
    #    done, so converting it buys nothing and costs pixel-parity: an <img>
    #    and a background-image resample slightly differently. Leave those as
    #    images and dedupe only the carousels, which is where the 2.7x came
    #    from in the first place.
    from collections import Counter
    cell_count = Counter(m.group(2) for m in CELL.finditer(doc))
    cell_assets = [n for n, k in cell_count.items() if k > 1]
    var_of = {name: f"--a{i}" for i, name in enumerate(cell_assets)}

    # 2. Rewrite each cell to paint the shared property, with the crop
    #    converted from img-offset to background-position/size.
    def cell(m: re.Match) -> str:
        uar, name = m.group(1), m.group(2)
        if name not in var_of:
            return m.group(0)          # solo cell: keep the <img>
        w, h = float(m.group(3)), float(m.group(4))
        left, top = float(m.group(5)), float(m.group(6))
        px = 0.0 if abs(w - 100.0) < 1e-9 else -left / (w - 100.0) * 100.0
        py = 0.0 if abs(h - 100.0) < 1e-9 else -top / (h - 100.0) * 100.0
        return (f'<div class="uf" style="--uar:{uar};'
                f'background-image:var({var_of[name]});'
                f'background-size:{w:.4f}% {h:.4f}%;'
                f'background-position:{px:.4f}% {py:.4f}%;'
                f'background-repeat:no-repeat"></div>')

    doc, n_cells = CELL.subn(cell, doc)

    # 3. Inline the shared properties once each.
    props = "\n".join(f"  {var_of[n]}:url({data_uri(n)});" for n in cell_assets)
    doc = doc.replace("<style>\n", "<style>\n:root{\n" + props + "\n}\n", 1)

    # 4. Remaining img elements keep a literal src, one copy each.
    seen = {}
    def sub(m: re.Match) -> str:
        name = m.group(2)
        seen[name] = seen.get(name, 0) + 1
        return f'{m.group(1)}="{data_uri(name)}"'
    doc, n_img = re.subn(r'\b(src)="assets/([^"]+)"', sub, doc)

    assert "assets/" not in doc, "a folder reference survived"
    for bad in ("srcset", "<picture", "<source"):
        assert bad not in doc, f"banned markup: {bad}"
    assert "document.createElement" not in doc and "innerHTML" not in doc, \
        "runtime DOM construction present"

    DST.write_text(doc)
    dup = {k: v for k, v in seen.items() if v > 1}
    print(f"crop cells rewritten to shared properties : {n_cells}")
    print(f"assets given a shared property            : {len(cell_assets)}")
    print(f"<img> elements with a literal data: src   : {n_img}")
    print(f"  of which any asset appears more than once as an img: {len(dup)} {dup}")
    print(f"wrote {DST}  {DST.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
