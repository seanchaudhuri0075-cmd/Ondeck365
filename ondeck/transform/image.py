"""transform/image.py — extract slide images, convert to WebP, write manifest.

Mirrors transform/video.py but for still images. Every <p:pic> shape that
isn't a video gets:

  1. Extracted from the .pptx zip via parse/images.py extract_image_ref.
  2. Decoded with Pillow and auto-rotated via the EXIF orientation tag
     (so portrait phone photos record post-rotation dimensions).
  3. Optionally flattened against the slide's canvas_bg color when the
     manifest entry has `flatten_on_canvas: true` (default: preserve alpha).
  4. Blip-level transforms (<a:duotone>, <a:alphaModFix>) pre-baked into
     the pixel data. Slide 2 Picture 62 is the canonical case: image3.jpeg
     is duotoned (black ↔ tinted-saturated cyan) at 82% alpha. Without
     pre-baking, the renderer would emit the natural-color photo, which
     diverges visibly from PPT (the cyan-tinted faded photo behind the
     overlay rect is the deck-author's design intent).
  5. Encoded WebP at quality 85 (default; tunable per call).
  6. Written to {output_dir}/{deck_slug}_slide_{NN:02d}_img_{KK:02d}.webp.
  7. Recorded in slides.<N>.media.images: [{src_id, filename, format,
     width, height}, ...] — a list, ordered by document order.

Render templates read media.images by src_id (the OOXML cNvPr/@id) to
resolve which file goes in which <img> slot.

Scope: raster only — JPEG, PNG, BMP, TIFF. SVGs and animated GIFs are
skipped (no .webp output, no manifest entry). SVGs continue through
parse/svg.py and the inline-base64 path; animated GIFs are rare and
not currently in any P&G slide.

JPEG-on-background handling: opt-in per image. The deck author edits
the manifest after the first transform run to add `flatten_on_canvas:
true` on a specific image's entry; on subsequent runs (with --overwrite),
the alpha is flattened against the slide's canvas_bg (hints.canvas_bg,
falling back to deck_brand_color, falling back to "#FFFFFF"). Default
behavior preserves alpha — opt-in keeps the design decision visible
in the manifest and avoids destroying intentional transparent overlays
(e.g., the GIF logo PNG with transparent background).

Idempotency caveat: toggling `flatten_on_canvas` on an existing image
requires running with --overwrite; otherwise the prior .webp on disk
is reused (the file's own metadata doesn't record whether it was
flattened, so we can't auto-detect a state change).

Sandbox constraint: same as transform/video.py — sequential conversion,
atomic .__partial.webp rename, no parallel jobs.

Requires Pillow (PIL).
"""
from __future__ import annotations

import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from lxml import etree
from PIL import Image, ImageOps
from pptx.slide import Slide as _PptxSlide

from ondeck.parse.images import extract_image_ref
from ondeck.parse.media import is_video_pic
from ondeck.parse.pptx import Pptx
from ondeck.parse.shapes import flatten_slide
from ondeck.parse.slide import NS


# ────────────────────────────────────────────────────────────────────────────
# Public types

@dataclass(frozen=True)
class ImageInfo:
    """Probe + transform result for one image. format is always 'webp' for outputs."""

    src_id: str        # OOXML cNvPr/@id from the source <p:pic>
    filename: str
    format: str        # currently always "webp"
    width: int         # post-EXIF-rotation pixel width
    height: int        # post-EXIF-rotation pixel height


# ────────────────────────────────────────────────────────────────────────────
# Public API — top-level entry point

def process_deck_images(
    pptx_path: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    overwrite: bool = False,
    quality: int = 85,
) -> int:
    """Run the image transform stage end-to-end for one deck.

    For each slide, for each non-video <p:pic>:
      - Extract via parse/images.py.
      - If content_type is SVG or PIL detects animated GIF: skip.
      - Otherwise: decode, EXIF-rotate, optionally flatten, encode WebP.
      - Update slides.<N>.media.images, preserving any user-set per-image
        fields like `flatten_on_canvas`.

    Idempotent: skips conversion when the .webp already exists and
    overwrite=False (still re-probes to refresh manifest dimensions).

    Manifest is written atomically. Returns the count of WebP files
    produced or refreshed (skipped SVG / animated-GIF pass-throughs
    don't count).
    """
    pptx_path = Path(pptx_path)
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text())
    deck_slug = _deck_slug(manifest, pptx_path)
    deck_brand_color = manifest.get("deck_brand_color", "")

    pptx = Pptx(pptx_path)
    count = 0
    for slide_index, slide, pics in _iter_image_pics_per_slide(pptx):
        existing_entries = (
            manifest.get("slides", {})
            .get(str(slide_index), {})
            .get("media", {})
            .get("images", [])
        )
        existing_by_id = {e.get("src_id"): e for e in existing_entries}

        slide_hints = (
            manifest.get("slides", {})
            .get(str(slide_index), {})
            .get("hints", {})
        )
        canvas_bg = (
            slide_hints.get("canvas_bg")
            or deck_brand_color
            or "#FFFFFF"
        )

        new_entries: list[dict] = []
        image_index = 0
        for pic_elem in pics:
            ref = extract_image_ref(pic_elem, slide)
            if ref is None or ref.blob is None:
                continue
            if "svg" in ref.content_type.lower():
                continue

            try:
                img = Image.open(io.BytesIO(ref.blob))
                img.load()
            except Exception as e:
                print(
                    f"  warn: slide {slide_index}: PIL can't decode "
                    f"({ref.content_type}): {e}",
                    file=sys.stderr,
                )
                continue
            if getattr(img, "is_animated", False):
                continue

            image_index += 1
            src_id = _pic_id(pic_elem) or f"_anon_{image_index}"
            filename = _image_filename(deck_slug, slide_index, image_index)
            out_path = output_dir / filename

            existing = existing_by_id.get(src_id, {})
            flatten = bool(existing.get("flatten_on_canvas", False))
            background = canvas_bg if flatten else None
            blip_transforms = _extract_blip_transforms(pic_elem)

            info = transcode_webp(
                ref.blob, out_path,
                quality=quality,
                background=background,
                overwrite=overwrite,
                src_id=src_id,
                filename=filename,
                blip_transforms=blip_transforms,
            )

            entry = dict(existing)  # preserve user-set hints
            entry.update({
                "src_id": info.src_id,
                "filename": info.filename,
                "format": info.format,
                "width": info.width,
                "height": info.height,
            })
            new_entries.append(entry)
            count += 1
            flatten_note = f", flattened on {canvas_bg}" if flatten else ""
            tx_note = ""
            if blip_transforms:
                tx_parts = []
                if "duotone" in blip_transforms:
                    d = blip_transforms["duotone"]
                    tx_parts.append(f"duotone {d['dark_hex']}↔{d['light_hex']}")
                if "alpha" in blip_transforms:
                    tx_parts.append(f"alpha={blip_transforms['alpha']:.2f}")
                tx_note = f", blip[{', '.join(tx_parts)}]"
            print(
                f"  slide {slide_index} img {image_index}: {filename} "
                f"({info.width}×{info.height}, src_id={src_id}{flatten_note}{tx_note})"
            )

        if new_entries:
            _update_manifest_images(manifest, slide_index, new_entries)

    _atomic_write_json(manifest_path, manifest)
    return count


def transcode_webp(
    src_blob: bytes,
    dst: Path,
    *,
    quality: int = 85,
    background: Optional[str] = None,
    overwrite: bool = False,
    src_id: str = "",
    filename: str = "",
    blip_transforms: Optional[dict] = None,
) -> ImageInfo:
    """Decode src_blob, EXIF-rotate, optionally flatten, apply blip
    transforms, encode WebP at dst.

    background: hex color "#RRGGBB" or None.
        - None  → preserve alpha if the source has it; encode as RGBA WebP.
        - "..." → composite the image on a solid color background; encode
                  as RGB WebP.

    blip_transforms: dict from _extract_blip_transforms or None.
        Recognized keys:
        - "duotone": {"dark_hex": "RRGGBB", "light_hex": "RRGGBB"} — applied
          via grayscale + ImageOps.colorize, mapping black→dark, white→light.
        - "alpha": float in (0, 1] — multiplied into the image's alpha
          channel post-duotone (image converted to RGBA if needed).
        Order: duotone is applied BEFORE alpha (alpha modulates the
        duotoned pixel data, matching PowerPoint's <a:blip> order
        — color-modify children apply in document order, alphaModFix
        is the last visual transform per ECMA-376 §20.1.8).
        When blip_transforms also requests duotone AND background is set,
        the flatten happens AFTER duotone+alpha (the duotoned RGBA is
        composited on the background).

    Sequential, atomic via {stem}.__partial.webp rename. Returns ImageInfo
    populated with post-rotation pixel dimensions.

    Idempotent at the file level: if dst exists and overwrite=False,
    skips encoding and just probes dimensions. To toggle flatten state or
    blip-transform behavior on an existing file, callers must pass
    overwrite=True.
    """
    if dst.exists() and not overwrite:
        w, h = probe_image(dst)
        return ImageInfo(
            src_id=src_id, filename=filename or dst.name,
            format="webp", width=w, height=h,
        )

    img = Image.open(io.BytesIO(src_blob))
    img.load()
    img = ImageOps.exif_transpose(img)  # honor EXIF orientation tag

    # Apply blip-level color/alpha transforms BEFORE flatten/encoding.
    if blip_transforms:
        img = _apply_blip_transforms(img, blip_transforms)

    if background is not None:
        bg_rgb = _hex_to_rgb(background)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, bg_rgb)
        bg.paste(img, mask=img.split()[3])
        encode_img = bg
    else:
        if img.mode in ("RGBA", "LA"):
            encode_img = img.convert("RGBA")
        elif img.mode == "P" and "transparency" in img.info:
            encode_img = img.convert("RGBA")
        elif img.mode in ("L", "P", "I", "F"):
            encode_img = img.convert("RGB")
        else:
            encode_img = img  # already RGB / RGBA

    partial = _partial_path(dst)
    partial.unlink(missing_ok=True)
    try:
        encode_img.save(partial, "WEBP", quality=quality, method=6)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, dst)

    return ImageInfo(
        src_id=src_id,
        filename=filename or dst.name,
        format="webp",
        width=encode_img.size[0],
        height=encode_img.size[1],
    )


def _apply_blip_transforms(img: Image.Image, transforms: dict) -> Image.Image:
    """Apply duotone + alphaModFix to a PIL image. Returns transformed copy.

    Duotone first (via grayscale + colorize), alpha second (via per-pixel
    alpha-channel scaling).
    """
    out = img
    if "duotone" in transforms:
        d = transforms["duotone"]
        gray = out.convert("L")
        dark = _hex_to_rgb(d["dark_hex"])
        light = _hex_to_rgb(d["light_hex"])
        out = ImageOps.colorize(gray, black=dark, white=light)
    if "alpha" in transforms:
        a = float(transforms["alpha"])
        if a < 1.0:
            if out.mode != "RGBA":
                out = out.convert("RGBA")
            r, g, b, alpha_ch = out.split()
            alpha_ch = alpha_ch.point(lambda v: int(v * a))
            out = Image.merge("RGBA", (r, g, b, alpha_ch))
    return out


def _extract_blip_transforms(pic_elem: etree._Element) -> Optional[dict]:
    """Parse <a:blip> child elements that affect rendered pixel data.

    Currently recognized:
    - <a:duotone>: requires exactly two color children (a:prstClr or
      a:srgbClr). Returns {"dark_hex", "light_hex"} as 6-char hex strings.
      Color modifiers (a:tint, a:satMod, a:lumMod, a:lumOff) are NOT
      currently resolved — the raw srgbClr value is used. For slide 2
      Picture 62 this means tint=45000 + satMod=400000 on the cyan
      endpoint are dropped; visual diff shows whether this is acceptable.
      If not, extend with proper modifier resolution.
    - <a:alphaModFix amt="N"/>: returns {"alpha": N/100000} where N is
      thousandths-of-percent (e.g., 82000 → 0.82).

    Returns None when the blip carries no recognized transforms.
    Other blip-level transforms (a:lum, a:biLevel, a:grayscl, a:tile,
    a:stretch within blipFill, etc.) are not yet handled — extend when
    a slide needs them.
    """
    blip = pic_elem.find("p:blipFill/a:blip", NS)
    if blip is None:
        return None
    out: dict = {}

    duotone = blip.find("a:duotone", NS)
    if duotone is not None:
        colors = []
        for child in duotone:
            tag = child.tag.split("}")[-1]
            if tag == "prstClr":
                # Map a few common preset names; default black for unknown.
                preset = child.get("val", "").lower()
                hex_val = {
                    "black": "000000", "white": "FFFFFF",
                    "red": "FF0000", "green": "00FF00", "blue": "0000FF",
                }.get(preset, "000000")
                colors.append(hex_val)
            elif tag == "srgbClr":
                colors.append(child.get("val", "000000").upper())
        if len(colors) >= 2:
            out["duotone"] = {"dark_hex": colors[0], "light_hex": colors[1]}

    amf = blip.find("a:alphaModFix", NS)
    if amf is not None:
        amt = amf.get("amt")
        if amt is not None:
            try:
                out["alpha"] = max(0.0, min(1.0, int(amt) / 100000.0))
            except ValueError:
                pass

    return out or None


def probe_image(image_path: Path) -> tuple[int, int]:
    """Return (width, height) post-EXIF-rotation for an existing image file.

    Pillow lazy-loads dimensions without decoding pixels in most formats.
    EXIF orientation is applied via ImageOps.exif_transpose so dimensions
    match what was encoded — important for portrait JPEGs with EXIF rotation.
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    return (img.size[0], img.size[1])


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers

def _image_filename(deck_slug: str, slide_index: int, image_index: int) -> str:
    """Filename pattern: {slug}_slide_{NN:02d}_img_{KK:02d}.webp."""
    return f"{deck_slug}_slide_{slide_index:02d}_img_{image_index:02d}.webp"


def _deck_slug(manifest: dict, pptx_path: Path) -> str:
    """Same slug rule as transform/video.py — kept duplicated to avoid a
    cross-module import for one helper. If we add transform/_shared.py
    for other reasons, lift this there.
    """
    raw = (manifest.get("deck_name") or "").strip()
    parts = []
    for token in raw.split():
        cleaned = "".join(c for c in token if c.isalnum())
        if cleaned:
            parts.append(cleaned.lower())
    return "_".join(parts) or pptx_path.stem


def _iter_image_pics_per_slide(
    pptx: Pptx,
) -> Iterator[tuple[int, _PptxSlide, list[etree._Element]]]:
    """Yield (slide_index_1based, slide, [pic_element, ...]) per slide w/ images.

    Filters out videos (is_video_pic). Preserves document order via
    flatten_slide's z-order traversal.
    """
    for idx, slide in enumerate(pptx.slides(), start=1):
        pics = [
            fs.element for fs in flatten_slide(slide)
            if fs.kind == "pic" and not is_video_pic(fs.element)
        ]
        if pics:
            yield (idx, slide, pics)


def _pic_id(pic_elem: etree._Element) -> Optional[str]:
    """Read the OOXML cNvPr/@id from a <p:pic>. None if missing."""
    cnv = pic_elem.find("p:nvPicPr/p:cNvPr", NS)
    return cnv.get("id") if cnv is not None else None


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse '#RRGGBB' or 'RRGGBB' → (R, G, B). Raises on bad input."""
    s = color.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Expected #RRGGBB hex color, got {color!r}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _update_manifest_images(
    manifest: dict,
    slide_index: int,
    entries: list[dict],
) -> None:
    """Replace slides.<N>.media.images with the merged list."""
    slides = manifest.setdefault("slides", {})
    slide_entry = slides.setdefault(str(slide_index), {})
    media = slide_entry.setdefault("media", {})
    media["images"] = entries


def _partial_path(target: Path) -> Path:
    """The {stem}.__partial{suffix} sibling we write to before atomic rename."""
    return target.parent / f"{target.stem}.__partial{target.suffix}"


def _atomic_write_json(path: Path, data: dict) -> None:
    """JSON write with the same atomic-rename pattern as transform/video.py."""
    path = Path(path)
    partial = _partial_path(path)
    partial.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, path)


# ────────────────────────────────────────────────────────────────────────────
# CLI

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Run the image transform stage on a deck.",
    )
    p.add_argument("pptx", type=Path, help="Source .pptx")
    p.add_argument("manifest", type=Path, help="Manifest JSON")
    p.add_argument("output_dir", type=Path, help="Where to write .webp output(s)")
    p.add_argument(
        "--overwrite", action="store_true",
        help="Force re-encode even if output already exists",
    )
    p.add_argument(
        "--quality", type=int, default=85,
        help="WebP quality (1-100, default 85)",
    )
    args = p.parse_args()

    n = process_deck_images(
        args.pptx, args.manifest, args.output_dir,
        overwrite=args.overwrite, quality=args.quality,
    )
    print(f"processed {n} image(s)")
