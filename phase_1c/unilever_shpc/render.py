"""Unilever SHPC (deck 11) -- DESKTOP renderer. Local preview only.

A NEW renderer, not a copy of `phase_1c/secret/render.py`. Secret shipped a
mobile reflow of one DOM and no scroll-snap; this deck's locked rules
(DECK11_HANDOFF.md section 8) are the opposite: a separate mobile DOM and one
desktop snap point per slide. What is taken from Secret is exactly the list
its handoff calls reusable -- `run_css` / `para_html` / `box_style` /
`crop_img` / `rgba` in shape, `deckkit.css` and `deckkit.markup`, and the
`p.t` strut lesson (LEARNINGS 41(s): a paragraph that carries a unitless
line-height also carries the font-size of its own runs). `plate_css`,
`divider_css`, `header_css` and the `@media` reflow block are NOT here.

Document shape (step 13):

    <nav class="rail" hidden>            editor metadata, slide names
    <main id="deck-desktop">             35 x <section class="slide">
    <main id="deck-mobile" hidden>       EMPTY -- reserved for the mobile round

The mobile round must NOT put `class="slide"` sections inside #deck-mobile:
Deck Editor v14 keys on `class="slide"` (LEARNINGS rule 22) and would harvest
70 slides. That constraint is recorded here because it is the next author's
first trap.

Editor vocabulary (Deck_Editor_v14.html:783-788): headlines are `.L > .t`,
body copy is any `.ci .tlt .tlb ...` element -- on save the editor replaces
an element's innerHTML with its TRIMMED text, which is why `.ci` never goes
on a run whose whitespace matters. Images are only harvested when their src
is absolute (http / r2.dev / data:), so with the relative `assets/` paths of
this preview the editor sees 0 images -- known (handoff section 6), and the
reason MEDIA_BASE exists.

Fonts come from roles.stack_for / sub_for exactly (section 4's decision):
runs of 30pt and up lead with the Apple system entries, runs under 30pt are
Archivo wdth 90 on every device. `build_html(..., apple=False)` is the QA
switch from section 4's rule: the same document with the Apple entries
removed, which is the only way this Mac can show the non-Apple path.

Rule 21: nothing inside the canvas carries a z-index; paint order is DOM
order, so shapes are emitted in the model's order and the poster-under-video
pair is emitted poster-first.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from ondeck.render.fonts import font_face_css
from phase_1c.deckkit import css as dkcss
from phase_1c.deckkit import markup as dkmarkup
from phase_1c.deckkit.paths import REPO, DeckPaths
from phase_1c.unilever_shpc import roles

esc = dkmarkup.esc

# Media URLs are `MEDIA_BASE + "assets/" + file`. Empty = relative paths for
# the local preview. The R2 publish sets it to the absolute media origin
# (handoff section 6: this deck is the GAP shape, every <video>/poster
# absolute on media.globalimaige.com/<R2_PREFIX>/...). R2_PREFIX is still None.
MEDIA_BASE = ""
ASSETS = "assets/"

# Faces roles.sub_for refuses (roles.FONTS_PENDING): rendered with a VISIBLE
# fallback and a TODO comment in the document. One run each --
#   League Gothic  slide 13  "STUNNING" 50pt
#   Calibri        slide 35  "." 18pt bold (the inherited theme minor font)
PENDING_FALLBACK = {
    "league gothic": "'League Gothic',Impact,'Arial Narrow',sans-serif",
    "calibri":       "Carlito,Calibri,'Liberation Sans',Arial,sans-serif",
}

# Editor role for a text box. `.L > .t` headlines: any box holding a display
# run (roles.APPLE_MIN_PT and up -- 30/35/40pt here). `.tlt` / `.tlb`: the
# showcase slides' one-paragraph top title and bottom label (a box whose top
# edge sits in the top or bottom 15% of the canvas). Everything else is body
# copy, harvested run by run through `.ci`. Recorded as this build's mapping;
# the editor defines the class names, not what a deck puts in them.
TLT_BAND = 0.15

# The deck's lime accent (the "AI" in ImAIge, the stat numerals): #A8BA01 on
# 30 runs. Headline runs in it also carry the editor's `.lime` class.
ACCENT = "#A8BA01"


def media_url(file: str) -> str:
    return f"{MEDIA_BASE}{ASSETS}{file}"


# ---------------------------------------------------------------- text

def rgba(hexv, alpha):
    if alpha is None or alpha >= 1.0:
        return hexv
    h = hexv.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{round(alpha, 4)})"


def font_for(r, apple: bool):
    """(stack, weight, pending_note) for a run, via roles. Never a guess: a
    face roles does not map is a KeyError here too."""
    face = r.get("typeface") or ""
    key = face.strip().lower()
    if key in roles.FONTS_PENDING:
        return PENDING_FALLBACK[key], (700 if r.get("bold") else 400), roles.FONTS_PENDING[key]
    sub = roles.sub_for(face, r.get("size_pt"), apple=apple)
    w = sub["weight"]
    if w is None:
        w = 700 if r.get("bold") else 400
    return sub["stack"], w, None


def run_css(r, W: float, apple: bool) -> str:
    stack, weight, _ = font_for(r, apple)
    out = [f"font-family:{stack}", f"font-weight:{weight}"]
    if r.get("italic"):
        out.append("font-style:italic")
    if r.get("size_pt"):
        out.append(f"font-size:{r['size_pt'] / W * 100:.4f}cqw")
    if r.get("color"):
        out.append(f"color:{rgba(r['color'], r.get('color_alpha'))}")
    return ";".join(out)


def ci_ok(text: str) -> bool:
    """`.ci` only on a run the editor can round-trip: non-blank, and no
    leading or trailing whitespace (the editor trims on save)."""
    return bool(text) and text == text.strip()


def run_span(r, W: float, apple: bool, role: str) -> str:
    text = r.get("text") or ""
    classes = []
    if role == "body" and ci_ok(text):
        classes.append("ci")
    if role == "headline" and (r.get("color") or "").upper() == ACCENT:
        # The editor re-wraps exactly one `<span class="lime">` per headline
        # after an edit; the deck's accent runs ("AI" in ImAIge) ride on it.
        classes.append("lime")
    _, _, pending = font_for(r, apple)
    todo = f"<!-- TODO font: {esc(r.get('typeface'))} -- {esc(pending)} -->" if pending else ""
    cls = f' class="{" ".join(classes)}"' if classes else ""
    data = f' data-font-todo="{esc(r.get("typeface"))}"' if pending else ""
    return f'{todo}<span{cls}{data} style="{run_css(r, W, apple)}">{esc(text)}</span>'


def para_html(p, W: float, apple: bool, role: str, fallback_pt=None) -> str:
    bits = []
    css_align = {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(p.get("align"))
    if css_align:
        bits.append(f"text-align:{css_align}")
    if p.get("marL"):
        bits.append(f"padding-left:{p['marL'] / W * 100:.4f}cqw")
    if p.get("indent"):
        bits.append(f"text-indent:{p['indent'] / W * 100:.4f}cqw")
    # OOXML spcPct is a multiple of SINGLE LINE SPACING, and the single-line
    # factor is SOURCE_LINE_HEIGHT (secret/roles.py, the four-deck fit).
    # Emitted on EVERY paragraph so no paragraph inherits `normal`, which is
    # face-dependent and would move on the Apple/Archivo split.
    bits.append(f"line-height:{(p.get('line_pct') or 1.0) * roles.SOURCE_LINE_HEIGHT:.4f}")
    # The strut lesson (LEARNINGS 41(s)): the paragraph sizes its own line box
    # from its runs, never from an inherited px value.
    sizes = [r["size_pt"] for r in p["runs"] if r.get("size_pt")]
    size = max(sizes) if sizes else fallback_pt
    if size:
        bits.append(f"font-size:{size / W * 100:.4f}cqw")
    # Same contract as deckkit.markup.runs_html (a `<br>` after any run marked
    # br_after, even an empty one); inlined only because the span carries
    # editor classes that helper's style callback cannot add.
    spans = "".join((run_span(r, W, apple, role) if r.get("text") else "")
                    + ("<br>" if r.get("br_after") else "") for r in p["runs"])
    cls = "t" + (f" {role}" if role in ("tlt", "tlb") else "")
    return f'<p class="{cls}" style="{";".join(bits)}">{spans or "<br>"}</p>'


def text_role(sh, H: float) -> str:
    sizes = [r.get("size_pt") or 0 for p in sh["paras"] for r in p["runs"] if (r.get("text") or "").strip()]
    if sizes and max(sizes) >= roles.APPLE_MIN_PT:
        return "headline"
    live = [p for p in sh["paras"] if any((r.get("text") or "").strip() for r in p["runs"])]
    if len(live) == 1:
        if sh["y"] / H <= TLT_BAND:
            return "tlt"
        if sh["y"] / H >= 1 - TLT_BAND:
            return "tlb"
    return "body"


# ---------------------------------------------------------------- shapes

def box_style(sh, W: float, H: float) -> str:
    """Absolute placement in container units: x/w in cqw, y/h in cqh."""
    s = [f"left:{sh['x'] / W * 100:.4f}cqw", f"top:{sh['y'] / H * 100:.4f}cqh",
         f"width:{sh['w'] / W * 100:.4f}cqw", f"height:{sh['h'] / H * 100:.4f}cqh"]
    if sh.get("rot"):
        s.append(f"transform:rotate({sh['rot']:.3f}deg)")
    return ";".join(s)


def crop_style(crop) -> str:
    """A srcRect crop as a CSS window over the WHOLE asset (never baked)."""
    vw = 1.0 - crop.get("l", 0) - crop.get("r", 0)
    vh = 1.0 - crop.get("t", 0) - crop.get("b", 0)
    if vw <= 0 or vh <= 0:
        return ""
    return (f"width:{100 / vw:.4f}%;height:{100 / vh:.4f}%;"
            f"left:{-crop.get('l', 0) / vw * 100:.4f}%;top:{-crop.get('t', 0) / vh * 100:.4f}%")


def nm(sh) -> str:
    return f' data-name="{esc(sh.get("name", ""))}"'


def stroke_css(st, H: float) -> str:
    if not st:
        return ""
    return (f"border:{(st.get('w_pt') or 1.0) / H * 100:.4f}cqh "
            f"{'dashed' if 'dash' in (st.get('dash') or '') .lower() and st.get('dash') != 'solid' else 'solid'} "
            f"{rgba(st.get('hex', '#000000'), st.get('alpha'))}")


def video_html(sh, man, W, H, src_name, poster_name, playback, loop, muted, extra_cls="") -> str:
    v = man["videos"].get(src_name) if src_name in man["videos"] else None
    p = man["images"].get(poster_name)
    poster = media_url(p["out"]) if p else ""
    under = f'<img class="poster" src="{poster}" alt="" aria-hidden="true">' if poster else ""
    attrs = [f'src="{media_url(v["out"]) if v else src_name}"', 'preload="none"', "playsinline"]
    if poster:
        attrs.append(f'poster="{poster}"')
    # `muted` FOLLOWS model.json. An auto clip the author did not mute still
    # STARTS muted (browsers block audible autoplay) -- the player script does
    # that at runtime and shows the unmute control, so the attribute stays
    # honest about what the deck says.
    if muted:
        attrs.append("muted")
    if loop:
        attrs.append("loop")
    attrs.append(f'data-playback="{playback}"')
    if not muted:
        attrs.append('data-sound="1"')
    style = f"{box_style(sh, W, H)};--ar:{v['aspect'] if v else '16/9'}"
    inner = ""
    if sh.get("crop"):
        cs = crop_style(sh["crop"])
        under = f'<img class="poster" src="{poster}" alt="" aria-hidden="true" style="{cs}">' if poster else ""
        inner = f'<video {" ".join(attrs)} style="{cs}"></video>'
    else:
        inner = f'<video {" ".join(attrs)}></video>'
    ctl = ('<button class="vplay" type="button" aria-label="Play"></button>' if playback == "click"
           else ('<button class="vsound" type="button" aria-label="Unmute" hidden></button>' if not muted else ""))
    cls = "sh vid" + (" cropped" if sh.get("crop") else "") + (f" {extra_cls}" if extra_cls else "")
    return f'<div class="{cls}"{nm(sh)} style="{style}">{under}{inner}{ctl}</div>'


def shape_html(sh, man, W, H, apple: bool) -> str:
    t = sh.get("type")
    style = box_style(sh, W, H)

    if t == "image":
        a = man["images"].get(sh.get("poster"))
        if not a:
            return ""
        if sh.get("animated_gif") and a.get("animated"):
            # Slide 26: the GIF ships as a silent H.264 clip + its frame-0 WebP
            # poster (handoff 7.4). A muted looping <video>, autoplay.
            anim = a["animated"]
            return video_html(sh, {"videos": {anim["out"]: {"out": anim["out"], "aspect": anim["aspect"]}},
                                   "images": man["images"]},
                              W, H, anim["out"], sh.get("poster"), "auto", bool(anim.get("loop", True)),
                              True, extra_cls="gif")
        src = media_url(a["out"])
        alt = esc(sh.get("name", ""))
        if sh.get("crop"):
            inner = f'<img data-media src="{src}" alt="{alt}" style="{crop_style(sh["crop"])}">'
            return f'<div class="sh im cropped"{nm(sh)} style="{style}">{inner}</div>'
        return f'<div class="sh im"{nm(sh)} style="{style}"><img data-media src="{src}" alt="{alt}"></div>'

    if t == "video":
        if sh.get("video") not in man["videos"]:
            return ""
        return video_html(sh, man, W, H, sh["video"], sh.get("poster"),
                          sh.get("playback") or "auto", bool(sh.get("loop")), bool(sh.get("muted")))

    if t in ("text", "rect"):
        bits = [style]
        r = dkcss.prst_css(sh.get("prst"))
        if r:
            bits.append(r.rstrip(";"))
        if sh.get("fill"):
            bits.append(f"background:{rgba(sh['fill'], sh.get('fill_alpha'))}")
        st = stroke_css(sh.get("stroke"), H)
        if st:
            bits.append(st)
        if t == "rect":
            return f'<div class="sh rc"{nm(sh)} style="{";".join(bits)}"></div>'
        ins = sh.get("insets") or {}
        # 22 wrap="square" text boxes overhang the canvas's RIGHT edge by
        # 2-43pt (slides 2, 3, 5-8, 10, 11, 13, 15, 34). Their authored width
        # is where PowerPoint WRAPPED, but anything past the edge is clipped
        # on screen; and Archivo, 3.4% narrower than SF Pro, pulls a word up
        # onto a line that then runs into the clip (slide 2 "Expand creative
        # capacity ... with more formats" lost "formats"). The wrap width is
        # therefore clamped at the canvas edge. Measured before it was done,
        # on every one of the 22 boxes with the shipped Archivo file: at the
        # clamped width every SF Pro line still fits on one line -- no new
        # wrap anywhere -- and slide 2's box now breaks exactly where SF Pro
        # did. The display boxes (s6-15, s34) have 8-85% slack at the clamp.
        # Left overhang (the -16.4pt footer on 27 slides) is left as authored:
        # the text is inset 7.2pt and the canvas clips what PowerPoint clips.
        if sh.get("wrap") == "square" and sh["x"] + sh["w"] > W and sh["x"] < W:
            style = box_style(dict(sh, w=W - sh["x"]), W, H)
            bits[0] = style
        # Vertical insets in cqh, horizontal in cqw (LEARNINGS 41(c): a %
        # padding resolves against WIDTH on all four sides).
        bits.append(f"padding:{ins.get('t', 0) / H * 100:.3f}cqh {ins.get('r', 0) / W * 100:.3f}cqw "
                    f"{ins.get('b', 0) / H * 100:.3f}cqh {ins.get('l', 0) / W * 100:.3f}cqw")
        bits.append("justify-content:" + {"ctr": "center", "b": "flex-end"}.get(sh.get("anchor"), "flex-start"))
        role = text_role(sh, H)
        cls = "sh tx" + (" L" if role == "headline" else "") + (" nowrap" if sh.get("wrap") == "none" else "")
        # An EMPTY paragraph (20 boxes end in one) has no run to size its strut
        # from; the model does not carry endParaRPr. It takes the nearest
        # sized paragraph before it (else after), which is what the autofit
        # box heights measured in STEP 11 imply: one blank line of that size.
        para_sizes = [max((r["size_pt"] for r in p["runs"] if r.get("size_pt")), default=None) for p in sh["paras"]]
        paras = []
        for i, p in enumerate(sh["paras"]):
            fb = next((sz for sz in reversed(para_sizes[:i]) if sz), None) or next((sz for sz in para_sizes[i + 1:] if sz), None)
            paras.append(para_html(p, W, apple, role, fallback_pt=fb))
        return f'<div class="{cls}"{nm(sh)} style="{";".join(bits)}">{"".join(paras)}</div>'

    return ""


# ---------------------------------------------------------------- document

def archivo_font_face() -> str:
    """'Archivo wdth90' from the committed woff2, inlined. url() only -- a
    `local()` source would let an installed face leak in (section 4)."""
    f = roles.FONT_FILES[roles.ARCHIVO_FAMILY]
    b64 = base64.b64encode((REPO / f["path"]).read_bytes()).decode("ascii")
    return (f"@font-face{{font-family:'{roles.ARCHIVO_FAMILY}';font-style:normal;"
            f"font-weight:{f['font_weight']};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('{f['format']}')}}")


def build_css(deck) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    bp = dkcss.MOBILE_BP
    return f"""{dkcss.ratio_root(W, H)}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:#111;color:#111;height:100%}}
body{{font-family:{roles.stack_for(0, apple=False)};-webkit-text-size-adjust:100%}}
img,video{{display:block;max-width:100%}}

/* ---- desktop: one snap point per slide (section 8) ---- */
#deck-desktop{{height:100svh;overflow-y:auto;overflow-x:hidden;
  scroll-snap-type:y mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:none}}
#deck-desktop::-webkit-scrollbar{{display:none}}
section.slide{{scroll-snap-align:start;scroll-snap-stop:always;
  height:100svh;display:flex;align-items:center;justify-content:center;background:#111}}

/* ---- the authored canvas: 16:9 from p:sldSz, container units ---- */
.canvas{{position:relative;width:{dkcss.CANVAS_WIDTH_FIT};aspect-ratio:var(--ratio);
  container-type:size;overflow:hidden;background:var(--bg,{deck["master_bg"]})}}
.sh{{position:absolute;display:flex;flex-direction:column;overflow:visible}}
{dkcss.crop_frame_clip('.sh.im', '.sh.vid')}
/* fill, not cover: PowerPoint STRETCHES an uncropped picture to its box. Slide
   33's three billboard photos sit in a group scaled 5% wider than its
   children, and LibreOffice draws them stretched exactly as PowerPoint does;
   `cover` had cropped them instead. Every other box matches its source
   aspect within 3%, so nothing else moves. */
.sh.im>img,.sh.vid>video,.sh.vid>img.poster{{width:100%;height:100%;object-fit:fill}}
/* poster under video by DOM order -- no z-index inside the canvas (rule 21) */
.sh.vid>img.poster,.sh.vid>video{{position:absolute;inset:0}}
.sh.cropped>img,.sh.cropped>video,.sh.cropped>img.poster{{position:absolute;max-width:none;object-fit:fill;inset:auto}}
/* wrap="square" wraps AT THE BOX EDGE, mid-word if a token does not fit
   (PowerPoint's behaviour); wrap="none" never wraps and overhangs instead. */
.sh.tx{{overflow-wrap:anywhere}}
.sh.tx.nowrap p.t{{white-space:pre}}
p.t{{margin:0;white-space:pre-wrap;font-kerning:normal}}
.lime{{color:{ACCENT}}}

/* ---- video controls: glyphs are CSS content, never live text ---- */
.vplay,.vsound{{position:absolute;border:0;cursor:pointer;background:rgba(0,0,0,.55);color:#fff;
  font:inherit;padding:0;display:flex;align-items:center;justify-content:center}}
.vplay{{left:50%;top:50%;width:9cqw;height:9cqw;margin:-4.5cqw 0 0 -4.5cqw;border-radius:50%}}
.vplay::before{{content:"";display:block;width:0;height:0;margin-left:0.8cqw;
  border-style:solid;border-width:2cqw 0 2cqw 3.4cqw;border-color:transparent transparent transparent #fff}}
.vsound{{right:1cqw;bottom:1cqw;height:2.6cqw;padding:0 1cqw;border-radius:1.3cqw;font-size:1.1cqw}}
.vsound::before{{content:"\\1F507  tap for sound"}}
.vsound[hidden],.vplay[hidden]{{display:none}}
.sh.vid.playing>.vplay{{opacity:0}}
.sh.vid.playing:hover>.vplay{{opacity:1;background:rgba(0,0,0,.35)}}
.sh.vid.playing>.vplay::before{{border-width:0;width:1.2cqw;height:3cqw;margin:0;
  border-left:1cqw solid #fff;border-right:1cqw solid #fff;background:none}}

/* ---- mobile DOM: reserved; the desktop tree shows meanwhile ---- */
#deck-mobile[hidden]{{display:none}}
@media (max-width:{bp}px){{
{dkcss.mobile_scroll_release('section.slide', '#deck-desktop')}
}}
/* editor metadata, not part of the deck (rule 22) */
.rail[hidden]{{display:none !important}}
"""


PLAYER_JS = r"""
(function(){
  var root=document.getElementById('deck-desktop');
  var vids=Array.prototype.slice.call(document.querySelectorAll('#deck-desktop video'));
  if(!('IntersectionObserver' in window)){return;}
  // QA: `?noplay` leaves every clip on its poster so a screenshot compares
  // posters with posters (validate.py --shots). Never set by the deck itself.
  var noplay=/[?&]noplay\b/.test(location.search);
  function wrap(v){return v.parentNode;}
  function tryPlay(v){var p=v.play();if(p&&p.catch){p.catch(function(){});}}
  vids.forEach(function(v){
    var w=wrap(v),mode=v.dataset.playback||'auto';
    v.addEventListener('play',function(){w.classList.add('playing');});
    v.addEventListener('pause',function(){w.classList.remove('playing');});
    if(mode==='click'){
      // poster + play control; plays WITH SOUND on the viewer's click
      var b=w.querySelector('.vplay');
      var toggle=function(e){e.preventDefault();if(v.paused){v.muted=false;tryPlay(v);}else{v.pause();}};
      if(b){b.addEventListener('click',toggle);}
      v.addEventListener('click',toggle);
    }else if(v.dataset.sound==='1'){
      // authored WITHOUT mute: autoplay must still start silent, so offer sound
      var s=w.querySelector('.vsound');
      if(s){s.hidden=false;s.addEventListener('click',function(){v.muted=!v.muted;s.setAttribute('aria-label',v.muted?'Unmute':'Mute');s.style.opacity=v.muted?'':'0.5';});}
    }
  });
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(en){
      var v=en.target,mode=v.dataset.playback||'auto';
      if(en.isIntersecting&&en.intersectionRatio>=0.5){
        if(mode==='auto'&&!noplay){v.muted=true;tryPlay(v);}
      }else{
        if(!v.paused){v.pause();}
      }
    });
  },{root:root,threshold:[0,0.5,1]});
  vids.forEach(function(v){io.observe(v);});
})();
"""


def build_html(deck, man, apple: bool = True) -> str:
    W, H = deck["w_pt"], deck["h_pt"]
    secs, rail = [], []
    for sl in deck["slides"]:
        n = sl["n"]
        shapes = [sh for sh in sl["shapes"]
                  if not (roles.SUPPRESS_REVIEW_STICKERS and sh.get("review_sticker"))
                  and not (roles.SUPPRESS_OCCLUDED_SHAPES and sh.get("occluded"))]
        body = "".join(shape_html(sh, man, W, H, apple) for sh in shapes)
        bg = sl.get("bg") or ("#FFFFFF" if sl.get("bg_from") == "none" else deck["master_bg"])
        label = next((r["text"] for sh in shapes for p in (sh.get("paras") or [])
                      for r in p["runs"] if (r.get("text") or "").strip()), f"Slide {n}")
        rail.append(f'<li class="rail-item" data-target="s{n}">'
                    f'<span class="rail-num">{n:02d}</span>'
                    f'<span class="rail-label">{esc(label.strip()[:60])}</span></li>')
        grp = roles.group(sl) or ""
        secs.append(
            f'<section class="slide" id="s{n}" data-slide="{n}" data-group="{grp}" '
            f'aria-label="{esc(label.strip()[:80])}">'
            f'<div class="canvas" style="--bg:{bg}">{body}</div></section>')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(roles.DECK_TITLE)}</title>
<style>
{archivo_font_face()}
{font_face_css(families=roles.FONT_FAMILIES)}
{build_css(deck)}
</style>
</head>
<body{'' if apple else ' data-qa="archivo-forced"'}>
<nav class="rail" hidden aria-hidden="true"><ol>
{chr(10).join(rail)}
</ol></nav>
<main id="deck-desktop">
{chr(10).join(secs)}
</main>
<main id="deck-mobile" hidden></main>
<script>{PLAYER_JS}</script>
</body>
</html>
"""


def paths_for() -> DeckPaths:
    return DeckPaths(slug=roles.SLUG, raw=Path("/nonexistent/raw"),
                     out=REPO / "out" / roles.SLUG, shots=Path("/nonexistent/shots"))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-apple", action="store_true",
                    help="QA: force the Archivo path (Apple entries removed from every stack)")
    ap.add_argument("--out", default=None, help="write here instead of out/<slug>/index.html")
    a = ap.parse_args(argv)
    paths = paths_for()
    deck = json.loads((paths.out / "model.json").read_text())
    man = json.loads((paths.out / "asset_manifest.json").read_text())
    out = build_html(deck, man, apple=not a.no_apple)
    dest = Path(a.out) if a.out else paths.out / "index.html"
    dest.write_text(out)
    print("%s  %.0f KB  sections=%d  apple=%s" % (dest, len(out) / 1024,
          out.count('<section class="slide'), not a.no_apple))


if __name__ == "__main__":
    main()
