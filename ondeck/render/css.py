"""CSS value helpers — pt-to-percentage/cqw conversion + color formatting.

Pure functions, no I/O. Used by templates and layout renderers to translate
parsed values (points, hex colors, alpha) into CSS strings.

Position percentages use 4 decimal places to match the bundle's precision
(it uses 4-5 places). cqw values use 3 places.
"""
from __future__ import annotations

from typing import Optional


def pt_to_pct_x(pt: float, slide_w_pt: float) -> str:
    """Horizontal position/size as percentage of slide width."""
    return f"{pt / slide_w_pt * 100:.4f}%"


def pt_to_pct_y(pt: float, slide_h_pt: float) -> str:
    """Vertical position/size as percentage of slide height."""
    return f"{pt / slide_h_pt * 100:.4f}%"


def pt_to_cqw(pt: float, slide_w_pt: float) -> str:
    """Value in cqw (1cqw = 1% of canvas inline-size).

    At design width (e.g. 1280pt), 1cqw = 12.8pt. Used for font-sizes
    and other sizes that should scale linearly with the canvas.
    """
    return f"{pt / slide_w_pt * 100:.3f}cqw"


def color_with_alpha(hex_color: str, alpha: Optional[float]) -> str:
    """Format as `#RRGGBB` when opaque, `rgba(...)` when alpha < 1."""
    if alpha is None or alpha >= 1.0:
        return f"#{hex_color.upper()}"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"
