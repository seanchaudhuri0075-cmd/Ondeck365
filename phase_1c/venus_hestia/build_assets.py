"""Deck 9 asset stage. Videos at 5 Mbps, images at the canvas's real scale.

Bitrate (5 Mbps) is settled in DECK9_HANDOFF.md section 4: the 1080x1080 clip
is the busiest frame -- fine bottle-label type plus water droplets -- and 3 Mbps
softens it first. These are client ad boards.
"""
from __future__ import annotations

import json
import sys

from phase_1c.deckkit import assets
from phase_1c.venus_hestia.paths import PATHS

# The canvas is 1224pt wide. On a 2560x1440 monitor it resolves to
# min(100vw, 100svh * 1.5455) = 2226px, so a full-bleed image needs ~2226px to
# stay sharp at 1x. deckkit's 2000 default was sized for a 960pt/16:9 canvas and
# would soften the full-bleed boards here.
MAX_DIM = 2400
VIDEO_BITRATE = "5M"


def main() -> None:
    used = json.loads((PATHS.out / "used_assets.json").read_text())
    imgs, vids = set(used["images"]), set(used["videos"])
    what = sys.argv[1] if len(sys.argv) > 1 else "all"

    if what in ("all", "images"):
        print(f"images: {len(imgs)} -> max {MAX_DIM}px webp", flush=True)
        m = assets.build_images(PATHS, imgs, max_dim=MAX_DIM)
        (PATHS.out / "image_manifest.json").write_text(json.dumps(m, indent=1))
        src = sum(v["src_bytes"] for v in m.values())
        out = sum(v["out_bytes"] for v in m.values())
        print(f"  {src/1e6:.1f} MB -> {out/1e6:.1f} MB  ({out/src*100:.0f}%)", flush=True)

    if what in ("all", "videos"):
        print(f"videos: {len(vids)} @ {VIDEO_BITRATE}, sequential+atomic", flush=True)
        m = assets.build_videos(PATHS, vids, bitrate=VIDEO_BITRATE, progress=True)
        (PATHS.out / "video_manifest.json").write_text(json.dumps(m, indent=1))
        src = sum(v["src_bytes"] for v in m.values())
        out = sum(v["out_bytes"] for v in m.values())
        print(f"  {src/1e6:.1f} MB -> {out/1e6:.1f} MB  ({out/src*100:.0f}%)", flush=True)

    left = sorted(p.name for p in PATHS.assets.glob("*.__partial.*"))
    assert not left, f"partial files left (rule 8): {left}"


if __name__ == "__main__":
    main()
