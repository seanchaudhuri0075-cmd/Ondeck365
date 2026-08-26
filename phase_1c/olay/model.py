"""Build the Olay slide model straight from the extracted OOXML.

Reuses the pipeline's own topology walk (`parse.shapes.flatten_slide`), which
already composes nested-group transforms and assigns depth-first z-order —
LEARNINGS rule 3. It takes anything exposing `.element`, so we hand it an
lxml root rather than loading a 746MB file through python-pptx.

Every rule this stage is holding:
  1 — media bound ONLY through slideN.xml.rels, never by visual position.
      A video <p:pic> carries TWO rIds: a:videoFile/@r:link for the movie and
      a:blip/@r:embed for its poster.
  2 — real parser, explicit namespaces, no regex on structural attributes.
  3 — every shape in the spTree is emitted or explicitly logged as skipped.
  4/5 — z-order preserved exactly; nothing is flattened or promoted.
 14 — text emitted verbatim, typos and all.
"""
from __future__ import annotations

import json, os, sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from functools import lru_cache

from lxml import etree
from PIL import Image

sys.path.insert(0, "/Users/gif025/Downloads/ondeck-pipeline")
from ondeck.parse.shapes import flatten_slide
from ondeck.parse.slide import NS, _is_design_locker
from ondeck.parse.theme import parse_theme, SCHEME_ALIASES
from ondeck.parse.color import ColorResolver
from ondeck.parse.font_calibration import (
    MATCHED_METRIC_SUBS, SOURCE_LINE_HEIGHT_RATIOS, MATCHED_METRIC_AXES,
    classify_substitution,
)

RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/olay/raw")
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
EMU_PT = 12700.0

# Master otherStyle/lvl1pPr/defRPr — what a run with no rPr resolves to.
# Read from the file rather than assumed; asserted in build().
INHERITED = {"size_pt": None, "typeface": None, "color": None}


class _SlideShim:
    """flatten_slide() only ever touches `.element`."""
    def __init__(self, root): self.element = root


def _rels(n: int) -> dict:
    p = RAW / "ppt" / "slides" / "_rels" / f"slide{n}.xml.rels"
    return {r.get("Id"): {"target": r.get("Target"), "type": r.get("Type").rsplit("/", 1)[-1]}
            for r in etree.parse(str(p)).getroot()}


_CR_CACHE: dict = {}


def _resolver_for(theme):
    """ColorResolver for a Theme, cached. ColorResolver takes a plain dict and
    does not know the bg1/tx1/bg2/tx2 -> lt1/dk1/lt2/dk2 aliases that
    Theme.resolve() handles, so the dict is expanded with SCHEME_ALIASES first
    (rule 28's practical note)."""
    key = id(theme)
    cr = _CR_CACHE.get(key)
    if cr is None:
        tdict = asdict(theme)
        tdict.update({k: getattr(theme, v) for k, v in SCHEME_ALIASES.items()})
        cr = _CR_CACHE[key] = ColorResolver(tdict)
    return cr


def _solid_color(fill_el, theme):
    """Resolve <a:solidFill> to (hex, alpha) through ColorResolver — rule 28.

    This previously read `schemeClr/@val`, looked it up in the theme and
    stopped, which silently dropped every colour transform. It shipped the
    slide 9/10 wash as #FFFFFF where `bg1 + lumMod 85%` resolves to #D9D9D9 —
    a plausible wrong colour rather than an error, live for months. Alpha is
    still read separately: `final_hex` does not carry it.
    """
    if fill_el is None:
        return None, None
    srgb = fill_el.find("a:srgbClr", NS)
    schem = fill_el.find("a:schemeClr", NS)
    node = srgb if srgb is not None else schem
    if node is None:
        return None, None
    a = node.find("a:alpha", NS)
    alpha = int(a.get("val")) / 100000.0 if a is not None else None
    try:
        hexv = _resolver_for(theme).resolve(fill_el).get("final_hex")
        if hexv:
            return "#" + hexv.upper().lstrip("#"), alpha
    except (KeyError, ValueError, AttributeError):
        pass
    hexv = (srgb.get("val").upper() if srgb is not None
            else theme.resolve(schem.get("val")))
    return "#" + hexv, alpha


@lru_cache(maxsize=256)
def _opaque_fraction(src: str) -> float:
    """Fraction of an image's pixels that are fully opaque.

    Presence of an alpha CHANNEL says nothing about whether an image is
    see-through. Slide 33's cover art is RGBA with alpha 128..255, but only
    0.023% of pixels are below 255 — scattered dither, and the areas sitting
    directly over the buried content are solid 255. Judging it by mode alone
    would have missed a real occlusion; judging it by min-alpha would have
    rejected one. Measure the pixels.
    """
    im = Image.open(RAW / "ppt" / "media" / src)
    if im.mode not in ("RGBA", "LA"):
        return 1.0
    a = im.getchannel("A")
    hist = a.histogram()
    return hist[255] / float(sum(hist))


OPAQUE_MIN = 0.999


def _is_opaque(shape) -> bool:
    if shape["type"] == "rect":
        return bool(shape.get("fill")) and (shape.get("fill_alpha") is None
                                            or shape["fill_alpha"] >= 1.0)
    if shape["type"] in ("image", "video"):
        src = shape.get("poster")
        return bool(src) and _opaque_fraction(src) >= OPAQUE_MIN
    return False


def _covers_canvas(shape, W, H, tol=1.0) -> bool:
    return (shape["x"] <= tol and shape["y"] <= tol
            and shape["x"] + shape["w"] >= W - tol
            and shape["y"] + shape["h"] >= H - tol)


def _full_height(shape, H, tol=1.0) -> bool:
    return shape["y"] <= tol and shape["y"] + shape["h"] >= H - tol


def _mark_occluded_and_backdrop(shapes, W, H):
    """Flag content buried under an opaque cover, and the slide's ground layer.

    OCCLUSION — slide 33 is slide 2 duplicated, with an opaque full-canvas
    image laid over it and new content on top. PowerPoint simply paints in
    z-order so the old slide is invisible. A mobile reflow flattens z-order
    into a flow stack, which resurrects every buried shape. Anything sitting
    below an opaque full-canvas shape is therefore not part of the deck.

    BACKDROP — the run of shapes at the bottom of the VISIBLE stack that forms
    the slide's ground: a full-canvas image (optionally with a tint/wash rect
    over it), or the full-height panel rects that make up a split background.
    The run stops at the first non-full-canvas image, which is where real
    content starts. These become a full-bleed layer on mobile rather than
    boxed tiles — on a phone the background IS the slide.
    """
    for s in shapes:
        s["occluded"] = False
        s["backdrop"] = False

    covers = [i for i, s in enumerate(shapes)
              if _covers_canvas(s, W, H) and _is_opaque(s)]
    start = max(covers) if covers else 0
    for s in shapes[:start]:
        s["occluded"] = True

    for s in shapes[start:]:
        if s["type"] in ("image", "video"):
            if not _covers_canvas(s, W, H):
                break
            s["backdrop"] = True
        elif s["type"] == "rect":
            if not _full_height(s, H):
                break
            s["backdrop"] = True
        else:
            break


def _is_review_sticker(paras, fill_hex, fill_from_style, style_font, autofit, theme):
    """Flag a text shape that looks like a comment box dropped on the slide.

    DETECTION ONLY. This never removes anything — the shape stays in the model
    carrying `review_sticker: true`, and suppression is an explicit per-deck
    opt-in in roles.py. That split is the same rule PHASE_1C_ARCHITECTURE.md
    sets for the deck classifier: a signature may inform the workflow, never
    silently change what renders. A legitimately theme-styled callout on some
    future deck must not vanish because it matched a heuristic.

    The signature is a behavioural fingerprint, not a string match. On the Olay
    deck it separates 6 shapes from 22 real text blocks with no overlap on any
    of five independent properties:

      * fill resolves to a theme ACCENT, and does so through <p:style>/fillRef
        rather than direct formatting
      * text colour comes from <a:fontRef> (lt1 / white here)
      * no declared typeface on any run  -> falls back to the theme minor font
      * no declared size on any run      -> falls back to the master's 18pt
      * no <a:spAutoFit/>                -> the box was hand-dragged

    Together those say: whoever made this shape chose nothing. They took
    PowerPoint's default shape and typed. Every authored caption in the deck
    picks a typeface and a size and was auto-sized to its text.
    """
    if not fill_hex or not fill_from_style or not style_font:
        return False
    accents = {("#" + getattr(theme, f"accent{i}").lstrip("#")).upper() for i in range(1, 7)}
    if fill_hex.upper() not in accents:
        return False
    if autofit:
        return False
    runs = [r for p in paras for r in p["runs"]]
    if not runs:
        return False
    if any(r.get("declared_face") or r.get("declared_size") or r.get("declared_color")
           for r in runs):
        return False
    return True


def _style_colors(el, cr, fill_style_lst):
    """Resolve a shape's <p:style> fillRef / fontRef against the theme.

    A shape can carry no explicit fill at all and still paint, because
    <a:fillRef idx="n"> points into the theme's fillStyleLst and substitutes
    its own colour for the template's phClr. That is the two-phase
    composition ColorResolver.resolve_with_theme() exists for (rule 13).

    This is load-bearing on the Olay deck: the six client review stickers
    ("Move forward if feedback is able to be incorporated", "Wrong package")
    carry no spPr fill and no run colour. Their dark-teal box and white text
    come entirely from fillRef -> accent1 and fontRef -> lt1. Rendering them
    without this leaves black text floating on the slide background.

    An explicit <a:noFill/> beats the reference, and Designer-locker shapes
    never reach here — flatten_slide drops them first, which matches what
    PowerPoint and LibreOffice both do with them.
    """
    st = el.find("p:style", NS)
    if st is None:
        return None, None
    fill_hex = font_hex = None
    sp_pr = el.find("p:spPr", NS)
    has_explicit = sp_pr is not None and any(
        sp_pr.find(f"a:{k}", NS) is not None
        for k in ("solidFill", "noFill", "gradFill", "blipFill", "pattFill"))
    fr = st.find("a:fillRef", NS)
    if fr is not None and not has_explicit and len(fr):
        idx = int(fr.get("idx", 0))
        if 1 <= idx <= len(fill_style_lst):
            tmpl = fill_style_lst[idx - 1]
            if etree.QName(tmpl).localname == "solidFill":
                fill_hex = cr.resolve_with_theme(fr, tmpl).get("final_hex")
    fo = st.find("a:fontRef", NS)
    if fo is not None and len(fo):
        font_hex = cr.resolve(fo).get("final_hex")
    return fill_hex, font_hex


def _shadow(el):
    """<a:outerShdw> -> CSS box-shadow parts. dir is in 60000ths of a degree,
    measured clockwise from the positive x-axis; dist and blurRad are EMU."""
    import math
    sh = el.find("p:spPr/a:effectLst/a:outerShdw", NS)
    if sh is None:
        return None
    dist = int(sh.get("dist", 0)) / EMU_PT
    blur = int(sh.get("blurRad", 0)) / EMU_PT
    ang = math.radians(int(sh.get("dir", 0)) / 60000.0)
    clr = sh.find("a:prstClr", NS)
    srgb = sh.find("a:srgbClr", NS)
    if srgb is not None:
        hexv = srgb.get("val").upper(); node = srgb
    elif clr is not None:
        hexv = {"black": "000000", "white": "FFFFFF"}.get(clr.get("val"), "000000"); node = clr
    else:
        hexv, node = "000000", sh
    a = node.find("a:alpha", NS)
    alpha = int(a.get("val")) / 100000.0 if a is not None else 1.0
    return {"dx_pt": round(dist * math.cos(ang), 3), "dy_pt": round(dist * math.sin(ang), 3),
            "blur_pt": round(blur, 3), "color": "#" + hexv, "alpha": alpha}


def _bg_image(bg_el, rl):
    """Slide background <a:blipFill>. <a:fillRect> insets are per-100000 of the
    destination rect; negative values mean the image overflows the slide."""
    if bg_el is None:
        return None
    blip = bg_el.find(".//a:blip", NS)
    if blip is None:
        return None
    tgt = rl.get(blip.get(R + "embed"), {}).get("target")
    if not tgt:
        return None
    fr = bg_el.find(".//a:stretch/a:fillRect", NS)
    rect = {k: int(fr.get(k, 0)) / 100000.0 for k in ("l", "t", "r", "b")} if fr is not None else {}
    return {"src": os.path.basename(tgt), "fill_rect": rect or None}


def _srcrect(pic_el):
    """<a:srcRect> in per-100000 units -> fractions of the SOURCE to remove.

    Values can be negative (a slight outset rather than a crop); the render
    maths handles that sign without special-casing.
    """
    sr = pic_el.find(".//a:srcRect", NS)
    if sr is None:
        return None
    d = {k: int(sr.get(k, 0)) / 100000.0 for k in ("l", "t", "r", "b")}
    return d if any(d.values()) else None


def build():
    theme = parse_theme((RAW / "ppt" / "theme" / "theme1.xml").read_bytes())
    theme2 = parse_theme((RAW / "ppt" / "theme" / "theme2.xml").read_bytes())
    assert asdict(theme) == asdict(theme2), "theme1/theme2 disagree — resolver path is unverified for that case"

    # Inherited run defaults, read from the master rather than assumed.
    m = etree.parse(str(RAW / "ppt" / "slideMasters" / "slideMaster1.xml")).getroot()
    lvl1 = m.find("p:txStyles/p:otherStyle/a:lvl1pPr", NS)
    defr = lvl1.find("a:defRPr", NS)
    INHERITED["size_pt"] = int(defr.get("sz")) / 100.0
    fill = defr.find("a:solidFill", NS)
    INHERITED["color"] = _solid_color(fill, theme)[0]
    latin = defr.find("a:latin", NS)
    # fontScheme lives in the theme, not the master.
    theme_root = etree.parse(str(RAW / "ppt" / "theme" / "theme1.xml")).getroot()
    minor = theme_root.find(".//a:fontScheme/a:minorFont/a:latin", NS)
    INHERITED["typeface"] = (minor.get("typeface")
                             if latin is not None and latin.get("typeface") == "+mn-lt"
                             else (latin.get("typeface") if latin is not None else None))

    cr = ColorResolver(asdict(theme))
    fill_style_lst = theme_root.find(".//a:fmtScheme/a:fillStyleLst", NS)

    m_bg = m.find("p:cSld/p:bg", NS)
    master_bg = "#FFFFFF"
    if m_bg is not None:
        ref = m_bg.find("p:bgRef/a:schemeClr", NS)
        direct, _ = _solid_color(m_bg.find(".//a:solidFill", NS), theme)
        master_bg = direct or ("#" + theme.resolve(ref.get("val")) if ref is not None else "#FFFFFF")

    pres = etree.parse(str(RAW / "ppt" / "presentation.xml")).getroot()
    prels = {r.get("Id"): r.get("Target")
             for r in etree.parse(str(RAW / "ppt" / "_rels" / "presentation.xml.rels")).getroot()}
    order = [os.path.basename(prels[s.get(R + "id")]) for s in pres.find("p:sldIdLst", NS)]
    sz = pres.find("p:sldSz", NS)
    W, H = int(sz.get("cx")) / EMU_PT, int(sz.get("cy")) / EMU_PT

    deck = {"w_pt": W, "h_pt": H, "theme": asdict(theme), "master_bg": master_bg,
            "inherited": dict(INHERITED), "slides": [], "coverage": []}
    used_images, used_videos = set(), set()

    for idx, fname in enumerate(order, 1):
        root = etree.parse(str(RAW / "ppt" / "slides" / fname)).getroot()
        rl = _rels(idx)
        bg_el = root.find("p:cSld/p:bg", NS)
        bg_hex = bg_alpha = None
        if bg_el is not None:
            bg_hex, bg_alpha = _solid_color(bg_el.find(".//a:solidFill", NS), theme)
        bg_img = _bg_image(bg_el, rl)
        if bg_img:
            used_images.add(bg_img["src"])

        shapes, skipped = [], []
        for fs in flatten_slide(_SlideShim(root)):
            el = fs.element
            nv = el.find(".//p:cNvPr", NS)
            name = nv.get("name") if nv is not None else ""
            geo = dict(x=fs.x_pt, y=fs.y_pt, w=fs.w_pt, h=fs.h_pt, z=fs.z)
            if fs.x_pt is None:
                skipped.append({"name": name, "kind": fs.kind, "why": "no xfrm"})
                continue

            if fs.kind == "pic":
                blip = el.find(".//a:blip", NS)
                vid = el.find(".//a:videoFile", NS)
                poster = rl.get(blip.get(R + "embed"), {}).get("target") if blip is not None else None
                poster = os.path.basename(poster) if poster else None
                rec = {"type": "video" if vid is not None else "image", "name": name,
                       **geo, "crop": _srcrect(el), "poster": poster}
                if vid is not None:
                    tgt = rl.get(vid.get(R + "link"), {}).get("target")
                    rec["video"] = os.path.basename(tgt) if tgt else None
                    if rec["video"]: used_videos.add(rec["video"])
                    if poster: used_images.add(poster)
                    if not rec["video"]:
                        skipped.append({"name": name, "kind": "pic", "why": "video rId unresolved"})
                        continue
                else:
                    if not poster:
                        skipped.append({"name": name, "kind": "pic", "why": "image rId unresolved"})
                        continue
                    used_images.add(poster)
                shapes.append(rec)
                continue

            if fs.kind == "sp":
                tx = el.find("p:txBody", NS)
                paras = []
                if tx is not None:
                    for p in tx.findall("a:p", NS):
                        runs = []
                        for r in p.findall("a:r", NS):
                            rPr = r.find("a:rPr", NS)
                            lat = rPr.find("a:latin", NS) if rPr is not None else None
                            face = lat.get("typeface") if lat is not None else None
                            size = (float(rPr.get("sz")) / 100 if rPr is not None and rPr.get("sz")
                                    else None)
                            col, calpha = (_solid_color(rPr.find("a:solidFill", NS), theme)
                                           if rPr is not None else (None, None))
                            runs.append({
                                "text": r.find("a:t", NS).text or "",
                                "typeface": face or INHERITED["typeface"],
                                "declared_face": face,
                                "size_pt": size if size else INHERITED["size_pt"],
                                "declared_size": size,
                                "bold": (rPr.get("b") == "1") if rPr is not None else False,
                                "color": col or INHERITED["color"],
                                "declared_color": col,
                            })
                        pPr = p.find("a:pPr", NS)
                        paras.append({"align": pPr.get("algn") if pPr is not None else None,
                                      "runs": runs})
                has_text = any(r["text"].strip() for pa in paras for r in pa["runs"])
                sp_hex, sp_alpha = _solid_color(el.find("p:spPr/a:solidFill", NS), theme)
                style_fill, style_font = _style_colors(el, cr, fill_style_lst)
                fill_from_style = False
                if sp_hex is None and style_fill:
                    sp_hex = style_fill
                    fill_from_style = True
                if style_font:
                    for pa in paras:
                        for r in pa["runs"]:
                            if r["color"] == INHERITED["color"] and not r.get("declared_color"):
                                r["color"] = style_font
                bp = tx.find("a:bodyPr", NS) if tx is not None else None
                if has_text:
                    ins = {k: float(bp.get(a, d)) / EMU_PT for k, a, d in
                           (("l", "lIns", 91440), ("r", "rIns", 91440),
                            ("t", "tIns", 45720), ("b", "bIns", 45720))} if bp is not None else {}
                    autofit = bp.find("a:spAutoFit", NS) is not None if bp is not None else False
                    sticker = _is_review_sticker(
                        paras, sp_hex, fill_from_style, style_font, autofit, theme)
                    shapes.append({"type": "text", "name": name, **geo, "paras": paras,
                                   "review_sticker": sticker,
                                   "fill": sp_hex, "fill_alpha": sp_alpha, "insets": ins,
                                   "anchor": bp.get("anchor") if bp is not None else None,
                                   "shadow": _shadow(el),
                                   "autofit": autofit})
                elif sp_hex:
                    shapes.append({"type": "rect", "name": name, **geo,
                                   "fill": sp_hex, "fill_alpha": sp_alpha,
                                   "shadow": _shadow(el)})
                else:
                    skipped.append({"name": name, "kind": "sp", "why": "no fill, no text"})
                continue

            skipped.append({"name": name, "kind": fs.kind, "why": "unhandled kind"})

        # Rels present on the slide but never reached by the shape walk.
        bound = {s.get("poster") for s in shapes} | {s.get("video") for s in shapes}
        if bg_img:
            bound.add(bg_img["src"])
        unbound = [v["target"].split("/")[-1] for k, v in rl.items()
                   if v["type"] in ("image", "video", "media", "hdphoto")
                   and v["target"].split("/")[-1] not in bound]
        _mark_occluded_and_backdrop(shapes, W, H)

        # flatten_slide drops true Designer lockers before we see them; count
        # them here so the coverage map accounts for every shape in the spTree.
        lockers = [etree.QName(c).localname for c in root.find("p:cSld/p:spTree", NS).iter()
                   if etree.QName(c).localname in ("sp", "pic") and _is_design_locker(c)]
        deck["coverage"].append({"slide": idx, "shapes": len(shapes),
                                 "skipped": skipped, "design_lockers": len(lockers),
                                 "unbound_rels": sorted(set(unbound))})
        deck["slides"].append({"n": idx, "file": fname, "bg": bg_hex,
                               "bg_alpha": bg_alpha, "bg_image": bg_img,
                               "shapes": shapes})

    return deck, used_images, used_videos


if __name__ == "__main__":
    deck, imgs, vids = build()
    out = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.json").write_text(json.dumps(deck, indent=1))
    (out / "used_images.json").write_text(json.dumps(sorted(imgs)))
    print(f"slides={len(deck['slides'])} images={len(imgs)} videos={len(vids)}")
    print(f"inherited run defaults: {deck['inherited']}")
    tot = sum(len(s['shapes']) for s in deck['slides'])
    sk = sum(len(c['skipped']) for c in deck['coverage'])
    print(f"shapes emitted={tot} skipped={sk}")
    for c in deck["coverage"]:
        if c["skipped"] or c["unbound_rels"]:
            print(f"  slide {c['slide']}: skipped={[(s['name'],s['why']) for s in c['skipped']]} "
                  f"unbound={c['unbound_rels']}")
