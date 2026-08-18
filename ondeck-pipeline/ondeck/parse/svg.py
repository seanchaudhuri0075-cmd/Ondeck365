"""SVG-only blip handler.

Owns: detecting and extracting vector graphics referenced from
<p:pic> shapes via the Microsoft SVG-blip extension. python-pptx's
shape.image raises on these because the shape carries no raster
fallback in some cases. We reach into the raw XML, find the
<asvg:svgBlip r:embed="rIdN"/> nested inside the blip's <a:extLst>,
and resolve the relationship to the SVG part's bytes.

XML structure:
    <p:pic>
      <p:blipFill>
        <a:blip [r:embed="rIdRaster"]>
          <a:extLst>
            <a:ext uri="{96DAC541-...}">
              <asvg:svgBlip r:embed="rIdSvg"/>     ← here
            </a:ext>
          </a:extLst>
        </a:blip>
      </p:blipFill>
    </p:pic>

Two cases:
  - SVG-only: <a:blip> has no direct r:embed; only the nested svgBlip.
  - Hybrid:   <a:blip> carries a raster r:embed AND a nested svgBlip.
              parse/images.py picks up the raster side; this module
              picks up the SVG. Rendering layer decides which to use.

P&G has 2 SVG-only cases (no hybrids):
  - slide 1  hero "P&G" letterform graphic
  - slide 23 "GIF" logo
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lxml import etree
from pptx.slide import Slide

from .slide import NS

R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ASVG_NS = "{http://schemas.microsoft.com/office/drawing/2016/SVG/main}"


@dataclass
class SvgRef:
    """Resolved SVG part with provenance."""

    rid: str
    part_name: str          # e.g. '/ppt/media/image1.svg'
    blob: bytes             # raw SVG XML bytes
    content_type: str       # typically 'image/svg+xml'


def has_svg_blip(pic_elem: etree._Element) -> bool:
    """True iff the shape's <a:blip> carries a nested <asvg:svgBlip>.

    Use this as a cheap pre-check before extract_svg_ref(). A pic may
    be SVG-only (raster missing) OR hybrid (raster + SVG); both cases
    return True here.
    """
    return pic_elem.find(f".//p:blipFill/a:blip//{ASVG_NS}svgBlip", NS) is not None


def extract_svg_ref(pic_elem: etree._Element, slide: Slide) -> Optional[SvgRef]:
    """Resolve the <asvg:svgBlip r:embed=...> on a <p:pic>'s blip.

    Returns None if the shape has no SVG side (raster-only).
    """
    svg_blip = pic_elem.find(f".//p:blipFill/a:blip//{ASVG_NS}svgBlip", NS)
    if svg_blip is None:
        return None
    rid = svg_blip.get(R_NS + "embed")
    if rid is None:
        return None

    part = slide.part.related_part(rid)
    return SvgRef(
        rid=rid,
        part_name=str(part.partname),
        blob=part.blob,
        content_type=part.content_type or "",
    )
