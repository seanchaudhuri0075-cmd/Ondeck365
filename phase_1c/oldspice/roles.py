"""Old Spice (deck 7) operator manifest — archetypes and editor hooks.

Manifest-driven, per LEARNINGS "Open gaps": auto-detection of slide templates
stays deferred. These tags come from the measured structure (three identical
9-slide destination series), not from guessing at render time.
"""

DECK_TITLE = "Old Spice — Destination Theme Product Series Concepts"

# 34 slides, six archetypes. 24 of them are one pattern.
COVER        = {1, 34}          # SVG wordmark + title on brand red
BRIEF        = {2}              # title + prose + product image
VARIANT_TABLE= {3}              # 4x5 table, the deck's only tabular slide
DIVIDER      = {4, 14, 24}      # destination name only
KEY_VISUAL   = {5, 15, 25}      # full-canvas image + label + concept prose
# everything else is a product plate: one image + one short label

BRAND_RED = "#AF000F"

# The authored shape boxes stretch these photos (up to 1.56x on s7) because
# <a:stretch><a:fillRect/> fills the box regardless of the image's own aspect.
# DESKTOP keeps that stretch — it is what PowerPoint renders and the canvas is
# signed off. MOBILE does not: reviewed on a phone, the distortion at
# full-screen scale is worse than the desktop/mobile divergence, and a product
# shot blown up to fill the screen is the wrong place to reproduce a 1.56x
# horizontal stretch. Fill by scaling, never by distorting (rule 29).
KEEP_AUTHORED_STRETCH = False

# Slides carrying real prose. Everything else is a one-line label, so it gets a
# headline hook and no body hook — editing it is renaming a label, which is the
# honest affordance for 28 of 34 slides.
BODY_SLIDES = {2, 3, 5, 15, 25}

# Same two suppression rules as Olay, both confirmed against this deck:
#   review stickers  -> 0 matches (no shape here carries <p:style> at all)
#   occluded shapes  -> 2 slides, 542 chars (Maldives copy buried under the
#                       Sao Paulo and Sedona key visuals)
SUPPRESS_REVIEW_STICKERS = True
SUPPRESS_OCCLUDED_SHAPES = True


def archetype(n: int) -> str:
    if n in COVER: return "cover"
    if n in BRIEF: return "brief"
    if n in VARIANT_TABLE: return "table"
    if n in DIVIDER: return "divider"
    if n in KEY_VISUAL: return "keyvisual"
    return "plate"


def text_role(n: int, is_first_text: bool) -> str:
    """Editor vocabulary: `.L > .t` for the headline, body classes for prose.

    Every slide has exactly one label or title, so the headline hook is
    universal; body hooks exist only on the five prose slides.
    """
    if is_first_text:
        return "title"
    if n in VARIANT_TABLE:
        return "ci"      # table cells
    if n in BODY_SLIDES:
        return "cbi"     # brief / concept prose
    return "sl"          # sub-line (slide 1's "CONCEPTS")
