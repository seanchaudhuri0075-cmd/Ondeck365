"""Font @font-face block builder — inlines woff2 binaries as base64.

Why inline instead of <link href="https://fonts.googleapis.com/...">: when
HTML is opened over file:// (AirDrop to iPhone, Files-app preview, Quick
Look, double-click on the desktop), iOS Safari doesn't reliably execute
the Google Fonts CSS request. With `display: swap`, the page hands off to
the system fallback (SF Pro on iOS) the moment the font hasn't arrived,
and never swaps back. Inlining the woff2 removes the network dependency
entirely — the font travels with the file.

The bundle's prior conversion uses Google Fonts CSS the same way; under
http(s) hosting it works, but for AirDrop/local-preview sharing it
silently degrades.

Phase 1B: inline as base64 in every slide. ~78KB added per slide (4
weights × ~19.6KB base64 each). At 23 slides that's ~1.8MB duplicated
deck-wide — acceptable for the regression-testing phase. Phase 2 publish
will switch to a sibling `.woff2` file with proper Cache-Control so the
font is loaded once per origin.

Latin subset only — the deck content is English with no accented
characters in the 23 slides surveyed. If a future deck needs latin-ext
or vietnamese, add those subsets here.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"
WEIGHTS = (300, 400, 500, 700)
FONT_FAMILY = "Barlow Condensed"

# unicode-range from Google Fonts' latin subset @font-face block (v13).
# Trimming this would shrink the woff2 (or break missing glyphs); the
# binaries are already subsetted to this range, so just declare it
# verbatim so the browser can apply per-codepoint loading.
LATIN_UNICODE_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, "
    "U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, "
    "U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)


@lru_cache(maxsize=1)
def font_face_css() -> str:
    """One @font-face declaration per weight, woff2 inlined as data URL.

    Cached because the base64 encoding is non-trivial and the result
    never changes across renders in the same process.
    """
    rules = []
    for weight in WEIGHTS:
        path = FONT_DIR / f"BarlowCondensed-{weight}.woff2"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            f"@font-face {{\n"
            f"  font-family: '{FONT_FAMILY}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            f"  font-display: swap;\n"
            f"  src: url(data:font/woff2;base64,{b64}) format('woff2');\n"
            f"  unicode-range: {LATIN_UNICODE_RANGE};\n"
            f"}}"
        )
    return "\n".join(rules)
