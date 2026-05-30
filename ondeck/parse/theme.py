"""Theme color extraction + lumMod/lumOff resolver.

Owns: parsing <a:clrScheme> from ppt/theme/themeN.xml, exposing the 12
named theme colors, and applying PowerPoint's lumMod/lumOff modifiers
that derive grays and tints from a base color.

Per the spec: brand colors must be extracted per-deck, NEVER assumed.
P&G's accent1 is cyan #00B0F0 but other decks differ.
"""
from __future__ import annotations

import colorsys
import zipfile
from dataclasses import dataclass
from typing import Optional

from lxml import etree

from .pptx import Pptx

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

# PowerPoint XML uses per-mille scaling for modifiers and alpha:
#   <a:lumMod val="50000"> = 50%, <a:alpha val="38000"> = 38%.
# This was a trip-wire bug class in prior conversion sessions; centralize
# the constant so future-self can grep for it.
PER_MILLE = 100000

# bg1/tx1/bg2/tx2 are how shapes reference the four base colors;
# they map to lt1/dk1/lt2/dk2 in the clrScheme.
SCHEME_ALIASES = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}


@dataclass
class Theme:
    """Resolved color palette for one deck. Values are 6-char uppercase hex (no #)."""

    dk1: str
    lt1: str
    dk2: str
    lt2: str
    accent1: str
    accent2: str
    accent3: str
    accent4: str
    accent5: str
    accent6: str
    hlink: str
    folHlink: str

    def resolve(self, token: str) -> str:
        """Look up a scheme color token like 'accent1' or 'bg1' (alias-aware)."""
        return getattr(self, SCHEME_ALIASES.get(token, token))


def extract_theme(pptx: Pptx, index: int = 1) -> Theme:
    """Read ppt/theme/themeN.xml from the .pptx zip and parse it."""
    with zipfile.ZipFile(pptx.path) as zf:
        theme_bytes = zf.read(f"ppt/theme/theme{index}.xml")
    return parse_theme(theme_bytes)


def parse_theme(theme_xml: bytes) -> Theme:
    """Parse a theme XML document and return its color palette."""
    root = etree.fromstring(theme_xml)
    scheme = root.find(".//a:clrScheme", NS)
    if scheme is None:
        raise ValueError("no <a:clrScheme> found in theme XML")
    palette: dict[str, str] = {}
    for child in scheme:
        tag = etree.QName(child).localname
        palette[tag] = _resolve_color_node(child)
    return Theme(**palette)


def _resolve_color_node(node) -> str:
    """Extract the hex value from a clrScheme child node.

    Handles both <a:srgbClr val="..."/> (direct) and
    <a:sysClr val="..." lastClr="..."/> (system color with fallback).
    """
    srgb = node.find("a:srgbClr", NS)
    if srgb is not None:
        return srgb.get("val").upper()
    sys_clr = node.find("a:sysClr", NS)
    if sys_clr is not None:
        last = sys_clr.get("lastClr")
        if last:
            return last.upper()
        return {"window": "FFFFFF", "windowText": "000000"}.get(
            sys_clr.get("val", ""), "000000"
        )
    raise ValueError(f"can't resolve color from <{etree.QName(node).localname}>")


def apply_lum_mod_off(
    hex_color: str,
    lum_mod: Optional[int],
    lum_off: Optional[int],
) -> str:
    """Apply PowerPoint's lumMod/lumOff modifiers to a base color.

    The formula (per the spec) operates on the L channel of HSL:
        new_lightness = lightness * (lumMod/100000) + (lumOff/100000)
    clamped to [0, 1]. Either modifier may be None (identity:
    lumMod=100000 and lumOff=0). Used heavily for theme color shades —
    e.g. a "lighter accent1" for backgrounds is accent1 with lumMod<100000
    and lumOff>0.
    """
    if lum_mod is None and lum_off is None:
        return hex_color.upper()

    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    mod = (lum_mod / PER_MILLE) if lum_mod is not None else 1.0
    off = (lum_off / PER_MILLE) if lum_off is not None else 0.0
    new_l = max(0.0, min(1.0, l * mod + off))

    r, g, b = colorsys.hls_to_rgb(h, new_l, s)
    return f"{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
