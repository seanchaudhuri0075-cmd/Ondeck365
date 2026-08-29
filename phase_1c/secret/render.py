"""Secret (deck 10) — DESKTOP renderer.

Scope, deliberately: desktop only. There is no `@media` block in this file and
no mobile treatment, because deck 9's mobile build was rejected at review after
being written in the same pass as its desktop (NOTES 2026-08-26), and the
instruction here is to stop at desktop review. The mobile query is a separate
round, on top of a desktop that has been signed off.

Everything shared is taken from `deckkit`, which is what it exists for:
  * `dkcss.ratio` / `ratio_root`  -- the canvas aspect, from p:sldSz (rule 15).
    720x405pt here, which IS 16:9, and is still read rather than assumed.
  * `dkcss.CANVAS_WIDTH_FIT`      -- fit the canvas to the viewport.
  * `dkcss.crop_frame_clip`       -- rule 29's silent trap.
  * `dkcss.media_box_reserve`     -- the --ar consumer. NOT emitted at desktop
    (the authored box is absolute and already has a size); it belongs to the
    mobile round, and is referenced here so the next author finds it instead of
    re-deriving it the way deck 9 did.

Rule 21: nothing inside the canvas carries a z-index. Paint order IS DOM order,
so shapes are emitted in the model's z order and the poster-under-video pair is
emitted poster-first.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from ondeck.render.fonts import font_face_css
from phase_1c.deckkit import css as dkcss
from phase_1c.deckkit import markup as dkmarkup
from phase_1c.deckkit.paths import DeckPaths
from phase_1c.secret import roles

SCR = ("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline"
       "/be9bf97d-d1ac-4401-9e81-272f6261d537/scratchpad")


def esc(s):
    return html.escape(s or "", quote=True)


def run_css(r, W: float) -> str:
    """Inline style for one run. Sizes are cqw against the canvas (rule 9)."""
    sub = roles.sub_for(r.get("typeface"))
    out = [f"font-family:{sub['stack']}"]
    w = sub["weight"]
    if w is None:
        w = 700 if r.get("bold") else 400
    out.append(f"font-weight:{w}")
    if r.get("italic"):
        out.append("font-style:italic")
    if r.get("size_pt"):
        out.append(f"font-size:{r['size_pt'] / W * 100:.4f}cqw")
    if r.get("color"):
        # Authored run-fill alpha, through the same rgba() every fill here uses.
        # Eight runs in this deck declare one (deck-wide: slide 3's four agenda
        # numerals, and the chapter numeral on 4/9/14/21), all at ~50%. They are
        # a deliberate pale tint sitting on a photograph; at full opacity they
        # read as a second headline competing with the title beside them.
        out.append(f"color:{rgba(r['color'], r.get('color_alpha'))}")
    return ";".join(out)


def para_html(p, W: float) -> str:
    align = p.get("align")
    bits = []
    # OOXML alignment tokens are NOT CSS keywords. This gated on
    # ("center", "right", "justify") -- the CSS spellings -- against a model
    # value that is always `l` / `ctr` / `r` / `just`, so nothing ever matched
    # and `text-align` was emitted ZERO times in the whole document. 101
    # authored `ctr` paragraphs rendered flush-left, including slide 1's
    # BEAUTY and 99 badge letters that should sit centred in their circles.
    # The mapping below is the same one the other four builders already use
    # (henhouse render.py:690, olay 271, oldspice 208, venus_hestia's ALIGN);
    # this was the one builder that wrote its own gate instead of reusing it.
    # An unmapped token emits nothing, exactly as an absent one does.
    css_align = {"l": "left", "ctr": "center",
                 "r": "right", "just": "justify"}.get(align)
    if css_align:
        bits.append(f"text-align:{css_align}")
    # Paragraph indents, in the SAME unit as every other canvas-relative
    # horizontal measure here (run_css sizes in cqw): `.sh` declares no
    # container-type, so the nearest container is `.canvas` and 1cqw is 1% of
    # canvas width. A percentage would resolve against the SHAPE box instead,
    # which is rule 41(c)'s trap wearing its horizontal face -- same expression,
    # different containing block, silently wrong by the ratio between them.
    # marL is the block indent; indent is the FIRST LINE, negative for a
    # hanging indent, which is what CSS text-indent already means.
    if p.get("marL"):
        bits.append(f"padding-left:{p['marL'] / W * 100:.4f}cqw")
    if p.get("indent"):
        bits.append(f"text-indent:{p['indent'] / W * 100:.4f}cqw")
    # Authored line spacing wins over the deck's recovered autofit ratio.
    # Ignoring it collapsed slide 4's eight A-H labels from 206% to 121%
    # spacing, so they no longer lined up with the badges beside them and read
    # as a broken pairing. --slh is the FALLBACK for paragraphs that state
    # nothing, not a deck-wide override (rule 14: reproduce what is authored).
    if p.get("line_pct"):
        # OOXML spcPct is a multiple of SINGLE LINE SPACING; CSS line-height is
        # a multiple of FONT SIZE. They are not the same number. Converting
        # 206% straight to `line-height:2.06` advanced 9pt labels by 18.5pt
        # against a badge pitch of 21.86pt -- 3.3pt short per row, a full row
        # of drift over eight. The factor is the source face's single-line
        # spacing: SOURCE_LINE_HEIGHT, corrected to 1.21172 on 2026-08-28
        # (see roles.py -- the old 1.2135 charged a per-BOX constant to every
        # line).
        bits.append(f"line-height:{p['line_pct'] * roles.SOURCE_LINE_HEIGHT:.4f}")
    style = ";".join(bits)
    # Authored <a:br/> is honoured here (deckkit.markup), not dropped. This
    # deck's divider titles are COLOR+ <br> TREATMENT and INGREDIENT <br> LED;
    # concatenating them fused each into one unbreakable token.
    spans = dkmarkup.runs_html(p["runs"], lambda r: run_css(r, W), esc)
    if not spans:
        spans = "<br>"
    bullet = p.get("bullet")
    battr = f' data-bullet="{esc(bullet)}"' if bullet else ""
    if bullet:
        # PowerPoint puts the glyph in the HANG and the text at marL. The
        # hang is exactly -indent wide, so an inline-block of that width puts
        # the text on marL regardless of how wide the glyph itself draws --
        # which matters because the bullet face is substituted like any other
        # and its advance is not the authored one.
        #
        # Explicitly NOT HenHouse's `p.t[data-bullet]{padding-left:1.6em;
        # text-indent:-1.6em}`: 1.6em is a guess that happens to look right at
        # one size, it tracks font size rather than the authored indent, and it
        # silently disagrees with the marL/indent this same paragraph already
        # emits. Two mechanisms for one measurement is how they drift apart.
        bs = [f"font-family:{roles.sub_for(p.get('bullet_font'))['stack']}"]
        b_sz = p.get("bullet_size_pt")
        if not b_sz and p.get("bullet_size_pct"):
            _r0 = next((r for r in p["runs"] if r.get("size_pt")), None)
            if _r0:
                b_sz = _r0["size_pt"] * p["bullet_size_pct"]
        if b_sz:
            bs.append(f"font-size:{b_sz / W * 100:.4f}cqw")
        if p.get("bullet_color"):
            bs.append(f"color:{p['bullet_color']}")
        ind = p.get("indent")
        if ind and ind < 0:
            bs.append("display:inline-block")
            bs.append(f"width:{-ind / W * 100:.4f}cqw")
        spans = f'<span class="bu" style="{";".join(bs)}">{esc(bullet)}</span>' + spans
    return f'<p class="t"{battr}{f" style={chr(34)}{style}{chr(34)}" if style else ""}>{spans}</p>'


def rgba(hexv, alpha):
    if alpha is None or alpha >= 1.0:
        return hexv
    h = hexv.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{round(alpha, 4)})"


def grad_css(g):
    """OOXML gradient -> CSS. Angles: OOXML measures clockwise from +x, CSS
    from +y, hence the +90. Same shape as HenHouse's helper — the first deck
    whose BACKGROUND is a gradient, because it arrives on a layout shape."""
    stops = ", ".join(f"{rgba(s['hex'], s['alpha'])} {round(s['pos'] * 100, 2)}%"
                      for s in g["stops"])
    if g.get("kind") == "radial":
        c = g.get("center") or {}
        cx = round((c.get("l", 0.5) + (1 - c.get("r", 0.5))) / 2 * 100, 1)
        cy = round((c.get("t", 0.5) + (1 - c.get("b", 0.5))) / 2 * 100, 1)
        return f"radial-gradient(circle at {cx}% {cy}%, {stops})"
    return f"linear-gradient({round((g.get('angle_deg', 0.0) + 90.0) % 360.0, 2)}deg, {stops})"


def box_style(sh, W: float, H: float) -> str:
    """Absolute placement in % of the canvas — aspect-agnostic (rule 15)."""
    s = [f"left:{sh['x'] / W * 100:.4f}%", f"top:{sh['y'] / H * 100:.4f}%",
         f"width:{sh['w'] / W * 100:.4f}%", f"height:{sh['h'] / H * 100:.4f}%"]
    if sh.get("rot"):
        s.append(f"transform:rotate({sh['rot']:.3f}deg)")
    # Authored picture-fill alpha. Emitted on the shape wrapper rather than the
    # <img> so a cropped picture (where the img is oversized inside .cropw)
    # washes as one element instead of compositing the crop window separately.
    if sh.get("opacity") is not None and sh["opacity"] < 1.0:
        s.append(f"opacity:{sh['opacity']:.4f}")
    return ";".join(s)


def crop_img(sh, src: str, alt: str) -> str:
    """A srcRect crop as a CSS window over the WHOLE asset (rules 6/7/31).

    Nothing is cut: the crop is a wrapper with overflow:hidden and an oversized
    child, so the asset stays one file, one URL and reversible in the editor.
    """
    c = sh["crop"]
    vw = 1.0 - c.get("l", 0) - c.get("r", 0)
    vh = 1.0 - c.get("t", 0) - c.get("b", 0)
    if vw <= 0 or vh <= 0:
        return f'<img src="{src}" alt="{alt}">'
    return (f'<span class="cropw">'
            f'<img src="{src}" alt="{alt}" style="'
            f'width:{100 / vw:.4f}%;height:{100 / vh:.4f}%;'
            f'left:{-c.get("l", 0) / vw * 100:.4f}%;'
            f'top:{-c.get("t", 0) / vh * 100:.4f}%"></span>')


# OOXML prstDash -> CSS border-style. CSS has three dash idioms against
# OOXML's nine, so the mapping is lossy BY CONSTRUCTION: every dashed variant
# collapses to `dashed` and every dotted one to `dotted`. Recorded as a
# deliberate flattening rather than left implicit. `cap` and `cmpd` have no CSS
# border equivalent at all -- they survive in model.json and nowhere else.
DASH_CSS = {"solid": "solid",
            "dot": "dotted", "sysDot": "dotted",
            "dash": "dashed", "sysDash": "dashed", "lgDash": "dashed",
            "dashDot": "dashed", "sysDashDot": "dashed",
            "lgDashDot": "dashed", "lgDashDotDot": "dashed",
            "sysDashDotDot": "dashed"}


def nm(sh) -> str:
    """A stable selector hook for the mobile block.

    The mobile reflow has to address INDIVIDUAL shapes -- slide 1's lockup is
    two specific siblings out of eight -- and the only alternatives were
    `nth-child`, which renumbers the moment a shape is suppressed, or a new
    wrapper, which is forbidden: grouping wrappers may not go inside a
    harvested column, and the editor addresses images and text by INDEX, so
    inserting an element would silently repoint every edit after it.

    An attribute on the element that is already there changes neither the
    child order nor the harvest index. Shape names come from the source deck
    and are unique within a slide.
    """
    return f' data-name="{esc(sh.get("name", ""))}"'


def shape_html(sh, man, W, H) -> str:
    t = sh.get("type")
    style = box_style(sh, W, H)

    if t == "image":
        a = man["images"].get(sh.get("poster"))
        if not a:
            return ""
        src = f'assets/{a["out"]}'
        alt = esc(sh.get("name", ""))
        inner = crop_img(sh, src, alt) if sh.get("crop") else f'<img src="{src}" alt="{alt}">'
        cls = "sh im cropped" if sh.get("crop") else "sh im"
        return f'<div class="{cls}"{nm(sh)} style="{style}">{inner}</div>'

    if t == "video":
        v = man["videos"].get(sh.get("video"))
        p = man["images"].get(sh.get("poster"))
        if not v:
            return ""
        poster = f'assets/{p["out"]}' if p else ""
        # Poster FIRST, video second, both absolute in one wrapper: rule 4's
        # two layers, achieved by DOM order because rule 21 forbids z-index.
        # --ar is written here and consumed by the mobile round's
        # dkcss.media_box_reserve(); desktop sizes from the authored box.
        under = (f'<img class="poster" src="{poster}" alt="" aria-hidden="true">'
                 if poster else "")
        return (f'<div class="sh vid"{nm(sh)} style="{style};--ar:{v["aspect"]}">{under}'
                f'<video src="assets/{v["out"]}"'
                f'{f" poster={chr(34)}{poster}{chr(34)}" if poster else ""}'
                f' preload="none" muted loop playsinline></video></div>')

    if t == "line":
        # A CONNECTOR IS A STROKE, NOT A BOX. Deck 10's eight are all
        # cx x 0 -- zero height -- so a filled div draws nothing whatever
        # colour it is given. The mark has to be a BORDER on the zero-height
        # element: `border-top` paints along the box's top edge, which is where
        # the authored geometry puts the line.
        #
        # Weight in cqh, not pt or %: a 0.75pt rule on a 405pt-tall canvas is
        # 0.1852% of canvas height, and cqh is the unit that resolves against
        # height (rule 41(c) -- a percentage would resolve against WIDTH and
        # come out 1.778x too thick, the same trap as the vertical insets).
        st = sh.get("stroke") or {}
        w_pt = st.get("w_pt") or 1.0
        # PowerPoint centres a stroke on its geometric line; a CSS border-top
        # paints downward from the edge. At 0.75pt the difference is 0.375pt --
        # 0.67px at 1280 -- so it is recorded here rather than corrected, since
        # a half-width offset would be a bigger lie at any larger weight.
        bits = [box_style(sh, W, H),
                f"border-top:{w_pt / H * 100:.4f}cqh "
                f"{DASH_CSS.get(st.get('dash'), 'solid')} "
                f"{rgba(st.get('hex', '#000000'), st.get('alpha'))}"]
        return f'<div class="sh ln"{nm(sh)} style="{";".join(bits)}"></div>'

    if t in ("text", "rect"):
        bits = [style]
        # 87 shapes in this deck are prst="ellipse" (the A-H badges and the
        # numbered chips), across 23 of 31 slides. Without this they render
        # square. deckkit owns the mapping so the next builder inherits it.
        r = dkcss.prst_css(sh.get("prst"))
        if r:
            bits.append(r.rstrip(";"))
        if sh.get("grad"):
            bits.append(f'background:{grad_css(sh["grad"])}')
        elif sh.get("fill"):
            bits.append(f'background:{rgba(sh["fill"], sh.get("fill_alpha"))}')
        ins = sh.get("insets") or {}
        if any(ins.get(k) for k in "ltrb"):
            # Vertical insets are cqh, horizontal are %. NOT a style choice:
            # CSS resolves padding percentages -- ALL FOUR SIDES -- against the
            # containing block's WIDTH. Emitting tIns/bIns as a % of canvas
            # HEIGHT therefore inflated every vertical inset by the canvas
            # aspect ratio (720/405 = 1.778), i.e. 78% too large: an authored
            # 7.2pt inset resolved to 12.80pt, and a 3.6pt one to 6.40pt.
            # `cqh` resolves against the query container's height, and .canvas
            # declares container-type:size, so 1cqh is 1% of canvas height --
            # which is exactly what these numbers already are.
            # Horizontal is left as % because % against width is correct there.
            bits.append(
                f'padding:{ins.get("t",0)/H*100:.3f}cqh {ins.get("r",0)/W*100:.3f}%'
                f' {ins.get("b",0)/H*100:.3f}cqh {ins.get("l",0)/W*100:.3f}%')
        anchor = {"ctr": "center", "b": "flex-end"}.get(sh.get("anchor"), "flex-start")
        bits.append(f"justify-content:{anchor}")
        # OOXML wrap="none" means the text NEVER wraps -- it overhangs the box
        # instead. Ignoring it let a 0.01pt overflow (a 50.39pt box with 14.4pt
        # of default insets = 35.99pt inner, against 36.00pt of type) break "01"
        # into "0" / "1", stranding the 0 above the title on some viewport
        # widths and not others. Overhang is the CORRECT behaviour here, not a
        # defect to suppress: the source asks for it explicitly.
        # Deck-wide this reaches exactly 4 shapes -- the chapter numbers on
        # slides 4, 9, 14 and 21. Nothing else declares wrap="none".
        if sh.get("wrap") == "none":
            bits.append("white-space:nowrap")
        paras = "".join(para_html(p, W) for p in (sh.get("paras") or []))
        return f'<div class="sh tx"{nm(sh)} style="{";".join(bits)}">{paras}</div>'

    return ""


def build_css(deck) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    bp = dkcss.MOBILE_BP
    band = f"769-{bp}"
    scroll_release = dkcss.mobile_scroll_release("section.slide")
    return f"""{dkcss.ratio_root(W, H)}
:root{{--deck-font:{roles.BODY_STACK};--display-font:{roles.DISPLAY_STACK}}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:#111;color:#111}}
body{{font-family:var(--deck-font);-webkit-text-size-adjust:100%}}
img,video{{display:block;max-width:100%}}

#deck{{height:100svh;overflow-y:auto;overflow-x:hidden;
      scroll-snap-type:y proximity;-webkit-overflow-scrolling:touch}}
section.slide{{scroll-snap-align:start;scroll-snap-stop:always;
      display:flex;align-items:center;justify-content:center;
      min-height:100svh;background:#111}}

/* ---- desktop: the authored canvas, absolutely positioned (rule 15) ---- */
.canvas{{position:relative;width:{dkcss.CANVAS_WIDTH_FIT};
        aspect-ratio:var(--ratio);container-type:size;overflow:hidden;
        background:var(--bg,{deck["master_bg"]})}}
.sh{{position:absolute;display:flex;flex-direction:column;overflow:visible}}
{dkcss.crop_frame_clip('.sh.im', '.sh.vid')}
.sh.im>img,.sh.vid>video,.sh.vid>img.poster{{width:100%;height:100%;object-fit:cover}}
/* poster under video, by DOM order — no z-index inside the canvas (rule 21) */
.sh.vid>img.poster,.sh.vid>video{{position:absolute;inset:0}}
.sh.cropped>.cropw{{position:absolute;inset:0;overflow:hidden;display:block}}
.sh.cropped>.cropw>img{{position:absolute;max-width:none;object-fit:fill}}
/* wrap="square" means wrap AT THE BOX EDGE, breaking mid-word if one token
   does not fit -- ground truth renders COLOR+TREATMENT as COLOR+ / TREATM /
   ENT. CSS has no break opportunity in that token without this, so the word
   ran off the canvas instead. */
.sh.tx{{overflow-wrap:anywhere}}
/* Default line spacing is the FONT'S OWN (`normal`), not --slh. --slh is
   PowerPoint's AUTOFIT constant, recovered from this deck's four autofit
   boxes (rule 34) -- it belongs to the layout engine, not to any face, and
   applying it to every paragraph that declares no <a:lnSpc> imposes an
   autofit rhythm on 111 single-line boxes that were never autofit. It is
   still used where it belongs: as the single-line factor that converts
   OOXML spcPct to CSS line-height, baked in per-paragraph by para_html --
   which is why no --slh custom property is emitted. A declared-but-unconsumed
   variable is the dead-consumer smell rule 35's sibling instance records.
   Honest note on scale: this is a CORRECTNESS fix, not a fix for the title
   collisions. Barlow Condensed's natural ratio is 1.2000 against the
   constant's 1.21172, so a 96pt title's line box moves 116.5pt -> 115.0pt.
   The collisions are authored overflow and this barely touches them. */
p.t{{margin:0;line-height:normal}}

/* ==================================================================
   MOBILE -- same DOM, no second .slide tree, no duplicated media.
   Gated on dkcss.MOBILE_BP ({bp}px), the shared constant. NOT 768:
   css.py records that 768 is the drift value behind the Patchology
   767/768 sliver, and mobile_scroll_release() below documents that it
   belongs inside the MOBILE_BP block. A deck-local breakpoint would
   leave deck 10 on desktop across {band}px while every sibling reflowed.

   Slide 1 only, so far. Everything is scoped to #s1; slides 2-31 keep
   their desktop canvas untouched below the breakpoint until each is
   done in its own pass.
   ================================================================== */
@media (max-width:{bp}px){{
{scroll_release}

  /* ---- the panel: full height, no letterbox ----
     Desktop fits the canvas to the authored aspect, which on a phone
     leaves a dark band top and bottom. Below the breakpoint the canvas
     takes the whole viewport and the aspect goes; `container-type:size`
     is KEPT (henhouse switches to inline-size) because this deck writes
     vertical insets and stroke weights in `cqh`, which is invalid
     without a block axis -- switching would silently drop every padding
     and every rule weight in the deck.

     `height:100svh`, NOT `height:auto;min-height:100svh`. Measured: with
     auto+min-height the box still COMPUTES to 844px on a 390x844 probe,
     but the block axis is not DEFINITE, so container-query units against
     it resolve to zero -- `100cqh` measured 0px and the flanking rules'
     `border-top:0.1852cqh` computed to `0px`, i.e. they were in the
     layout at the right coordinates and painting nothing. Keeping
     container-type:size is necessary but not sufficient; the height has
     to be definite as well, or this is inline-size with extra steps. */
  #s1.slide{{align-items:stretch;min-height:100svh}}
  #s1 .canvas{{width:100%;height:100svh;aspect-ratio:auto;
    /* Sized against PANEL width. vw below the breakpoint, the authored
       cqw above -- the property is declared and consumed only in here,
       matching henhouse's --pad, so nothing is left declared-but-dead
       on desktop. Below the breakpoint the panel IS the viewport, so
       1vw and 1cqw are the same length; vw is written because the
       clamps also need a unit that survives the canvas going auto. */
    --edge:clamp(14px,4.5vw,26px);
    --logo-w:clamp(52px,14vw,88px);
    --script-w:min(70vw,400px);
    /* THE WORDMARK IS DERIVED FROM ITS BOX, NOT FROM A RAMP.
       Two rounds of vw tuning failed because a font-size ramp only fixes
       the TYPE SIZE; the RENDERED WIDTH is the type size times the face's
       set width, and that second factor is not ours. Measured width of
       "BEAUTY" per 1px of font-size: Bebas Neue 2.328, Roboto Condensed
       3.227 (+38.6%), Helvetica/Arial 4.001 (+71.9%). At the old capped
       120.4px that is 280.3px, 388.5px and 481.7px for the same slide --
       so a ramp tuned on Bebas overflows a 440px canvas by 41.7px the
       moment the deck falls back, which is the reported clip.
       Inverting it removes the guesswork: pick the width we want the word
       to occupy -- 90% of the lockup box, i.e. --beauty-fit -- and divide
       by the set-width ratio to get the type size. Rendered width is then
       0.90 x --script-w at EVERY width by construction, the same way
       Picture 1 fills its box by being 100% of it rather than by being
       given a size that happens to land there. */
    --beauty-ratio:2.328;
    --beauty-fit:0.90;
    --beauty-fs:calc(var(--script-w) * var(--beauty-fit) / var(--beauty-ratio));
    --kv-fs:clamp(11px,3.2vw,15px);
    --kv-inset:clamp(22px,7vw,44px);
    --kv-gap:clamp(52px,17vw,78px);
    --rule-w:clamp(26px,8vw,48px);
    /* The seam the lockup hangs off. Below 50% = above centre: an
       optically centred lockup reads as sunk on a tall phone because
       the eye weights the KEY VISUALS block at the bottom. */
    --lockup-axis:41%;
    --lockup-gap:clamp(6px,2vw,14px)}}

  /* ---- gradient: edge to edge, full height ----
     Authored as a 100% x 69.48% rect with a 359.994deg rotation. The
     rotation is a rounding artefact of the source and visibly shears a
     full-height box, so it goes. The gradient function itself is inline
     and untouched: its 0deg stop is transparent at the BOTTOM, which is
     what keeps KEY VISUALS legible under it -- this shape paints after
     KEY VISUALS in DOM order and rule 21 forbids fixing that with
     z-index. */
  #s1 [data-name="Google Shape;12;p2"]{{
    left:0!important;top:0!important;right:0!important;bottom:0!important;
    width:100%!important;height:100%!important;transform:none!important}}

  /* ---- logo: small, top right ----
     A media element, so it stays POSITIONED -- the static reflow is for
     the text column. Height comes from the authored aspect (66.20 x
     24.29pt) rather than a second magic number. */
  #s1 [data-name="Picture 3"]{{
    left:auto!important;right:var(--edge)!important;
    top:var(--edge)!important;bottom:auto!important;
    width:var(--logo-w)!important;height:auto!important;
    aspect-ratio:66.20/24.29}}

  /* Picture 2 is the same asset authored at left:153.12% -- off-canvas
     in the source. It is left exactly where it is: `overflow:hidden` on
     the canvas already clips it, and it is NOT hidden, because removing
     an authored shape from the mobile view would put the two breakpoints
     out of sync for the editor, which addresses images by index. */

  /* ---- the lockup: script over BEAUTY, centred ----
     Side by side on desktop. Both halves hang off one seam --
     --lockup-axis -- so neither needs to know the other's height and
     no wrapper is required: the script's BOTTOM sits on the seam, the
     word's TOP sits on it. */
  #s1 [data-name="Picture 1"]{{
    left:50%!important;right:auto!important;
    top:auto!important;
    bottom:calc(100% - var(--lockup-axis) + var(--lockup-gap)/2)!important;
    width:var(--script-w)!important;height:auto!important;
    aspect-ratio:352.37/182.52;
    transform:translateX(-50%)!important}}

  #s1 [data-name="Google Shape;131;p29"]{{
    left:50%!important;right:auto!important;
    top:calc(var(--lockup-axis) + var(--lockup-gap)/2)!important;
    bottom:auto!important;
    width:var(--script-w)!important;height:auto!important;
    padding:0!important;transform:translateX(-50%)!important}}
  /* A WORDMARK IS ONE WORD. build_css sets `.sh.tx{{overflow-wrap:anywhere}}`
     deck-wide because OOXML wrap="square" means break AT THE BOX EDGE, mid-word
     if a token does not fit -- correct for the authored body copy, fatal here:
     it converts "the box is 1px too narrow" into "BEA / UTY" rather than into
     an overflow anyone would see in review. Reported on iPhone 17 Pro Max
     (440 CSS px), which is the first width above the 430 this was tuned at.
     `nowrap` removes every break opportunity, so the wordmark cannot split at
     ANY width regardless of what the ramp does; overflow-wrap goes back to
     `normal` so the two rules cannot disagree. This is the guarantee -- the
     cap below is what keeps it from needing to overflow. */
  #s1 [data-name="Google Shape;131;p29"]{{
    white-space:nowrap!important;overflow-wrap:normal!important}}
  /* Size only. The authored stack is left exactly as roles.py emits it:
     the face is ground truth and a fallback substitution here was a
     mistake -- it changed WHICH typeface renders whenever Bebas Neue does
     not load, which is the state the reported device is in. */
  #s1 [data-name="Google Shape;131;p29"] p.t span{{
    font-size:var(--beauty-fs)!important}}

  /* ---- KEY VISUALS: letterspaced, centred, fixed bottom inset ----
     Anchored to the BOTTOM, while the lockup is anchored near the top.
     The gap between them is therefore the only elastic dimension on the
     slide: it absorbs the whole difference between a short phone and a
     tall one. That is why the lockup gets no top margin -- a fixed
     margin would move the elasticity into the wrong place and strand
     the lockup low on a tall screen. */
  #s1 [data-name="Google Shape;133;p29"]{{
    left:0!important;right:0!important;width:auto!important;
    top:auto!important;bottom:var(--kv-inset)!important;
    height:auto!important;padding:0!important}}
  #s1 [data-name="Google Shape;133;p29"] p.t span{{
    font-size:var(--kv-fs)!important;letter-spacing:.3em!important}}

  /* The two flanking rules ride the same bottom inset, offset up by
     roughly half a cap height so they sit on the text's optical midline,
     and out from centre by --kv-gap (half the set width of the
     letterspaced word plus air). */
  #s1 [data-name="Google Shape;134;p29"],
  #s1 [data-name="Google Shape;135;p29"]{{
    top:auto!important;
    bottom:calc(var(--kv-inset) + 0.42 * var(--kv-fs))!important;
    width:var(--rule-w)!important}}
  #s1 [data-name="Google Shape;134;p29"]{{
    left:auto!important;right:calc(50% + var(--kv-gap))!important}}
  #s1 [data-name="Google Shape;135;p29"]{{
    left:calc(50% + var(--kv-gap))!important;right:auto!important}}
}}
"""


def build_html(deck, man) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    secs, rail = [], []
    for sl in deck["slides"]:
        n = sl["n"]
        arch = roles.archetype(sl)
        shapes = [sh for sh in sl["shapes"]
                  if not (roles.SUPPRESS_REVIEW_STICKERS and sh.get("review_sticker"))
                  and not (roles.SUPPRESS_OCCLUDED_SHAPES and sh.get("occluded"))]
        body = "".join(shape_html(sh, man, W, H) for sh in shapes)
        # bg_from "none" means the layout declared <a:noFill/>: nothing paints
        # at any level, so the canvas is bare rather than showing the master.
        bg = sl.get("bg") or ("#FFFFFF" if sl.get("bg_from") == "none"
                              else deck["master_bg"])
        label = next((r["text"] for sh in shapes for p in (sh.get("paras") or [])
                      for r in p["runs"] if r.get("text", "").strip()), f"Slide {n}")
        rail.append(f'<li class="rail-item" data-target="s{n}">'
                    f'<span class="rail-num">{n:02d}</span>'
                    f'<span class="rail-label">{esc(label[:60])}</span></li>')
        secs.append(
            f'<section class="slide k-{arch}" id="s{n}" data-slide="{n}" '
            f'data-arch="{arch}" data-slide-name="{esc(label[:80])}" '
            f'aria-label="{esc(label[:80])}">'
            f'<div class="canvas" style="--bg:{bg}">{body}</div></section>')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(roles.DECK_TITLE)}</title>
<style>
{font_face_css(families=roles.FONT_FAMILIES)}
{build_css(deck)}
/* editor metadata, not part of the deck (rule 22) */
.rail[hidden]{{display:none !important}}
</style>
</head>
<body>
<nav class="rail" hidden aria-hidden="true"><ol>
{chr(10).join(rail)}
</ol></nav>
<main id="deck">
{chr(10).join(secs)}
</main>
</body>
</html>
"""


def main():
    paths = DeckPaths.for_deck(roles.SLUG, f"{SCR}/secret/raw", f"{SCR}/secret/shots")
    deck = json.loads((paths.out / "model.json").read_text())
    man = json.loads((paths.out / "asset_manifest.json").read_text())
    out = build_html(deck, man)
    (paths.out / "index.html").write_text(out)
    n = out.count('class="slide')
    print("index.html %.0f KB  sections=%d" % (len(out) / 1024, n))


if __name__ == "__main__":
    main()
