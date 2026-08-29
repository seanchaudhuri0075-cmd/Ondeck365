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


# Group A: BLANK-layout photo plates. Nine slides, one code path -- the block
# below is GENERATED from the model rather than hand-written per slide, which
# is what makes the group pass repeatable and keeps nine slides from drifting
# apart. Slide 13 was built by hand first and is now emitted from here; its
# measured numbers are unchanged, which is the regression check on the
# generator itself.
# Every slide whose content is media. Group A's nine plus the media splits
# (5-8, 11, 15, 18-20, 24) and the two video slides (28, 29).
PLATE_SLIDES = (5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20,
                22, 23, 24, 25, 26, 28, 29)

# The separator between slides, in the deck's OWN white. Measured, not chosen:
# every inset plate slide carries an authored white margin around its media,
# and the modal value is 10.14pt top and bottom (6 of 14 slides; the spread is
# 9.54-10.25pt). Two consecutive slides therefore show 10.14 + 10.14 = 20.28pt
# of white between them on the authored canvas, which against the 720pt width
# the plates are now sized by is 2.8167% -- 11.0px at 390, 12.1px at 430.
# The white is #FFFFFF, which is what `--bg` already resolves to on every
# BLANK-layout plate slide. Nothing here is invented: the band is the gap the
# deck already puts between two slides, carried across to a full-bleed stack.
BAND_VW = 20.28 / 720 * 100


def plate_css(sl, W: float) -> str:
    """Each image becomes its own full-bleed plate; badges travel with theirs."""
    n = sl["n"]
    ims = [sh for sh in sl["shapes"] if sh["type"] in ("image", "video")]
    # Badges only. A `rect` or `line` is not a badge: slides 28 and 29 carry
    # the deck's full-width gradient wash as a rect, and treating it as one
    # would size a 720pt background to 24px and park it over a video.
    tx = [sh for sh in sl["shapes"] if sh["type"] == "text"]
    bg = [sh for sh in sl["shapes"] if sh["type"] in ("rect", "line")]
    if not ims:
        return ""
    out = [f"  #s{n}.slide{{align-items:stretch;min-height:0;"
           f"justify-content:flex-start;"
           # The band rides on the slide, so it appears BETWEEN slides and
           # never between plates inside one -- the run stays continuous,
           # which is what makes a multi-plate slide read as one scroll.
           f"border-bottom:{BAND_VW:.4f}vw solid #FFFFFF}}",
           f"  #s{n} .canvas{{",
           "    --plate:100vw;",
           "    --badge:clamp(20px,6.2vw,28px);"]
    # DOM order is authored z order and is kept: no `order` is emitted anywhere,
    # per rule 41(v) -- on this deck it would re-rank the images past the
    # absolutely positioned badges and paint over them.
    cum = "0px"
    tops = []
    gaps = {}          # 1-based index k -> gap in vw BEFORE plate k+1
    for k, im in enumerate(ims, 1):
        ar = im["w"] / im["h"]
        out.append(f"    --ar{k}:{ar:.4f};")
        out.append(f"    --h{k}:calc(var(--plate) / var(--ar{k}));")
        out.append(f"    --top{k}:{cum};")
        tops.append(k)
        if k < len(ims):
            nxt = ims[k]
            # Authored VERTICAL gap only. Side-by-side images have none: their
            # horizontal gutter does not survive being stacked, and inventing a
            # vertical one would be inventing a gap the file does not have.
            gap = max(0.0, nxt["y"] - (im["y"] + im["h"]))
            # vw, NOT vh. The plates are sized by 100vw and every height on
            # them derives from that width through the authored aspect, so a
            # canvas-relative vertical distance has to travel in the same
            # unit. Written as vh it is measured against a viewport height the
            # plate stack has nothing to do with -- and since these slides set
            # min-height:0, there is no canvas height for it to mean anything
            # against either. Caught by a probe frame sized to the whole deck:
            # 2.6182vh became 776px instead of 22px and threw slide 5's fourth
            # badge clean off the slide. Same family as rule 41(m).
            gvw = gap / W * 100
            if gvw > 0.001:
                gaps[k] = gvw
            cum = (f"calc(var(--top{k}) + var(--h{k}))" if gap <= 0.01 else
                   f"calc(var(--top{k}) + var(--h{k}) + {gvw:.4f}vw)")
    out.append("    container-type:inline-size;")
    out.append("    width:100%;height:auto;min-height:0;aspect-ratio:auto;")
    out.append("    display:flex;flex-direction:column;align-items:stretch;")
    out.append("    padding:0}")
    # position:relative, never static -- rule 41(u): `.cropw` is
    # absolute;inset:0 and needs this shape to stay its containing block.
    # The wash rect behind the videos on 28/29 has no job once each video is
    # its own full-bleed plate: it is a background for a composed spread, and
    # there is no spread left. It is a rect, not an image, so nothing in the
    # editor's index-addressed image list moves when it goes.
    for b in bg:
        out.append(f'  #s{n} [data-name="{esc(b["name"])}"]{{display:none!important}}')
    out.append(f"  #s{n} .sh.im,#s{n} .sh.vid{{position:relative!important;"
               "inset:auto!important;")
    out.append("    left:auto!important;top:auto!important;")
    out.append("    width:100%!important;height:auto!important;")
    out.append("    transform:none!important;flex:0 0 auto}")
    for k, im in enumerate(ims, 1):
        # The authored gap becomes a real gap between the plates, not merely a
        # term in the badge's coordinate chain: if it only shifted the badge,
        # the badge would sit where no plate is. Plates with no authored gap
        # get none -- a run inside one slide stays continuous.
        mt = f";margin-top:{gaps[k - 1]:.4f}vw" if (k - 1) in gaps else ""
        out.append(f'  #s{n} [data-name="{esc(im["name"])}"]'
                   f"{{aspect-ratio:var(--ar{k}){mt}}}")
    if tx:
        out.append(f"  #s{n} .sh.tx{{width:var(--badge)!important;"
                   "height:var(--badge)!important;")
        out.append("    padding:0!important;right:auto!important;"
                   "bottom:auto!important}")
    for b in tx:
        cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        host, hk = None, None
        # The badge's host is the TOPMOST image containing its centre -- on a
        # slide whose images overlap (26) that is the one it visually sits on.
        for k, im in enumerate(ims, 1):
            if im["x"] <= cx <= im["x"] + im["w"] and im["y"] <= cy <= im["y"] + im["h"]:
                host, hk = im, k
        if host is None:                       # nearest by centre distance
            hk, host = min(enumerate(ims, 1),
                           key=lambda t: abs(cx - (t[1]["x"] + t[1]["w"] / 2)))
        rx = (cx - host["x"]) / host["w"]
        ry = (cy - host["y"]) / host["h"]
        out.append(f'  #s{n} [data-name="{esc(b["name"])}"]{{')
        out.append(f"    left:calc({rx:.4f} * var(--plate) - var(--badge) / 2)!important;")
        out.append(f"    top:calc(var(--top{hk}) + {ry:.4f} * var(--h{hk})"
                   " - var(--badge) / 2)!important}")
    if tx:
        out.append(f"  #s{n} .sh.tx p.t span"
                   "{font-size:calc(var(--badge) * 0.44)!important}")
    return "\n".join(out)


def build_css(deck) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    plate_blocks = "\n\n".join(
        plate_css(sl, W) for sl in deck["slides"] if sl["n"] in PLATE_SLIDES)
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

   Slides 1 and 2 so far. Everything is scoped to #s1 / #s2; slides 3-31
   keep their desktop canvas untouched below the breakpoint until each is
   done in its own pass.
   ================================================================== */
@media (max-width:{bp}px){{
{scroll_release}

  /* ==================================================================
     DECK-WIDE READING SIZE -- a target X-HEIGHT, not a target px.
     This is the vertical twin of --head-fs's inversion: there, a type size
     was derived from the width the word had to occupy, because rendered
     width is size times the face's SET WIDTH and that second factor is not
     ours. The same is true of reading size. **A px size is not a reading
     size.** Perceived size is x-height, and the two faces carrying body
     copy in this deck differ by 31% on it -- measured from the deck's own
     embedded fonts, OS/2 sxHeight over unitsPerEm:

         Darker Grotesque  0.4040   <- slide 2's subtitle
         Roboto Condensed  0.5283   <- slides 3, 4, 9, 14, 21 and the rest
         Liberation Sans   0.5283   (Helvetica/Arial metrics, for reference)

     Slide 2's body under the old `clamp(14px,4vw,18px)` computed 15.6px at
     390, which in Darker Grotesque is 6.30px of x-height -- the reading
     size of 11.9px Helvetica. That is the reported defect, and no px ramp
     could have fixed it for both faces at once: the same px number reads
     31% smaller in Darker Grotesque than in Roboto Condensed.

     --read-x belongs to the DECK. Each face divides it by its own ratio,
     so two shapes in two faces at two different px sizes read the SAME.
     8.89px at 390 is the x-height of 16.8px Helvetica, i.e. a hair under
     the iOS default body size.

     DECLARED HERE, CONSUMED PER SLIDE. Slides 3-31 have not had their
     reflow pass yet: below the breakpoint they still show the authored
     16:9 canvas letterboxed to 390x219, where the authored cqw sizes are
     correct FOR THAT CANVAS and this token is roughly 2.5-3.3x too large
     to fit their boxes. A custom property paints nothing until something
     reads it, so this is inert on every slide but slide 2 -- and it is the
     value each of those slides should adopt AS IT IS REFLOWED, not before.
     ================================================================== */
  .canvas{{
    --read-x:clamp(8.0px,2.28vw,9.6px);
    --x-darker-grotesque:0.4040;
    --x-roboto-condensed:0.5283}}

  /* ==================================================================
     THE LINE-BOX STRUT -- rule 41(s).
     `p.t` carries a unitless line-height but NO font-size of its own, so
     its strut is computed against the 16px it inherits from `body`: a
     FIXED PIXEL leading that does not scale with the canvas, sitting under
     text that does. A line box is the taller of the strut and its inline
     content, so whichever is larger silently takes over.

     Above the breakpoint the cqw text is the larger of the two and wins,
     which is why this never appeared in desktop review. Below it the canvas
     shrinks, every cqw size drops under 16px, and the STRUT wins on every
     paragraph in the deck. Measured on slide 4 at 390: eight paragraphs of
     39.94px each instead of 12.16px -- 320px of ink on a 219px canvas,
     text running clean off the slide. Setting `p.t{{font-size:4.875px}}`,
     the size of its own span, returned it to 12.16px, which is the proof.

     `font-size:0` collapses the strut to nothing so the line box is decided
     by the spans that actually carry the text. Checked before writing it:
     all 149 paragraphs put their text inside spans, none is empty, no `<br>`
     stands without content beside it, and no two spans are separated by
     whitespace that a zero font-size would collapse -- so no line box loses
     its only content. The one `em` length in the deck (`letter-spacing:.3em`)
     sits on a span and resolves against the span's own size.

     SCOPE: this is inside the breakpoint, so the standing test still holds.
     THE SAME DEFECT IS STILL LIVE ON DESKTOP between the breakpoint and the
     width at which each run outgrows the strut -- for slide 4's 1.25cqw runs
     at line-height 2.4961 that is a canvas width of 39.94 / (0.0125 x
     2.4961) = 1280px, so 820-1280px is unfixed. Fixing it there means
     emitting a font-size on `p.t` from the paragraph's own runs, which
     changes the desktop build and moves the standing test's baseline. That
     is a separate change and is NOT made here.
     ================================================================== */
  .sh.tx p.t{{font-size:0}}

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

  /* ==================================================================
     SLIDE 2 -- SECTION_HEADER: composited hero, headline, body.
     Same rules as slide 1: scoped to the slide, media stays positioned,
     no wrapper, no mobile-only duplicate of any img.
     ================================================================== */
  #s2.slide{{align-items:stretch;min-height:100svh}}
  #s2 .canvas{{width:100%;height:100svh;aspect-ratio:auto;
    --edge:clamp(14px,4.5vw,26px);
    /* ONE column, shared by headline and body, so their centres and their
       measure agree without either knowing about the other. Capped so the
       headline does not run away at the top of the range. */
    --col:min(calc(100vw - 2 * var(--edge)),460px);
    /* Hero height DERIVED from the authored aspect (722.36 x 246.62pt)
       rather than typed, so the stack under it stays correct if the asset
       is ever re-exported at a different size. */
    --hero-h:calc(100vw * 246.62070866141732 / 722.3566929133858);

    /* THE HEADLINE IS DERIVED FROM ITS COLUMN, not from a vw ramp -- the
       slide 1 construction, applied here because rule 41(r) says to do it
       BEFORE the break appears. Advance width of "OBJECTIVE" per 1px of
       font-size, read from this deck's own embedded faces: Anton 3.8198,
       Roboto Condensed 4.5225 (+18.4%), Liberation Sans i.e. Helvetica and
       Arial metrics 5.5566 (+45.5%). A ramp tuned on Anton overflows the
       column by 45% the moment the deck falls back to the system stack, so
       the size is computed from the width we want the word to OCCUPY.
       Rendered width is --head-fit x --col at every viewport by
       construction. (Cross-check: the same measurement reproduces slide
       1's published BEAUTY numbers -- Bebas 2.328, Roboto Condensed 3.227,
       Helvetica 4.001 -- so the ratios are on the same footing.) */
    --head-ratio:3.8198;
    --head-fit:0.82;
    --head-fs:calc(var(--col) * var(--head-fit) / var(--head-ratio));
    /* The authored line-height, restated as a property so the line box and
       the --head-h that predicts it below cannot drift apart. */
    --head-lh:0.9694;
    --head-h:calc(var(--head-fs) * var(--head-lh));
    /* Body copy is sized from the DECK-WIDE reading size, not from a px
       ramp of its own -- see the --read-x block above the slide 1 rules.
       Darker Grotesque is this shape's face, so it divides by that face's
       own x-height ratio: at 390 the token is 8.89px of x-height, which is
       22.01px of Darker Grotesque. */
    --body-fs:calc(var(--read-x) / var(--x-darker-grotesque));

    /* THE HEADLINE-TO-BODY GAP IS STATED, NOT INHERITED. The desktop boxes
       OVERLAP: Title 1 ends at 350.92pt, Subtitle 2 starts at 336.03pt --
       14.90pt of box overlap -- and the ink overlaps too, because Anton at
       96pt sets a 93.06pt line box inside a 77.55pt inner height and the
       centred anchor spills it 7.75pt past each edge. Inheriting that stack
       on a phone would inherit the collision. Desktop is NOT touched: this
       is inside the breakpoint and the authored overlap stays authored. */
    --hero-gap:clamp(20px,6vw,36px);
    --head-gap:clamp(12px,3.6vw,22px);
    /* Where the headline starts. `max()` is the guard, not decoration: the
       46% keeps the pair optically placed on a tall phone instead of
       stranded under the hero, and the hero-derived term wins on a short or
       wide viewport, where 46% would put the headline INSIDE the image. The
       elastic dimension is therefore the air between hero and headline --
       the same choice slide 1 makes between its lockup and KEY VISUALS. */
    --stack-top:max(calc(var(--hero-h) + var(--hero-gap)),46%)}}

  /* ---- the wash: edge to edge ----
     Authored as a 100% x 80.31% rect at 179.994deg. Unlike slide 1's, this
     rotation is NOT a rounding artefact of zero -- it is 180deg, and it is
     LOAD-BEARING: the inline gradient puts its blue stop at 0deg, i.e. at
     the top of the element, so the rotation is the only thing placing the
     wash at the BOTTOM of the slide. Dropping it, as slide 1 drops its
     359.994deg, would flip the gradient end for end. Normalised to a flat
     180deg -- a half turn maps a full-bleed rect onto itself, so there is
     nothing left to shear -- and kept. */
  #s2 [data-name="Google Shape;16;p3"]{{
    left:0!important;top:0!important;right:0!important;bottom:0!important;
    width:100%!important;height:100%!important;
    transform:rotate(180deg)!important}}

  /* ---- hero: full bleed at the top ----
     ONE asset. The three product panels are composited INSIDE it, so there
     is nothing to split without cutting new files, which rule 31 forbids.
     Sized by `aspect-ratio` rather than by --hero-h so the box matches the
     image exactly and the deck-wide `object-fit:cover` has nothing to trim
     -- a height that missed by a pixel would crop the outer two panels,
     which is the one failure this slide cannot afford. It stays POSITIONED,
     like every other media element here. */
  #s2 [data-name="Picture 4"]{{
    left:0!important;right:0!important;top:0!important;bottom:auto!important;
    width:100%!important;height:auto!important;
    aspect-ratio:722.3566929133858/246.62070866141732}}

  /* ---- headline: below the hero, one line, derived size ---- */
  #s2 [data-name="Title 1"]{{
    left:50%!important;right:auto!important;
    top:var(--stack-top)!important;bottom:auto!important;
    width:var(--col)!important;height:auto!important;
    padding:0!important;transform:translateX(-50%)!important}}
  /* RULE 41(r), APPLIED BEFORE IT BITES. build_css sets
     `.sh.tx{{overflow-wrap:anywhere}}` deck-wide -- correct for the authored
     wrap="square" body copy, hazardous here: OBJECTIVE is one word, and a
     1px overflow would come back as OBJECT / IVE, which reads as
     typesetting rather than as a bug. `nowrap` removes every break
     opportunity at any width; `overflow-wrap:normal` stops the two
     declarations disagreeing. --head-fs above is what keeps it from
     NEEDING to overflow; this is the guarantee that it cannot split if it
     ever does. Declared on the shape, which is what carries `anywhere`. */
  #s2 [data-name="Title 1"]{{
    white-space:nowrap!important;overflow-wrap:normal!important}}
  #s2 [data-name="Title 1"] p.t{{line-height:var(--head-lh)!important}}
  #s2 [data-name="Title 1"] p.t span{{font-size:var(--head-fs)!important}}

  /* ---- body: below the headline ----
     ALIGNMENT IS ALREADY CORRECT AND IS DELIBERATELY NOT RESTATED. The
     paragraph resolves to algn="ctr" -- through the layout's subTitle
     placeholder, since slide2.xml states no algn of its own -- and
     para_html emits `text-align:center` INLINE on p.t, so the body is
     centred on both breakpoints already. `algn="just"` appears nowhere in
     the source deck. Writing a centring override here would be a rule that
     restates the value it is given, and the next reader would have to
     disprove it before touching anything.
     The hanging indent DOES go: marL 36pt / indent -25pt with
     `bullet_suppressed` true and `bullet` None is a marker indent with no
     marker, and on a centred paragraph it pushes the block right while
     pulling line 1 left, which reads as a centring bug. Leading is left
     exactly as authored (rule 14). */
  #s2 [data-name="Subtitle 2"]{{
    left:50%!important;right:auto!important;
    top:calc(var(--stack-top) + var(--head-h) + var(--head-gap))!important;
    bottom:auto!important;
    width:var(--col)!important;height:auto!important;
    padding:0!important;transform:translateX(-50%)!important}}
  #s2 [data-name="Subtitle 2"] p.t{{
    padding-left:0!important;text-indent:0!important}}
  #s2 [data-name="Subtitle 2"] p.t span{{font-size:var(--body-fs)!important}}
  /* ==================================================================
     SLIDE 3 -- MODE B: a FLOWING panel, not a positioned canvas.
     Slides 1 and 2 kept the authored canvas and moved shapes inside it.
     This one cannot: it is a 2x2 of numeral / title / description, and a
     2x2 on a phone is a 1x4 -- the rows have to stack and the panel has to
     grow with them. The headroom measurement is what forces it: on the
     letterbox canvas slide 3's description boxes top out at 8.46-9.56px
     against the 16.83px the deck's reading size asks for, so no amount of
     resizing inside the authored boxes reaches a legible size. The boxes
     themselves have to be re-laid, which is what Mode B does.
     ================================================================== */
  #s3.slide{{align-items:stretch;min-height:100svh}}

  /* container-type:inline-size, and ONLY on this slide.
     A flowing panel needs an INDEFINITE block axis; `container-type:size`
     forbids exactly that, because size containment makes the box's height
     independent of its contents. Slide 1's comment explains why the deck as
     a whole must not switch -- every cqh value silently retargets. Slide 3
     can, because it has only two kinds of cqh value and both are overridden
     below: the four numeral paddings go to 0 with the static reflow, and the
     two flanking rules are given an explicit border-width. cqw is NOT
     affected -- inline-size still supplies the inline axis -- so any
     authored type left unoverridden keeps resolving as before. */
  #s3 .canvas{{
    --edge3:clamp(18px,5.5vw,30px);
    --pad3:clamp(26px,7vw,44px);
    --row-gap:clamp(22px,6vw,34px);
    --hook-fs:clamp(34px,10.5vw,54px);
    --num-fs:clamp(30px,9vw,46px);
    --ttl-fs:clamp(20px,6vw,29px);
    /* the reading size, adopted now that this slide is reflowed */
    --desc-fs:calc(var(--read-x) / var(--x-roboto-condensed));
    /* Roboto Condensed digits are TABULAR -- 0.4937em each, so every
       two-digit numeral is exactly 0.9873em wide and all four rows share one
       offset. The title starts at 0.72 of that, so it overlaps the numeral's
       right quarter; authored, the title box starts 32.3% into the numeral
       box, which is the same relationship read off the source. */
    --num-ink:calc(var(--num-fs) * 0.9873);
    --ttl-indent:calc(var(--num-ink) * 0.72);
    --ttl-rise:calc(var(--num-fs) * 0.44);
    /* ---- the photo BAND ----
       svh, not %: this canvas has `height:auto` so a percentage height
       resolves to auto (rule 22's note), and the band would collapse.
       46svh is the share the band wants; the second term is the floor guard
       -- measured, the four rows plus their gap and the bottom padding need
       442px at 375x667, the shortest phone supported, so the band may not
       take more than what is left. min() picks whichever binds: 374px at
       390x844, 429px at 430x932, 197px at 375x667, all fitting without
       scroll. */
    --band-h:min(46svh,calc(100svh - 470px));
    --head-m:clamp(10px,3vw,16px);
    /* the header's own height, stated so --band-slack can place it: two 1px
       rules, their two margins, and one line of --hook-fs at 1.02. */
    --head-h3:calc(2px + 2 * var(--head-m) + var(--hook-fs) * 1.02);
    /* half the air left in the band once the header is in it. Used TWICE --
       once to centre the header on the band, once to drop the first row past
       the band's bottom edge -- so the two cannot drift apart. */
    --band-slack:calc((var(--band-h) - var(--pad3) - var(--head-h3)) / 2);
    container-type:inline-size;
    width:100%;height:auto;min-height:100svh;aspect-ratio:auto;
    display:flex;flex-direction:column;align-items:flex-start;
    padding:var(--pad3) var(--edge3) calc(var(--pad3) * 1.15)}}

  /* ---- the photo is a BAND, at full strength ----
     Both earlier attempts put the text ON the photograph and then tried to
     make a moving ground safe -- first a flat scrim, then per-element halos.
     Neither can work: on a tall panel the photo is behind every line, so each
     line lands on a different tone, and no per-element treatment fixes a
     ground that moves. The photo now occupies the upper band ONLY, the rows
     sit below it on the bare authored blue, and nothing overlays anything
     except VISUAL HOOKS and its two rules, which are white and belong on a
     photograph.

     THE 22% WASH IS DROPPED HERE. It is not decoration: a wash exists to make
     a photograph safe to put text on, and no text sits on this one any more.
     Keeping it would spend the picture for a service nothing is asking for.
     At the authored 22% the photo carries 33.4% of its own tonal range; at
     0.51 of scrim it carried 8.2%; at full strength it carries all of it.
     This is the same reasoning slide 4 already applies -- its photo is
     opacity 1, because its text sits beside the photo rather than on it.

     object-position 92%, and the 92 is DERIVED, not picked. The subject --
     most-saturated columns x 1504-1632 -- centres at x=1568, i.e. 81.7% of
     the image width. object-position is a percentage of the OVERFLOW, not of
     the image, so the number that centres her depends on the box: it was
     85.6% for the full-height panel and is 92% for this band. That is rule
     41(t) restated -- the position has to be re-solved whenever the box
     changes, and only the SUBJECT's 81.7% travels between them. Checked
     across the range: at 390 the band shows source x 1325-1805, at 430
     x 1305-1766, at 375 x 961-1837; she is inside all three. */
  #s3 [data-name="Picture 2"]{{
    position:absolute!important;left:0!important;right:0!important;
    top:0!important;bottom:auto!important;
    width:auto!important;height:var(--band-h)!important;
    opacity:1!important}}
  #s3 [data-name="Picture 2"]>.cropw{{opacity:1}}
  #s3 [data-name="Picture 2"]>.cropw>img{{
    position:absolute!important;inset:0!important;
    left:auto!important;top:auto!important;
    width:100%!important;height:100%!important;
    object-fit:cover!important;object-position:92% 50%}}

  /* ==================================================================
     NO SCRIM AND NO HALO. READ THIS BEFORE ADDING EITHER.
     A flat rgba(0,32,96,0.51) ::after shipped here first, then per-element
     text-shadow halos replaced it. Both were removed, and both failed for the
     same reason: they assumed the text had to overlay the photograph.

     The scrim was also solved against the WRONG PICTURE. Its alpha was tuned
     while object-position was 66.4% -- the authored srcRect midpoint -- which
     showed sky and a bridge railing rather than the subject at 81.7%. That
     region is bright and near-featureless, so it flattered the arithmetic
     twice: it made white text look like the only problem, and it left the
     navy titles on a light ground where they still passed at 3.23. Reframe
     onto the subject and hold the same 0.51 and those titles fall to 2.57.
     The scrim passed a test taken over a featureless bright region; it never
     passed over the photograph. And it cost the picture: p1-p99 luminance of
     the photo region went 0.8132 source -> 0.2717 at the authored 22% ->
     0.0663 under the scrim, i.e. 8.2% of the original, because a flat scrim
     multiplies whatever survives by (1 - alpha). The knob that buys text
     contrast is the same knob that spends the image.

     The halos then read on device as artefact rather than lift -- a grey
     outline on VISUAL HOOKS, dark fringing on the descriptions -- and they
     could not help the titles at all, which sat on her face in row 1 and her
     shirt in row 4. One navy cannot serve two grounds that far apart.
     ================================================================== */

  /* ---- the static reflow, TEXT COLUMN ONLY ----
     rule 22's two mechanics: shapes go static, and every inline left/top is
     neutralised or a positioned ancestor re-applies it as a flow offset. The
     image is deliberately not in this selector -- it is the ground, and it
     stays positioned. */
  #s3 .sh.tx,#s3 .sh.ln{{
    position:static!important;inset:auto!important;
    left:auto!important;top:auto!important;
    width:auto!important;height:auto!important;
    transform:none!important;padding:0!important;
    flex:0 0 auto;max-width:100%}}

  /* ---- header: the two authored rules keep their job as a divider ----
     They flank VISUAL HOOKS horizontally on the canvas. In a column there is
     no beside, so one goes above and one below -- both shapes kept, neither
     hidden. border-top is restated in px because this canvas is inline-size
     and the authored 0.1852cqh no longer has a block axis to resolve
     against. */
  #s3 .sh.ln{{align-self:center;width:clamp(38px,11vw,58px)!important;
    border-top-width:1px!important}}
  /* position:relative, and it is LOAD-BEARING, not tidiness. The static
     reflow above sets `position:static` on every text shape; the photo is
     `position:absolute`. A positioned element paints above a non-positioned
     one whatever the DOM order, so the band would cover these three outright
     -- the same trap henhouse's render.py records against its own captions.
     Making them relative puts them back in the positioned set, where DOM
     order decides, and the photo is first in DOM. Still no z-index (rule 21).
     `!important` IS REQUIRED and is not decoration: the static reflow above
     declares `position:static!important`, so a plain `position:relative` here
     loses to it and the header goes on painting underneath the band. It needs
     to WIN the cascade, not out-specify it -- which is the same note henhouse
     leaves against its own captions, and which was written into this comment
     one round before the declaration actually obeyed it.
     --band-slack centres the header on the band; the first row below reuses
     the same term, so the two cannot drift. */
  /* The selector carries `.sh.tx` / `.sh.ln` for a reason: BOTH declarations
     are `!important`, so importance no longer separates them and SPECIFICITY
     decides. `#s3 .sh.tx` is (1,2,0); `#s3 [data-name=...]` is only (1,1,0),
     so the plain attribute selector loses even with !important on it and the
     header keeps painting under the band. Adding the class puts this at
     (1,3,0), which wins. !important is necessary and was not sufficient. */
  #s3 .sh.ln[data-name="Google Shape;162;p31"],
  #s3 .sh.tx[data-name="Google Shape;152;p31"],
  #s3 .sh.ln[data-name="Google Shape;161;p31"]{{position:relative!important}}
  #s3 [data-name="Google Shape;162;p31"]{{order:1;
    margin-top:var(--band-slack);margin-bottom:var(--head-m)}}
  #s3 [data-name="Google Shape;152;p31"]{{order:2;align-self:center}}
  #s3 [data-name="Google Shape;161;p31"]{{order:3;margin-top:var(--head-m)}}
  #s3 [data-name="Google Shape;152;p31"] p.t span{{
    font-size:var(--hook-fs)!important;line-height:1.02!important}}
  /* rule 41(r), the two-word case. VISUAL HOOKS may break at its SPACE --
     that is ordinary wrapping and costs nothing. What it must not do is
     break inside a word, which the deck-wide overflow-wrap:anywhere would
     do the moment the pair is 1px too wide. `normal` removes the mid-word
     break without removing the space break, so nowrap is not needed here
     and would only force an overflow. */
  #s3 [data-name="Google Shape;152;p31"]{{overflow-wrap:normal!important}}

  #s3 [data-name="Google Shape;151;p31"]{{order:10}}
  #s3 [data-name="Google Shape;160;p31"]{{order:11}}
  #s3 [data-name="Google Shape;153;p31"]{{order:12}}
  #s3 [data-name="Google Shape;150;p31"]{{order:20}}
  #s3 [data-name="Google Shape;154;p31"]{{order:21}}
  #s3 [data-name="Google Shape;155;p31"]{{order:22}}
  #s3 [data-name="Google Shape;149;p31"]{{order:30}}
  #s3 [data-name="Google Shape;156;p31"]{{order:31}}
  #s3 [data-name="Google Shape;158;p31"]{{order:32}}
  #s3 [data-name="Google Shape;148;p31"]{{order:40}}
  #s3 [data-name="Google Shape;157;p31"]{{order:41}}
  #s3 [data-name="Google Shape;159;p31"]{{order:42}}

  /* ---- numeral: sets the row, and the title rides its right edge ----
     The pair is kept by FLOW, not by positioning: a wrapper is forbidden,
     and `position:absolute` cannot resolve against a SIBLING, which is all
     the numeral ever is to its title. Negative margins give the same
     relationship with no new element -- the title rises by 0.44 of the
     numeral's line box and indents by 0.72 of its ink width, so it overlaps
     the numeral's right quarter exactly as authored. */
  #s3 [data-name="Google Shape;151;p31"],
  #s3 [data-name="Google Shape;150;p31"],
  #s3 [data-name="Google Shape;149;p31"],
  #s3 [data-name="Google Shape;148;p31"]{{
    margin-top:var(--row-gap)}}
  /* row 1 starts BELOW the band. --band-slack + --row-gap is exactly the
     distance from the header's flow position to the band's bottom edge plus
     one gap, which is why the same term appears here and on the header. */
  #s3 [data-name="Google Shape;151;p31"]{{
    margin-top:calc(var(--band-slack) + var(--row-gap))}}
  #s3 [data-name="Google Shape;151;p31"] p.t,
  #s3 [data-name="Google Shape;150;p31"] p.t,
  #s3 [data-name="Google Shape;149;p31"] p.t,
  #s3 [data-name="Google Shape;148;p31"] p.t{{text-align:left!important}}
  #s3 [data-name="Google Shape;151;p31"] p.t span,
  #s3 [data-name="Google Shape;150;p31"] p.t span,
  #s3 [data-name="Google Shape;149;p31"] p.t span,
  #s3 [data-name="Google Shape;148;p31"] p.t span{{
    font-size:var(--num-fs)!important;line-height:1!important}}

  #s3 [data-name="Google Shape;160;p31"],
  #s3 [data-name="Google Shape;154;p31"],
  #s3 [data-name="Google Shape;156;p31"],
  #s3 [data-name="Google Shape;157;p31"]{{
    margin-top:calc(-1 * var(--ttl-rise));
    margin-left:var(--ttl-indent)}}
  #s3 [data-name="Google Shape;160;p31"] p.t,
  #s3 [data-name="Google Shape;154;p31"] p.t,
  #s3 [data-name="Google Shape;156;p31"] p.t,
  #s3 [data-name="Google Shape;157;p31"] p.t{{text-align:left!important}}
  #s3 [data-name="Google Shape;160;p31"] p.t span,
  #s3 [data-name="Google Shape;154;p31"] p.t span,
  #s3 [data-name="Google Shape;156;p31"] p.t span,
  #s3 [data-name="Google Shape;157;p31"] p.t span{{
    font-size:var(--ttl-fs)!important;line-height:1.04!important}}

  /* ---- description: the plain static reflow, left ranged, NAVY ----
     #002060, not the authored #FFFFFF. READ THIS BEFORE REVERTING IT.
     On this same #A7C6ED panel, SLIDE 4 PUTS ITS READING TEXT IN NAVY: its
     Subtitle 4 body is #002060 (8.68 against the blue), its display title is
     white (1.76) and its numeral is white at 50% (1.34). That is the deck's
     convention -- dark text reads, light text is tonal. Slide 3 INVERTS it,
     white body and navy titles, and that inversion is the whole reason the
     white body had no solution on the blue: white on #A7C6ED is 1.76, which
     no layout fixes and no scrim reaches without destroying the photograph.
     Two rounds went into building a dark ground under white body copy on a
     slide whose own sibling solves it by making the body dark. Taking slide
     4's colour is not inventing one; it is adopting the deck's.
     The titles were already #002060 and are untouched. The numerals stay
     white at 50% -- 1.34, failing, and DELIBERATELY so: that is exactly what
     slide 4's numeral scores, because it is an authored decorative mark and
     not something anyone reads.
     Leading is left exactly as authored (rule 14). The authored hanging
     indent goes, as on slide 2: marL/indent with bullet_suppressed true is a
     marker indent with no marker. */
  #s3 [data-name="Google Shape;153;p31"],
  #s3 [data-name="Google Shape;155;p31"],
  #s3 [data-name="Google Shape;158;p31"],
  #s3 [data-name="Google Shape;159;p31"]{{
    margin-top:clamp(6px,1.8vw,10px);max-width:34em}}
  #s3 [data-name="Google Shape;153;p31"] p.t,
  #s3 [data-name="Google Shape;155;p31"] p.t,
  #s3 [data-name="Google Shape;158;p31"] p.t,
  #s3 [data-name="Google Shape;159;p31"] p.t{{
    text-align:left!important;padding-left:0!important;text-indent:0!important}}
  #s3 [data-name="Google Shape;153;p31"] p.t span,
  #s3 [data-name="Google Shape;155;p31"] p.t span,
  #s3 [data-name="Google Shape;158;p31"] p.t span,
  #s3 [data-name="Google Shape;159;p31"] p.t span{{color:#002060!important}}
  #s3 [data-name="Google Shape;153;p31"] p.t span,
  #s3 [data-name="Google Shape;155;p31"] p.t span,
  #s3 [data-name="Google Shape;158;p31"] p.t span,
  #s3 [data-name="Google Shape;159;p31"] p.t span{{font-size:var(--desc-fs)!important}}

  /* ==================================================================
     GROUP A -- EACH IMAGE IS ITS OWN FULL-BLEED PLATE.
     Ten slides' worth of rules below this comment are GENERATED by
     plate_css() from the model, one code path for all nine, so they
     cannot drift apart slide by slide.
     Group A (10, 12, 13, 16, 17, 22, 23, 25, 26) is BLANK-layout with no
     title, no description and no prose: one to three photographs plus Oval
     badges carrying a single letter. Slide 3's shape does not transfer --
     there is no reading text to move onto the blue -- but its PRINCIPLE does:
     let the photograph read at full strength, and adopt what a sibling
     already solves rather than inventing a treatment. The badge is
     `border-radius:50%;background:#1665BA` with a white glyph, i.e. it
     CARRIES ITS OWN GROUND (5.83 against that fill on any photograph). That
     is the thing the slide 3 scrim and halos both failed at, already solved
     in the authored file. So nothing is added here: no scrim, no halo, no
     recolour.

     THE MULTI-IMAGE COMPOSITION IS NOT PRESERVED AS A UNIT. Two images
     become two plates, three become three, each edge to edge and stacked.
     That also settles slide 26: three images is three plates, not a Group D
     screen-break question.

     PANEL MODEL -- these are NOT viewport-height panels.
     `min-height:0` on both the section and the canvas, deliberately, against
     the deck-wide `section.slide{{min-height:100svh}}`. A plate is exactly as
     tall as its own photograph: slide 23's single 1:1 image would otherwise
     sit in a 844px box with 454px of dead ground under it, and the run of
     plates would read as a series of viewport pages rather than one
     continuous scroll. Height comes from the image and nothing else.

     SCROLL-SNAP IS OFF ENTIRELY, NOT PROXIMITY, and it already is: deckkit's
     mobile_scroll_release sets `#deck{{scroll-snap-type:none}}` for the whole
     deck below the breakpoint. That is the correct setting here rather than
     something to revisit -- `proximity` would still re-target a fling toward
     a slide edge, and with plates of unequal height and no viewport-height
     floor there is no meaningful page boundary to snap TO. The authored
     `scroll-snap-align:start` stays on the section and is inert without a
     snap container, exactly as mobile_scroll_release documents.
     ================================================================== */
{plate_blocks}

  /* ==================================================================
     SLIDE 9 -- GROUP B (4, 9, 14, 21): photo band, text on the blue.
     Slide 3's ethos, not its layout. The photograph takes a full-bleed band
     at its OWN authored aspect (0.9260, the authored 52.09% x 100% box), so
     unlike slide 3 there is no cover-crop and rule 41(t) never arises -- the
     whole frame shows. Everything else sits below it on the authored blue.
     Nothing overlays a moving ground; no scrim, no halo.

     NO COLOUR IS CHANGED ON THIS SLIDE, and that is the finding rather than
     an omission. Slide 3's descriptions went navy because slide 4 authors ITS
     reading text navy; here the reading text ALREADY IS #002060, measuring
     8.68 on #A7C6ED. Adopting the sibling's convention means leaving it
     exactly as authored. Everything else is display or decoration and keeps
     its authored white by the same rule slide 3's numerals keep theirs:
         Subtitle 4   #002060   8.68  reading text  -- correct as authored
         Title 3      #FFFFFF   1.76  display type  -- decorative, kept
         TextBox 5    white 50% 1.34  numeral       -- decorative, kept
         Oval A-H     #FFFFFF on #1665BA  5.83      -- carries its own ground
     The badges are the same self-grounded disc as Group A's, so they need
     nothing on any ground.

     GROUND: rule 33, carry the ground and drop the geometry. The authored
     panel is a rect filling the right 50%; on a phone there is no right half,
     so its FILL becomes the canvas background and the rect itself goes. The
     colour is the deck's own #A7C6ED, not a chosen one.

     THE BOXES ARE RE-LAID, NOT RESIZED. The earlier headroom table put this
     slide's description at 4.92px maximum inside its authored box against the
     16.83px the deck's reading size asks for -- 0.29x, no headroom at all. So
     the text block is rebuilt from the top rather than scaled: every offset
     below is arithmetic from the band, and nothing depends on flow.
     ================================================================== */
  #s9.slide{{align-items:stretch;min-height:100svh}}
  #s9 .canvas{{
    --edge9:clamp(16px,5vw,26px);
    --pad9:clamp(18px,5vw,28px);
    --gutter9:clamp(8px,2.4vw,12px);
    --photo-h:calc(100vw / 0.9260);
    --num-fs:clamp(28px,8.4vw,40px);
    --ttl-fs:clamp(30px,9.2vw,44px);
    --desc-fs:calc(var(--read-x) / var(--x-roboto-condensed));
    --badge9:clamp(18px,5.4vw,24px);
    --gap1:clamp(8px,2.4vw,14px);
    --gap2:clamp(14px,4vw,22px);
    /* The badge pitch IS the line pitch -- one disc per description line, as
       authored (8 paragraphs, 8 discs, a 21.863pt pitch on the canvas). They
       are driven by the same --line so they cannot drift apart. */
    --line:calc(var(--desc-fs) * 1.62);
    --num-top:calc(var(--photo-h) + var(--pad9));
    --ttl-top:calc(var(--num-top) + var(--num-fs) + var(--gap1));
    --desc-top:calc(var(--ttl-top) + var(--ttl-fs) * 1.02 + var(--gap2));
    /* THE PANEL MUST BE TOLD ITS OWN HEIGHT. Every shape on this slide is
       absolutely positioned, and an absolutely positioned child contributes
       NOTHING to its parent's height -- so `height:auto` leaves the canvas at
       exactly `min-height:100svh` no matter how far the content runs, and
       `.canvas{{overflow:hidden}}` then clips whatever is past it. On a 440px
       iPhone the eighth list row fell outside that box: H invisible, G half
       cut, and unreachable because the panel had no height to scroll into.
       --content-h is the real bottom of the content, from the same terms that
       place it, and max() keeps 100svh as a FLOOR rather than a ceiling.
       Mode B means the panel grows to its content; that only happens if the
       content is in flow OR the height is stated, and here it is stated. */
    --content-h:calc(var(--desc-top) + 8 * var(--line) + var(--pad9));
    container-type:inline-size;
    width:100%;height:auto;aspect-ratio:auto;
    min-height:max(100svh,var(--content-h));
    background:#A7C6ED;padding:0}}
  #s9 [data-name="Google Shape;37;p9"]{{display:none!important}}

  /* the band: authored aspect, so the crop's srcRect percentages stay valid
     and `.cropw` keeps this shape as its positioned ancestor (rule 41(u)). */
  #s9 [data-name="Picture 7"]{{
    left:0!important;right:0!important;top:0!important;bottom:auto!important;
    width:auto!important;height:var(--photo-h)!important}}

  /* every text shape is placed by arithmetic, not flow */
  #s9 .sh.tx{{right:auto!important;bottom:auto!important;
    width:auto!important;height:auto!important;padding:0!important}}
  #s9 [data-name="TextBox 5"]{{
    left:var(--edge9)!important;top:var(--num-top)!important}}
  #s9 [data-name="TextBox 5"] p.t span{{
    font-size:var(--num-fs)!important;line-height:1!important}}
  /* rule 41(r): display type, one line, no mid-word break */
  #s9 [data-name="Title 3"]{{
    left:var(--edge9)!important;top:var(--ttl-top)!important;
    white-space:nowrap!important;overflow-wrap:normal!important}}
  #s9 [data-name="Title 3"] p.t span{{
    font-size:var(--ttl-fs)!important;line-height:1.02!important}}

  /* the description: one line per paragraph, pinned, so the disc column
     cannot fall out of step with it. Measured at the reading size the longest
     line is 192.3px ("Harsh lighting & shadow play") in a column of roughly
     310px, so nowrap costs nothing and buys the alignment guarantee -- and if
     a future line did outgrow the column it would overflow visibly rather
     than wrap and silently shift every disc below it. `line-height` is a
     LENGTH, not a ratio, because p.t carries font-size:0 from the strut fix
     (rule 41(s)) and a ratio would resolve against zero. */
  #s9 [data-name="Subtitle 4"]{{
    left:calc(var(--edge9) + var(--badge9) + var(--gutter9))!important;
    top:var(--desc-top)!important}}
  /* `height`, not only `line-height`. Measured: with line-height:27.27px the
     paragraph box still came out 32.77px, because the line box takes the
     font's own ascent+descent when those exceed the declared leading -- so
     the discs drifted -5.5px per row, reaching -46px by the eighth. Setting
     the box height to the same --line makes the pitch exact BY CONSTRUCTION
     rather than by prediction: the disc column and the text column are then
     two readings of one variable and cannot disagree. */
  #s9 [data-name="Subtitle 4"] p.t{{
    height:var(--line)!important;overflow:visible;
    line-height:var(--line)!important;text-align:left!important;
    padding-left:0!important;text-indent:0!important;
    white-space:nowrap!important;overflow-wrap:normal!important}}
  #s9 [data-name="Subtitle 4"] p.t span{{font-size:var(--desc-fs)!important}}

  /* the A-H discs, one per line, on the same --line pitch.
     Selectors carry `.sh.tx` because `#s9 .sh.tx` above sets
     `height:auto!important` at (1,2,0) while a bare attribute selector is
     (1,1,0): both !important, so specificity decides, and the discs rendered
     11.6px instead of 21.1px and sat a constant 4.77px above their lines.
     Third time on this deck (slide 3's header, slide 13's images):
     !important settles importance, not rank. */
  #s9 .sh.tx[data-name="Oval 9"],#s9 .sh.tx[data-name="Oval 10"],
  #s9 .sh.tx[data-name="Oval 11"],#s9 .sh.tx[data-name="Oval 12"],
  #s9 .sh.tx[data-name="Oval 13"],#s9 .sh.tx[data-name="Oval 14"],
  #s9 .sh.tx[data-name="Oval 15"],#s9 .sh.tx[data-name="Oval 16"],
  #s9 .sh.tx[data-name="Oval 17"],#s9 .sh.tx[data-name="Oval 1"]{{
    width:var(--badge9)!important;height:var(--badge9)!important}}
  #s9 .sh.tx[data-name="Oval 9"],#s9 .sh.tx[data-name="Oval 10"],
  #s9 .sh.tx[data-name="Oval 11"],#s9 .sh.tx[data-name="Oval 12"],
  #s9 .sh.tx[data-name="Oval 13"],#s9 .sh.tx[data-name="Oval 14"],
  #s9 .sh.tx[data-name="Oval 15"],#s9 .sh.tx[data-name="Oval 16"]{{
    left:var(--edge9)!important}}
  #s9 .sh.tx[data-name="Oval 9"]{{top:calc(var(--desc-top) + 0.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 10"]{{top:calc(var(--desc-top) + 1.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 11"]{{top:calc(var(--desc-top) + 2.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 12"]{{top:calc(var(--desc-top) + 3.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 13"]{{top:calc(var(--desc-top) + 4.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 14"]{{top:calc(var(--desc-top) + 5.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 15"]{{top:calc(var(--desc-top) + 6.5 * var(--line)
    - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 16"]{{top:calc(var(--desc-top) + 7.5 * var(--line)
    - var(--badge9) / 2)!important}}

  /* the two discs that live ON the photograph travel with it, written as
     their authored fraction of the photo box (rule 41(v)'s companion: they
     are absolute over an absolute band, DOM-later, so they paint above it
     without a z-index). */
  #s9 .sh.tx[data-name="Oval 17"]{{
    left:calc(0.0979 * 100vw - var(--badge9) / 2)!important;
    top:calc(0.0813 * var(--photo-h) - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name="Oval 1"]{{
    left:calc(0.1517 * 100vw - var(--badge9) / 2)!important;
    top:calc(0.0813 * var(--photo-h) - var(--badge9) / 2)!important}}
  #s9 .sh.tx[data-name^="Oval"] p.t span{{
    font-size:calc(var(--badge9) * 0.46)!important}}

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
