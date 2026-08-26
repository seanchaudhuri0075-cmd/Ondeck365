"""Deck-agnostic canvas and scroll CSS primitives, shared by the per-deck builders.

Only two concerns live here, and both earned their place by having been got
wrong *independently* in more than one builder:

* **The canvas aspect.** Three builders hardcoded `16/9`. That is correct for a
  960x540 deck and silently wrong for any other -- deck 9 (Venus/Hestia) is
  1224x792pt, tabloid landscape, aspect 1.5455. The aspect is a measured
  signature: read it from `p:sldSz` and never type it. See LEARNINGS rule 15.

* **The mobile scroll gate.** `scroll-snap-stop:always` is a DISCRETE-paging
  affordance -- per CSS Scroll Snap it forbids the container passing over a
  snap position during a scrolling operation, so every fling is forced to the
  nearest snap point. That is what a wheel or an arrow key wants and exactly
  wrong on an inertial surface. Diagnosed on HenHouse (2026-08-24), ported to
  Olay (2026-08-25), and MISSED on Old Spice, which still ships
  `y mandatory` + `always` at every width -- the strictest of the three.

Three builders, three chances to get the same two things wrong, nothing shared.
That is the argument for this module, and it is why it exists before deck 9 is
written rather than after.

What is deliberately NOT here: each deck's mobile reflow. Bands, heroes,
carousels, plates, pairs and merges are that deck's design, not a shared
concern. Folding them together would be the restructure LEARNINGS warns about
rather than the de-duplication this is. These are primitives -- a number, a
custom property, an expression, a two-line gate -- that each builder splices
into the stylesheet it already owns.
"""

# Every phase_1c deck gates its mobile reflow on the same breakpoint. Stated
# once so a builder cannot drift to 768 or 800 and half-apply a shared rule
# (see NOTES 2026-08-24 on the Patchology 767/768 sliver, where a correctly
# authored unlock was live in a 1px window and inert at every real width).
MOBILE_BP = 820


def ratio(slide_w_pt: float, slide_h_pt: float) -> float:
    """The deck's aspect, from its own `p:sldSz`. 960x540 -> 1.777778."""
    return slide_w_pt / slide_h_pt


def ratio_root(slide_w_pt: float, slide_h_pt: float) -> str:
    """A `:root` block publishing `--ratio`.

    Emitted as its own block so a builder whose stylesheet is a static constant
    can prepend it without that constant needing access to the model. Multiple
    `:root` blocks are valid CSS and merge.
    """
    return (
        "/* The deck's own aspect, read from p:sldSz -- never hardcoded.\n"
        "   Everything below sizes off this, so a non-16:9 deck needs no other\n"
        "   change. (LEARNINGS rule 15.) */\n"
        f":root{{--ratio:{ratio(slide_w_pt, slide_h_pt):.6f}}}"
    )


# The canvas width for a builder that fits the canvas to the viewport directly
# (HenHouse's idiom). `svh` not `vh`: mobile URL-bar collapse makes `vh`
# unstable (LEARNINGS rule 25).
#
# Olay and Old Spice use the other idiom -- `width:100%` inside a padded slide,
# with `max-width` carrying the aspect -- and write that expression inline,
# because their stylesheet is a static constant with no access to the model.
# They previously wrote it as the literal `calc(177.78vh - 8vh)`, in which
# `177.78` is `16/9 x 100`: the hardcoded aspect in disguise, and the `8vh` is
# the slide's own `padding:2vh` top and bottom, doubled. Against `--ratio` the
# same 16:9 deck resolves to `calc(100vh * 1.777778 - 8vh)` = 169.7778vh, which
# is 0.0022vh SMALLER than the old 169.78vh. Measured across viewport heights
# 400-2000: worst case 0.044 CSS px at H=2000, i.e. 0.13 device px at DPR 3.
# It would take a 15,152px-tall viewport at DPR 3 to reach one device pixel.
# That is the only reason the two are not character-identical.
CANVAS_WIDTH_FIT = "min(100vw, calc(100svh * var(--ratio)))"


def mobile_scroll_release(slide_sel: str, deck_sel: str = "#deck") -> str:
    """The two declarations that release scroll-snap on touch.

    Belongs inside the builder's existing `@media (max-width:{MOBILE_BP}px)`
    block. Desktop keeps its snap untouched -- this only ever loosens, and only
    below the breakpoint.

    `scroll-snap-align` on the slide is deliberately left in place by the
    caller: it is inert without a snap container and still serves desktop from
    the same rule. `scroll-snap-stop:normal` is likewise inert while snap is
    off; it is set anyway so that re-enabling snap here restores the correct
    touch value rather than silently inheriting the desktop `always`.
    """
    return (
        "  /* Snap OFF on touch, and stop released. scroll-snap-stop:always is a\n"
        "     DISCRETE-paging affordance -- it forbids the container passing over a\n"
        "     snap position, which is what a wheel or arrow key wants and what turns\n"
        "     every fling into a single-step advance on an inertial surface. Snap\n"
        "     re-targeting is also what overrides the browser's own deceleration\n"
        "     curve, so the container goes to `none`. The cost is exact and accepted:\n"
        "     slides no longer align, so a flick can rest mid-slide.\n"
        "     Desktop keeps its authored snap. See LEARNINGS rule 15, NOTES\n"
        "     2026-08-24 (HenHouse) and 2026-08-25 (Olay). */\n"
        f"  {deck_sel}{{scroll-snap-type:none}}\n"
        f"  {slide_sel}{{scroll-snap-stop:normal}}"
    )
