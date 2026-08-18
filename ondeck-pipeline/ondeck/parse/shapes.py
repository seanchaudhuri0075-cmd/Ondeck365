"""Group transform composition + recursive shape flattening.

Owns: descending into <p:grpSp> shapes, composing nested transforms, and
yielding every leaf shape on a slide with WORLD-space coordinates in
z-order. Per the spec — python-pptx applies nested group transforms
incorrectly, so we walk raw XML and do the math ourselves.

The math (per the spec):
    world_x = group.off.x + (child.x - group.chOff.x) * (group.ext.x / group.chExt.x)
    world_y = group.off.y + (child.y - group.chOff.y) * (group.ext.y / group.chExt.y)
    world_w = child.w * (group.ext.x / group.chExt.x)
    world_h = child.h * (group.ext.y / group.chExt.y)

For nested groups the transforms compose: each <p:grpSp> declares its own
off/ext in its parent's child-coord-space, so we resolve the group's own
position into world space first, then build the inner-space → world map
for that group's children.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from lxml import etree
from pptx.slide import Slide

from .pptx import EMU_PER_PT
from .slide import NS, SHAPE_KINDS, _is_design_locker, _xfrm_pt


@dataclass(frozen=True)
class Transform:
    """Affine map (axis-aligned scale + translate): world = local * scale + offset.

    Identity transform = no group ancestry; local coords are already world.
    """

    scale_x: float = 1.0
    scale_y: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0

    def map_point(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.scale_x + self.offset_x, y * self.scale_y + self.offset_y)

    def map_size(self, w: float, h: float) -> tuple[float, float]:
        return (w * self.scale_x, h * self.scale_y)


@dataclass
class FlatShape:
    """A leaf shape (sp/pic/cxnSp/graphicFrame/contentPart) in WORLD coordinates.

    Groups themselves are NOT yielded — only their leaf descendants. The
    `group_path` carries provenance (cNvPr ids of enclosing groups,
    outermost first) so downstream consumers can correlate flattened
    shapes back to the original group structure if needed.
    """

    kind: str
    z: int
    x_pt: Optional[float]
    y_pt: Optional[float]
    w_pt: Optional[float]
    h_pt: Optional[float]
    element: etree._Element
    group_path: tuple[str, ...]


def flatten_slide(slide: Slide) -> Iterator[FlatShape]:
    """Yield every leaf shape on a slide in world coords + z-order.

    Z-order is depth-first pre-order across nested groups, matching how
    PowerPoint renders: a group's children paint in the z-slot the group
    occupies, in the group's internal document order.
    """
    sp_tree = slide.element.find(".//p:spTree", NS)
    if sp_tree is None:
        return
    z_counter = [0]
    yield from _walk(sp_tree, Transform(), (), z_counter)


def _walk(
    parent: etree._Element,
    transform: Transform,
    group_path: tuple[str, ...],
    z_counter: list,
) -> Iterator[FlatShape]:
    for child in parent:
        kind = etree.QName(child).localname
        if kind not in SHAPE_KINDS:
            continue  # nvGrpSpPr / grpSpPr / extLst on group itself
        if _is_design_locker(child):
            continue
        if kind == "grpSp":
            yield from _descend_group(child, transform, group_path, z_counter)
        else:
            x, y, w, h = _xfrm_pt(child, kind)
            wx, wy, ww, wh = _to_world(x, y, w, h, transform)
            yield FlatShape(
                kind=kind,
                z=z_counter[0],
                x_pt=wx,
                y_pt=wy,
                w_pt=ww,
                h_pt=wh,
                element=child,
                group_path=group_path,
            )
            z_counter[0] += 1


def _descend_group(
    group: etree._Element,
    transform: Transform,
    group_path: tuple[str, ...],
    z_counter: list,
) -> Iterator[FlatShape]:
    """Compose this group's child-space → world transform, recurse into children."""
    gid = _group_id(group)
    next_path = group_path + (gid,)

    xfrm = group.find("p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        # Group with no transform — children inherit parent transform unchanged.
        # Rare; defensive.
        yield from _walk(group, transform, next_path, z_counter)
        return

    off_x, off_y = _read_xy(xfrm.find("a:off", NS), default=(0.0, 0.0))
    ext_x, ext_y = _read_cx_cy(xfrm.find("a:ext", NS), default=(1.0, 1.0))
    ch_off_x, ch_off_y = _read_xy(xfrm.find("a:chOff", NS), default=(0.0, 0.0))
    ch_ext_x, ch_ext_y = _read_cx_cy(xfrm.find("a:chExt", NS), default=(ext_x, ext_y))

    # Map the group's own off/ext into world coords using the inherited transform.
    world_off_x, world_off_y = transform.map_point(off_x, off_y)
    world_ext_x, world_ext_y = transform.map_size(ext_x, ext_y)

    # New transform: this group's child-space → world.
    sx = world_ext_x / ch_ext_x if ch_ext_x else 0.0
    sy = world_ext_y / ch_ext_y if ch_ext_y else 0.0
    new_transform = Transform(
        scale_x=sx,
        scale_y=sy,
        offset_x=world_off_x - ch_off_x * sx,
        offset_y=world_off_y - ch_off_y * sy,
    )

    yield from _walk(group, new_transform, next_path, z_counter)


def _to_world(x, y, w, h, transform: Transform):
    if x is None:
        return (None, None, None, None)
    wx, wy = transform.map_point(x, y)
    ww, wh = transform.map_size(w, h)
    return (wx, wy, ww, wh)


def _read_xy(node, default):
    if node is None:
        return default
    return (int(node.get("x")) / EMU_PER_PT, int(node.get("y")) / EMU_PER_PT)


def _read_cx_cy(node, default):
    if node is None:
        return default
    return (int(node.get("cx")) / EMU_PER_PT, int(node.get("cy")) / EMU_PER_PT)


def _group_id(group: etree._Element) -> str:
    cNvPr = group.find("p:nvGrpSpPr/p:cNvPr", NS)
    return cNvPr.get("id", "?") if cNvPr is not None else "?"
