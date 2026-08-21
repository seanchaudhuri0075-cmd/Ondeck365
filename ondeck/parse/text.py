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

from .pptx import EMU_PER_PT
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
    spacing_pt: Optional[float] = None   # letter-spacing/tracking; None = default


@dataclass
class Run:
    text: str
    style: RunStyle


@dataclass
class Paragraph:
    align: Optional[str] = None  # 'l' | 'ctr' | 'r' | 'just' | None (inherited)
    runs: list = field(default_factory=list)
    blank_line_size_pt: Optional[float] = None  # pPr/defRPr size, for empty paragraphs
    # used as manual vertical spacers — the line still needs to take up
    # its declared height even though it renders no visible text.
    bullet_char: Optional[str] = None  # resolved bullet glyph (e.g. '▪'), None if unbulleted
    marL_pt: Optional[float] = None    # hanging-indent depth (pPr/@marL), for bullet layout


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


# PowerPoint's built-in bullet presets encode bullet glyphs as codepoints
# in a symbol font (usually Wingdings/Wingdings 2/3 or Symbol) rather than
# real Unicode bullet characters — the raw codepoint only looks right if
# that exact font is installed and used, which it won't be here. Map the
# handful of codepoints PowerPoint's bullet picker actually offers to their
# closest real Unicode equivalents. Unmapped codepoints in a known symbol
# font fall back to a plain round bullet rather than showing the wrong
# glyph (e.g. a random dingbat) or the raw font's private-use character.
_WINGDINGS_BULLETS = {
    "\u00a7": "\u25aa",  # section-sign codepoint -> small black square (this deck)
    "\u00fc": "\u2713",  # -> checkmark
    "\u00d8": "\u25c6",  # -> diamond
    "\u00ac": "\u27a2",  # -> arrow
}
_SYMBOL_BULLET_FONTS = {"wingdings", "wingdings 2", "wingdings 3", "symbol", "webdings"}


def _resolve_bullet_char(p_pr: etree._Element) -> Optional[str]:
    bu_char = p_pr.find("a:buChar", NS)
    if bu_char is None:
        return None
    ch = bu_char.get("char")
    if not ch:
        return None
    bu_font = p_pr.find("a:buFont", NS)
    font_name = bu_font.get("typeface", "").lower() if bu_font is not None else ""
    if font_name in _SYMBOL_BULLET_FONTS:
        return _WINGDINGS_BULLETS.get(ch, "\u2022")  # default: round bullet
    return ch  # already a real Unicode bullet (e.g. buChar char="•")


def _parse_paragraph(p_elem: etree._Element, theme: Theme) -> Paragraph:
    p_pr = p_elem.find("a:pPr", NS)
    align = p_pr.get("algn") if p_pr is not None else None

    bullet_char = None
    marL_pt = None
    blank_line_size_pt = None
    if p_pr is not None:
        bullet_char = _resolve_bullet_char(p_pr)
        marL = p_pr.get("marL")
        if marL is not None:
            marL_pt = int(marL) / EMU_PER_PT
        def_rpr = p_pr.find("a:defRPr", NS)
        if def_rpr is not None:
            sz = def_rpr.get("sz")
            if sz is not None:
                blank_line_size_pt = int(sz) / SZ_PER_PT

    # Iterate runs in document order. Both <a:r> (regular run) and
    # <a:fld> (field — date, slide number, etc.) carry an <a:t> and
    # styling, so treat them uniformly. <a:br> (soft line break) is
    # punted in Phase 1B; surface if a deck needs it.
    runs = []
    for child in p_elem:
        tag = etree.QName(child).localname
        if tag in ("r", "fld"):
            runs.append(_parse_run(child, theme))

    return Paragraph(
        align=align, runs=runs, blank_line_size_pt=blank_line_size_pt,
        bullet_char=bullet_char, marL_pt=marL_pt,
    )


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

    # spc is letter-spacing/tracking, also in hundredths of a point
    # (same unit convention as sz — see SZ_PER_PT note above). This is
    # load-bearing on decks that hand-tune box positions assuming a
    # specific rendered run width (e.g. centering several differently
    # sized text boxes so a single leading character lines up across
    # rows) — dropping it silently breaks that alignment even though
    # every box's coordinates are otherwise pixel-exact.
    spc = r_pr.get("spc")
    if spc is not None:
        style.spacing_pt = int(spc) / SZ_PER_PT

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
