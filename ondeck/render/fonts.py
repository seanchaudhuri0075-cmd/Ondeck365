"""Font @font-face block builder — inlines font binaries as base64.

Why inline instead of <link href="https://fonts.googleapis.com/...">: when
HTML is opened over file:// (AirDrop to iPhone, Files-app preview, Quick
Look, double-click on the desktop), iOS Safari doesn't reliably execute
the Google Fonts CSS request. With `display: swap`, the page hands off to
the system fallback (SF Pro on iOS) the moment the font hasn't arrived,
and never swaps back. Inlining the font removes the network dependency
entirely — the font travels with the file. This also matters for a
generic/unknown deck specifically: the renderer's font-family resolution
tries the deck's own declared typeface first, but for a machine that
doesn't have it installed (most machines, for most decks — very few
people have "real" Helvetica or licensed corporate fonts installed), the
bundled fallback below is what actually determines whether text renders
at anywhere close to the right width. An unbundled fallback (generic
"sans-serif") is a guess; these are metric-compatible, licensed-for-
redistribution substitutes chosen deliberately.

Bundled families:
  - Barlow Condensed (woff2, 4 weights) — matched-metric substitute for
    Univers Condensed / DIN-style condensed corporate sans (see
    font_calibration.MATCHED_METRIC_SUBS and LEARNINGS.md rule 10/19).
  - Liberation Sans (woff, 2 weights) — SIL Open Font License, metric-
    compatible with Arial (and close to Helvetica, the single most common
    "generic corporate sans" typeface declared in real decks). woff (v1,
    zlib) rather than woff2 (brotli) here only because of a build-
    environment constraint (no brotli library available at conversion
    time) — swap in woff2 versions of the same files later without any
    other code changes; browsers happily take multiple `src` entries and
    pick the first supported format.

Phase 1B note (inherited from the Barlow Condensed bundling): inlining as
base64 on every slide duplicates the payload deck-wide (~78KB/slide for
Barlow Condensed alone, more with Liberation Sans added) — acceptable for
the current regression-testing phase. A production publish path should
switch to a sibling font file with proper Cache-Control so it loads once
per origin instead of once per slide.

Latin subset only for Barlow Condensed (see its own unicode-range below).
Liberation Sans ships its own default cmap (no subsetting applied here).
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"

# unicode-range from Google Fonts' latin subset @font-face block (v13).
# Trimming this would shrink the woff2 (or break missing glyphs); the
# binaries are already subsetted to this range, so just declare it
# verbatim so the browser can apply per-codepoint loading.
_BARLOW_UNICODE_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, "
    "U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, "
    "U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)

# (family, filename, weight, format, mime, unicode-range-or-None)
_BUNDLED_FONTS = (
    ("Barlow Condensed", "BarlowCondensed-300.woff2", 300, "woff2", "font/woff2", _BARLOW_UNICODE_RANGE),
    ("Barlow Condensed", "BarlowCondensed-400.woff2", 400, "woff2", "font/woff2", _BARLOW_UNICODE_RANGE),
    ("Barlow Condensed", "BarlowCondensed-500.woff2", 500, "woff2", "font/woff2", _BARLOW_UNICODE_RANGE),
    ("Barlow Condensed", "BarlowCondensed-700.woff2", 700, "woff2", "font/woff2", _BARLOW_UNICODE_RANGE),
    ("Liberation Sans", "LiberationSans-Regular.woff", 400, "woff", "font/woff", None),
    ("Liberation Sans", "LiberationSans-Bold.woff", 700, "woff", "font/woff", None),
    # Big Shoulders: SIL OFL, industrial/wayfinding-signage heritage —
    # closest free match found for this deck's DIN Condensed acrostic
    # treatment specifically (confirmed directly against a reference
    # screenshot: matches DIN's flat-topped "A", which Barlow Condensed's
    # rounder, pointed-apex "A" does not). Used narrowly for that one
    # design element, not as a general DIN substitute — Barlow Condensed
    # remains the matched-metric substitute everywhere else.
    ("Big Shoulders", "BigShoulders-Bold.ttf", 700, "ttf", "font/ttf", None),
)

# Opt-in families, requested by name via font_face_css(families=...).
# These are NOT in the default bundle: font_face_css() with no arguments
# must keep emitting exactly the _BUNDLED_FONTS block above, because every
# existing template inlines its output and the P&G slides are baselined
# byte-for-byte (NOTES.md). A new deck's families ride here instead.
#
# (family, filename, weight, format, mime, unicode-range, font-stretch)
_OPTIONAL_FONTS = {
    # Archivo variable (wght 100-900, wdth 62-125), SIL OFL.
    # Matched-metric substitute for Franklin Gothic Book at wdth=94 —
    # measured, not assumed. Every text box in the Olay deck carries
    # <a:spAutoFit/>, so PowerPoint stored the exact height each string
    # wrapped to in the real font; solving that gives the true line count
    # per box. Archivo at wdth=94 reproduces all 20 boxes exactly (valid
    # window 93.5-95.0). Libre Franklin — the obvious lineage match, being
    # a Franklin Gothic revival — is 8.7% too wide and fails the same test,
    # which is rule 10 in miniature: the fit belongs to the font pair, not
    # to the name. Also carries the Aptos fallback at wdth=100 for the
    # deck's inherited runs, hence keeping the wdth axis rather than
    # shipping a static instance.
    "Archivo": (
        ("Archivo", "Archivo-var.woff2", "100 900", "woff2-variations", "font/woff2", None, "62% 125%"),
    ),
    # Poppins SemiBold, SIL OFL. Substitute for Boston SemiBold (Latinotype
    # geometric sans, "slightly rounded-edged ... inspired by Trenda").
    # UNVERIFIED metrically: Boston appears on only 52 characters across
    # three short strings, and every candidate fits those boxes with 20-30%
    # width to spare, so the autofit oracle cannot discriminate. Chosen on
    # design class (geometric, generous x-height 0.554) — swap freely if
    # the licensed original turns up.
    # HenHouse (deck 8). Montserrat instanced at wght=800, SIL OFL, subset to
    # Latin + smart punctuation (9.7 KB). Substitute for Gotham Black, chosen
    # on measurement rather than lineage: the deck's one Gotham box is
    # <a:spAutoFit/> at 60pt with 228.8pt of authored inner width, holding
    # "MAKES" on a single line. Montserrat wght=900 needs 231.3pt and would
    # have wrapped; wght=800 needs 228.7pt. Static instance rather than the
    # variable font because only this one weight is ever set.
    "Montserrat": (
        ("Montserrat", "Montserrat-800.woff2", 800, "woff2", "font/woff2", None, None),
    ),
    "Poppins": (
        ("Poppins", "Poppins-600.woff2", 600, "woff2", "font/woff2", None, None),
    ),
    # Old Spice (deck 7). Reuses the binaries already bundled by default for
    # P&G rather than shipping a second copy — exposed here as an opt-in family
    # so a deck can request Barlow Condensed WITHOUT pulling in the whole
    # default bundle (Liberation Sans, Big Shoulders) it does not use.
    # Substitute for DIN Pro Condensed; see font_calibration.MATCHED_METRIC_SUBS
    # for why that pairing is provisional.
    "Barlow Condensed": (
        ("Barlow Condensed", "BarlowCondensed-400.woff2", 400, "woff2", "font/woff2",
         _BARLOW_UNICODE_RANGE, None),
        ("Barlow Condensed", "BarlowCondensed-700.woff2", 700, "woff2", "font/woff2",
         _BARLOW_UNICODE_RANGE, None),
    ),
}

# Bundled-family name each typeface-resolution fallback should try, keyed
# by the same lowercased-typeface-keyword matching used elsewhere in the
# renderer. Deliberately small and explicit rather than a broad heuristic:
# add an entry here only once a real deck needs it, backed by a bundled
# font, not as a speculative default.
BUNDLED_FALLBACKS = {
    "helvetica": "Liberation Sans",
    "helvetica neue": "Liberation Sans",
    "arial": "Liberation Sans",
    "univers": "Barlow Condensed",
    "univers condensed": "Barlow Condensed",
    "univers condensed light": "Barlow Condensed",
    "din": "Barlow Condensed",
    "din condensed": "Barlow Condensed",
    # Olay — see _OPTIONAL_FONTS. Only reachable when a caller asks for
    # those families, so this stays inert for the default bundle.
    "franklin gothic book": "Archivo",
    "aptos": "Archivo",
    "boston semibold": "Poppins",
}


@lru_cache(maxsize=8)
def font_face_css(families: tuple[str, ...] | None = None) -> str:
    """One @font-face declaration per (family, weight), binary inlined as a data URL.

    With no argument, emits exactly the default `_BUNDLED_FONTS` block —
    unchanged output for every existing template and baseline. Pass
    `families` to emit an opt-in set from `_OPTIONAL_FONTS` instead, for a
    deck that needs its own typefaces without paying for (or perturbing)
    the default bundle.

    Cached because the base64 encoding is non-trivial and the result
    never changes across renders in the same process.
    """
    if families is None:
        entries = [(*e, None) for e in _BUNDLED_FONTS]
    else:
        entries = []
        for name in families:
            if name not in _OPTIONAL_FONTS:
                raise KeyError(
                    f"unknown optional font family {name!r}; "
                    f"known: {sorted(_OPTIONAL_FONTS)}"
                )
            entries.extend(_OPTIONAL_FONTS[name])

    rules = []
    for family, filename, weight, fmt, mime, unicode_range, stretch in entries:
        path = FONT_DIR / filename
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        range_line = f"\n  unicode-range: {unicode_range};" if unicode_range else ""
        stretch_line = f"\n  font-stretch: {stretch};" if stretch else ""
        rules.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {weight};"
            f"{stretch_line}\n"
            f"  font-display: swap;\n"
            f"  src: url(data:{mime};base64,{b64}) format('{fmt}');"
            f"{range_line}\n"
            f"}}"
        )
    return "\n".join(rules)
