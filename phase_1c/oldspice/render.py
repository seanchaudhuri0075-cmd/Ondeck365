"""Old Spice renderer — one editable document, 34 static sections.

Carries the Olay architecture unchanged: single DOM (rule 22), absolute % on a
16:9 `container-type: size` canvas with type in cqw (rules 9, 15), z-order
intact (4/5), verbatim text (14), backdrops and occlusion (24), no z-index
inside the canvas (21).

Mobile differs from Olay by evidence, not preference. Olay was 34 hand-built
canvases that had to be taken apart. This deck is 2.35 shapes/slide and 24 of
34 slides are one image plus one <=24-char label, so there is almost nothing to
reflow. Per archetype:
  plate      image at its authored aspect, label OVERLAID — which is exactly
             what ondeck/layout/archetype.py says photo_with_caption needs
             ("the caption should overlay the photo, not stack below it")
  keyvisual  full-canvas image as backdrop, label + prose over it
  divider    title centred on a full-screen ground
  cover      wordmark + title centred
  brief      single column: title, prose, image
  table      transposed to one card per variant row (desktop keeps the table)
"""
from __future__ import annotations

import html, json, sys
from pathlib import Path

sys.path.insert(0, "/Users/gif025/Downloads/ondeck-pipeline")
from ondeck.render.fonts import font_face_css
from phase_1c.deckkit import css as dkcss
from ondeck.parse.font_calibration import (SOURCE_LINE_HEIGHT_RATIOS, MATCHED_METRIC_AXES,
                                           normalize_typeface)

sys.path.insert(0, str(Path(__file__).parent))
from roles import (DECK_TITLE, archetype, text_role, BODY_SLIDES,
                   SUPPRESS_REVIEW_STICKERS, SUPPRESS_OCCLUDED_SHAPES,
                   KEEP_AUTHORED_STRETCH)

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")

STACK = {
    "DIN Pro Condensed": "'DIN Pro Condensed','DIN Condensed','Barlow Condensed',sans-serif",
    "Aptos": "'Aptos','Archivo',system-ui,sans-serif",
}
VAR = {"Aptos": "'wdth' 100, 'wght' 400"}
MOBILE_PT = {"title": "1.15rem", "cbi": "0.95rem", "ci": "0.9rem", "sl": "0.95rem"}


def esc(s): return html.escape(s, quote=True)
def pct(v, t): return round(v / t * 100, 4)


def rgba(hexv, alpha):
    if not hexv: return None
    if alpha is None or alpha >= 1.0: return hexv
    c = hexv.lstrip("#"); r, g, b = (int(c[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.3f})"


def over(hexv, alpha, base):
    if not hexv: return None
    if alpha is None or alpha >= 1.0: return hexv
    c, bs = hexv.lstrip("#"), base.lstrip("#")
    return "#{:02X}{:02X}{:02X}".format(*[
        round(int(c[i:i+2], 16) * alpha + int(bs[i:i+2], 16) * (1 - alpha)) for i in (0, 2, 4)])


def crop_style(crop):
    if not crop: return "width:100%;height:100%;left:0;top:0;"
    l, t = crop.get("l", 0), crop.get("t", 0)
    r, b = crop.get("r", 0), crop.get("b", 0)
    vw, vh = 1 - l - r, 1 - t - b
    if vw <= 0 or vh <= 0: return "width:100%;height:100%;left:0;top:0;"
    return (f"width:{100/vw:.4f}%;height:{100/vh:.4f}%;"
            f"left:{-l/vw*100:.4f}%;top:{-t/vh*100:.4f}%;")


def run_css(r, W):
    face = r["typeface"]
    key = normalize_typeface(face)
    lh = SOURCE_LINE_HEIGHT_RATIOS.get(key, 1.2143)
    fam = STACK.get(face, "system-ui,sans-serif")
    vs = VAR.get(face)
    axes = MATCHED_METRIC_AXES.get(key)
    if axes and not vs:
        vs = ", ".join(f"'{k}' {v}" for k, v in axes.items())
    return (f"font-family:{fam};" + (f"font-variation-settings:{vs};" if vs else "")
            + f"font-size:{pct(r['size_pt'],W):.4f}cqw;line-height:{lh};"
            + f"font-weight:{700 if r['bold'] else 400};color:{r['color'] or '#000'};")


def render_table(s, W, H, n):
    t = s["table"]
    total = sum(t["grid_pt"]) or 1
    cols = "".join(f"<col style=\"width:{c/total*100:.3f}%\">" for c in t["grid_pt"])
    rows = []
    for ri, row in enumerate(t["rows"]):
        cells = []
        for ci, c in enumerate(row["cells"]):
            if c["h_merge"]: continue
            body = []
            for p in c["paras"]:
                txt = "".join(r["text"] for r in p["runs"])
                if not txt.strip():
                    continue
                r0 = p["runs"][0]
                bul = (f'<span class="bu" aria-hidden="true">{esc(p["bullet"])}</span>'
                       if p.get("bullet") else "")
                cls = ' class="li"' if p.get("bullet") else ""
                body.append(f'<p{cls} style="{run_css(r0,W)}">{bul}{esc(txt)}</p>')
            bg = rgba(c["fill"], c["fill_alpha"])
            tag = "th" if ri == 0 else "td"
            span = f' colspan="{c["grid_span"]}"' if c["grid_span"] > 1 else ""
            cells.append(f'<{tag} class="ci"{span} style="{f"background:{bg};" if bg else ""}">'
                         + ("".join(body) or "&nbsp;") + f"</{tag}>")
        rows.append(f'<tr data-variant="{ri}">' + "".join(cells) + "</tr>")
    box = (f"left:{pct(s['x'],W):.4f}%;top:{pct(s['y'],H):.4f}%;"
           f"width:{pct(s['w'],W):.4f}%;height:{pct(s['h'],H):.4f}%;")
    return (f'<div class="sh tbl" style="{box}--o:{s["z"]+1};">'
            f'<table><colgroup>{cols}</colgroup><tbody>' + "".join(rows) + "</tbody></table></div>")


def unit_cells(sl, man, units_by_slide):
    """Mobile-only cells for a plate slide: a carousel, or one filled frame.

    The cells reference the SAME asset the desktop <img> does, each with its own
    CSS crop window — the Olay badge-sprite technique. No image is sliced into
    new bytes, so rule 6 holds and rule 7 still sees one asset and one URL.

    Cell aspect carries the authored stretch (roles.KEEP_AUTHORED_STRETCH) so a
    product has the same proportions on both builds; sizing is by HEIGHT so a
    tall unit fills a portrait viewport instead of letterboxing (rule 25).
    """
    u = units_by_slide.get(str(sl["n"]))
    if not u or not u.get("units"):
        return ""
    img = [s for s in sl["shapes"] if s["type"] == "image"][0]
    md = man[img["poster"]]
    src_ar = md["src_w"] / md["src_h"]
    box_ar = img["w"] / img["h"]
    stretch = (box_ar / src_ar) if KEEP_AUTHORED_STRETCH else 1.0
    cells = []
    for un in u["units"]:
        ar = (un["w_px"] / un["h_px"]) * stretch
        crop = {"l": un["l"], "t": un["t"], "r": un["r"], "b": un["b"]}
        # Two levels on purpose: .unit is the full-width scroll page, .uf is
        # the aspect box the crop maths resolves against. Collapsing them makes
        # the crop resolve against the viewport and distorts the product.
        cells.append(f'<div class="unit"><div class="uf" style="--uar:{ar:.4f}">'
                     f'<img src="assets/{md["out"]}" alt="" loading="lazy" '
                     f'style="{crop_style(crop)}"></div></div>')
    kind = "carousel" if len(cells) > 1 else "solo"
    return (f'<div class="units {kind}" data-units="{len(cells)}" aria-hidden="true">'
            + "".join(cells) + "</div>")


def render(model, man, units_by_slide):
    W, H = model["w_pt"], model["h_pt"]
    sections, dropped = [], {"sticker": [], "occluded": []}
    for sl in model["slides"]:
        n = sl["n"]; arch = archetype(n)
        bg = over(sl["bg"], sl["bg_alpha"], model.get("master_bg", "#FFFFFF")) \
             or model.get("master_bg", "#FFFFFF")
        parts, order, seen_text = [], 0, False
        for s in sl["shapes"]:
            if s.get("review_sticker") and SUPPRESS_REVIEW_STICKERS:
                dropped["sticker"].append((n, s["name"])); continue
            if s.get("occluded") and SUPPRESS_OCCLUDED_SHAPES:
                dropped["occluded"].append((n, s["name"])); continue
            order += 1
            box = (f"left:{pct(s['x'],W):.4f}%;top:{pct(s['y'],H):.4f}%;"
                   f"width:{pct(s['w'],W):.4f}%;height:{pct(s['h'],H):.4f}%;")
            ar = f"--ar:{s['w']/s['h']:.4f};" if s["h"] else ""
            od = f"--o:{order};"
            bd = " backdrop" if s.get("backdrop") else ""

            if s["type"] == "rect":
                shape = "border-radius:50%;" if s.get("prst") == "ellipse" else ""
                # A backdrop rect spanning the canvas IS the slide's ground; a
                # narrower one is a composition rail framing desktop content.
                # Only the rail loses its meaning when the layout is transposed.
                rail = " rail" if (s.get("backdrop") and s["w"] < W * 0.97) else ""
                parts.append(f'<div class="sh rect{bd}{rail}" style="{box}{od}{shape}'
                             f'background:{rgba(s["fill"], s.get("fill_alpha"))}"></div>')
            elif s["type"] == "table":
                parts.append(render_table(s, W, H, n))
            elif s["type"] == "image":
                # Rule 6: an SVG-only picture embeds the actual vector. The
                # wordmark's <a:blip> has no r:embed at all, so there is no
                # raster to fall back to.
                key = s.get("svg") or s.get("poster")
                asset = man[key]["out"]
                alt = "Old Spice" if s.get("svg") else ""
                parts.append(f'<div class="sh im{bd}" style="{box}{ar}{od}">'
                             f'<img src="assets/{asset}" alt="{alt}" loading="lazy" '
                             f'style="{crop_style(s["crop"])}"></div>')
            elif s["type"] == "text":
                role = text_role(n, not seen_text); seen_text = True
                r0 = s["paras"][0]["runs"][0]
                ins = s.get("insets") or {}
                pad = (f"padding:{pct(ins.get('t',3.6),H):.4f}% {pct(ins.get('r',7.2),W):.4f}% "
                       f"{pct(ins.get('b',3.6),H):.4f}% {pct(ins.get('l',7.2),W):.4f}%;")
                anchor = "center" if s.get("anchor") == "ctr" else "flex-start"
                # wrap="none" means the source lets text overflow its box rather
                # than wrap; reproducing that keeps the authored line breaks.
                wrap = "white-space:nowrap;" if s.get("wrap") == "none" else ""
                body = []
                for p in s["paras"]:
                    txt = "".join(r["text"] for r in p["runs"])
                    al = {"ctr": "center", "r": "right", "just": "justify"}.get(p["align"], "left")
                    bul = (f'<span class="bu" aria-hidden="true">{esc(p["bullet"])}</span>'
                           if p.get("bullet") else "")
                    cls = ' class="li"' if p.get("bullet") else ""
                    body.append(f'<p{cls} style="text-align:{al}">{bul}'
                                f'{esc(txt) if txt.strip() else "&nbsp;"}</p>')
                bgf = rgba(s.get("fill"), s.get("fill_alpha"))
                shape = "border-radius:50%;" if s.get("prst") == "ellipse" else ""
                style = (f"{box}{od}{pad}{run_css(r0,W)}{wrap}"
                         f"{f'background:{bgf};' if bgf else ''}{shape}"
                         f"justify-content:{anchor};--ms:{MOBILE_PT[role]};")
                inner = "".join(body)
                if role == "title":
                    parts.append(f'<div class="sh tx L" style="{style}">'
                                 f'<div class="t">{inner}</div></div>')
                else:
                    parts.append(f'<div class="sh tx {role}" style="{style}">{inner}</div>')

        if arch == "plate":
            parts.append(unit_cells(sl, man, units_by_slide))

        has_bd = any(x.get("backdrop") for x in sl["shapes"]
                     if not (x.get("occluded") and SUPPRESS_OCCLUDED_SHAPES))
        attrs = f' data-arch="{arch}"' + (' data-backdrop="1"' if has_bd else "")
        if arch == "divider":
            # Carry the divider's own ground with its title when merging. The
            # destination name is bg1+lumMod50% grey, which reads correctly on
            # the divider's white slide and disappears over a photo. Recolouring
            # the text would be inventing; reproducing its ground preserves both
            # the authored colour AND the contrast relationship it was set for.
            attrs += f' style="--dbg:{bg}"'

        sections.append(
            f'<section class="slide" id="s{n}" data-slide="{n}"{attrs}>\n'
            f'  <div class="canvas" style="background:{bg}">\n    '
            + "\n    ".join(parts) + "\n  </div>\n</section>")
    return "\n".join(sections), dropped


# ---------------------------------------------------------------------------
# KNOWN-OPEN DEFECT, deliberately not fixed in this pass.
#
# This deck still ships `#deck{scroll-snap-type:y mandatory}` and
# `.slide{scroll-snap-stop:always}` at EVERY width -- the discrete-paging
# affordance diagnosed on HenHouse (NOTES 2026-08-24) and ported to Olay
# (2026-08-25). Old Spice was missed, and is the strictest of the three
# (`mandatory`, not `proximity`).
#
# It is left off because oldspicepackaging.globalimaige.com is signed off and
# live: turning it on changes the mobile feel of a shipped deck, which is a
# re-ship decision, not a refactor. Flip to True, rebuild, re-verify on a
# phone, and re-import to fix it. Same per-deck opt-in shape as
# DEDUPE_CROP_HALVES and KEEP_AUTHORED_STRETCH.
EMIT_MOBILE_SCROLL_GATE = False

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
/* The deck's own default stack (theme minor font -> its substitute) and the
   mobile type scale, declared once. Anything the pipeline generates rather
   than reads from a run — the transposed table cards — inherits from here
   instead of falling through to the browser default, which rendered them in
   Times against an otherwise Aptos deck. Authored runs still carry their own
   family inline and override this. */
:root{--deck-font:'Aptos','Archivo',system-ui,sans-serif;
  --ms-title:1.15rem;--ms-body:0.95rem;--ms-small:0.82rem;--ms-lh:1.3}
html,body{width:100%;background:#111;-webkit-font-smoothing:antialiased;
  font-family:var(--deck-font)}
img{display:block;max-width:none}

#deck{scroll-snap-type:y mandatory;overflow-y:auto;height:100vh}
.slide{scroll-snap-align:start;scroll-snap-stop:always;display:flex;
  align-items:center;justify-content:center;min-height:100vh;padding:2vh 2vw}
.canvas{position:relative;width:100%;max-width:calc(100vh * var(--ratio) - 8vh);
  aspect-ratio:var(--ratio);container-type:size;overflow:hidden}

.sh{position:absolute}
.sh.im{overflow:hidden}
.sh.im img{position:absolute;object-fit:fill}
.sh.tx{display:flex;flex-direction:column}
.sh.tx p{margin:0}
.sh.tbl table{width:100%;height:100%;border-collapse:collapse;table-layout:fixed}
p.li{padding-left:1em;text-indent:-1em}
.bu{display:inline-block;width:1em;text-indent:0}
.sh.tbl th,.sh.tbl td{vertical-align:top;padding:0.6cqw 0.8cqw;
  border:0.08cqw solid rgba(0,0,0,.18);text-align:left}
.card{display:none}
/* Mobile-only cells. Hidden on desktop so the signed-off canvas is untouched. */
.units{display:none}

@media (max-width:820px){
/*__SCROLL_GATE__*/
  .slide{min-height:auto;padding:0;display:block}
  .canvas{max-width:none;aspect-ratio:auto;height:auto;container-type:inline-size;
    display:flex;flex-wrap:wrap;align-items:flex-start;align-content:center;
    min-height:100svh;padding:18px 14px 26px}
  .sh:not(.backdrop){position:static;order:var(--o);width:100%;height:auto;
    flex:0 0 100%;inset:auto!important}
  .sh.backdrop{position:absolute!important;top:0!important;bottom:0!important;
    height:auto!important;aspect-ratio:auto!important;order:-1;z-index:0}
  /* Only IMAGE backdrops go full-bleed. A panel rect keeps its authored
     left/width, or slide 3's 16.5% grey band stretches across the whole
     slide and buries everything under it. */
  .sh.im.backdrop{left:0!important;right:0!important;width:auto!important}
  .sh.backdrop img{position:absolute;inset:0;width:100%!important;height:100%!important;
    object-fit:cover!important;left:0!important;top:0!important}
  .canvas>.sh:not(.backdrop){position:relative;z-index:1}
  .sh.rect:not(.backdrop){display:none}
  .sh.im:not(.backdrop){position:relative;aspect-ratio:var(--ar,1);margin:0 0 12px}
  .sh.tx{font-size:var(--ms)!important;line-height:1.3!important;
    padding:2px 2px 10px!important;white-space:normal!important}

  /* photo_with_caption: the label rides ON the plate rather than stacking
     under it — 24 of 34 slides, and the case archetype.py was written for.
     The desktop <img> is replaced by measured unit cells: whitespace authored
     for a 16:9 canvas is not worth reproducing at 390px (rule 29). */
  .slide[data-arch=plate] .canvas{position:relative;padding:0;min-height:100svh;
    align-content:stretch}
  .slide[data-arch=plate] .sh.im{display:none}
  .slide[data-arch=plate] .units{display:flex;position:absolute;inset:0;
    align-items:center}
  .units .unit{flex:0 0 100%;width:100%;height:100%;display:flex;
    align-items:center;justify-content:center;padding:7.5svh 12px 4svh;
    container-type:size}
  /* Largest box of the unit's aspect that fits the page, computed exactly.
     `height:100% + aspect-ratio` does NOT do this: an explicit height wins
     over aspect-ratio, so max-width clamps the width and the product is
     stretched vertically instead of scaled. */
  /* overflow:hidden is load-bearing: the crop scales the image up to ~5.5x
     the frame, so without clipping each cell shows its neighbours. */
  .units .uf{position:relative;margin:0 auto;overflow:hidden;
    width:min(100cqw, calc(100cqh * var(--uar)));
    height:min(100cqh, calc(100cqw / var(--uar)))}
  .units .uf img{position:absolute;object-fit:fill}
  /* Carousel: one unit per screen, snapped, first centred and focused. */
  .units.carousel{overflow-x:auto;scroll-snap-type:x mandatory;
    -webkit-overflow-scrolling:touch;scrollbar-width:none}
  .units.carousel::-webkit-scrollbar{display:none}
  .units.carousel .unit{scroll-snap-align:center;scroll-snap-stop:always}
  .slide[data-arch=plate] .sh.tx{position:absolute!important;z-index:3;
    top:3.5%!important;left:5%!important;width:90%!important;padding:0!important}

  /* Concept copy on the key visuals sits on a photograph. One continuous
     scrim behind BOTH blocks — they are adjacent siblings with a 0px gap, so
     two matching backgrounds read as one band without needing a wrapper.
     Tint + blur rather than tint alone: what actually destroys 12pt copy over
     a photo is high-frequency detail, not just luminance, and blurring it lets
     a lighter tint do the same work. The blur is progressive enhancement — the
     tint alone still clears 4.5:1 where it is unsupported. Text colours are
     untouched; only the ground is added (rule 32). */
  .slide[data-arch=keyvisual] .sh.tx{background:rgba(12,12,14,.62);
    -webkit-backdrop-filter:blur(10px) saturate(.92);
    backdrop-filter:blur(10px) saturate(.92);
    padding-left:5%!important;padding-right:5%!important}
  .slide[data-arch=keyvisual] .sh.tx.L{padding-top:14px!important;
    padding-bottom:2px!important;border-radius:12px 12px 0 0}
  /* The label needs the OPPOSITE ground to the body it shares a card with:
     #AF000F is dark (L=0.0915), so it needs L>=0.374 for 3:1 while the white
     body needs L<=0.183 for 4.5:1. Rather than split the card into two tones —
     a hard seam that reads as a rendering fault — the light ground shrink-wraps
     the label into a chip on top of the dark card. Shrink-to-fit is what makes
     it read as a deliberate eyebrow tag rather than a band that changed colour
     halfway. Applied to .t so the chip hugs the text, not the shape box. */
  .slide[data-arch=keyvisual] .sh.tx.L .t{align-self:flex-start;
    background:#FFFFFF;padding:3px 10px 2px;border-radius:6px;
    -webkit-backdrop-filter:none;backdrop-filter:none}
  .slide[data-arch=keyvisual] .sh.tx.cbi{padding-top:2px!important;
    padding-bottom:16px!important;border-radius:0 0 12px 12px}

  /* Destination dividers merge into the key visual that follows: the section
     collapses to zero height and its title overlays the next slide. The
     SECTION IS NOT REMOVED — the editor still sees 34 slides, the rail and
     counter still read 34, and every hook keeps its place (rule 30). */
  .slide[data-arch=divider]{min-height:0!important;height:0!important;
    padding:0!important;overflow:visible!important;position:relative;z-index:6}
  .slide[data-arch=divider] .canvas{min-height:0!important;height:0!important;
    padding:0!important;overflow:visible!important;background:transparent!important}
  /* height:auto is not optional. The shape carries an inline percentage height
     from the desktop canvas, and this section is collapsed to zero, so that
     percentage resolves to 0 — the glyphs render outside a zero-height content
     box and are clipped. The more specific rule has to restate it. */
  .slide[data-arch=divider] .sh.tx{position:absolute!important;
    top:0!important;left:0!important;width:100%!important;height:auto!important;
    font-size:2.15rem!important;line-height:1.15!important;z-index:6;
    display:block!important;
    background:var(--dbg,#fff);padding:4.4svh 6% 2.4svh!important}
  .slide[data-arch=divider] .sh.tx .t,
  .slide[data-arch=divider] .sh.tx p{height:auto!important}

  /* The variant matrix transposes: one card per variant row, each cell a
     labelled field. A 5-column table at 390px is unreadable, and a scroller
     would drag in the ground-sizing problem for a single slide. */
  .slide[data-arch=table] .sh.tbl{display:none}
  /* The 16.5% grey rail is a composition device for the 16:9 canvas — it lines
     up with the desktop table. Once the content is TRANSPOSED into cards there
     is nothing for it to align to, so it reads as a stray stripe down the edge.
     The full-canvas backdrop still supplies the ground. Scoped to transposed
     slides, not to a slide number: a partial-width rail only loses its meaning
     where the layout it framed no longer exists. */
  .slide[data-arch=table] .sh.rect.backdrop.rail{display:none}
  /* The title is an ELLIPSE on the 16:9 canvas — a composition device that
     reads as a stray red blob once the content around it is transposed. On
     mobile it becomes a plain full-bleed header at the top of the section,
     matching how every other label in this deck sits.
     The ellipse GEOMETRY goes; the FILL stays. Its text is #FFFFFF, chosen
     against that red ground — stripping the fill while keeping the authored
     colour would render white on white at 1.00:1, i.e. invisible. Same
     reasoning as rule 32: drop the shape, carry the ground. */
  .slide[data-arch=table] .sh.tx{order:-1;border-radius:0!important;
    flex:0 0 calc(100% + 28px);width:calc(100% + 28px)!important;
    margin:-10px -14px 10px!important;padding:15px 14px 13px!important}
  /* Static elements paint BELOW positioned ones, so a card with no z-index
     lands under the backdrop and reads as an empty slide even though every
     value is in the DOM. */
  /* Spacing tightened to fit three variants on one screen WITHOUT reducing
     type below the deck's body size — the type scale is shared with the rest
     of the deck (--ms-*) and is not this slide's to shrink. */
  .slide[data-arch=table] .card{display:block;position:relative;z-index:1;flex:0 0 100%;
    background:rgba(255,255,255,.92);border-radius:10px;padding:9px 14px 10px;margin:0 0 7px}
  .slide[data-arch=table] .canvas{padding:10px 14px 12px}
  .card h3{font-size:var(--ms-title);line-height:var(--ms-lh);margin:0 0 4px}
  .card dt{font-size:var(--ms-small);letter-spacing:.06em;text-transform:uppercase;
    opacity:.62;margin-top:5px}
  .card dd{font-size:var(--ms-body);line-height:var(--ms-lh);margin:2px 0 0}
}
"""


def build_cards(model, W):
    """Mobile-only transposition of the variant table into per-row cards.

    Emitted as static markup alongside the table (CSS picks one), so both
    representations parse with scripts disabled and every cell stays editable.
    """
    for sl in model["slides"]:
        for s in sl["shapes"]:
            if s["type"] != "table":
                continue
            rows = s["table"]["rows"]
            heads = ["".join(r["text"] for p in c["paras"] for r in p["runs"]).strip()
                     for c in rows[0]["cells"]]
            out = []
            for row in rows[1:]:
                vals = []
                for c in row["cells"]:
                    lines = []
                    for p in c["paras"]:
                        t = "".join(r["text"] for r in p["runs"]).strip()
                        if t:
                            lines.append((p.get("bullet") + " " if p.get("bullet") else "") + t)
                    vals.append("\n".join(lines))
                title = " ".join(v for v in vals[:2] if v)
                fields = "".join(
                    f"<dt>{esc(h)}</dt><dd class=\"ci\">"
                    + (esc(v).replace("\n", "<br>") or "&nbsp;") + "</dd>"
                    for h, v in list(zip(heads, vals))[2:])
                out.append(f'<div class="card"><h3 class="ci">{esc(title)}</h3>'
                           f"<dl>{fields}</dl></div>")
            return sl["n"], "".join(out)
    return None, ""


def main():
    model = json.load(open(OUT / "model.json"))
    man = json.load(open(OUT / "image_manifest.json"))
    units_by_slide = json.loads((OUT / "units.json").read_text()) \
        if (OUT / "units.json").exists() else {}
    body, dropped = render(model, man, units_by_slide)
    css = CSS.replace("/*__SCROLL_GATE__*/",
                      dkcss.mobile_scroll_release(".slide")
                      if EMIT_MOBILE_SCROLL_GATE else
                      "  /* mobile scroll gate NOT emitted -- see"
                      " EMIT_MOBILE_SCROLL_GATE above */")
    card_slide, cards = build_cards(model, model["w_pt"])
    if cards:
        marker = f'<section class="slide" id="s{card_slide}"'
        i = body.index(marker); j = body.index("</div>\n</section>", i)
        body = body[:j] + "    " + cards + "\n  " + body[j:]
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(DECK_TITLE)}</title>
<style>
{font_face_css(families=("Barlow Condensed", "Archivo"))}
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
    for k, v in dropped.items():
        if v:
            print(f"  dropped {len(v)} {k}: " + ", ".join(f"s{a}/{b}" for a, b in v))
    print(f"wrote {OUT/'index.html'}  {len(doc)/1024:.0f}KB")


if __name__ == "__main__":
    main()
