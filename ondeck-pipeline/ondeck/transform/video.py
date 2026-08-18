"""Video transform stage — extract from .pptx, transcode, probe, write manifest.

Runs once per deck before render. For every slide containing a <p:pic>
shape with <p14:media> (a video), this module:

  1. Extracts the binary from the .pptx zip member (via parse.media).
  2. Re-encodes to web-friendly H.264 .mp4 via ffmpeg.
  3. Probes the output for width / height / aspect ratio.
  4. Writes media.video.{aspect, width, height, filename} into the slide's
     manifest entry.

Render reads the manifest only — no per-slide aspect decisions in
templates. See the "Video aspect ratio policy — auto-detected,
manifest-driven" entry in NOTES.md for the policy this implements.

Sandbox constraint: ffmpeg parallel jobs (& backgrounding, GNU parallel,
job arrays) truncate output files in this environment. All transcodes
run sequentially. Each writes to {stem}.__partial.{suffix}, then
atomically renames on success — readers in another process never see
a half-written file. The same atomic-write pattern applies to the
manifest itself.

Encoder defaults: H.264, crf=23, preset="medium". Documented as the
prototype default; tunable via transcode_h264() kwargs if production
R2 hosting wants smaller files (e.g. crf=28).

Multi-video slides: not supported in the current schema. If a slide
carries more than one video, the FIRST in document order is used and
a warning is printed to stderr. Bumping to multi-video means changing
_iter_video_pics to yield all and the orchestrator to write
media.videos: [...] (an array). Add when a deck needs it.

Filename pattern: {deck_name_slug}_slide_{NN:02d}_video.mp4. The slug
is derived from manifest.deck_name by splitting on whitespace, stripping
non-alnum, lowercasing, and joining with underscores. "P&G Creative
Deck" → "pg_creative_deck". Falls back to pptx_path.stem if deck_name
is empty.

Requires `ffmpeg` and `ffprobe` on PATH.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from lxml import etree
from pptx.slide import Slide as _PptxSlide

from ondeck.parse.media import extract_video, is_video_pic
from ondeck.parse.pptx import Pptx
from ondeck.parse.shapes import flatten_slide


# ────────────────────────────────────────────────────────────────────────────
# Public types

@dataclass(frozen=True)
class VideoInfo:
    """Probe result. aspect is reduced "W/H" string (e.g. "16/9", not "1920/1080")."""

    aspect: str
    width: int
    height: int


# ────────────────────────────────────────────────────────────────────────────
# Public API — top-level entry point

def process_deck_videos(
    pptx_path: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> int:
    """Run the video transform stage end-to-end for one deck.

    For each slide with at least one video <p:pic>:
      1. Extract the binary (first video if multiple).
      2. Transcode to {output_dir}/{deck_slug}_slide_{NN:02d}_video.mp4.
      3. Probe the output and merge {aspect, width, height, filename}
         into slides.<N>.media.video in the manifest.

    Idempotent: skips transcoding when the output mp4 already exists
    (re-probes to refresh manifest values). Use overwrite=True to force
    re-encoding.

    The manifest is written back atomically — readers in another process
    never see a half-written file. Returns the number of videos processed.
    """
    pptx_path = Path(pptx_path)
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text())
    prefix = _deck_prefix(manifest, pptx_path)

    pptx = Pptx(pptx_path)
    count = 0
    for slide_index, pic_elem, slide in _iter_video_pics(pptx):
        ref = extract_video(pic_elem, slide)
        if ref is None or ref.video_blob is None:
            print(f"  slide {slide_index}: no video blob, skipping", file=sys.stderr)
            continue

        filename = f"{prefix}_slide_{slide_index:02d}_video.mp4"
        out_path = output_dir / filename

        if not out_path.exists() or overwrite:
            src_path = output_dir / f"{filename}.__src.mp4"
            src_path.write_bytes(ref.video_blob)
            try:
                transcode_h264(src_path, out_path, overwrite=overwrite)
            finally:
                src_path.unlink(missing_ok=True)

        info = probe_aspect(out_path)
        _update_manifest_video(manifest, slide_index, info, filename)
        count += 1
        print(
            f"  slide {slide_index}: {filename} "
            f"({info.width}×{info.height}, aspect={info.aspect})"
        )

    _atomic_write_json(manifest_path, manifest)
    return count


def probe_aspect(video_path: Path) -> VideoInfo:
    """Run ffprobe on a video file. Returns reduced "W/H" aspect + width + height.

    Aspect string is reduced via math.gcd so committed manifests stay
    human-readable ("16/9" not "1920/1080"). The CSS aspect-ratio
    property accepts either form, but reduced is easier to scan in diffs.
    """
    data = _ffprobe_json(video_path)
    w = int(data["width"])
    h = int(data["height"])
    g = math.gcd(w, h)
    return VideoInfo(aspect=f"{w // g}/{h // g}", width=w, height=h)


def transcode_h264(
    src: Path,
    dst: Path,
    *,
    crf: int = 23,
    preset: str = "medium",
    overwrite: bool = False,
) -> None:
    """Re-encode src to H.264 MP4 at dst. Sequential, atomic via __partial.

    Writes to {dst.stem}.__partial{dst.suffix} first, then atomically
    renames to dst on success. On exception, removes the partial.
    Callers MUST run one transcode at a time — parallel ffmpeg jobs in
    this sandbox truncate output. If dst exists and overwrite=False,
    returns immediately (idempotent).

    Encoder settings:
        -c:v libx264 -crf 23 -preset medium  (good quality, reasonable size)
        -pix_fmt yuv420p                      (Safari-safe pixel format)
        -movflags +faststart                  (metadata at start, streamable)
        -c:a aac -b:a 128k                    (audio for non-muted contexts)
    """
    if dst.exists() and not overwrite:
        return

    partial = _partial_path(dst)
    partial.unlink(missing_ok=True)

    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-y",
        "-i", str(src),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
        str(partial),
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, dst)


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers

def _deck_prefix(manifest: dict, pptx_path: Path) -> str:
    """Slug deck_name to a filename-safe prefix; fall back to pptx stem.

    Splits on whitespace, strips non-alnum from each token, lowercases,
    joins with underscores. "P&G Creative Deck" → "pg_creative_deck".
    Empty / missing / fully-stripped deck_name → pptx_path.stem.
    """
    raw = (manifest.get("deck_name") or "").strip()
    parts = []
    for token in raw.split():
        cleaned = "".join(c for c in token if c.isalnum())
        if cleaned:
            parts.append(cleaned.lower())
    return "_".join(parts) or pptx_path.stem


def _iter_video_pics(
    pptx: Pptx,
) -> Iterator[tuple[int, etree._Element, _PptxSlide]]:
    """Yield (slide_index_1based, pic_element, slide) for every video shape.

    Filters via parse.media.is_video_pic(). Multi-video slides emit a
    stderr warning and yield only the first video pic; the current
    manifest schema is media.video (singular). Bump to media.videos:
    [...] when a deck needs multi-video support.
    """
    for idx, slide in enumerate(pptx.slides(), start=1):
        videos_on_slide = [
            fs for fs in flatten_slide(slide)
            if fs.kind == "pic" and is_video_pic(fs.element)
        ]
        if not videos_on_slide:
            continue
        if len(videos_on_slide) > 1:
            print(
                f"  warn: slide {idx} has {len(videos_on_slide)} videos; "
                f"using first only (multi-video schema not implemented)",
                file=sys.stderr,
            )
        yield (idx, videos_on_slide[0].element, slide)


def _ffprobe_json(video_path: Path) -> dict:
    """ffprobe wrapper → first video stream as a dict.

    Runs `ffprobe -v error -select_streams v:0 -show_entries stream=width,height
    -of json <path>` and returns the first stream dict from the parsed JSON.
    """
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(video_path),
        ]
    )
    streams = json.loads(out).get("streams", [])
    if not streams:
        raise ValueError(f"ffprobe returned no video streams for {video_path}")
    return streams[0]


def _update_manifest_video(
    manifest: dict,
    slide_index: int,
    info: VideoInfo,
    filename: str,
) -> None:
    """Merge media.video.{aspect, width, height, filename} into slides.<N>.

    Preserves all other manifest keys. Creates slides.<N> and slides.<N>.media
    if they don't exist (defensive — the slide should already be classified
    in the manifest, but allow either order of build steps).
    """
    slides = manifest.setdefault("slides", {})
    entry = slides.setdefault(str(slide_index), {})
    media = entry.setdefault("media", {})
    media["video"] = {
        "aspect": info.aspect,
        "width": info.width,
        "height": info.height,
        "filename": filename,
    }


def _partial_path(target: Path) -> Path:
    """The {stem}.__partial{suffix} sibling we write to before atomic rename."""
    return target.parent / f"{target.stem}.__partial{target.suffix}"


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to {stem}.__partial{suffix}, then atomically rename to path.

    Same pattern as transcode_h264 — a reader in another process never
    sees a half-written manifest. JSON is serialized with indent=2 and
    a trailing newline so diffs stay clean.
    """
    path = Path(path)
    partial = _partial_path(path)
    partial.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, path)


# ────────────────────────────────────────────────────────────────────────────
# CLI

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Run the video transform stage on a deck.",
    )
    p.add_argument("pptx", type=Path, help="Source .pptx")
    p.add_argument("manifest", type=Path, help="Manifest JSON")
    p.add_argument("output_dir", type=Path, help="Where to write .mp4 output(s)")
    p.add_argument(
        "--overwrite", action="store_true",
        help="Force re-encode even if output already exists",
    )
    args = p.parse_args()

    n = process_deck_videos(
        args.pptx, args.manifest, args.output_dir, overwrite=args.overwrite,
    )
    print(f"processed {n} video(s)")
