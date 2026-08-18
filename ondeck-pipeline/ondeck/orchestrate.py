"""End-to-end orchestrator: a .pptx in, an HTML deck + staged assets out.

This is GLUE CODE. It wires the existing pipeline modules together and owns
NONE of their logic — it only calls them with their real signatures and
arranges the outputs on disk.

Architecture discovered while reading the modules (the call shapes below
follow reality, not assumption):

  * `Pptx.slide_size_pt` is a PROPERTY (no parens); `Pptx.slides()` is a
    method returning an iterator of python-pptx Slide objects.
  * `extract_theme(pptx)` reads ppt/theme/theme1.xml by default.
  * Each `render_*` template function ALREADY returns a complete, self-
    contained `<!DOCTYPE html>` document — it calls `render_page()` itself
    with internal root_vars / body_html / slide_css the orchestrator can't
    see. So we do NOT call `render_page()` again here (that would double-
    wrap and we lack the inputs). Instead we write one self-contained HTML
    file per slide, which is exactly the single-file / AirDrop delivery
    model the renderers were built for (see _shared.inline_data_url). An
    index.html ties them together.
  * `render_media_showcase` returns a TUPLE `(html, aux_files)` where
    aux_files is a list of (relative_filename, blob) to stage next to the
    HTML (e.g. the .mp4 for a video slide). The other five renderers return
    a plain `str`.
  * Template signatures differ: `render_cover` takes neither
    deck_brand_color nor media_dir; `card_grid` / `media_showcase` take
    media_dir; the rest take deck_brand_color only. The router below passes
    each exactly what it accepts.

Manifest handling: a manifest is OPTIONAL. The SHELF deck under test has
none. Without one we classify every slide with a generic fallback template
(`two_column` — a plain title + text-column layout that degrades
gracefully on arbitrary shape structure and, unlike card_grid /
media_showcase, never needs a media_dir). Classification will be wrong
without a manifest; that is expected — this stage validates the plumbing,
not the fidelity.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from .layout.detect import Manifest, SlideClass
from .parse.pptx import Pptx
from .parse.theme import extract_theme
from .render.templates.card_grid import render_card_grid
from .render.templates.cover import render_cover
from .render.templates.freeform import render_freeform
from .render.templates.media_showcase import render_media_showcase
from .render.templates.section_divider import render_section_divider
from .render.templates.title_stats import render_title_stats
from .render.templates.two_column import render_two_column

# Generic default when no manifest tells us otherwise. freeform positions
# every shape at its real PPTX coordinates, so it degrades gracefully on
# an arbitrary/unknown deck instead of forcing a hand-tuned layout (like
# two_column's fixed two-column boxes) onto a structurally different slide.
FALLBACK_TEMPLATE = "freeform"

# Default canvas/brand color when no manifest supplies deck_brand_color.
# Non-cover templates fall back to this for any uncovered canvas area.
DEFAULT_BRAND_COLOR = "#000000"


def _render_one(
    template: str,
    *,
    slide,
    theme,
    slide_index: int,
    slide_class: SlideClass,
    deck_name: str,
    slide_w_pt: float,
    slide_h_pt: float,
    deck_brand_color: str,
    media_dir,
    default_tab_pt: float = 72.0,
    section_headers: dict | None = None,
) -> tuple[str, list]:
    """Route one slide to its template renderer, normalizing the return to
    (html, aux_files). Each renderer is called with exactly the arguments its
    real signature accepts.
    """
    if template == "cover":
        # render_cover takes no deck_brand_color and no media_dir.
        return render_cover(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt,
        ), []
    if template == "title_stats":
        return render_title_stats(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color,
        ), []
    if template == "section_divider":
        return render_section_divider(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color,
        ), []
    if template == "two_column":
        return render_two_column(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color,
        ), []
    if template == "freeform":
        return render_freeform(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color, media_dir,
            default_tab_pt, section_headers,
        ), []
    if template == "card_grid":
        return render_card_grid(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color, media_dir,
        ), []
    if template == "media_showcase":
        # This one returns (html, aux_files) already.
        html, aux_files = render_media_showcase(
            slide, theme, slide_index, slide_class, deck_name,
            slide_w_pt, slide_h_pt, deck_brand_color, media_dir,
        )
        return html, list(aux_files)
    raise ValueError(f"unknown template {template!r}")


def convert(pptx_path: str, out_dir: str, manifest_path: str | None = None) -> None:
    """Convert a .pptx into an HTML deck + staged assets in out_dir.

    A manifest is optional. With one, each slide is classified via
    Manifest.classify(i). Without one, every slide falls back to
    FALLBACK_TEMPLATE. Per-slide render failures are caught so one bad
    slide can't abort the whole deck — the slide gets a placeholder page and
    the run continues (plumbing validation: end-to-end, no crash).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pptx = Pptx(pptx_path)
    slide_w_pt, slide_h_pt = pptx.slide_size_pt   # property, not a call
    theme = extract_theme(pptx)

    manifest: Manifest | None = None
    deck_brand_color = DEFAULT_BRAND_COLOR
    if manifest_path is not None:
        manifest = Manifest.load(manifest_path)
        if manifest.deck_brand_color:
            deck_brand_color = manifest.deck_brand_color
        deck_name = manifest.deck_name or Path(pptx_path).stem
    else:
        deck_name = Path(pptx_path).stem

    media_dir = None  # no transform stage has run; inline-only path

    slides = list(pptx.slides())
    print(f"Deck: {deck_name}")
    print(f"Source: {pptx_path}")
    print(f"Slides: {len(slides)}  canvas: {slide_w_pt:g}x{slide_h_pt:g}pt")
    print(f"Manifest: {manifest_path or '(none — fallback to %s)' % FALLBACK_TEMPLATE}")
    print(f"Out: {out}")
    print("-" * 60)

    page_files: list[tuple[int, str, str]] = []  # (index, template, filename)
    # Shared across the whole render loop: lets a section's "closer" photo
    # slide (no caption of its own in the source) borrow the header text
    # its section's "hero" slide already showed, instead of rendering as a
    # bare photo. Works because slides render in document order and every
    # section's hero slide precedes its closer in this deck's structure —
    # see freeform.py's _build_body for the read/write logic itself.
    section_headers: dict = {}

    for i, slide in enumerate(slides, start=1):
        if manifest is not None:
            try:
                slide_class = manifest.classify(i)
            except KeyError:
                slide_class = SlideClass(slide_index=i, template=FALLBACK_TEMPLATE)
            template = slide_class.template
        else:
            template = FALLBACK_TEMPLATE
            slide_class = SlideClass(slide_index=i, template=template)

        page_name = f"slide_{i:02d}.html"
        try:
            html, aux_files = _render_one(
                template,
                slide=slide,
                theme=theme,
                slide_index=i,
                slide_class=slide_class,
                deck_name=deck_name,
                slide_w_pt=slide_w_pt,
                slide_h_pt=slide_h_pt,
                deck_brand_color=deck_brand_color,
                media_dir=media_dir,
                default_tab_pt=pptx.default_tab_pt,
                section_headers=section_headers,
            )
            (out / page_name).write_text(html, encoding="utf-8")
            for rel_name, blob in aux_files:
                asset_path = out / rel_name
                asset_path.parent.mkdir(parents=True, exist_ok=True)
                asset_path.write_bytes(blob)
            extra = f"  +{len(aux_files)} asset(s)" if aux_files else ""
            print(f"  slide {i:2d}  [{template:<15}] -> {page_name}{extra}")
            page_files.append((i, template, page_name))
        except Exception as exc:  # noqa: BLE001 - keep the deck building
            tb = traceback.format_exc()
            placeholder = (
                "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
                f"<title>{deck_name} — Slide {i} (render error)</title></head>"
                "<body style='font-family:monospace;background:#111;color:#eee;"
                "padding:2rem'>"
                f"<h1>Slide {i} failed to render ({template})</h1>"
                f"<pre style='white-space:pre-wrap'>{_escape(tb)}</pre>"
                "</body></html>"
            )
            (out / page_name).write_text(placeholder, encoding="utf-8")
            print(f"  slide {i:2d}  [{template:<15}] -> {page_name}  "
                  f"ERROR: {type(exc).__name__}: {exc}")
            page_files.append((i, template, page_name))

    index_path = out / "index.html"
    index_path.write_text(_build_index(deck_name, page_files), encoding="utf-8")
    print("-" * 60)
    print(f"Wrote {len(page_files)} slide page(s) + index.html to {out}")


def _build_index(deck_name: str, page_files: list[tuple[int, str, str]]) -> str:
    """Assemble a simple index page linking every per-slide HTML file."""
    rows = "\n".join(
        f"  <li><a href='{fn}'>Slide {i:02d}</a> "
        f"<span style='opacity:.5'>[{_escape(tpl)}]</span></li>"
        for i, tpl, fn in page_files
    )
    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>{_escape(deck_name)}</title>\n"
        "<style>body{font-family:system-ui,sans-serif;background:#0b0b0b;"
        "color:#eee;padding:2rem;max-width:680px;margin:auto}"
        "a{color:#4cc2ff;text-decoration:none}a:hover{text-decoration:underline}"
        "li{margin:.35rem 0;list-style:none}ul{padding:0}</style>\n</head>\n"
        f"<body>\n<h1>{_escape(deck_name)}</h1>\n<ul>\n{rows}\n</ul>\n"
        "</body>\n</html>\n"
    )


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a .pptx into an HTML deck + staged assets.",
    )
    parser.add_argument("--pptx", required=True, help="path to the source .pptx")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--manifest", default=None,
        help="optional manifest JSON (omit to use the fallback template)",
    )
    args = parser.parse_args(argv)
    convert(args.pptx, args.out, args.manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
