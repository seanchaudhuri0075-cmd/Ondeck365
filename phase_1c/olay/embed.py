"""Fold the folder build into one self-contained HTML file.

Contract this file has to satisfy (all learned on P&G):
  * every slide is STATIC markup — nothing is constructed at runtime, so a
    DOMParser with scripts disabled sees all 34 sections
  * every <img>/<video> carries a literal src="data:..." in the markup
  * no srcset, no <picture>, no <source>
  * each unique asset is encoded ONCE and reused by string identity

On that last point: a literal `src` per element means shared assets appear at
each DOM site. Unavoidable for the badge sprite (one asset, 36 sites) and for
section art used on two slides. It IS avoidable for video posters, which the
folder build inlines twice each — once as the <img class="poster"> underlay and
again as the <video poster> attribute. The underlay is the layer rule 4
requires; the attribute is a duplicate of it, so it is dropped here. Saves
~3MB of base64 and changes nothing on screen (verified by pixel parity).
"""
from __future__ import annotations

import base64, re, sys
from functools import lru_cache
from pathlib import Path

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
ASSETS = OUT / "assets"
SRC = OUT / "index.html"
DST = OUT / "olay_deck_embedded.html"

MIME = {".webp": "image/webp", ".mp4": "video/mp4", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@lru_cache(maxsize=None)
def data_uri(name: str) -> str:
    p = ASSETS / name
    mime = MIME[p.suffix.lower()]
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def main() -> None:
    doc = SRC.read_text()

    # Drop the redundant poster attribute (the <img> underlay carries it).
    doc, n_poster = re.subn(r'\s+poster="assets/[^"]+"', "", doc)

    seen: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        attr, name = m.group(1), m.group(2)
        seen[name] = seen.get(name, 0) + 1
        return f'{attr}="{data_uri(name)}"'

    doc, n_ref = re.subn(r'\b(src|poster)="assets/([^"]+)"', sub, doc)

    # Nothing may still point at the folder, and the banned elements must be absent.
    assert "assets/" not in doc, "a reference to the assets folder survived"
    for bad in ("srcset", "<picture", "<source"):
        assert bad not in doc, f"banned markup present: {bad}"
    assert "document.createElement" not in doc and "innerHTML" not in doc, \
        "runtime DOM construction present"

    DST.write_text(doc)
    uniq_bytes = sum((ASSETS / n).stat().st_size for n in seen)
    print(f"inlined {n_ref} references over {len(seen)} unique assets "
          f"({uniq_bytes/1e6:.2f} MB raw)")
    print(f"dropped {n_poster} redundant video poster attributes")
    multi = {n: c for n, c in seen.items() if c > 1}
    print(f"assets appearing at more than one DOM site: {len(multi)} "
          f"(max {max(multi.values()) if multi else 0} sites)")
    print(f"wrote {DST}  {DST.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
