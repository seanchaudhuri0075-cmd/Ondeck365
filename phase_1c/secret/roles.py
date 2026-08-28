"""Secret "Beauty Creative Strategy" (deck 10) operator manifest.

Manifest-driven per LEARNINGS "Open gaps": template auto-detection stays
deferred. Every set below comes from the measured structure of the file — see
NOTES for the diagnostic numbers behind each.

WHAT IS DIFFERENT ABOUT THIS DECK, in one place:

* **It was exported from Google Slides, not authored in PowerPoint.** The tell
  is everywhere once seen: shape names like `Google Shape;152`, layouts named
  TITLE / SECTION_HEADER / BLANK / CUSTOM_11, and a theme pair whose schemes are
  "Simple Light" (slides) and "Default" (notes). First deck of this origin in
  the corpus, and the reason the layout names are worth reading at all — a
  Google Slides author picks a named layout far more consistently than a
  PowerPoint author picks a master placeholder.

* **It embeds its fonts.** Four faces, six parts. They are EVIDENCE ONLY and
  are never extracted, converted or served — LEARNINGS rule 38. The headers
  measured the width classes that fixed a wrong entry in MATCHED_METRIC_SUBS.

* **Its videos are already web-rate** (0.97-2.73 Mbps, 15.5 MB for 7 clips), so
  the asset stage STREAM-COPIES rather than re-encodes. Deck 9 was the opposite
  case at 24 Mbps. See `deckkit.assets.build_videos(copy=...)`.
"""

DECK_TITLE = "Secret — Beauty Creative Strategy"
DECK_CLIENT = "Secret (P&G)"
N_SLIDES = 31

# ---------------------------------------------------------------- slug
# Both authored names are preserved in CHAPTERS below and both render as
# authored (rule 14); CHAPTER_01_NAME only decides which one a slug uses.
SLUG = "secret"             # build dir + asset prefix: out/secret/
# SETTLED 2026-08-27 by ground truth, not by preference: the LibreOffice render
# of slide 4 shows PRODUCT SILOS set as the large display type on the layout3
# divider (73pt, from the layout's title placeholder), while VISUAL HOOKS
# appears only as an agenda line on slide 3. The divider is what a reader lands
# on when following a chapter link, so it names the chapter.
CHAPTER_01_NAME = "PRODUCT SILOS"

# The R2 publish prefix is a SEPARATE value typed into the Deck Editor's Deck
# Name field, and is deliberately not the same string as the build slug (the
# shipped decks pair out/henhouse with hh-creativestrategy, out/oldspice with
# oldspicepackaging). Not set yet — nothing is published from this session.
# It must not collide with: olay, olay-v2, oldspicepackaging,
# hh-creativestrategy, pgdigital, venus-hestia.
R2_PREFIX = None

# ---------------------------------------------------------------- archetypes
# Keyed by the AUTHORED LAYOUT NAME, read by deckkit.model.build_layout_index
# and mapped through deckkit.css.archetype_of. This is the first deck to route
# on layout rather than on shape geometry, and it is only safe here because the
# author named the layouts themselves. An unlisted layout returns PLATE_DEFAULT
# rather than a guess.
LAYOUT_ARCHETYPE = {
    "TITLE":                         "cover",      # s1 (KEY VISUALS), s31 (THANK YOU)
    "SECTION_HEADER":                "statement",  # s2 OBJECTIVE, s27 VIDEOS, s28-29 video walls
    "SECTION_TITLE_AND_DESCRIPTION": "divider",    # s4, s9, s14, s21, s30 — the chapters
    "BLANK":                         "plate",      # 19 image boards
    "CUSTOM":                        "agenda",     # s3, the numbered 01-04 index
}
PLATE_DEFAULT = "plate"

# The five chapter dividers, in order, with the number the source prints on
# each. s30 (EXECUTION) carries a divider layout but NO number and is absent
# from the agenda — it is a closing section, not a numbered chapter. Recorded
# rather than smoothed over.
CHAPTERS = [
    {"slide": 4,  "number": "01", "divider_title": "PRODUCT SILOS",
     "agenda_title": "VISUAL HOOKS"},
    {"slide": 9,  "number": "02", "divider_title": "GROUP SHOTS",
     "agenda_title": "GROUP SHOTS"},
    {"slide": 14, "number": "03", "divider_title": "INGREDIENT LED",
     "agenda_title": "INGREDIENT LED"},
    {"slide": 21, "number": "04", "divider_title": "COLOR+ TREATMENT",
     "agenda_title": "COLOR + TREATMENT"},
    {"slide": 30, "number": None, "divider_title": "EXECUTION",
     "agenda_title": None},
]

VIDEO_SLIDES = {28, 29}          # 3 + 4 clips; the only media-bearing slides

# ---------------------------------------------------------------- suppression
# Read these two together, because they are NOT the same kind of empty and the
# difference is the whole point of rule 31's "probe that lied".
#
#   review stickers -> a DISCRIMINATED NEGATIVE, not an empty domain. 87 shapes
#       carry BOTH <p:style> and text, so the five-property signature had a real
#       87-candidate domain to fire on, and matched ZERO. It discriminated on
#       properties 3 and 4: every authored run here declares a typeface AND a
#       size, which is exactly what rule 23 says separates authored copy from a
#       comment box where the author chose nothing. Contrast HenHouse and Old
#       Spice, where the domain was empty (no shape had both) and the negative
#       therefore proved nothing about the signature.
#   occluded shapes -> genuinely none. No slide carries an opaque full-canvas
#       shape with content buried under it.
#
# Sean confirmed this is a client deliverable, not a working file, so both stay
# on: they cost nothing here and a deck revision that introduces a sticker will
# be caught rather than shipped.
SUPPRESS_REVIEW_STICKERS = True
SUPPRESS_OCCLUDED_SHAPES = True

# ---------------------------------------------------------------- fonts
# Live faces, measured from the RUNS rather than from typeface= references
# anywhere (which include buFont/ea/cs entries and the theme's script-fallback
# table — 30-odd names that render nothing):
#
#   Univers            126 runs   8/9/12/14/16pt   body + all plate labels
#   Arial               11 runs   14/100pt         inherited default
#   Aura AT             10 runs   14/54/96pt       DISPLAY — every section title
#   Univers Condensed    4 runs   40pt             the 01-04 chapter numbers
#
# Darker Grotesque Medium is NOT here on purpose. It is the most-referenced name
# in the package (498 refs) and appears in ZERO runs: it is a layout/master
# default that nothing inherits, because the deck's inherited face resolves to
# Arial. It needs no binary. Checking references rather than runs would have
# had us fetch and bundle a font the deck never renders.
#
# All four resolve to binaries already in ondeck/render/fonts/ — no new asset.
FONT_FAMILIES = ("Bebas Neue", "Darker Grotesque", "Anton",
                 "PT Sans Narrow", "Roboto Condensed", "Liberation Sans")

BODY_STACK    = "'Roboto Condensed','Helvetica Neue',Helvetica,Arial,sans-serif"
DISPLAY_STACK = "'Anton','Roboto Condensed',Helvetica,Arial,sans-serif"
TITLE_STACK   = "'Bebas Neue','Roboto Condensed',Helvetica,Arial,sans-serif"
PROSE_STACK   = "'Darker Grotesque','Roboto Condensed',Helvetica,Arial,sans-serif"
NUMBER_STACK  = "'PT Sans Narrow','Roboto Condensed',Helvetica,Arial,sans-serif"

# ---------------------------------------------------------------------------
# TWO GROUPS. The distinction is the whole point and must not be flattened.
#
# GROUP 1 — NOT substitutions. The deck's own faces, shipping as themselves
# because both are SIL OFL. No matching was done and no judgement was made.
# They arrive through INHERITANCE (the runs declare no face): the master's
# `title` placeholder declares Bebas Neue Regular, its `body` placeholder
# declares Darker Grotesque Medium. 11 runs depend on this walk.
#
# GROUP 2 — substitutions for proprietary faces. ALL THREE ARE SHAPE-BASED
# JUDGEMENT CALLS MADE WHERE WIDTH DID NOT DISCRIMINATE. Do not read any of
# them as a measured winner; the measurement only ruled candidates OUT.
#
#   The deck's geometry yields a width BUDGET per authored string -- an UPPER
#   BOUND from the box, not a target. On the display titles SEVENTEEN faces fit
#   and the top six sat within 12-15% mean slack of each other. That is a tie,
#   and a tie is not a result. Sean chose against his own PowerPoint
#   screenshots, on weight and colour.
#
#   aura at -> Anton              +16.2% slack, 7th of 17 that fit. The tightest
#     was Asap Condensed (+11.7%), then Oswald (+12.3%), PT Sans Narrow
#     (+14.1%). Anton was chosen because Aura AT reads near-black in the source
#     and Anton is the only candidate in that weight range -- the better-
#     measuring faces are regular-weight text faces that would measure right
#     and look wrong.
#   univers condensed -> PT Sans Narrow   the ONLY face top-3 on both
#     constraints, landing exactly on the 0.900em two-digit budget (+0.0%).
#     This is the closest any of the three comes to a measured result, and it
#     is still only a tie-break, not a discrimination.
#   univers -> Roboto Condensed   WIDTH CANNOT CHOOSE HERE AT ALL. The long
#     strings budget 0.177-0.239 em/char, unachievable for mixed case, so they
#     wrap in PowerPoint and constrain nothing; the short labels clear
#     ~1.09 em/char trivially. Chosen purely on shape: x-height 0.528 (equal to
#     Archivo, the previous pick) with a tighter lc advance of 0.403, suiting
#     the 8-9pt plate labels that are 87 of the deck's 151 runs.
#
# Re-derive all three if a licensed original or a real metric source appears.
SUBS = {
    # group 1 — the deck's own faces
    "bebas neue":              {"stack": TITLE_STACK,   "weight": None},
    "bebas neue regular":      {"stack": TITLE_STACK,   "weight": None},
    "darker grotesque":        {"stack": PROSE_STACK,   "weight": 500},
    "darker grotesque medium": {"stack": PROSE_STACK,   "weight": 500},
    # group 2 — judgement-call substitutions
    "aura at":                 {"stack": DISPLAY_STACK, "weight": None},
    "univers condensed":       {"stack": NUMBER_STACK,  "weight": None},
    "univers":                 {"stack": BODY_STACK,    "weight": None},
    # web-safe, metric-compatible
    "arial":                   {"stack": "'Liberation Sans',Arial,Helvetica,sans-serif",
                                "weight": None},
}
FALLBACK_STACK = BODY_STACK

# PowerPoint's autofit constant. Per rule 34 it says nothing about the face --
# it is the value to SET line-height to, not evidence for a substitute.
#
# CORRECTED 2026-08-28 from 1.2135. That figure came from this deck's four
# <a:spAutoFit/> boxes, which are the SAME shape copied onto four slides:
# Univers Condensed 40pt, one line, no spcPct. One distinct datapoint, and
# rule 17's single-term recovery folded a per-BOX constant into the per-LINE
# factor. Fitting both terms across 25 autofit boxes in four decks, six sizes
# (12-40pt) and six faces gives
#
#     height = 0.07034pt + 1.211720 x (lines x size x spcPct) + insets
#
# to a max residual of 0.00051pt. The per-line factor is 1.21172 and it is
# independent of size AND face; the old spread of 1.2121-1.2143 across the
# corpus was 1.21172 + 0.07034/(lines x size), i.e. the box constant charged
# to every line. Deck 10 alone could not have caught this: with one value of
# (lines x size) the two terms are not separable.
#
# HONEST EFFECT OF THIS CHANGE, so nobody expects more of it than it does:
# it moves the divider labels by -0.033pt per row (9pt) and -0.044pt (12pt).
# Against the badge/label drift on slides 4/9/14 that is about 5% of the
# error. The other 95% -- 0.6027pt per row, 4.22pt over seven rows -- is the
# gap between the AUTHORED oval pitch (21.86263pt) and PowerPoint's own line
# pitch at 9pt/206% (22.4653pt), and is not ours to remove. Slide 21's 12pt
# oval pitch matches PowerPoint's to +0.03%, which is why it does not drift.
SOURCE_LINE_HEIGHT = 1.21172


def archetype(slide: dict) -> str:
    """Layout-name archetype for a model slide dict. Advisory (rule: never
    changes how a shape renders, only which treatment it is offered)."""
    from phase_1c.deckkit import css as dkcss
    return dkcss.archetype_of(slide, LAYOUT_ARCHETYPE, PLATE_DEFAULT)


def sub_for(typeface):
    if not typeface:
        return {"stack": FALLBACK_STACK, "weight": None}
    return SUBS.get(str(typeface).strip().lower(),
                    {"stack": FALLBACK_STACK, "weight": None})
