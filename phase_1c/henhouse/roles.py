"""HenHouse Market (deck 8) operator manifest.

Manifest-driven per LEARNINGS "Open gaps": auto-detection of slide templates
stays deferred. These tags come from the measured structure of the file, not
from guessing at render time — see the diagnostic pass for the numbers behind
each set.
"""

DECK_TITLE = "Hen House — A Creative Strategy for the Modern Meat Case"
DECK_CLIENT = "Hen House Market"
N_SLIDES = 52

# ---------------------------------------------------------------- archetypes
COVER = {1, 52}                       # title / thank-you
ARGUMENT = {2, 4}                     # title + prose column + statement column
ROUTE = {5, 32, 45}                   # creative route: eyebrow + headline + 3-up
PATH = {24}                           # PATH TO PURCHASE, 4-up process row
SOCIAL = {25}                         # densest: 7 blocks, 5 columns, display type
EXTENSION = {51}                      # paired lists (department <-> tagline)
VIDEO = {28, 29, 30, 44}              # paid-social video ads
# everything else is a plate: an image board, with or without a caption block

# ---------------------------------------------------------------- text
# Measured, not eyeballed: a slide is PROSE when its non-heading body runs to
# >=150 characters or >=3 paragraphs. 18 of 52 qualify; 17 more carry only a
# heading plus one sentence; 17 carry no text at all.
BODY_SLIDES = {2, 3, 4, 5, 11, 16, 18, 19, 20, 24, 25, 31, 32, 41, 45, 47, 48, 51}

# Slides whose text blocks sit side by side on the canvas — they overlap
# vertically but are horizontally disjoint, which is exactly what a 390px
# viewport cannot hold. These reflow into stacked bands INSIDE their one
# section; rule 22 forbids minting extra <section class="slide"> elements and
# rule 30 forbids removing any, so the section count stays 52 either way.
BROCHURE = {2, 3, 4, 5, 19, 20, 21, 24, 25, 31, 32, 45, 51}

# ---------------------------------------------------------------- suppression
# Both signatures were run against this deck and both come back empty, but for
# different reasons, and the difference is worth recording rather than
# flattening into "clean":
#   review stickers  -> NOT APPLICABLE. 25 shapes carry <p:style> and 72 carry
#                       text, but ZERO carry both, so the five-property
#                       signature has no surface to fire on. Same as deck 7.
#                       This is not a discriminated negative (cf. rule 31's
#                       "probe that lied") — it is an empty domain.
#   occluded shapes  -> genuinely none. No slide has an opaque full-canvas
#                       shape with content buried beneath it.
SUPPRESS_REVIEW_STICKERS = True
SUPPRESS_OCCLUDED_SHAPES = True

# ---------------------------------------------------------------- fonts
# "Gotham Black" is the deck's only declared face (3 runs, slide 25). Every
# other run declares no <a:latin> and inherits the theme minor font, Aptos.
# Both are registered in ondeck/parse/font_calibration.py; see the notes there
# for why Montserrat wght=800 rather than 900.
FONT_FAMILIES = ("Archivo", "Montserrat")
BODY_STACK = "'Archivo','Helvetica Neue',Helvetica,Arial,sans-serif"
DISPLAY_STACK = "'Montserrat','Archivo','Helvetica Neue',Helvetica,sans-serif"


# ---------------------------------------------------------------- mobile type
# Desktop sizes are cqw against the 960pt canvas (rule 15). On mobile the canvas
# becomes `container-type: inline-size` at viewport width, so the SAME cqw value
# resolves against ~390px instead of ~1600px and every size collapses to about a
# quarter — a 32pt headline lands at 13px. Mobile therefore needs its own ramp,
# as Olay and Old Spice do via their MOBILE_PT tables.
#
# Those two decks key the ramp by shape ROLE and set one size per shape. That
# model does not transfer: 20 of HenHouse's 72 text shapes carry more than one
# authored size, and the contrast is load-bearing (slide 2 sets a 32pt statement
# against 20pt prose inside one shape; the 12/14pt pairs are caption labels
# against caption bodies). Keying by role would flatten all 20. This ramp is
# therefore keyed by the RUN's own authored size and emitted per span.
#
# The deck's size vocabulary is closed at nine values. Each maps through
# (pt/14) ** 0.62 rem, frozen below: 14pt is the dominant body size (47 of 72
# shapes) and anchors 1rem, and the exponent compresses the 4.7x authored range
# to 2.9x so a 66pt display word stays inside a 390px viewport instead of
# scaling to 75px. Sizes outside the table fall through to the same formula.
MOBILE_REM = {
    12.0: "0.91rem",
    14.0: "1.00rem",
    16.0: "1.09rem",
    18.0: "1.17rem",
    20.0: "1.25rem",
    24.0: "1.40rem",
    32.0: "1.67rem",
    60.0: "2.47rem",
    66.0: "2.62rem",
}
MOBILE_REM_BASE_PT = 14.0
MOBILE_REM_EXP = 0.62


def mobile_rem(size_pt) -> str:
    """Mobile font-size for a run of `size_pt`, as the `--ms` custom property."""
    pt = float(size_pt or 18.0)
    hit = MOBILE_REM.get(pt)
    if hit:
        return hit
    return f"{(pt / MOBILE_REM_BASE_PT) ** MOBILE_REM_EXP:.2f}rem"


def archetype(n: int) -> str:
    if n in COVER: return "cover"
    if n in ARGUMENT: return "argument"
    if n in ROUTE: return "route"
    if n in PATH: return "path"
    if n in SOCIAL: return "social"
    if n in EXTENSION: return "extension"
    if n in VIDEO: return "video"
    return "plate"


def is_brochure(n: int) -> bool:
    return n in BROCHURE
