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

* **The media box reservation.** A `<video>` whose box is not reserved
  collapses to zero height until its first frame decodes, so the slide reflows
  under the reader mid-scroll. Every builder that ships video writes `--ar` on
  the element and then a rule to consume it -- and they had already drifted:
  HenHouse consumes it with a `16/9` fallback, Olay with `1`, so an unset
  `--ar` renders a landscape box on one deck and a square on the other. Deck 9
  writes `--ar` on every `<video>` (`venus_hestia/render.py:103,105`) and
  consumes it NOWHERE -- the reservation its own handoff (section 5a) relies on
  is not wired. Three builders, three different answers, one of them silently
  absent. Same argument as the two above.

* **Preset geometry.** `<a:prstGeom prst="ellipse">` is a round shape and
  renders square without a `border-radius`. Old Spice solved it at
  `phase_1c/oldspice/render.py:176` in Aug 2026 and it was carried to no other
  builder, so deck 10 shipped 87 ellipses as rectangles across 23 of its 31
  slides -- shapes literally named "Oval 9".."Oval 16". That is the FOURTH time
  a fix existed in one builder and not the others (after the scroll gate, the
  `--ar` consumer and the crop-frame clip), which is the whole argument for
  this module.

What is deliberately NOT here: each deck's mobile reflow. Bands, heroes,
carousels, plates, pairs and merges are that deck's design, not a shared
concern. Folding them together would be the restructure LEARNINGS warns about
rather than the de-duplication this is. These are primitives -- a number, a
custom property, an expression, a two-line gate -- that each builder splices
into the stylesheet it already owns.
"""

from typing import Optional


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


def media_box_reserve(fallback: str, im_sel: str = ".sh.im", vid_sel: str = ".sh.vid") -> str:
    """The rule that reserves a media box from `--ar`, for inside the mobile query.

    `fallback` is REQUIRED and has no default on purpose. The two builders that
    ship this already disagree -- HenHouse `16/9`, Olay `1` -- and a default
    here would silently pick a winner and change one of them. Pass what that
    deck already emits; a new deck should pass the value it can defend.

    Why a fallback at all, since an unset `--ar` means the producer failed:
    `aspect-ratio:var(--ar)` with `--ar` unset is invalid at computed-value
    time, so the property drops and the box collapses -- which is precisely the
    reflow-under-the-reader this rule exists to prevent. The fallback keeps a
    producer bug ugly rather than catastrophic. It does not make the bug
    visible, so pair it with the producer/consumer sweep, which is what caught
    deck 9's missing consumer in the first place.
    """
    return (f"  {im_sel},{vid_sel}{{aspect-ratio:var(--ar,{fallback})}}\n"
            f"  {im_sel}>img,{vid_sel}>video{{width:100%;height:100%}}")


# A crop frame renders its neighbours without this: the child is scaled far
# beyond the frame by the srcRect maths (~5.5x on Old Spice), so every cell
# paints into the next one. LEARNINGS rule 29 records it as one of two silent
# traps; all three video-bearing builders carry the declaration already, which
# is what makes it a primitive rather than a per-deck choice.
def crop_frame_clip(*selectors: str) -> str:
    """`overflow:hidden` on crop frames. Pass the deck's own media selectors."""
    return ",".join(selectors) + "{overflow:hidden}"


def archetype_of(slide: dict, mapping: dict, default: Optional[str] = None) -> Optional[str]:
    """Map a slide's authored layout name to a per-deck archetype. Advisory.

    `mapping` is the DECK's table (its roles.py), not a shared one -- see
    `deckkit.model.build_layout_index` for why nothing here interprets a name.
    Returns `default` for a layout the deck did not declare, so an unrecognised
    layout is a visible gap rather than a silent guess.

    This never decides how a shape renders. Per PHASE_1C_ARCHITECTURE.md the
    classifier may steer QA effort and nothing else; the same limit applies
    here, one level down.
    """
    return mapping.get(slide.get("layout_name"), default)


# OOXML preset geometries that map to a CSS corner radius. Deliberately tiny:
# only the shapes this pipeline has actually met are listed, and anything
# unknown returns "" rather than guessing a shape. A wrong radius is a visible
# design change, so an unrecognised prst renders as authored geometry allows
# (a rectangle) and shows up in review rather than being silently rounded.
_PRST_RADIUS = {
    "ellipse": "50%",
    "roundRect": "8%",     # PowerPoint's default adj is 16667/100000 of the
                           # SHORTER side; 8% of the box is a close approximation
                           # and is the value to replace with a real adj read
                           # when a deck first needs it.
}


def prst_css(prst) -> str:
    """`border-radius` for an OOXML preset geometry, or "" if it needs none.

    Returns a full declaration with trailing semicolon so a caller can splice
    it into a style attribute unconditionally.
    """
    r = _PRST_RADIUS.get(prst or "")
    return f"border-radius:{r};" if r else ""
