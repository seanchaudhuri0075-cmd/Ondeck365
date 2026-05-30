"""Text extraction — paragraph→run iteration with full run-level styling.

Owns: descending into <p:txBody>, walking paragraphs and runs, extracting
per-run styling (font, size, bold/italic/underline, color, alpha), and
resolving theme color references via a passed-in Theme.

Per the spec: the atomic styling unit is the RUN, not the paragraph. A
single paragraph routinely mixes bold + non-bold and different sizes
within it.

DECLARED sizes only — calibration to rendered sizes (Univers→Barlow
substitution) lives in `parse/font_calibration.py` and runs at render
time. Keeping the empirical magic in its own module makes it findable
when a future deck needs the rules tweaked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lxml import etree

from .slide import NS
from .theme import Theme, apply_lum_mod_off

# PowerPoint sz attribute is in HUNDREDTHS of a point.
#   sz="4400" = 44pt    sz="8800" = 88pt
# Trip-wire bug class — centralized so future-self can grep for it.
SZ_PER_PT = 100


@dataclass
class RunStyle:
    """Declared styling for one run. Any field may be None (= inherited)."""

    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    size_pt: Optional[float] = None      # declared, NOT calibrated
    typeface: Optional[str] = None       # latin font, e.g. "Univers"
    color_hex: Optional[str] = None      # already lumMod/lumOff-resolved
    color_alpha: Optional[float] = None  # 0.0–1.0, None = opaque


@dataclass
class Run:
    text: str
    style: RunStyle


@dataclass
class Paragraph:
    align: Optional[str] = None  # 'l' | 'ctr' | 'r' | 'just' | None (inherited)
    runs: list = field(default_factory=list)


@dataclass
class TextFrame:
    """A shape's text body. anchor maps to .uct/.ucb editor classes:
    'ctr' → .uct, 'b' → .ucb, 't' → .uct (default), None = inherited."""

    anchor: Optional[str] = None  # 't' | 'ctr' | 'b' | None
    paragraphs: list = field(default_factory=list)


def parse_text_frame(shape_elem: etree._Element, theme: Theme) -> Optional[TextFrame]:
    """Extract <p:txBody> from a shape element. Returns None if absent (e.g. a pic)."""
    tx_body = shape_elem.find("p:txBody", NS)
    if tx_body is None:
        return None

    body_pr = tx_body.find("a:bodyPr", NS)
    anchor = body_pr.get("anchor") if body_pr is not None else None

    paragraphs = [_parse_paragraph(p, theme) for p in tx_body.findall("a:p", NS)]
    return TextFrame(anchor=anchor, paragraphs=paragraphs)


def _parse_paragraph(p_elem: etree._Element, theme: Theme) -> Paragraph:
    p_pr = p_elem.find("a:pPr", NS)
    align = p_pr.get("algn") if p_pr is not None else None

    # Iterate runs in document order. Both <a:r> (regular run) and
    # <a:fld> (field — date, slide number, etc.) carry an <a:t> and
    # styling, so treat them uniformly. <a:br> (soft line break) is
    # punted in Phase 1B; surface if a deck needs it.
    runs = []
    for child in p_elem:
        tag = etree.QName(child).localname
        if tag in ("r", "fld"):
            runs.append(_parse_run(child, theme))

    return Paragraph(align=align, runs=runs)


def _parse_run(r_elem: etree._Element, theme: Theme) -> Run:
    text_node = r_elem.find("a:t", NS)
    text = (text_node.text or "") if text_node is not None else ""

    r_pr = r_elem.find("a:rPr", NS)
    style = _parse_run_props(r_pr, theme) if r_pr is not None else RunStyle()
    return Run(text=text, style=style)


def _parse_run_props(r_pr: etree._Element, theme: Theme) -> RunStyle:
    style = RunStyle()
    style.bold = _bool_attr(r_pr, "b")
    style.italic = _bool_attr(r_pr, "i")

    underline = r_pr.get("u")
    if underline == "none":
        style.underline = False
    elif underline is not None:
        style.underline = True

    sz = r_pr.get("sz")
    if sz is not None:
        style.size_pt = int(sz) / SZ_PER_PT

    latin = r_pr.find("a:latin", NS)
    if latin is not None:
        style.typeface = latin.get("typeface")

    fill = r_pr.find("a:solidFill", NS)
    if fill is not None:
        style.color_hex, style.color_alpha = _resolve_color(fill, theme)

    return style


def _bool_attr(elem: etree._Element, name: str) -> Optional[bool]:
    """OOXML booleans use '1'/'0' or 'true'/'false'. None = absent = inherited."""
    val = elem.get(name)
    if val is None:
        return None
    return val in ("1", "true")


def _resolve_color(fill_elem, theme: Theme) -> tuple[Optional[str], Optional[float]]:
    """Resolve <a:solidFill> with srgbClr or schemeClr (+ optional lumMod/lumOff/alpha).

    Returns (hex_or_none, alpha_or_none). Alpha is 0.0–1.0; None means opaque.
    """
    srgb = fill_elem.find("a:srgbClr", NS)
    scheme = fill_elem.find("a:schemeClr", NS)

    if srgb is not None:
        base = srgb.get("val").upper()
        modifier_node = srgb
    elif scheme is not None:
        token = scheme.get("val")
        try:
            base = theme.resolve(token)
        except AttributeError:
            return (None, None)
        modifier_node = scheme
    else:
        return (None, None)

    lum_mod = _per_mille_child(modifier_node, "a:lumMod")
    lum_off = _per_mille_child(modifier_node, "a:lumOff")
    base = apply_lum_mod_off(base, lum_mod, lum_off)

    alpha_val = _per_mille_child(modifier_node, "a:alpha")
    alpha = (alpha_val / 100000) if alpha_val is not None else None

    return (base, alpha)


def _per_mille_child(parent: etree._Element, child_xpath: str) -> Optional[int]:
    """Return the int value of a per-mille child element (lumMod, lumOff, alpha)."""
    child = parent.find(child_xpath, NS)
    if child is None:
        return None
    val = child.get("val")
    return int(val) if val is not None else None
