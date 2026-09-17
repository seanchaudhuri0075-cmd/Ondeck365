"""Unilever "Skin, Hair & Personal Care" capabilities deck (deck 11) operator manifest.

Manifest-driven, like Secret's. Every set below is MEASURED -- the numbers and
the reasoning behind them are in DECK11_HANDOFF.md, and the section is named
beside each block so a value can be traced rather than trusted.

WHAT IS DIFFERENT ABOUT THIS DECK, in one place:

* **It is 20x Secret.** 1.57 GB, 49 videos, ~500 MB of assets after encoding.
  The video cannot live in git; only model.json, used_assets.json and
  asset_manifest.json are committed, and the manifest's `out_sha256` is what
  the byte-for-byte gate runs against (section 6, section 7 item 8).

* **Nothing is inherited.** 268 of 268 shapes are locally authored, the deck
  has no placeholders at all, and the layout names are PowerPoint defaults
  (`DEFAULT` covers the cover, the diagrams AND seven video slides). So it is
  routed on measured geometry, per slide -- never on `layout_name`
  (section 5). LAYOUT_ARCHETYPE below says only what the names honestly say.

* **It is deck 9 and deck 10 at once.** 27 clips are over 3 Mbps and 22 are
  under it, with nothing in between, so the video mode is per file (section 6,
  section 7 item 2) -- and three of the 27 are copied anyway, because
  re-encoding them made them bigger (BUILD 2).

* **Its films are spoken.** Audio is KEPT in every file; whether a clip plays
  muted, and whether it waits for a click, come from model.json's `muted` and
  `playback`, which come from the deck's own <p:timing> (section 9 item 5).
"""

DECK_TITLE = "Global ImAIge Factory — Skin, Hair & Personal Care"
DECK_CLIENT = "Unilever"
N_SLIDES = 35

# ---------------------------------------------------------------- slug
SLUG = "unilever_shpc"      # build dir + asset prefix: out/unilever_shpc/

# The R2 publish prefix is a SEPARATE value typed into the Deck Editor's Deck
# Name field, and is deliberately not the build slug (see secret/roles.py).
# NOT CHOSEN. Nothing is uploaded or published from this build. It must not
# collide with: olay, olay-v2, oldspicepackaging, hh-creativestrategy,
# pgdigital, venus-hestia.
R2_PREFIX = None

# ---------------------------------------------------------------- archetypes
# What the authored layout names can honestly carry, which is almost nothing.
# Advisory only (deckkit.css.archetype_of); an unlisted layout returns
# PLATE_DEFAULT. The real routing is GEOMETRY_GROUPS.
LAYOUT_ARCHETYPE = {
    "DEFAULT":        None,          # cover, statements, diagrams, 7 video slides
    "23_Title Slide": "showcase",    # every showcase slide, 1 clip or 4
    "Blank":          None,
    "Title Only":     None,
}
PLATE_DEFAULT = None

# Per-slide routing, from the dry-run model's geometry (section 3, "Geometry
# groups"; % of the 960x540pt canvas). Keyed on measured geometry in the manner
# of Secret's PLATE_SLIDES / GROUP_B / HEADER_SLIDES -- and for Secret's
# slide-30 reason: a layout name sweeps in slides it does not describe.
# ADVISORY: steers which treatment a slide is offered and where QA looks. It
# never changes how a shape renders.
GEOMETRY_GROUPS = {
    "statement":        (1, 6, 15, 35,      # text only, 2 shapes
                         13, 34),           # text + logo
    "diagram":          (2, 3, 4, 5),       # 28-31 shapes: numbered rect cards + text
    "full_bleed_video": (9, 12, 14, 27, 28, 29, 31, 32,   # one clip at 100x100 (12: 104x104)
                         11),                             # one clip at 72x72
    "portrait_wall":    (16, 17, 19, 21, 22, 23, 24, 25,  # 3-4 portrait clips, ~23-26% x 74-83%
                         7, 10),                          # 2 portrait clips at 28x88
    "mixed_video":      (8, 18, 20),        # landscape + portrait clips side by side
    "image_board":      (26,                # 73x74 animated GIF + one portrait clip
                         30,                # one 1920x9419 capture through three crop windows
                         33),               # four billboards, one group, two off-canvas
}
# NOTE on 20: the handoff table lists it under BOTH "portrait video wall"
# (as part of 19-25) and "mixed video". Its three clips are 24x75, 42x75 and
# 24x75 -- one landscape-ish between two portraits -- so it is mixed, and is
# listed once, there.

SLIDE_GROUP = {n: g for g, slides in GEOMETRY_GROUPS.items() for n in slides}
assert sorted(SLIDE_GROUP) == list(range(1, N_SLIDES + 1)), "every slide in exactly one group"
assert sum(len(v) for v in GEOMETRY_GROUPS.values()) == N_SLIDES, "a slide is listed twice"

# ---------------------------------------------------------------- video
# Written out per file, NOT computed from a threshold at build time: the
# decision was made against measured numbers (section 6, "Every video") and
# should read as one. Rule applied: re-encode every clip over 3 Mbps, stream-
# copy the rest. The two populations do not touch -- the heaviest copy is
# 2.82 Mbps, the lightest re-encode 3.99 -- so no file is a judgement call.
#
# THREE EXCEPTIONS, found by BUILD 1 (2026-09-17) and switched to copy on
# Sean's decision: media19, media42 and media49 are over 3 Mbps, but CRF 23
# made each of them LARGER than its source. A second lossy generation that also
# costs bytes is the trade `copy` exists to refuse. They sit in the copy block
# below with both sizes. The rule is a proxy for "too heavy for the web"; the
# measured output is the thing itself, and it wins.
# The trailing comment is the SOURCE: Mbps, WxH, slide.
#
# build.py refuses to run unless this map names exactly the deck's used videos.
VIDEO_MODES = {
    # ---- re-encode: 24 clips, 1,266.2 MB of the 1,464.7 -------------------
    "media1.mp4":  "encode",   # 15.29  1080x1920  s7
    "media3.mp4":  "encode",   # 45.13  1920x1440  s8
    "media6.mp4":  "encode",   # 14.94  1080x1920  s10
    "media7.mp4":  "encode",   # 15.23  1080x1920  s10
    "media8.mp4":  "encode",   # 18.36  1920x1080  s11
    "media9.mp4":  "encode",   #  7.54  1280x720   s12
    "media10.mp4": "encode",   # 33.37  1920x1080  s14   242 MB, click-to-play
    "media11.mp4": "encode",   #  3.99  1080x1920  s16   the lightest re-encode
    "media15.mp4": "encode",   #  5.44  1080x1920  s17
    "media27.mp4": "encode",   # 10.39  1080x1920  s21   click-to-play
    "media28.mp4": "encode",   # 19.57  1080x1920  s21   118 MB, click-to-play
    "media29.mp4": "encode",   # 15.87  1080x1920  s21   225 MB, click-to-play
    "media30.mp4": "encode",   # 18.18  1080x1920  s21   click-to-play
    "media34.mov": "encode",   #  5.45   540x960   s22
    "media35.mp4": "encode",   #  5.11  1080x1920  s23
    "media36.mp4": "encode",   #  5.38  1080x1920  s23
    "media37.mp4": "encode",   #  5.21  1080x1920  s23
    "media38.mp4": "encode",   #  5.03  1080x1920  s24
    "media39.mp4": "encode",   #  5.13  1080x1920  s24
    "media40.mp4": "encode",   #  5.13  1080x1920  s24
    "media41.mp4": "encode",   #  5.17  1080x1920  s25
    "media43.mp4": "encode",   #  5.09  1080x1920  s25
    "media47.mp4": "encode",   # 34.07  1920x1080  s29   207 MB, click-to-play
    "media48.mp4": "encode",   #  4.55  1920x1080  s31
    # ---- stream-copy: 22 clips, 166.1 MB, already web-rate ----------------
    # (media16 at 2.82 Mbps is the heaviest of these 22)
    "media2.mp4":  "copy",     #  0.82   720x1280  s7
    "media4.mp4":  "copy",     #  2.14  1080x1920  s8
    "media5.mp4":  "copy",     #  2.80  1920x1080  s9
    "media12.mp4": "copy",     #  1.47  1080x1920  s16   the clip behind the "NULL" link
    "media13.mp4": "copy",     #  1.36  1080x1920  s16
    "media14.mp4": "copy",     #  1.96  1080x1920  s16
    "media16.mp4": "copy",     #  2.82  1080x1920  s17   the heaviest copy
    "media17.mp4": "copy",     #  1.08  1080x1920  s17
    "media18.mp4": "copy",     #  0.90   828x1792  s17
    "media20.mp4": "copy",     #  1.49   600x900   s18
    "media21.mp4": "copy",     #  1.97  1080x1920  s19
    "media22.mp4": "copy",     #  1.94  1080x1920  s19
    "media23.mp4": "copy",     #  1.96  1080x1920  s19
    "media24.mp4": "copy",     #  2.32  1080x1920  s20
    "media25.mp4": "copy",     #  1.44  1080x1080  s20
    "media26.mp4": "copy",     #  2.23  1080x1920  s20
    "media31.mp4": "copy",     #  2.60   480x854   s22   50 fps, Constrained Baseline
    "media32.mp4": "copy",     #  1.61   720x1280  s22   NO AUDIO TRACK at source
    "media33.mp4": "copy",     #  1.27   720x1280  s22
    "media44.mov": "copy",     #  1.28   300x600   s26   .mov in, .mp4 out
    "media45.mp4": "copy",     #  1.84  1920x1080  s27
    "media46.mp4": "copy",     #  0.76  1920x1080  s28
    # ---- stream-copy BY MEASUREMENT: 3 clips, 32.4 MB ---------------------
    # Over 3 Mbps, but BUILD 1's CRF 23 re-encode came out larger than the
    # source, so copying is both smaller and one lossy generation cleaner.
    "media19.mp4": "copy",     #  4.44  1920x1080  s18   re-encode 11.72 MB > source  8.33 MB
    "media42.mp4": "copy",     #  5.05  1080x1920  s25   re-encode  6.45 MB > source  6.31 MB
    "media49.mp4": "copy",     #  5.10  1920x1080  s32   re-encode 18.79 MB > source 17.73 MB
}
assert sum(m == "encode" for m in VIDEO_MODES.values()) == 24
assert sum(m == "copy" for m in VIDEO_MODES.values()) == 25

# CRF 23 / medium are deckkit's defaults and are named here so the call site
# reads as a decision: measured on the seven heaviest clips, CRF 23 beat deck
# 9's 5 Mbps cap on five of seven (section 6).
VIDEO_CRF = 23
VIDEO_PRESET = "medium"

# Settled from the deck's own XML, not from a preference (section 9 item 5):
# the six click-to-play films are spoken and the author left them audible.
# Muting is the page's job, from model.json. What is stripped here cannot be
# given back there.
AUDIO = "keep"
SILENT_AT_SOURCE = {"media32.mp4"}    # the only clip of 49 with no audio stream

# ---------------------------------------------------------------- suppression
# Reconnaissance found no review stickers and no occluded shapes (section 7,
# "Not gaps for this deck"). Left on for the same reason as Secret: they cost
# nothing, and a revision that introduces one is caught rather than shipped.
SUPPRESS_REVIEW_STICKERS = True
SUPPRESS_OCCLUDED_SHAPES = True

# ---------------------------------------------------------------- fonts
# TODO -- NOT DECIDED. See DECK11_HANDOFF.md section 4. Do not fill this in by
# eye, and do not fill it in from a render on this Mac:
#
#   SF Pro Semibold   260 runs   35pt display (206 runs), 15/20
#   SF Pro Medium      66 runs   12/15/16
#   Helvetica           6 runs
#   Arial               1 run
#   League Gothic       1 run    SIL OFL -- ships as itself; binary not bundled yet
#   Calibri             1 run    inherited theme minor font; identify before bundling
#
# SF Pro is 326 of 335 runs (97%) and CANNOT ship: Apple licenses it for UI
# mock-ups on Apple platforms, not as a web font. A substitute is required and
# is the largest fidelity decision in this build. It must be made the way
# Secret's were: width budgets from the authored boxes rule candidates OUT, and
# the pick among the survivors is a recorded judgement call against Sean's
# PowerPoint screenshots. SF Pro IS installed on this machine, so a local
# render will look right and the shipped deck will not -- `local()` must never
# appear in the @font-face src, and text fit must not be judged here with the
# local face enabled.
#
# Until then there is deliberately no FONT_FAMILIES, no SUBS and no sub_for():
# a renderer that imports them fails loudly instead of shipping a guess.
FONTS_DECIDED = False

# PowerPoint's autofit constant -- face- and size-independent per the four-deck
# fit recorded in secret/roles.py. Carries over unchanged.
SOURCE_LINE_HEIGHT = 1.21172


def archetype(slide: dict):
    """Layout-name archetype for a model slide dict. Advisory."""
    from phase_1c.deckkit import css as dkcss
    return dkcss.archetype_of(slide, LAYOUT_ARCHETYPE, PLATE_DEFAULT)


def group(slide: dict):
    """Measured geometry group for a model slide dict. Advisory. Keyed on the
    SOURCE slide number, so it survives a drop_slides renumbering."""
    return SLIDE_GROUP.get(slide.get("src_n", slide.get("n")))
