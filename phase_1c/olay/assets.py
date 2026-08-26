"""Olay asset stage: extract every referenced image, content-address it, transcode.

Rules this implements (LEARNINGS.md):
  6 — every image is EXTRACTED from ppt/media via its resolved rId. Nothing
      is recreated, traced or approximated.
  7 — output filenames are content hashes, so the logo referenced from 15
      slides is one asset and one URL.

srcRect crops are deliberately NOT baked into the pixels here: the crop
travels to CSS so it stays reversible in the editor. That means an asset
shown as a 25%-wide strip still ships whole, which is the cost the deck
owner accepted for reversibility.
"""
from __future__ import annotations

import hashlib, json, os, shutil
from pathlib import Path
from PIL import Image

RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/olay/raw")
OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
ASSETS = OUT / "assets"

MAX_DIM = 2000      # bounds the 3064x2451 CGI plates without touching framing
WEBP_Q = 80


def build_images(used: set[str]) -> dict:
    """Transcode each referenced image once. Returns {media_name: {...}}."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in sorted(used):
        src = RAW / "ppt" / "media" / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        im = Image.open(src)
        w0, h0 = im.size
        has_alpha = im.mode in ("RGBA", "LA", "P") and (
            im.mode != "P" or "transparency" in im.info
        )
        im = im.convert("RGBA" if has_alpha else "RGB")
        scale = min(1.0, MAX_DIM / max(im.size))
        if scale < 1.0:
            im = im.resize((round(im.width * scale), round(im.height * scale)),
                           Image.LANCZOS)
        out_name = f"img_{digest}.webp"
        dst = ASSETS / out_name
        partial = ASSETS / f"img_{digest}.__partial.webp"
        im.save(partial, "WEBP", quality=WEBP_Q, method=6)
        partial.replace(dst)
        manifest[name] = {
            "out": out_name, "sha": digest,
            "src_w": w0, "src_h": h0, "out_w": im.width, "out_h": im.height,
            "alpha": has_alpha,
            "src_bytes": src.stat().st_size, "out_bytes": dst.stat().st_size,
        }
    return manifest


if __name__ == "__main__":
    import sys
    used = set(json.load(open(sys.argv[1])))
    m = build_images(used)
    (OUT / "image_manifest.json").write_text(json.dumps(m, indent=1))
    tin = sum(v["src_bytes"] for v in m.values())
    tout = sum(v["out_bytes"] for v in m.values())
    resized = sum(1 for v in m.values() if v["out_w"] != v["src_w"])
    print(f"{len(m)} images  {tin/1e6:.0f}MB -> {tout/1e6:.1f}MB  ({resized} downscaled to <={MAX_DIM}px)")
    assert not list(ASSETS.glob("*.__partial.*")), "partial file left in outputs"
