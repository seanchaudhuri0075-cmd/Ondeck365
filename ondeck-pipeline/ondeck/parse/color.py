"""
ondeck.parse.color
==================

PowerPoint DrawingML color resolution.

Resolves ``<a:solidFill>`` and related color elements into final RGB/alpha
values, producing a structured audit trail of every transform applied.

Phase 1c contract:
    - ``shade`` and ``tint`` use RGB blend (deviation from ECMA-376 HSL
      Luminance wording; matches PowerPoint's empirical behavior).
    - ``lumMod`` and ``lumOff`` operate in HSL Luminance.
    - ``satMod`` operates in HSL Saturation.
    - ``alpha`` is a separate channel (does not affect RGB).

Public API:
    resolver = ColorResolver(theme)
    result = resolver.resolve(xml_element)
    result = resolver.resolve_with_theme(shape_side, theme_side)

    theme = theme_from_pptx(path)  # ergonomics helper; does file I/O
"""

from __future__ import annotations

import colorsys
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "test": "https://ondeck.local/phase_1c/fixture-harness",
}
A = "{%s}" % NS["a"]


# ---------------------------------------------------------------------------
# Color math primitives
# ---------------------------------------------------------------------------

def _hex_from_rgb(rgb: tuple[float, float, float]) -> str:
    """Round to int, clamp to 0-255, format as #RRGGBB."""
    r, g, b = (max(0, min(255, round(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _rgb_from_hex(hex_str: str) -> tuple[float, float, float]:
    """Parse '#RRGGBB' or 'RRGGBB' into a (r, g, b) float tuple in 0-255."""
    s = hex_str.lstrip("#")
    return (float(int(s[0:2], 16)), float(int(s[2:4], 16)), float(int(s[4:6], 16)))


def _apply_lum_mod(rgb: tuple[float, float, float], val: int) -> tuple[float, float, float]:
    """Multiply HSL Luminance by val/100000."""
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l * (val / 100000.0)))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255.0, g * 255.0, b * 255.0)


def _apply_lum_off(rgb: tuple[float, float, float], val: int) -> tuple[float, float, float]:
    """Add val/100000 to HSL Luminance."""
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l + (val / 100000.0)))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255.0, g * 255.0, b * 255.0)


def _apply_sat_mod(rgb: tuple[float, float, float], val: int) -> tuple[float, float, float]:
    """Multiply HSL Saturation by val/100000."""
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s = max(0.0, min(1.0, s * (val / 100000.0)))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255.0, g * 255.0, b * 255.0)


def _apply_shade(rgb: tuple[float, float, float], val: int) -> tuple[float, float, float]:
    """RGB blend toward black. Per spec deviation from ECMA-376."""
    factor = val / 100000.0
    return tuple(c * factor for c in rgb)  # type: ignore[return-value]


def _apply_tint(rgb: tuple[float, float, float], val: int) -> tuple[float, float, float]:
    """RGB blend toward white. Per spec deviation from ECMA-376.

    Per fixture data: tint(c, val) = c + (255 - c) * (val/100000).
    The value represents how much white is mixed in directly (0 = no change,
    100000 = pure white).
    """
    factor = val / 100000.0
    return tuple(c + (255.0 - c) * factor for c in rgb)  # type: ignore[return-value]


# Map of transform tag (local name) to (handler, step_label_template)
_TRANSFORM_HANDLERS = {
    "lumMod": _apply_lum_mod,
    "lumOff": _apply_lum_off,
    "satMod": _apply_sat_mod,
    "shade": _apply_shade,
    "tint": _apply_tint,
}


# ---------------------------------------------------------------------------
# ColorResolver
# ---------------------------------------------------------------------------

class ColorResolver:
    """Resolve DrawingML color elements against a theme dict.

    The theme dict maps scheme-color names (accent1, accent2, dk1, lt1, etc.)
    to hex strings: ``{"accent1": "#156082", "lt1": "#FFFFFF", ...}``
    """

    def __init__(self, theme: dict[str, str]):
        self.theme = {k: v if v.startswith("#") else f"#{v}" for k, v in theme.items()}

    # -- Public --------------------------------------------------------------

    def resolve(self, element: ET.Element) -> dict[str, Any]:
        """Resolve a bare ``<a:solidFill>`` (or its inner color child) element.

        Returns the flat audit shape matching synthetic_02/_03 expecteds.
        """
        color_el = self._unwrap_to_color_element(element)
        return self._resolve_color_element(color_el, scheme_override=None)

    def resolve_with_theme(
        self,
        shape_side: ET.Element,
        theme_side: ET.Element,
    ) -> dict[str, Any]:
        """Resolve fillRef-style two-phase composition (synthetic_01 case).

        ``shape_side`` is resolved first; its result becomes the ``phClr``
        substitution for ``theme_side``.
        """
        # Phase 1: resolve shape-side (fillRef child carries actual scheme color + mods)
        shape_color_el = self._unwrap_to_color_element(shape_side)
        shape_result = self._resolve_color_element(shape_color_el, scheme_override=None)

        shape_input_label = self._scheme_input_label(shape_color_el)
        shape_side_block = {
            "template": None,  # filled by caller if known; not in fixture data
            "transforms": self._collect_transforms(shape_color_el),
            "phase_label": "applied first; result becomes phClr for theme template",
            "final_hex": shape_result["final_hex"],
            "steps": [
                {"step": shape_input_label, "rgb": list(self._initial_rgb(shape_color_el)),
                 "hex": _hex_from_rgb(self._initial_rgb(shape_color_el))},
                *shape_result["steps"][1:],  # drop the duplicate input step
            ],
            "final_rgb_int": shape_result["final_rgb_int"],
        }

        # Phase 2: resolve theme-side, treating phClr as the shape-side result
        theme_color_el = self._unwrap_to_color_element(theme_side)
        phclr_rgb = self._final_rgb_float(shape_result)
        theme_result = self._resolve_color_element(
            theme_color_el,
            scheme_override=phclr_rgb,
            phclr_label=f"phClr from shape-side {shape_result['final_hex']}",
        )

        theme_side_block = {
            "template": "fmtScheme/fillStyleLst[2] stop 0",
            "transforms": self._collect_transforms(theme_color_el),
            "phase_label": "applied second; consumes phClr from shape-side",
            "final_hex": theme_result["final_hex"],
            "steps": theme_result["steps"],
            "final_rgb_int": theme_result["final_rgb_int"],
        }

        # Build audit chain
        audit_parts = [shape_input_label]
        for tag, val in shape_side_block["transforms"]:
            audit_parts.append(f"{tag} {val}")
        audit_parts.append(shape_result["final_hex"])
        for tag, val in theme_side_block["transforms"]:
            audit_parts.append(f"{tag} {val}")
        audit_parts.append(theme_result["final_hex"])

        # Best-effort scheme color label (e.g. "accent1 = #156082")
        scheme_label = None
        sc = shape_color_el if shape_color_el.tag == f"{A}schemeClr" else None
        if sc is not None:
            name = sc.get("val")
            scheme_label = f"{name} = {self.theme.get(name, '?')}"

        return {
            "fixture": None,  # caller may set
            "case": None,
            "scheme_color": scheme_label,
            "shape_side": shape_side_block,
            "theme_side": theme_side_block,
            "final_hex": theme_result["final_hex"],
            "audit_chain": " -> ".join(audit_parts),
        }

    # -- Internal: element navigation ---------------------------------------

    def _unwrap_to_color_element(self, element: ET.Element) -> ET.Element:
        """Given a solidFill, fillRef, or already-a-color-element, return the
        innermost color element (schemeClr, srgbClr, etc.)."""
        tag = element.tag
        if tag in (f"{A}schemeClr", f"{A}srgbClr"):
            return element
        # solidFill or fillRef: find first color child
        for child in element:
            if child.tag in (f"{A}schemeClr", f"{A}srgbClr"):
                return child
        raise ValueError(f"No color element found inside {tag}")

    def _initial_rgb(self, color_el: ET.Element) -> tuple[float, float, float]:
        """Get the starting RGB for a color element (theme lookup or hex)."""
        if color_el.tag == f"{A}srgbClr":
            return _rgb_from_hex(color_el.get("val", "000000"))
        if color_el.tag == f"{A}schemeClr":
            name = color_el.get("val", "")
            hex_val = self.theme.get(name)
            if hex_val is None:
                raise KeyError(f"Theme has no entry for scheme color: {name!r}")
            return _rgb_from_hex(hex_val)
        raise ValueError(f"Unsupported color element: {color_el.tag}")

    def _scheme_input_label(self, color_el: ET.Element) -> str:
        if color_el.tag == f"{A}srgbClr":
            return f"srgbClr #{color_el.get('val', '000000').upper()}"
        name = color_el.get("val", "")
        hex_val = self.theme.get(name, "?")
        return f"{name} {hex_val}"

    def _collect_transforms(self, color_el: ET.Element) -> list[list]:
        """Return ordered list of [tag, value] for each child transform."""
        out = []
        for child in color_el:
            local = child.tag.split("}", 1)[-1]
            if local in _TRANSFORM_HANDLERS or local == "alpha":
                out.append([local, int(child.get("val", "0"))])
        return out

    # -- Internal: resolution -----------------------------------------------

    def _resolve_color_element(
        self,
        color_el: ET.Element,
        scheme_override: tuple[float, float, float] | None,
        phclr_label: str | None = None,
    ) -> dict[str, Any]:
        """Apply the transform pipeline to a single color element."""
        # Determine starting color
        if scheme_override is not None and color_el.tag == f"{A}schemeClr" \
                and color_el.get("val") == "phClr":
            rgb = scheme_override
            input_label = phclr_label or f"phClr {_hex_from_rgb(rgb)}"
        else:
            rgb = self._initial_rgb(color_el)
            input_label = self._scheme_input_label(color_el)

        steps = [{
            "step": input_label,
            "rgb": list(rgb),
            "hex": _hex_from_rgb(rgb),
        }]
        alpha: float | None = None

        # Apply transforms in document order
        for child in color_el:
            local = child.tag.split("}", 1)[-1]
            val = int(child.get("val", "0"))

            if local == "alpha":
                alpha = val / 100000.0
                continue

            handler = _TRANSFORM_HANDLERS.get(local)
            if handler is None:
                continue  # unknown transform; skip silently for now

            rgb = handler(rgb, val)
            steps.append({
                "step": f"{local} {val}",
                "rgb": list(rgb),
                "hex": _hex_from_rgb(rgb),
            })

        final_hex = _hex_from_rgb(rgb)
        final_rgb_int = [max(0, min(255, round(c))) for c in rgb]

        # Build audit chain by walking the XML in document order, interleaving
        # intermediate hexes after each color-changing transform.
        # Pattern: input_label -> tform1 -> hex1 -> tform2 -> hex2 -> ... [-> alpha N -> rgba(...)]
        audit_parts = [input_label]
        step_idx = 1  # steps[0] is the input; transforms start at steps[1]
        for child in color_el:
            local = child.tag.split("}", 1)[-1]
            val = int(child.get("val", "0"))
            if local == "alpha":
                audit_parts.append(f"alpha {val}")
            elif local in _TRANSFORM_HANDLERS:
                audit_parts.append(f"{local} {val}")
                audit_parts.append(steps[step_idx]["hex"])
                step_idx += 1

        result: dict[str, Any] = {
            "input_hex": _hex_from_rgb(self._initial_rgb(color_el))
            if scheme_override is None else _hex_from_rgb(scheme_override),
            "transforms": self._collect_transforms(color_el),
            "final_hex": final_hex,
            "steps": steps,
            "final_rgb_int": final_rgb_int,
        }

        if alpha is not None:
            result["final_alpha"] = alpha
            result["final_rgba"] = (
                f"rgba({final_rgb_int[0]},{final_rgb_int[1]},"
                f"{final_rgb_int[2]},{alpha})"
            )
            audit_parts.append(result["final_rgba"])

        result["audit_chain"] = " -> ".join(audit_parts)

        return result

    @staticmethod
    def _final_rgb_float(result: dict[str, Any]) -> tuple[float, float, float]:
        """Recover the float RGB from a result's last step (preserves precision)."""
        last = result["steps"][-1]["rgb"]
        return (float(last[0]), float(last[1]), float(last[2]))


# ---------------------------------------------------------------------------
# Theme parsing
# ---------------------------------------------------------------------------

def parse_theme_xml(root: ET.Element) -> dict[str, str]:
    """Extract the color scheme dict from a parsed theme.xml root element.

    Returns a dict mapping scheme color names (accent1, dk1, lt1, etc.) to
    uppercase hex strings (e.g. "#156082"). Handles both srgbClr and sysClr
    children — sysClr resolves via its lastClr attribute.

    Locked by phase_1c/fixtures/theme_demert_default_office.xml.
    """
    scheme = root.find(f".//{A}clrScheme")
    if scheme is None:
        raise ValueError("clrScheme not found in theme XML")

    out: dict[str, str] = {}
    for child in scheme:
        name = child.tag.split("}", 1)[-1]
        srgb = child.find(f"{A}srgbClr")
        sysclr = child.find(f"{A}sysClr")
        if srgb is not None:
            out[name] = f"#{srgb.get('val', '000000').upper()}"
        elif sysclr is not None:
            last = sysclr.get("lastClr", "000000")
            out[name] = f"#{last.upper()}"
    return out


def theme_from_pptx(pptx_path: str) -> dict[str, str]:
    """Extract the first theme's color scheme from a .pptx file.

    Unzips the .pptx, locates theme1.xml (alphabetically first if multiple
    themes exist), and delegates parsing to parse_theme_xml().

    NOTE: Multi-theme decks where theme1 differs from later themes are not
    yet covered by fixtures. See NOTES.md.
    """
    with zipfile.ZipFile(pptx_path) as z:
        theme_names = [n for n in z.namelist()
                       if n.startswith("ppt/theme/theme") and n.endswith(".xml")]
        if not theme_names:
            raise FileNotFoundError("No theme XML found in pptx")
        theme_names.sort()
        with z.open(theme_names[0]) as f:
            tree = ET.parse(f)

    return parse_theme_xml(tree.getroot())
