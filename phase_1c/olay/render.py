"""Render the Olay model to one editable HTML document.

Deviation from LEARNINGS rule 15, deliberate and scoped to this deck:
rule 15 emits `#deck-desktop` and a separate `#deck-mobile` DOM. This deck
has to stay editable in Deck Editor v14, and the editor parses the document
with DOMParser and never runs JS. Two DOMs would put every live string in
the document twice, so the editor would harvest 68 slides instead of 34 and
an edit would update one view while the other silently went stale.

So: one set of 34 `<section class="slide">`, and the layout switch happens
in CSS. Desktop keeps exactly what rule 15 wants — absolute percentage
positioning on a `container-type: size` canvas at the deck's own aspect
(read from p:sldSz, never hardcoded), type in cqw. Mobile
flips the same nodes to static flow with per-shape `order`. Rule 15's root
cause ("one DOM cannot serve both cleanly") is what is being challenged
here; its goal (pixel-faithful desktop, sensible mobile) is preserved.

Rules held unchanged: 4/5 (z-order intact, nothing flattened or promoted),
6 (assets extracted, never recreated), 9 (no vh/vw for type on desktop),
14 (text verbatim).
"""
from __future__ import annotations

import html, json, sys
from pathlib import Path

sys.path.insert(0, "/Users/gif025/Downloads/ondeck-pipeline")
from ondeck.render.fonts import font_face_css
from ondeck.parse.font_calibration import SOURCE_LINE_HEIGHT_RATIOS, MATCHED_METRIC_AXES
from phase_1c.deckkit import css as dkcss

sys.path.insert(0, str(Path(__file__).parent))
from roles import (BADGE_SPRITE, BANNERS, LOGOS, STRIP_SLIDES,
                   SUPPRESS_REVIEW_STICKERS, SUPPRESS_OCCLUDED_SHAPES,
                   text_role, badge_for, image_role)

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
DECK_TITLE = "Premium BW and HBL — CGI Assets Visual Boards"

# Substitute stacks. The source face is named first so a machine that
# actually has it licensed uses the real thing; the bundled substitute is
# the fallback everyone else gets.
STACK = {
    "Franklin Gothic Book": "'Franklin Gothic Book','Archivo',system-ui,sans-serif",
    "Boston SemiBold":      "'Boston SemiBold','Poppins',system-ui,sans-serif",
    "Aptos":                "'Aptos','Archivo',system-ui,sans-serif",
}
# Archivo's wdth=94 is the measured Franklin Gothic Book match; Aptos uses
# the natural width. See font_calibration.MATCHED_METRIC_AXES.
VAR_SETTINGS = {"Franklin Gothic Book": "'wdth' 94, 'wght' 400",
                "Aptos": "'wdth' 100, 'wght' 400"}

MOBILE_PT = {"title": "1.55rem", "ci": "1rem", "cbi": "1rem", "fn": "0.95rem"}


def esc(s): return html.escape(s, quote=True)


def pct(v, total): return round(v / total * 100, 4)


def crop_style(crop):
    """srcRect -> absolute inset for a child that fills the visible window.

    l/t/r/b are fractions of the SOURCE to remove, so the visible slice is
    (1-l-r) x (1-t-b). Scaling the child by the reciprocal and shifting it
    by the removed margin puts that slice exactly over the shape box. The
    source uses <a:stretch>, so the slice stretches to fill: object-fit:fill.
    Negative values (a slight outset) fall out of the same arithmetic.
    """
    if not crop:
        return "width:100%;height:100%;left:0;top:0;"
    l, t = crop.get("l", 0), crop.get("t", 0)
    r, b = crop.get("r", 0), crop.get("b", 0)
    vw, vh = 1 - l - r, 1 - t - b
    if vw <= 0 or vh <= 0:
        return "width:100%;height:100%;left:0;top:0;"
    return (f"width:{100/vw:.4f}%;height:{100/vh:.4f}%;"
            f"left:{-l/vw*100:.4f}%;top:{-t/vh*100:.4f}%;")


# Mobile strip metrics. Every tile is `height: var(--th)` with a known aspect
# ratio, so the scroll width is H * sum(aspect) + gaps — computable in calc().
STRIP_GAP = 8      # gap between tiles
STRIP_PAD = 14     # canvas padding-left / padding-right


def strip_ground_metrics(shapes, W):
    """Map each ground panel to the span of tiles it covers on the DESKTOP canvas.

    On a phone the canvas becomes a horizontal scroller, and a percentage width
    on an absolutely-positioned child resolves against the containing block's
    padding box (the 390px viewport), NOT the scroll width. So a 55/45 ground
    painted in percentages covers only the first screen of a ~956px strip and
    then scrolls away, leaving the later renders on bare white.

    The split is structural, not decorative: on slides 4-7 no tile straddles the
    boundary — it sits exactly in the gap between render 4 and render 5,
    grouping 4 renders against 3. So rather than drop it, re-express each panel
    as the tile span it owns. Returns {shape_name: (left_ar, left_px, w_ar, w_px)}
    for `calc(var(--th) * ar + px)`.
    """
    tiles = [s for s in shapes if s["type"] in ("image", "video")
             and image_role(s.get("poster") or "", s.get("crop"), s["w"], s["h"]) == "tile"]
    if not tiles:
        return {}
    ars = [t["w"] / t["h"] for t in tiles]
    n = len(tiles)
    cum = [0.0]
    for a in ars:
        cum.append(cum[-1] + a)

    out = {}
    for panel in shapes:
        if panel["type"] != "rect" or not panel.get("backdrop"):
            continue
        idx = [i for i, t in enumerate(tiles)
               if panel["x"] <= (t["x"] + t["w"] / 2) <= panel["x"] + panel["w"]]
        if not idx or idx != list(range(idx[0], idx[-1] + 1)):
            continue          # non-contiguous span: leave it to the fallback
        a, b = idx[0], idx[-1]
        left_px = 0 if a == 0 else STRIP_PAD + a * STRIP_GAP - STRIP_GAP // 2
        right_px = (STRIP_PAD + (n - 1) * STRIP_GAP + STRIP_PAD) if b == n - 1 \
            else STRIP_PAD + b * STRIP_GAP + STRIP_GAP // 2
        out[panel["name"]] = (cum[a], left_px, cum[b + 1] - cum[a], right_px - left_px)
    return out


def shadow_css(sh, W):
    if not sh:
        return ""
    a = sh["alpha"]
    c = sh["color"].lstrip("#")
    rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
    return (f"box-shadow:{pct(sh['dx_pt'],W):.3f}cqw {pct(sh['dy_pt'],W):.3f}cqw "
            f"{pct(sh['blur_pt'],W):.3f}cqw rgba({rgb[0]},{rgb[1]},{rgb[2]},{a:.3f});")


def over(hexv, alpha, base):
    """Composite a translucent colour onto an opaque base, returning opaque hex.

    Used only for the SLIDE background. Three slides set <p:bg> to a colour
    with alpha (s15 #DD6467 @80.1%, s28 #FAC5D9 @27.1%, s31 #B1BFDB @18.0%),
    which PowerPoint composites over the master background. Emitting rgba()
    instead would let the page behind show through wherever no shape covers
    the slide — on s15 that is the whole right-hand caption column, which
    turns white instead of salmon.

    Shape-level fills keep their alpha: those composite over whatever art sits
    beneath them, which is a genuine transparency, not a fixed base.
    """
    if not hexv:
        return None
    if alpha is None or alpha >= 1.0:
        return hexv
    c, bs = hexv.lstrip("#"), base.lstrip("#")
    out = []
    for i in (0, 2, 4):
        fg, bg = int(c[i:i+2], 16), int(bs[i:i+2], 16)
        out.append(round(fg * alpha + bg * (1 - alpha)))
    return "#{:02X}{:02X}{:02X}".format(*out)


def rgba(hexv, alpha):
    if not hexv:
        return None
    if alpha is None or alpha >= 1.0:
        return hexv
    c = hexv.lstrip("#")
    r, g, b = (int(c[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.3f})"


def render(model, imgman, vidman):
    W, H = model["w_pt"], model["h_pt"]
    sections, css = [], []
    suppressed, occluded = [], []

    for sl in model["slides"]:
        n = sl["n"]
        parts = []
        # Slide background: solid fill, image fill, or both.
        bg = over(sl["bg"], sl["bg_alpha"], model.get("master_bg", "#FFFFFF")) \
             or model.get("master_bg", "#FFFFFF")
        if sl["bg_image"]:
            fr = sl["bg_image"].get("fill_rect") or {}
            l, t = fr.get("l", 0), fr.get("t", 0)
            r, b = fr.get("r", 0), fr.get("b", 0)
            src = imgman[sl["bg_image"]["src"]]["out"]
            parts.append(
                f'<div class="sh bgimg backdrop" style="left:{l*100:.4f}%;top:{t*100:.4f}%;'
                f'width:{(1-l-r)*100:.4f}%;height:{(1-t-b)*100:.4f}%">'
                f'<img src="assets/{src}" alt="" loading="lazy"></div>')

        ground = strip_ground_metrics(sl["shapes"], W) if n in STRIP_SLIDES else {}

        order = 0
        for s in sl["shapes"]:
            # Flagged in model.py, dropped only because roles.py opts in.
            if s.get("review_sticker") and SUPPRESS_REVIEW_STICKERS:
                suppressed.append((sl["n"], s["name"]))
                continue
            if s.get("occluded") and SUPPRESS_OCCLUDED_SHAPES:
                occluded.append((sl["n"], s["name"]))
                continue
            order += 1
            box = (f"left:{pct(s['x'],W):.4f}%;top:{pct(s['y'],H):.4f}%;"
                   f"width:{pct(s['w'],W):.4f}%;height:{pct(s['h'],H):.4f}%;")
            ar = f"--ar:{s['w']/s['h']:.4f};" if s["h"] else ""
            od = f"--o:{order};"
            bd = " backdrop" if s.get("backdrop") else ""

            if s["type"] == "rect":
                fill = rgba(s["fill"], s.get("fill_alpha"))
                g = ground.get(s["name"])
                gv = (f"--bl-ar:{g[0]:.4f};--bl-px:{g[1]}px;"
                      f"--bw-ar:{g[2]:.4f};--bw-px:{g[3]}px;") if g else ""
                parts.append(f'<div class="sh rect{bd}" style="{box}{od}{gv}background:{fill};'
                             f'{shadow_css(s.get("shadow"), W)}"></div>')

            elif s["type"] == "image":
                src = s["poster"]
                role = image_role(src, s["crop"], s["w"], s["h"])
                asset = imgman[src]["out"]
                extra, label = "", ""
                if role == "badge":
                    meta = badge_for(s["crop"])
                    if meta:
                        num, name = meta
                        extra = f' data-category="{num}" title="{esc(name)}"'
                        label = f' aria-label="Category {num}: {esc(name)}" role="img"'
                alt = ""
                if role == "banner":
                    alt = esc(BANNERS[src])
                elif role == "logo":
                    alt = esc(LOGOS[src])
                parts.append(
                    f'<div class="sh im {role}{bd}" style="{box}{ar}{od}"{extra}{label}>'
                    f'<img src="assets/{asset}" alt="{alt}" loading="lazy" '
                    f'style="{crop_style(s["crop"])}"></div>')

            elif s["type"] == "video":
                vid = vidman[s["video"]]["out"]
                poster = imgman[s["poster"]]["out"] if s["poster"] else None
                cs = crop_style(s["crop"])
                # Rule 4: poster underlay and video overlay stay distinct
                # stacked layers, both carrying the same crop transform.
                pimg = (f'<img class="poster" src="assets/{poster}" alt="" '
                        f'loading="lazy" style="{cs}">') if poster else ""
                pattr = f' poster="assets/{poster}"' if poster else ""
                parts.append(
                    f'<div class="sh vid" style="{box}{ar}{od}">{pimg}'
                    f'<video src="assets/{vid}"{pattr} autoplay muted loop playsinline '
                    f'preload="metadata" style="{cs}"></video></div>')

            elif s["type"] == "text":
                face = s["paras"][0]["runs"][0]["typeface"]
                size = s["paras"][0]["runs"][0]["size_pt"]
                role = text_role(n, face)
                lh = SOURCE_LINE_HEIGHT_RATIOS.get(face.lower(), 1.2121)
                ins = s.get("insets") or {}
                pad = (f"padding:{pct(ins.get('t',3.6),H):.4f}% {pct(ins.get('r',7.2),W):.4f}% "
                       f"{pct(ins.get('b',3.6),H):.4f}% {pct(ins.get('l',7.2),W):.4f}%;")
                vs = VAR_SETTINGS.get(face)
                fv = f"font-variation-settings:{vs};" if vs else ""
                anchor = "center" if s.get("anchor") == "ctr" else "flex-start"
                col = s["paras"][0]["runs"][0]["color"] or "#000000"
                body = []
                for p in s["paras"]:
                    txt = "".join(r["text"] for r in p["runs"])
                    align = {"ctr": "center", "r": "right", "just": "justify"}.get(p["align"], "left")
                    if not txt.strip():
                        body.append(f'<p class="e" style="text-align:{align}">&nbsp;</p>')
                    else:
                        body.append(f'<p style="text-align:{align}">{esc(txt)}</p>')
                inner = "".join(body)
                # A text shape can carry a fill of its own — for the review
                # stickers it comes from <p:style> fillRef, not spPr.
                bgf = rgba(s.get("fill"), s.get("fill_alpha"))
                bgcss = f"background:{bgf};" if bgf else ""
                style = (f"{box}{od}{pad}font-family:{STACK.get(face,'system-ui,sans-serif')};"
                         f"{fv}font-size:{pct(size,W):.4f}cqw;line-height:{lh};color:{col};"
                         f"{bgcss}{shadow_css(s.get('shadow'), W)}"
                         f"justify-content:{anchor};--ms:{MOBILE_PT[role]};")
                if role == "title":
                    parts.append(f'<div class="sh tx L" style="{style}">'
                                 f'<div class="t">{inner}</div></div>')
                else:
                    parts.append(f'<div class="sh tx {role}" style="{style}">{inner}</div>')

        layout = ' data-layout="strip"' if n in STRIP_SLIDES else ""
        if sl.get("bg_image") or any(x.get("backdrop") for x in sl["shapes"]
                                     if not (x.get("occluded") and SUPPRESS_OCCLUDED_SHAPES)):
            layout += ' data-backdrop="1"'
        sections.append(
            f'<section class="slide" id="s{n}" data-slide="{n}"{layout}>\n'
            f'  <div class="canvas" style="background:{bg}">\n    '
            + "\n    ".join(parts) + "\n  </div>\n</section>")

    if occluded:
        print(f"  dropped {len(occluded)} occluded shape(s): "
              + ", ".join(f"s{n}/{nm}" for n, nm in occluded))
    if suppressed:
        print(f"  suppressed {len(suppressed)} review sticker(s): "
              + ", ".join(f"s{n}/{nm}" for n, nm in suppressed))
    return "\n".join(sections)


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;background:#111;-webkit-font-smoothing:antialiased}
img,video{display:block;max-width:none}

#deck{scroll-snap-type:y mandatory;overflow-y:auto;height:100vh}
.slide{scroll-snap-align:start;scroll-snap-stop:always;display:flex;
  align-items:center;justify-content:center;min-height:100vh;padding:2vh 2vw}
.canvas{position:relative;width:100%;max-width:calc(100vh * var(--ratio) - 8vh);
  aspect-ratio:var(--ratio);container-type:size;overflow:hidden}

.sh{position:absolute}
.sh.im,.sh.vid,.sh.bgimg{overflow:hidden}
.sh.im img,.sh.vid img,.sh.vid video,.sh.bgimg img{position:absolute;object-fit:fill}
.sh.bgimg img{width:100%;height:100%}
/* No z-index on the video: .canvas has container-type:size, which implies
   contain:layout and so IS a stacking context. A z-index there promotes every
   video above all sibling .sh divs (which are z-index:auto), painting the
   videos over shapes that sit above them in source z-order — rule 5. The
   poster/video stack inside the wrapper is already correct by DOM order. */
.sh.tx{display:flex;flex-direction:column;white-space:pre-wrap}
.sh.tx p{margin:0}
.sh.tx p.e{min-height:1em}

@media (max-width:820px){
/*__SCROLL_GATE__*/
  /* Deck-specific geometry note, kept from the Olay port: unlike HenHouse
     (28 of 51 snap points exactly one viewport apart), Olay's are varied --
     11 of 33 -- but NO gap is shorter than a viewport (min 844px at 390x844),
     so proximity still intercepted most flings and `stop:always` was likely
     the dominant cause. The .slide selector is left blanket: it also lands on
     the strip carousel tiles, whose own snap is on the x axis, so `stop` there
     is inert. Left visible rather than pre-empted. */
  .slide{min-height:auto;padding:0;display:block}
  .canvas{max-width:none;aspect-ratio:auto;height:auto;container-type:inline-size;
    display:flex;flex-wrap:wrap;align-items:flex-start;padding:16px 14px 26px}
  /* inset:auto is not optional. The desktop canvas positions every shape with
     inline left/top, and a `position:relative` wrapper still applies those as
     offsets from its flow position — tiles slide sideways and downwards and
     tear holes in the stack. Static shapes ignore inset, but the crop wrappers
     have to stay positioned, so clear it explicitly for everything. */
  .sh:not(.backdrop){position:static;order:var(--o);width:100%;height:auto;
    flex:0 0 100%;inset:auto!important}
  /* Backdrops leave the flow entirely and paint behind the content. On a
     phone the background IS the slide: reflowing a full-canvas photo as an
     ordinary tile boxes the artwork onto white and loses the whole effect. */
  .sh.backdrop{position:absolute!important;top:0!important;bottom:0!important;
    height:auto!important;display:block!important;margin:0!important;
    order:-1;z-index:0;pointer-events:none}
  /* aspect-ratio must be cleared: with height:auto it wins over the
     top:0/bottom:0 stretch, collapsing a full-bleed backdrop to its aspect
     box (390x218) instead of filling the slide. */
  .sh.im.backdrop,.sh.vid.backdrop,.sh.bgimg.backdrop{
    left:0!important;right:0!important;width:auto!important;
    aspect-ratio:auto!important}
  /* Panel rects keep their authored left/width so a split background still
     splits; only the height is stretched to the reflowed canvas. */
  .sh.rect.backdrop{display:block!important}
  .sh.backdrop img,.sh.backdrop video{position:absolute;left:0!important;top:0!important;
    width:100%!important;height:100%!important;object-fit:cover!important}
  .canvas>.sh:not(.backdrop){position:relative;z-index:1}
  .canvas>.sh.im:not(.backdrop),.canvas>.sh.vid:not(.backdrop){position:relative}
  /* Every slide holds at least a screen. Without this a short slide (the
     cover is 507px) lets the NEXT slide scroll into the same viewport, so the
     cover's footer logo appeared to collide with slide 2's "Creative Brief"
     heading. Nothing was overlapping — two different slides were simply
     sharing the screen. align-content centres short slides; tall ones
     overflow and ignore it. */
  .canvas{min-height:100svh;align-content:center}
  .sh.rect:not(.backdrop),.sh.bgimg:not(.backdrop){display:none}
  /* The crop wrappers must stay POSITIONED. Their <img>/<video> children are
     absolutely positioned and scaled by the srcRect maths, so they resolve
     against the nearest positioned ancestor — make the wrapper static and
     that becomes .canvas, blowing every tile up to canvas size. */
  .sh.im,.sh.vid{position:relative;aspect-ratio:var(--ar,1);margin:0 0 10px}
  .sh.im img,.sh.vid img,.sh.vid video{position:absolute}
  /* Shapes carry an inline percentage width from the desktop canvas. In the
     mobile flex column `flex-basis:100%` overrides it, but anything set to
     `flex:0 0 auto` falls back to that inline width — badges rendered at 11px
     instead of 38px. So size these off flex-basis, not width alone.
     (Percentage HEIGHTS resolve to auto here because the canvas has no
     definite height, which is what lets aspect-ratio drive tile height.) */
  .sh.im.badge{flex:0 0 38px;width:38px!important;height:38px!important;
    aspect-ratio:1;margin:0 8px 12px 0}
  .sh.im.logo{flex:0 0 34%;width:34%!important;margin-top:12px;margin-bottom:14px}
  /* Section headline art leads its slide rather than sitting wherever it
     happened to fall in z-order. */
  .sh.im.banner{order:0;margin-bottom:12px}
  .sh.tx{font-size:var(--ms)!important;padding:2px 2px 14px!important;
    line-height:1.35!important;font-variation-settings:'wdth' 100,'wght' 400!important}
  .sh.tx.fn{opacity:.82;font-style:italic}
  /* Contact-sheet slides keep their side-by-side read instead of an
     eight-deep stack that would bury the comparison. Tiles are sized by
     HEIGHT, not width: these are tall narrow crops, so a width-based basis
     (46% -> 167x660px) made each render taller than the viewport and showed
     only a magnified sliver. Height-capped, a whole render fits on screen and
     roughly three sit side by side. */
  .slide[data-layout=strip] .canvas{--th:min(58svh,520px);
    flex-wrap:nowrap;overflow-x:auto;scroll-snap-type:x proximity;gap:8px;
    align-items:flex-start;padding-top:76px}
  .slide[data-layout=strip] .sh.im{flex:0 0 auto;width:auto!important;
    height:var(--th)!important;scroll-snap-align:start;margin:0}
  /* Ground panels span the tiles they own, measured in the same --th the tiles
     are sized by, so the split lands in the render-4/5 gap and the ground
     reaches the end of the scroll instead of stopping at the viewport edge. */
  .slide[data-layout=strip] .sh.rect.backdrop{
    left:calc(var(--th) * var(--bl-ar) + var(--bl-px))!important;
    width:calc(var(--th) * var(--bw-ar) + var(--bw-px))!important;
    right:auto!important}
  /* The section title is lifted out of the scroll row — inside it, it ate the
     first screenful and pushed every render off-screen. */
  /* Size the lifted banner by HEIGHT so its footprint is predictable: at a
     width-based 62% it grew to 73px tall and overlapped the tiles by 11px,
     because the canvas padding-top that clears it is a fixed number. */
  .slide[data-layout=strip] .sh.im.banner{position:absolute!important;
    top:14px!important;left:14px!important;height:46px!important;width:auto!important;
    flex:none;z-index:2;margin:0}
}
"""


def main():
    model = json.load(open(OUT / "model.json"))
    imgman = json.load(open(OUT / "image_manifest.json"))
    vidman = json.load(open(OUT / "video_manifest.json"))
    body = render(model, imgman, vidman)
    css = CSS.replace("/*__SCROLL_GATE__*/",
                      dkcss.mobile_scroll_release(".slide"))
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(DECK_TITLE)}</title>
<style>
{font_face_css(families=("Archivo", "Poppins"))}
{dkcss.ratio_root(model["w_pt"], model["h_pt"])}
{css}
</style>
</head>
<body>
<main id="deck">
{body}
</main>
</body>
</html>
"""
    (OUT / "index.html").write_text(doc)
    print(f"wrote {OUT/'index.html'}  {len(doc)/1024:.0f}KB")


if __name__ == "__main__":
    main()
