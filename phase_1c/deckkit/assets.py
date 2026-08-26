"""Asset stage: extract, content-address, transcode. Shared by every deck.

Rules (LEARNINGS.md):
  6 — every asset is EXTRACTED from ppt/media via its resolved rId. Nothing is
      recreated, traced or approximated.
  7 — output filenames are content hashes, so an asset referenced from N
      slides is one file and one URL.
  8 — video encodes SEQUENTIALLY, one at a time, to a `.__partial.` name that
      is only renamed on success. A partial left in the output set is a hard
      failure, not a warning.

srcRect crops are deliberately NOT baked into pixels: the crop travels to CSS
so it stays reversible in the editor. An asset shown as a narrow strip still
ships whole — the cost of reversibility.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .paths import DeckPaths

Image.MAX_IMAGE_PIXELS = None

MAX_DIM = 2000        # a 960x540pt canvas at 2x is 1920px; beyond that is waste
WEBP_Q = 80
VIDEO_CRF = 23
VIDEO_PRESET = "medium"


def build_images(paths: DeckPaths, used: set[str], max_dim: int = MAX_DIM,
                 quality: int = WEBP_Q) -> dict:
    paths.assets.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in sorted(used):
        src = paths.media / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]

        if src.suffix.lower() == ".svg":
            # rule 6: SVG-only pictures embed the actual vector. Nothing to
            # transcode — copy the bytes and keep the content address.
            out_name = f"img_{digest}.svg"
            shutil.copyfile(src, paths.assets / out_name)
            manifest[name] = {"out": out_name, "sha": digest, "svg": True,
                              "src_w": None, "src_h": None,
                              "out_w": None, "out_h": None, "alpha": True,
                              "src_bytes": src.stat().st_size,
                              "out_bytes": (paths.assets / out_name).stat().st_size}
            continue

        im = Image.open(src)
        w0, h0 = im.size
        has_alpha = im.mode in ("RGBA", "LA", "P") and (
            im.mode != "P" or "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        scale = min(1.0, max_dim / max(im.size))
        if scale < 1.0:
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                           Image.LANCZOS)
        out_name = f"img_{digest}.webp"
        dst = paths.assets / out_name
        partial = paths.assets / f"img_{digest}.__partial.webp"
        im.save(partial, "WEBP", quality=quality, method=6)
        partial.replace(dst)
        manifest[name] = {"out": out_name, "sha": digest, "svg": False,
                          "src_w": w0, "src_h": h0, "out_w": im.width, "out_h": im.height,
                          "alpha": has_alpha,
                          "src_bytes": src.stat().st_size, "out_bytes": dst.stat().st_size}
    return manifest


def _probe(path: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)])
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    g = math.gcd(w, h)
    return {"width": w, "height": h, "aspect": f"{w // g}/{h // g}"}


def build_videos(paths: DeckPaths, used: set[str], crf: int = VIDEO_CRF,
                 preset: str = VIDEO_PRESET, bitrate: str | None = None,
                 progress: bool = False) -> dict:
    """Sequential + atomic (rule 8). Aspect is PROBED, never assumed — deck 8
    is the first with mixed aspects (1:1 and 9:16, no 16:9 anywhere), so a
    hardcoded container ratio would crop or letterbox most of them.

    `bitrate` switches from quality-targeted (CRF) to rate-capped ABR, e.g.
    "5M". Deck 9 needs this: its source is 845 MB for 4.7 minutes — a 24 Mbps
    average — and the decision there was made by comparing encodes at a fixed
    RATE, not a fixed quality, because the deliverable is bounded by what can
    be shipped rather than by a quality target. 5 Mbps was chosen over 3 Mbps
    on the 1080x1080 clip, whose fine bottle-label type softens first.
    `-maxrate`/`-bufsize` cap the peak so a busy frame cannot blow the budget."""
    paths.assets.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in sorted(used):
        src = paths.media / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        out_name = f"vid_{digest}.mp4"
        dst = paths.assets / out_name
        partial = paths.assets / f"vid_{digest}.__partial.mp4"
        if not dst.exists():
            partial.unlink(missing_ok=True)
            rate = (["-b:v", bitrate, "-maxrate", bitrate,
                     "-bufsize", f"{int(bitrate.rstrip('Mm')) * 2}M"]
                    if bitrate else ["-crf", str(crf)])
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src),
                 "-c:v", "libx264", *rate, "-preset", preset,
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(partial)],
                check=True)
            partial.replace(dst)
        if progress:
            print(f"  {len(manifest) + 1:>3}/{len(used)}  {name:16} "
                  f"{src.stat().st_size / 1e6:7.2f} -> {dst.stat().st_size / 1e6:6.2f} MB",
                  flush=True)
        info = _probe(dst)
        manifest[name] = {"out": out_name, "sha": digest, **info,
                          "src_bytes": src.stat().st_size, "out_bytes": dst.stat().st_size}
    return manifest


def build_all(paths: DeckPaths, used_images: set[str], used_videos: set[str],
              video_kw: dict | None = None, **kw) -> dict:
    imgs = build_images(paths, used_images, **kw)
    vids = build_videos(paths, used_videos, **(video_kw or {}))
    leftovers = sorted(p.name for p in paths.assets.glob("*.__partial.*"))
    assert not leftovers, f"partial files left in outputs (rule 8): {leftovers}"
    m = {"images": imgs, "videos": vids}
    (paths.out / "asset_manifest.json").write_text(json.dumps(m, indent=1))
    return m
