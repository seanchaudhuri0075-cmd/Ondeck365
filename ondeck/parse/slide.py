"""Walk a slide's shape tree and yield top-level shapes in z-order.

Owns: traversing <p:spTree>, identifying shape kinds, extracting top-level
geometry, filtering out PowerPoint Designer decorative lockers.

Group recursion + nested-transform composition is NOT done here — groups
are yielded as opaque records with their own transform exposed. That math
lives in `parse/shapes.py` (next module). This separation keeps the
top-level walk simple and lets shape composition stay in one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from lxml import etree
from pptx.slide import Slide

from .pptx import EMU_PER_PT

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "p16": "http://schemas.microsoft.com/office/powerpoint/2015/main",
}

# Shape kinds we recognize on a slide. These are the localnames of the
# children of <p:spTree>. cxnSp is rare in pitch decks; contentPart is
# rarer still — both yielded for completeness.
SHAPE_KINDS = {"sp", "pic", "grpSp", "graphicFrame", "cxnSp", "contentPart"}


@dataclass
class ShapeRecord:
    """One shape in flattened slide-walk order.

    Geometry is in points (1pt = 9525 EMU) and represents the shape's own
    declared transform. For shapes inside groups, this is the LOCAL transform;
    composition into world coordinates is parse/shapes.py's job.

    Geometry may be None when the shape inherits position from the layout
    or master (placeholder pattern). Phase 1B punts on placeholder
    inheritance — most pitch-deck shapes carry explicit xfrm.
    """

    kind: str  # 'sp' | 'pic' | 'grpSp' | 'graphicFrame' | 'cxnSp' | 'contentPart'
    z: int  # 0-based, top-level document order; 0 = bottom-most
    x_pt: Optional[float]
    y_pt: Optional[float]
    w_pt: Optional[float]
    h_pt: Optional[float]
    element: etree._Element  # raw XML for downstream extraction


def walk_top_level(slide: Slide) -> Iterator[ShapeRecord]:
    """Yield top-level shapes on a slide in z-order (document order in spTree).

    Skips PowerPoint Designer decorative lockers (<p16:designElem val="1"/>);
    these are noFill/noLine metadata rectangles inserted by Designer that
    have no visual purpose. Filtering at this boundary means downstream
    code never sees them.
    """
    sp_tree = slide.element.find(".//p:spTree", NS)
    if sp_tree is None:
        return
    z = 0
    for child in sp_tree:
        kind = etree.QName(child).localname
        if kind not in SHAPE_KINDS:
            continue  # nvGrpSpPr, grpSpPr, and other non-shape children
        if _is_design_locker(child):
            continue
        x, y, w, h = _xfrm_pt(child, kind)
        yield ShapeRecord(
            kind=kind,
            z=z,
            x_pt=x,
            y_pt=y,
            w_pt=w,
            h_pt=h,
            element=child,
        )
        z += 1


def _is_design_locker(shape_elem) -> bool:
    """True if this shape is a Designer decorative metadata locker.

    Per the spec: <p16:designElem val="1"/> appears in nvPr extLst on
    rectangles Designer inserts with noFill noLine. They have zero visual
    output but appear in the shape tree.
    """
    return shape_elem.find(".//p16:designElem[@val='1']", NS) is not None


def _xfrm_pt(elem, kind: str) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Extract local x/y/w/h in points from a shape's xfrm element.

    The path to xfrm differs by kind:
      sp/pic/cxnSp/contentPart: <p:spPr><a:xfrm>
      graphicFrame:             <p:xfrm>            (presentation namespace)
      grpSp:                    <p:grpSpPr><a:xfrm>

    Returns (None, None, None, None) when the shape has no explicit xfrm
    (placeholder inheritance — left to downstream).
    """
    if kind == "graphicFrame":
        xfrm = elem.find("p:xfrm", NS)
    elif kind == "grpSp":
        xfrm = elem.find("p:grpSpPr/a:xfrm", NS)
    else:  # sp, pic, cxnSp, contentPart
        xfrm = elem.find("p:spPr/a:xfrm", NS)

    if xfrm is None:
        return (None, None, None, None)

    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    x = int(off.get("x")) / EMU_PER_PT if off is not None else None
    y = int(off.get("y")) / EMU_PER_PT if off is not None else None
    w = int(ext.get("cx")) / EMU_PER_PT if ext is not None else None
    h = int(ext.get("cy")) / EMU_PER_PT if ext is not None else None
    return (x, y, w, h)
