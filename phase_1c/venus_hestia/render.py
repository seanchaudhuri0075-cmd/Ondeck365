"""Deck 9 (Venus / Hestia) model.json -> a MULTI-FILE editable deck.

Two departures from every deck before this one, both forced by measurement and
both recorded in DECK9_HANDOFF.md:

MULTI-FILE. `index.html` plus a sibling `assets/` directory, referenced by
RELATIVE srcs. There is no embed step. At 169 MB of video plus 9 MB of images
the self-contained artefact would be ~240 MB, and Deck Editor v14's ceiling
measured between 180 and 240 MB (handoff section 8). The editor's R2 modal
uploads relative-path media off disk via its folder picker and rewrites every
src, which was tested end to end, so this shape publishes normally -- through
the modal, NEVER the one-click Publish button (LEARNINGS rule 37).

ASPECT. 1224 x 792pt, ratio 1.545455 -- 17x11in tabloid landscape, not 16:9.
Nothing here hardcodes it: `--ratio` comes from deckkit, which reads p:sldSz
(LEARNINGS rule 15, amended).

Rules held: 4/5 z-order preserved, poster under video as separate layers;
6 assets extracted never recreated; 9 type in cqw; 14 text verbatim;
21 no z-index inside the canvas -- paint order IS DOM order; 22 exactly one
`<section class="slide">` per source slide.
"""
from __future__ import annotations

import html
import json

from ondeck.render.fonts import font_face_css
from phase_1c.deckkit import css as dkcss
from phase_1c.venus_hestia import roles
from phase_1c.venus_hestia.paths import PATHS

E = html.escape

# OOXML alignment tokens are NOT CSS keywords. Emitting them raw produces
# `text-align:ctr`, which is invalid, silently ignored, and leaves the paragraph
# left-aligned. That is how 110 authored-centre paragraphs across 46 of this
# deck's 65 slides were rendering left -- including the retained cover title,
# which is what surfaced it at desktop review.
ALIGN = {"ctr": "center", "l": "left", "r": "right",
         "just": "justify", "dist": "justify", "justLow": "justify"}


def _pct(v: float, total: float) -> str:
    return f"{v / total * 100:.4f}%"


def run_css(r: dict, W: float) -> str:
    """Inline style for one run. Size in cqw so type scales with the canvas."""
    out = []
    sub = roles.sub_for(r.get("typeface"))
    if sub["stack"]:
        out.append(f"font-family:{sub['stack']}")
    weight = sub["weight"]
    if r.get("bold"):
        weight = 700
    if weight is not None:
        out.append(f"font-weight:{weight}")
    if r.get("italic"):
        out.append("font-style:italic")
    if r.get("size_pt"):
        out.append(f"font-size:{r['size_pt'] / W * 100:.4f}cqw")
    if r.get("color"):
        out.append(f"color:{r['color']}")
    return ";".join(out)


def shape_html(s: dict, W: float, H: float, imgman: dict, vidman: dict) -> str:
    cls = ["sh", {"text": "tx", "image": "im", "video": "vid", "rect": "rc"}[s["type"]]]
    style = [f"left:{_pct(s['x'], W)}", f"top:{_pct(s['y'], H)}",
             f"width:{_pct(s['w'], W)}", f"height:{_pct(s['h'], H)}"]
    if s.get("rot"):
        style.append(f"transform:rotate({s['rot']:.2f}deg)")
    if s.get("fill"):
        style.append(f"background:{s['fill']}")
    if s.get("stroke"):
        st = s["stroke"]
        col = st["hex"]
        if st.get("alpha") is not None and st["alpha"] < 1.0:
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            col = f"rgba({r},{g},{b},{st['alpha']:.4f})"
        # The 100 rects on this deck are hairline print guides: 0.31pt on a
        # 1224pt canvas is 0.025cqw, about half a device pixel at full size.
        # Kept in cqw so they scale with the canvas rather than thickening.
        style.append(f"border:{st['w_pt'] / W * 100:.4f}cqw solid {col}")

    inner = ""
    if s["type"] in ("image", "video"):
        poster = s.get("poster")
        pm = imgman.get(poster) if poster else None
        if pm:
            inner += (f'<img src="assets/{pm["out"]}" alt="" '
                      f'loading="lazy" decoding="async" class="poster">')
        if s["type"] == "video":
            vm = vidman.get(s.get("video"))
            if vm:
                # Rule 4: poster underlay and video overlay are separate layers,
                # video second so DOM order paints it above (rule 21 -- no z-index).
                # preload="none" + no autoplay: playback is driven by the
                # IntersectionObserver at the foot of the document.
                inner += (f'<video src="assets/{vm["out"]}" muted loop playsinline '
                          f'preload="none" poster="assets/{pm["out"]}" '
                          f'style="--ar:{vm["aspect"]}"></video>' if pm else
                          f'<video src="assets/{vm["out"]}" muted loop playsinline '
                          f'preload="none" style="--ar:{vm["aspect"]}"></video>')
    elif s["type"] == "text":
        paras = []
        for p in s.get("paras") or []:
            spans = "".join(f'<span style="{E(run_css(r, W))}">{E(r["text"])}</span>'
                            for r in (p.get("runs") or []) if r.get("text"))
            if not spans:
                paras.append('<p class="t e"></p>')
                continue
            css_align = ALIGN.get(p.get("align")) if p.get("align") else None
            assert p.get("align") is None or css_align, \
                f"unmapped OOXML alignment token {p.get('align')!r}"
            al = f"text-align:{css_align};" if css_align else ""
            paras.append(f'<p class="t" style="{al}">{spans}</p>')
        ins = s.get("insets") or {}
        if any(ins.get(k) for k in "lrtb"):
            style.append("padding:" + " ".join(
                f"{ins.get(k, 0) / (H if k in 'tb' else W) * 100:.4f}%"
                for k in ("t", "r", "b", "l")))
        if s.get("anchor"):
            style.append("justify-content:"
                         + {"t": "flex-start", "ctr": "center", "b": "flex-end"}
                         .get(s["anchor"], "flex-start"))
        inner = "".join(paras)

    return (f'<div class="{" ".join(cls)}" style="{";".join(style)}">{inner}</div>')


def build_css(deck: dict) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    return f"""
{dkcss.ratio_root(W, H)}
:root{{--deck-font:{roles.BODY_STACK};--slh:{roles.SOURCE_LINE_HEIGHT}}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;background:#111;-webkit-font-smoothing:antialiased;
  font-family:var(--deck-font)}}
img,video{{display:block;max-width:100%}}

#deck{{height:100svh;overflow-y:auto;overflow-x:hidden;
  scroll-snap-type:y proximity;-webkit-overflow-scrolling:touch}}
section.slide{{scroll-snap-align:start;scroll-snap-stop:always;display:flex;
  align-items:center;justify-content:center;min-height:100svh;background:#111}}

{dkcss.canvas_css('#FFFFFF') if hasattr(dkcss, 'canvas_css') else
 f'.canvas{{position:relative;width:{dkcss.CANVAS_WIDTH_FIT};'
 f'aspect-ratio:var(--ratio);container-type:size;overflow:hidden;'
 f'background:{deck["master_bg"]}}}'}

/* Rule 21: container-type makes the canvas a stacking context, so nothing
   inside carries a z-index. Paint order is DOM order, which is source
   z-order. */
.sh{{position:absolute;display:flex;flex-direction:column}}
.sh.im,.sh.vid{{overflow:hidden}}
.sh.im>img,.sh.vid>img,.sh.vid>video{{position:absolute;inset:0;
  width:100%;height:100%;object-fit:cover}}
.sh.tx{{white-space:pre-wrap}}
p.t{{margin:0;line-height:var(--slh)}}
p.t.e{{min-height:1em}}

@media (max-width:{dkcss.MOBILE_BP}px){{
{dkcss.mobile_scroll_release('section.slide')}
  /* MOBILE IS NOT REVIEWED YET. The desktop canvas is the deliverable for this
     round; this block only keeps the deck scrollable and legible on a phone so
     the first review is not blocked. A real reflow pass comes after desktop
     sign-off. */
  section.slide{{align-items:stretch;min-height:0}}
  .canvas{{width:100%;aspect-ratio:var(--ratio);container-type:size}}
}}
"""


def render(deck: dict, imgman: dict, vidman: dict) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    out = []
    for sl in deck["slides"]:
        shapes = "".join(shape_html(s, W, H, imgman, vidman) for s in sl["shapes"])
        out.append(f'<section class="slide" id="s{sl["n"]}" data-slide="{sl["n"]}">'
                   f'<div class="canvas">{shapes}</div></section>')
    return "\n".join(out)


# Playback bootstrap. Deck Editor v14 tolerates an inert <script> -- tested, all
# four positions survive byte-identical through import, commit and export
# (DECK9_HANDOFF.md section 7). 53 videos cannot all autoplay: preload="none"
# holds the bytes back and this starts at most MAX_PLAYING at a time.
PLAYER_JS = """
(function(){
  var MAX_PLAYING = 3, playing = [];
  function stop(v){ try{ v.pause(); v.currentTime = 0; }catch(e){} }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      var v = e.target;
      if (e.isIntersecting && e.intersectionRatio >= 0.5) {
        if (playing.indexOf(v) !== -1) return;
        while (playing.length >= MAX_PLAYING) stop(playing.shift());
        playing.push(v);
        var p = v.play(); if (p && p.catch) p.catch(function(){});
      } else {
        var i = playing.indexOf(v);
        if (i !== -1) { playing.splice(i, 1); stop(v); }
      }
    });
  }, {threshold:[0, 0.5]});
  document.querySelectorAll('video').forEach(function(v){ io.observe(v); });
})();
"""


def main() -> None:
    deck = json.loads((PATHS.out / "model.json").read_text())
    imgman = json.loads((PATHS.out / "image_manifest.json").read_text())
    vidman = json.loads((PATHS.out / "video_manifest.json").read_text())
    body = render(deck, imgman, vidman)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(roles.DECK_TITLE)}</title>
<style>
{font_face_css(families=roles.FONT_FAMILIES)}
{build_css(deck)}
</style>
</head>
<body>
<main id="deck">
{body}
</main>
<script>{PLAYER_JS}</script>
</body>
</html>
"""
    (PATHS.out / "index.html").write_text(doc)
    print(f"wrote {PATHS.out/'index.html'}  {len(doc)/1024:.0f} KB")


if __name__ == "__main__":
    main()
