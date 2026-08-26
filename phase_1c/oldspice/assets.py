"""Old Spice asset stage. No video in this deck, so no transcode step.

Rule 6: the SVG wordmark is carried through as the ACTUAL VECTOR, not
rasterised. Its <a:blip> has no r:embed at all, so there is no raster fallback
to fall back to — rasterising would be inventing bytes the source never had.
Rule 7: content-addressed names, so the wordmark used on slides 1 and 34 is one
asset and one URL.
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path
from PIL import Image

RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/oldspice/raw")
OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")
ASSETS = OUT / "assets"
MAX_DIM, WEBP_Q = 2000, 80


def build(used: set[str]) -> dict:
    ASSETS.mkdir(parents=True, exist_ok=True)
    man = {}
    for name in sorted(used):
        src = RAW / "ppt" / "media" / name
        if not src.exists():
            print(f"  MISSING {name}"); continue
        raw = src.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()[:12]

        if src.suffix.lower() == ".svg":
            out_name = f"vec_{digest}.svg"
            (ASSETS / out_name).write_bytes(raw)
            man[name] = {"out": out_name, "sha": digest, "kind": "svg",
                         "src_bytes": len(raw), "out_bytes": len(raw)}
            continue

        im = Image.open(src)
        w0, h0 = im.size
        alpha = im.mode in ("RGBA", "LA", "P") and (
            im.mode != "P" or "transparency" in im.info)
        im = im.convert("RGBA" if alpha else "RGB")
        s = min(1.0, MAX_DIM / max(im.size))
        if s < 1.0:
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        out_name = f"img_{digest}.webp"
        partial = ASSETS / f"img_{digest}.__partial.webp"
        im.save(partial, "WEBP", quality=WEBP_Q, method=6)
        partial.replace(ASSETS / out_name)
        man[name] = {"out": out_name, "sha": digest, "kind": "raster",
                     "src_w": w0, "src_h": h0, "out_w": im.width, "out_h": im.height,
                     "alpha": alpha, "src_bytes": len(raw),
                     "out_bytes": (ASSETS / out_name).stat().st_size}
    return man


if __name__ == "__main__":
    used = set(json.load(open(OUT / "used_images.json")))
    m = build(used)
    (OUT / "image_manifest.json").write_text(json.dumps(m, indent=1))
    tin = sum(v["src_bytes"] for v in m.values())
    tout = sum(v["out_bytes"] for v in m.values())
    nvec = sum(1 for v in m.values() if v["kind"] == "svg")
    print(f"{len(m)} assets ({nvec} vector kept as-is)  {tin/1e6:.1f} MB -> {tout/1e6:.2f} MB "
          f"({tin/tout:.0f}x)")
    assert not list(ASSETS.glob("*.__partial.*")), "partial file left in outputs"
