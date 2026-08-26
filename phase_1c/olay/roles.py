"""Per-shape roles for the Olay deck — manifest-driven, not auto-detected.

LEARNINGS closes on exactly this: auto-detection of slide templates is
deferred; the operator tags things until the pipeline has seen enough
variety to know what "typical" looks like. These tags are read off the
source deck's own structure (decoded in the conversion notes), not guessed
at render time.
"""

# The 7-badge category sprite. One asset, 15 slides, 7 distinct srcRect
# crops. Decoded from slide 3's legend by pairing chip geometry against
# text geometry, then cross-checked against slides 9 and 10, whose captions
# name the numbers in prose ("with 1 (Abstract)", "6 (Soap Foam)").
BADGE_SPRITE = "image9.png"
BADGE_CROPS = {          # (left%, right-edge%) -> category number + name
    (0.0, 8.0):    ("1", "Abstract elements"),
    (14.2, 23.7):  ("3", "Ambient"),
    (31.0, 40.8):  ("2", "Lifestyle"),
    (45.4, 54.7):  ("4", "Cinematic"),
    (61.2, 69.9):  ("5", "Application / in-situ"),
    (77.9, 86.8):  ("6", "Sensorial"),
    (92.1, 100.0): ("7", "Group shots / end cards"),
}

# Rasterised headline art — an italic display serif that exists only as
# pixels. Kept as image crops by decision; not re-set as live text.
BANNERS = {
    "image5.png":  "Creative Brief",
    "image8.png":  "Considerations with Category types",
    "image17.png": "Renders",
    "image39.png": "Assets in Motion (Solo) with Category types",
    "image60.png": "Assets in Motion (Group Shots) with Category types",
    "image73.png": "Still Assets",
    "image94.png": "Asset Library & Ads creation",
}

LOGOS = {"image2.png": "Olay", "image3.png": "Global Image Factory"}

# P&G's internal review comments, left in the source file: six teal boxes on
# slides 9, 10, 21 and 22 ("Wrong package", "Move forward with #5 as is", ...).
# They are authored content, so rule 14 renders them faithfully by default —
# suppressing them is a delivery decision, taken here explicitly rather than
# by the detector in model.py. Confirmed against the full list 2026-08-21.
SUPPRESS_REVIEW_STICKERS = True

# Slide 33 is slide 2 duplicated with an opaque full-canvas image painted over
# it. PowerPoint hides the old slide by simple z-order; a mobile reflow that
# flattens z-order resurrects it. Dropping occluded shapes makes mobile agree
# with desktop. Costs slide 33's 583 buried characters, which never render in
# the source deck either. Flip to False to keep them.
SUPPRESS_OCCLUDED_SHAPES = True

# Slides whose grammar is a contact sheet of narrow vertical strips. These
# reflow to a horizontal scroller on mobile rather than an 8-deep stack,
# which would bury the slide's whole point.
STRIP_SLIDES = {4, 5, 6, 7}

# Editor vocabulary. The Deck Editor harvests headlines from `.L > .t` and
# body copy from `.ci .tlt .tlb .uct .ucb .cbi .fn .agd .sn .sl`.
def text_role(slide_n: int, typeface: str) -> str:
    if typeface == "Boston SemiBold":
        return "title"          # -> .L > .t   (slides 1 and 34 only)
    if typeface == "Aptos":
        return "fn"             # inherited 18pt review stickers
    if slide_n in (2, 3, 33):
        return "cbi"            # brief / legend body copy
    return "ci"                 # board captions, slides 9-23


def badge_for(crop: dict):
    """Map a srcRect back to its category chip, tolerating rounding."""
    if not crop:
        return None
    l = round(crop.get("l", 0) * 100, 1)
    r = round((1 - crop.get("r", 0)) * 100, 1)
    for (cl, cr), meta in BADGE_CROPS.items():
        if abs(cl - l) < 1.2 and abs(cr - r) < 1.2:
            return meta
    return None


def image_role(src: str, crop: dict, w_pt: float, h_pt: float) -> str:
    if src == BADGE_SPRITE:
        return "badge"
    if src in BANNERS:
        return "banner"
    if src in LOGOS:
        return "logo"
    return "tile"
