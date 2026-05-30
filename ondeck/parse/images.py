"""Image extraction + transparency/overlap analysis.

Owns: resolving <p:pic> shapes' <a:blip r:embed=> references to image
bytes, analyzing transparency, computing the alpha-thresholded bounding
box, and deciding whether transparency must be preserved (vs allowed
to be flattened on a solid background).

The load-bearing rule, per the spec:
    if image has alpha < 255 anywhere
    AND any other shape is geometrically behind it in z-order
    -> preserve transparency (do NOT flatten-to-bg)

P&G slide 14 is the canonical regression case: a center product
mockup with a transparent left edge intentionally revealing a dieline
behind. Flattening it to white destroys the see-through layering.

Format conversion itself (WebP, JPEG-on-bg) lives in transform/image.py.
This module is read-only: extract bytes, analyze, decide. The decision
is consumed downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional

from lxml import etree
from PIL import Image
from pptx.slide import Slide

from .slide import NS

# Pixels with alpha below this 0–255 threshold are treated as fully
# transparent for bbox computation. The anti-aliased halo around drop-
# shadowed PNG subjects sits in the 5–50 range; without the threshold,
# getbbox() includes those pixels and inflates the box by tens of px.
# 30 was validated against P&G in the prior conversion session.
ALPHA_BBOX_THRESHOLD = 30

# Namespace prefix for the relationships namespace used on r:embed.
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


@dataclass
class ImageRef:
    """Resolved image binary with provenance."""

    rid: str                        # the r:embed value
    part_name: str                  # e.g. '/ppt/media/image3.png'
    blob: bytes                     # raw image bytes
    content_type: str               # e.g. 'image/png', 'image/svg+xml'


@dataclass
class ImageAnalysis:
    """PIL-based analysis of one raster image. None for SVG / unreadable."""

    ref: ImageRef
    natural_size: tuple             # (width_px, height_px)
    has_transparency: bool          # alpha channel AND at least one pixel < 255
    bbox_thresholded: Optional[tuple]  # (l,t,r,b) px after alpha threshold (None if empty)
    pil_mode: str                   # 'RGBA', 'RGB', 'P', etc.


@dataclass
class ImageDecision:
    """Output of decide_preservation()."""

    preserve_alpha: bool
    reason: str
    overlapping_behind: list = field(default_factory=list)


def extract_image_ref(pic_elem: etree._Element, slide: Slide) -> Optional[ImageRef]:
    """Resolve a <p:pic> shape's image bytes via its blip's relationship id.

    The XML structure (note the namespace mix):
        <p:pic>
          <p:blipFill>            ← presentation namespace
            <a:blip r:embed="rIdN"/>   ← drawingml namespace, normal raster case
          </p:blipFill>
        </p:pic>

    For SVG-only blips, the r:embed lives nested inside an <a:extLst>
    sub-element <asvg:svgBlip r:embed="rIdN"/> with no direct r:embed on
    <a:blip> itself. Those return ImageRef with content_type 'image/svg+xml'
    so callers can route them to parse/svg.py; analyze_image() returns
    None for them (PIL can't open SVG).

    Returns None if there is no <a:blip> or no resolvable rId.
    """
    blip = pic_elem.find("p:blipFill/a:blip", NS)
    if blip is None:
        return None

    rid = blip.get(R_NS + "embed")
    if rid is None:
        # SVG-only fallback: <asvg:svgBlip r:embed=...> inside the blip's extLst.
        ASVG = "{http://schemas.microsoft.com/office/drawing/2016/SVG/main}"
        svg_blip = blip.find(f".//{ASVG}svgBlip")
        if svg_blip is None:
            return None
        rid = svg_blip.get(R_NS + "embed")
        if rid is None:
            return None

    part = slide.part.related_part(rid)
    return ImageRef(
        rid=rid,
        part_name=str(part.partname),
        blob=part.blob,
        content_type=part.content_type or "",
    )


def analyze_image(ref: ImageRef) -> Optional[ImageAnalysis]:
    """Open with PIL and compute transparency + thresholded bbox.

    Returns None for unreadable formats (SVG, unsupported codecs).
    """
    if "svg" in ref.content_type.lower():
        return None
    try:
        img = Image.open(BytesIO(ref.blob))
        img.load()
    except Exception:
        return None

    has_alpha = _has_alpha_channel(img)
    if has_alpha:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        alpha = img.getchannel("A")
        min_a, _ = alpha.getextrema()
        has_trans = min_a < 255
        mask = alpha.point(lambda v: 255 if v >= ALPHA_BBOX_THRESHOLD else 0)
        bbox = mask.getbbox()
    else:
        has_trans = False
        bbox = img.getbbox()

    return ImageAnalysis(
        ref=ref,
        natural_size=img.size,
        has_transparency=has_trans,
        bbox_thresholded=bbox,
        pil_mode=img.mode,
    )


def find_overlapping_behind(this_shape, all_flat_shapes):
    """Return shapes with z < this_shape.z whose AABB overlaps this_shape's.

    Uses duck-typed access (x_pt/y_pt/w_pt/h_pt/z) so callers can pass
    parse/shapes.py's FlatShape records or any equivalent struct.
    """
    if this_shape.x_pt is None:
        return []
    return [
        s for s in all_flat_shapes
        if s is not this_shape
        and s.z < this_shape.z
        and s.x_pt is not None
        and _aabb_overlaps(this_shape, s)
    ]


def decide_preservation(
    analysis: Optional[ImageAnalysis],
    overlapping_behind: list,
) -> ImageDecision:
    """Apply the load-bearing rule.

    Preserve alpha when BOTH:
      - the image has at least one transparent pixel (not just an alpha channel)
      - at least one shape sits behind it in z-order with geometric overlap

    Otherwise the image can be safely flattened on a solid background.
    """
    if analysis is None:
        return ImageDecision(False, "unreadable / SVG", overlapping_behind)
    if not analysis.has_transparency:
        return ImageDecision(False, "opaque (no transparent pixels)", overlapping_behind)
    if overlapping_behind:
        return ImageDecision(
            True,
            f"transparent + {len(overlapping_behind)} shape(s) behind",
            overlapping_behind,
        )
    return ImageDecision(
        False,
        "transparent but nothing behind (safe to flatten on bg)",
        overlapping_behind,
    )


# === internals ===

def _has_alpha_channel(img) -> bool:
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def _aabb_overlaps(a, b) -> bool:
    """AABB overlap on FlatShape-like records. Touching edges = no overlap."""
    return not (
        a.x_pt + a.w_pt <= b.x_pt
        or b.x_pt + b.w_pt <= a.x_pt
        or a.y_pt + a.h_pt <= b.y_pt
        or b.y_pt + b.h_pt <= a.y_pt
    )
