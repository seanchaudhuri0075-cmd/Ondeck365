"""Page-level HTML scaffolding — head, body wrappers, font loading, CSS reset.

One function: render_page(). Templates assemble their per-template CSS
and body markup, then call render_page() to wrap with the shared shell.
"""
from __future__ import annotations

from .fonts import font_face_css


CSS_RESET = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  width: 100%;
  background: #000;
  color: var(--headline);
  font-family: var(--font-cond);
  -webkit-font-smoothing: antialiased;
}
img, video { display: block; max-width: 100%; }"""


def render_page(
    *,
    title: str,
    root_vars: dict,
    body_html: str,
    slide_css: str,
) -> str:
    """Assemble the full HTML document for one slide.

    Args:
        title:      browser tab title (HTML-escape outside if needed)
        root_vars:  CSS custom properties on :root (e.g. {'bg-cyan': '#00B0F0'})
        body_html:  the <body> contents (deck-desktop + deck-mobile sections)
        slide_css:  per-slide CSS (positioning, template-specific styles)
    """
    var_block = "\n  ".join(f"--{k}: {v};" for k, v in root_vars.items())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<style>
{font_face_css()}
:root {{
  {var_block}
}}
{CSS_RESET}
{slide_css}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""
