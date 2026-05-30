"""Desktop layout helpers — absolute positioning with percentage units.

The desktop canvas is constrained to the deck's design aspect ratio:
    width  = min(100vw, (w_pt / h_pt × 100) vh)
    height = min((h_pt / w_pt × 100) vw, 100vh)
plus `container-type: inline-size` so cqw units scale with the canvas
(used for font-size, gap, etc.).

Shapes are positioned with percentage-of-canvas left/top/width/height,
which keeps them locked to their pt coordinates regardless of viewport.
"""
from __future__ import annotations

from .css import pt_to_pct_x, pt_to_pct_y


def canvas_aspect_css(slide_w_pt: float, slide_h_pt: float) -> tuple[str, str]:
    """Return (width, height) CSS values clamping the canvas to the deck aspect.

    A 1280×720 deck (16:9) yields:
        width:  min(100vw, 177.78vh)
        height: min(56.25vw, 100vh)
    """
    w_to_h = slide_w_pt / slide_h_pt * 100  # vh equivalent of 100 vw at deck aspect
    h_to_w = slide_h_pt / slide_w_pt * 100  # vw equivalent of 100 vh at deck aspect
    return (f"min(100vw, {w_to_h:.2f}vh)", f"min({h_to_w:.2f}vw, 100vh)")


def positioned_style(
    x_pt: float, y_pt: float, w_pt: float, h_pt: float,
    slide_w_pt: float, slide_h_pt: float,
) -> str:
    """CSS declarations for an absolute-positioned shape sized by % of canvas."""
    return (
        f"position: absolute; "
        f"left: {pt_to_pct_x(x_pt, slide_w_pt)}; "
        f"top: {pt_to_pct_y(y_pt, slide_h_pt)}; "
        f"width: {pt_to_pct_x(w_pt, slide_w_pt)}; "
        f"height: {pt_to_pct_y(h_pt, slide_h_pt)};"
    )
