"""OOXML -> model.json. The shared spine of the Olay and Old Spice builders.

Carries the union of what those two decks each needed, because deck 8 needs
both halves and neither builder alone would run it:

  from Olay        video <p:pic> (a:videoFile, NOT p:), <p:bg> blipFill images
  from Old Spice   real <a:tbl> tables, SVG-only pictures, single-theme
                   tolerance, and every colour routed through ColorResolver

Rules implemented here (LEARNINGS.md):
  1  media bound via slideN.xml.rels, never by visual order
  2  lxml + explicit namespaces; no regex in the parse layer
  3  every shape in the spTree emitted or recorded in a coverage map
  4/5 z-order preserved; nothing flattened
  13/28 every colour through ColorResolver, so lumMod/tint/shade apply
  14 text emitted verbatim, including the source's mistakes
  18 designElem marker gates the locker check; visual emptiness decides it
  19 <p:style> fillRef/fontRef paint shapes with no explicit fill
  23 review stickers FLAGGED here, never suppressed here
  24 occlusion and backdrop classification
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from lxml import etree
from PIL import Image

from ondeck.parse.shapes import flatten_slide
from ondeck.parse.slide import NS, _is_design_locker
from ondeck.parse.theme import parse_theme, SCHEME_ALIASES
from ondeck.parse.color import ColorResolver

from .paths import DeckPaths

R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ASVG = {"asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main"}
EMU_PT = 12700.0
OPAQUE_MIN = 0.999
Image.MAX_IMAGE_PIXELS = None      # deck 8 ships a 42.6 MP plate


class _SlideShim:
    """flatten_slide() wants an object with .element."""

    def __init__(self, root):
        self.element = root


class Ctx:
    """Per-deck parse state. Replaces the module-level globals the two
    previous builders used (`_CR`, `INHERITED`, `RAW`)."""

    def __init__(self, paths: DeckPaths):
        self.paths = paths
        self.cr: ColorResolver | None = None
        self.theme = None
        self.fsl = None
        self.inherited = {"size_pt": None, "typeface": None, "color": None}

    # ---- colour -------------------------------------------------------
    def solid(self, fill_el):
        """Resolve a fill to (hex, alpha) through ColorResolver — rule 28.

        Reading `schemeClr/@val` and stopping is correct until the first deck
        that applies a transform, and then it returns a plausible wrong colour
        rather than an error. Old Spice's variant table (63 lumMod uses) is
        the case that proved it.
        """
        if fill_el is None:
            return None, None
        node = fill_el.find("a:srgbClr", NS)
        if node is None:
            node = fill_el.find("a:schemeClr", NS)
        if node is None:
            return None, None
        a_ = node.find("a:alpha", NS)
        alpha = int(a_.get("val")) / 100000.0 if a_ is not None else None
        if self.cr is not None:
            try:
                return self.cr.resolve(fill_el).get("final_hex"), alpha
            except KeyError:
                pass
        hexv = (node.get("val") if etree.QName(node).localname == "srgbClr"
                else self.theme.resolve(node.get("val")))
        return "#" + hexv.upper().lstrip("#"), alpha

    @lru_cache(maxsize=512)
    def _opaque_fraction_cached(self, src: str) -> float:
        p = self.paths.media / src
        if p.suffix.lower() == ".svg" or not p.exists():
            return 0.0
        im = Image.open(p)
        if im.mode not in ("RGBA", "LA"):
            return 1.0
        h = im.getchannel("A").histogram()
        return h[255] / float(sum(h))

    def opaque_fraction(self, src: str) -> float:
        return self._opaque_fraction_cached(src)


# ---------------------------------------------------------------- helpers
def _rels(paths: DeckPaths, n: int) -> dict:
    p = paths.rels_for(n)
    if not p.exists():
        return {}
    return {r.get("Id"): {"target": r.get("Target"),
                          "type": r.get("Type").rsplit("/", 1)[-1]}
            for r in etree.parse(str(p)).getroot()}


def _srcrect(el):
    sr = el.find(".//a:srcRect", NS)
    if sr is None:
        return None
    d = {k: int(sr.get(k, 0)) / 100000.0 for k in ("l", "t", "r", "b")}
    return d if any(d.values()) else None


def _grad(ctx, sp_pr):
    """<a:gradFill> -> stops the renderer can turn into a CSS gradient.

    Neither deck 6 nor 7 had one, so `solid()` alone was enough there. Deck 8's
    "PATH TO PURCHASE" wedge is a two-stop radial with per-stop alpha, and a
    solidFill-only reader drops the shape entirely (it has no solid fill and
    no text, so it fails the emit test and disappears).
    """
    if sp_pr is None:
        return None
    g = sp_pr.find("a:gradFill", NS)
    if g is None:
        return None
    stops = []
    for gs in g.findall("a:gsLst/a:gs", NS):
        hexv, alpha = ctx.solid(gs)
        if hexv is None:
            continue
        stops.append({"pos": int(gs.get("pos", 0)) / 100000.0,
                      "hex": hexv, "alpha": 1.0 if alpha is None else alpha})
    if not stops:
        return None
    lin = g.find("a:lin", NS)
    path = g.find("a:path", NS)
    out = {"stops": stops}
    if lin is not None:
        out["kind"] = "linear"
        out["angle_deg"] = (int(lin.get("ang", 0)) / 60000.0) % 360.0
    elif path is not None:
        out["kind"] = "radial"
        fr = path.find("a:fillToRect", NS)
        if fr is not None:
            out["center"] = {k: int(fr.get(k, 0)) / 100000.0 for k in ("l", "t", "r", "b")}
    else:
        out["kind"] = "linear"
        out["angle_deg"] = 0.0
    return out


def _stroke(ctx, sp_pr):
    """<a:ln> -> {hex, alpha, w_pt}. A shape can be nothing but an outline.

    LEARNINGS rule 18 already says a skipped shape must have "no fill, no line,
    no image and no text" — the line half had never been exercised, because
    decks 6 and 7 contained no stroke-only shape. Deck 8 slide 3 has one: an
    ellipse with <a:noFill/> and a bg1+lumMod95% outline.
    """
    if sp_pr is None:
        return None
    ln = sp_pr.find("a:ln", NS)
    if ln is None or ln.find("a:noFill", NS) is not None:
        return None
    hexv, alpha = ctx.solid(ln.find("a:solidFill", NS))
    if hexv is None:
        return None
    w = ln.get("w")
    return {"hex": hexv, "alpha": alpha, "w_pt": (int(w) / EMU_PT) if w else 1.0}


def _rot_deg(el):
    """xfrm/@rot is in 60000ths of a degree; absent means 0."""
    xf = el.find("p:spPr/a:xfrm", NS)
    if xf is None or not xf.get("rot"):
        return 0.0
    return (int(xf.get("rot")) / 60000.0) % 360.0


def _bg_image(bg_el, rl):
    """Slide background <a:blipFill>. fillRect insets are per-100000 of the
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


def _ph_key(el):
    ph = el.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
    if ph is None:
        return None
    return (ph.get("type") or "body", ph.get("idx"))


def build_ph_geometry(paths: DeckPaths) -> dict:
    """{layout filename: {(ph type, idx): (x, y, w, h) in pt}} plus a "" entry
    for the master.

    A placeholder that carries `<p:spPr/>` empty has NO geometry of its own —
    it inherits the layout's, then the master's. flatten_slide() reports x_pt
    as None for those, and a builder that treats None as "unpositioned" drops
    the shape. Decks 6 and 7 never hit this (Olay has zero placeholders; Old
    Spice's carry their own xfrm), so both builders skipped it silently. On
    deck 8 it is the title of slides 2 and 4 — 26 characters of heading.
    """
    out = {}
    for src in list((paths.raw / "ppt" / "slideLayouts").glob("slideLayout*.xml")) + \
               list((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml")):
        root = etree.parse(str(src)).getroot()
        table = {}
        for sp in root.iter("{%s}sp" % NS["p"]):
            k = _ph_key(sp)
            if k is None:
                continue
            off = sp.find("p:spPr/a:xfrm/a:off", NS)
            ext = sp.find("p:spPr/a:xfrm/a:ext", NS)
            if off is None or ext is None:
                continue
            table[k] = (int(off.get("x")) / EMU_PT, int(off.get("y")) / EMU_PT,
                        int(ext.get("cx")) / EMU_PT, int(ext.get("cy")) / EMU_PT)
        out["master" if "Master" in src.name else src.name] = table
    return out


def resolve_ph_geometry(el, layout_name, ph_geo):
    """Layout first, then master; match on (type, idx) then on type alone."""
    k = _ph_key(el)
    if k is None:
        return None
    for table in (ph_geo.get(layout_name, {}), ph_geo.get("master", {})):
        if k in table:
            return table[k]
        for (t, _idx), v in table.items():
            if t == k[0]:
                return v
    return None


def _local(el):
    t = el.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


def _runs_of(ctx: Ctx, p_el):
    """Runs in DOCUMENT order, with <a:br/> recorded as a break.

    ondeck/parse/text.py notes that <a:br> was "punted in Phase 1B; surface if
    a deck needs it". HenHouse surfaces it: slide 3 carries 8 of them between
    the beef-cut names and slide 2 three more between sentences. findall("a:r")
    skipped them silently, so the runs concatenated into "RibeyeStripChuck
    Eye..." with no separator anywhere in the output.
    """
    runs = []
    for r_ in p_el:
        if _local(r_) == "br":
            if runs:
                runs[-1]["br_after"] = True
            continue
        if _local(r_) != "r":
            continue
        rPr = r_.find("a:rPr", NS)
        lat = rPr.find("a:latin", NS) if rPr is not None else None
        face = lat.get("typeface") if lat is not None else None
        size = float(rPr.get("sz")) / 100 if rPr is not None and rPr.get("sz") else None
        col, _ = ctx.solid(rPr.find("a:solidFill", NS)) if rPr is not None else (None, None)
        t = r_.find("a:t", NS)
        runs.append({"text": (t.text or "") if t is not None else "",
                     "typeface": face or ctx.inherited["typeface"], "declared_face": face,
                     "size_pt": size if size else ctx.inherited["size_pt"], "declared_size": size,
                     "bold": (rPr.get("b") == "1") if rPr is not None else False,
                     "italic": (rPr.get("i") == "1") if rPr is not None else False,
                     "color": col or ctx.inherited["color"], "declared_color": col})
    return runs


def _paras_of(ctx: Ctx, tx):
    """Paragraphs with bullet, alignment and indent. <a:buNone/> is an explicit
    'no bullet' and must not be read as 'no bullet property stated'."""
    out = []
    for p in tx.findall("a:p", NS):
        pPr = p.find("a:pPr", NS)
        bullet = None
        if pPr is not None and pPr.find("a:buNone", NS) is None:
            bc = pPr.find("a:buChar", NS)
            if bc is not None:
                bullet = bc.get("char")
        ln = pPr.find("a:lnSpc/a:spcPct", NS) if pPr is not None else None
        out.append({"align": pPr.get("algn") if pPr is not None else None,
                    "bullet": bullet,
                    "line_pct": int(ln.get("val")) / 100000.0 if ln is not None else None,
                    "marL": float(pPr.get("marL")) / EMU_PT if pPr is not None and pPr.get("marL") else None,
                    "runs": _runs_of(ctx, p)})
    return out


def _table(ctx: Ctx, el):
    tbl = el.find(".//a:tbl", NS)
    if tbl is None:
        return None
    grid = [int(gc.get("w")) / EMU_PT for gc in tbl.findall("a:tblGrid/a:gridCol", NS)]
    rows = []
    for tr in tbl.findall("a:tr", NS):
        cells = []
        for tc in tr.findall("a:tc", NS):
            tx = tc.find("a:txBody", NS)
            fill, alpha = ctx.solid(tc.find("a:tcPr/a:solidFill", NS))
            cells.append({"paras": _paras_of(ctx, tx) if tx is not None else [],
                          "fill": fill, "fill_alpha": alpha,
                          "grid_span": int(tc.get("gridSpan", 1)),
                          "h_merge": tc.get("hMerge") == "1"})
        rows.append({"h_pt": int(tr.get("h", 0)) / EMU_PT, "cells": cells})
    return {"grid_pt": grid, "rows": rows}


def _style_colors(ctx: Ctx, el):
    """rule 19 — a shape with no explicit fill can still be painted by
    <p:style>/fillRef, and its run colour supplied by fontRef."""
    st = el.find("p:style", NS)
    if st is None:
        return None, None
    fill_hex = font_hex = None
    sp_pr = el.find("p:spPr", NS)
    explicit = sp_pr is not None and any(
        sp_pr.find(f"a:{k}", NS) is not None
        for k in ("solidFill", "noFill", "gradFill", "blipFill", "pattFill"))
    fr = st.find("a:fillRef", NS)
    if fr is not None and not explicit and len(fr) and ctx.fsl is not None:
        idx = int(fr.get("idx", 0))
        if 1 <= idx <= len(ctx.fsl) and etree.QName(ctx.fsl[idx - 1]).localname == "solidFill":
            fill_hex = ctx.cr.resolve_with_theme(fr, ctx.fsl[idx - 1]).get("final_hex")
    fo = st.find("a:fontRef", NS)
    if fo is not None and len(fo):
        font_hex = ctx.cr.resolve(fo).get("final_hex")
    return fill_hex, font_hex


def _is_review_sticker(ctx: Ctx, paras, fill_hex, from_style, style_font, autofit):
    """rule 23 — detection only. Suppression is the deck's roles.py call.

    Five properties, all required. Authored copy fails immediately because it
    picks a typeface and a size; a comment box chooses nothing.
    """
    if not fill_hex or not from_style or not style_font or autofit:
        return False
    accents = {("#" + getattr(ctx.theme, f"accent{i}").lstrip("#")).upper() for i in range(1, 7)}
    if fill_hex.upper() not in accents:
        return False
    runs = [r for p in paras for r in p["runs"]]
    if not runs:
        return False
    return not any(r.get("declared_face") or r.get("declared_size") or r.get("declared_color")
                   for r in runs)


def _covers(s, W, H, tol=1.0):
    return (s["x"] <= tol and s["y"] <= tol
            and s["x"] + s["w"] >= W - tol and s["y"] + s["h"] >= H - tol)


def _opaque(ctx: Ctx, s):
    if s["type"] == "rect":
        return bool(s.get("fill")) and (s.get("fill_alpha") is None or s["fill_alpha"] >= 1.0)
    if s["type"] in ("image", "video"):
        src = s.get("poster")
        return bool(src) and ctx.opaque_fraction(src) >= OPAQUE_MIN
    return False


def _mark(ctx: Ctx, shapes, W, H):
    """rule 24 — occluded (buried under an opaque full-canvas shape) and
    backdrop (the ground the slide sits on) are different things and both
    have to be known before a mobile reflow can be correct."""
    for s in shapes:
        s["occluded"] = False
        s["backdrop"] = False
    covers = [i for i, s in enumerate(shapes) if _covers(s, W, H) and _opaque(ctx, s)]
    start = max(covers) if covers else 0
    for s in shapes[:start]:
        s["occluded"] = True
    for s in shapes[start:]:
        if s["type"] in ("image", "video"):
            if not _covers(s, W, H):
                break
            s["backdrop"] = True
        elif s["type"] == "rect":
            if not (s["y"] <= 1 and s["y"] + s["h"] >= H - 1):
                break
            s["backdrop"] = True
        else:
            break


# ---------------------------------------------------------------- build
def _slide_master_theme(paths: DeckPaths) -> Path:
    """The theme the SLIDE MASTER references.

    `theme1.xml` is a convention, not a rule. A deck with a notes master has a
    second theme, and nothing guarantees the slide master owns the first one.
    Resolve it through the rels (rule 1: bindings come from `_rels`, never from
    position or filename).
    """
    masters = sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml"))
    rels_path = masters[0].parent / "_rels" / (masters[0].name + ".rels")
    for r in etree.parse(str(rels_path)).getroot():
        if r.get("Type").rsplit("/", 1)[-1] == "theme":
            return (masters[0].parent / r.get("Target")).resolve()
    raise AssertionError("slide master references no theme")


def _referenced_scheme_keys(paths: DeckPaths) -> set[str]:
    """Every scheme colour token that a RENDERING part actually names.

    Slides, the layouts they inherit from, and the slide master. Notes masters
    and handout masters are excluded: they never reach the canvas. Tokens are
    normalised through SCHEME_ALIASES so `tx1` and `dk1` compare as one key.
    """
    parts = (list(paths.raw.glob("ppt/slides/slide*.xml"))
             + list(paths.raw.glob("ppt/slideLayouts/slideLayout*.xml"))
             + list(paths.raw.glob("ppt/slideMasters/slideMaster*.xml")))
    keys = set()
    for f in parts:
        for el in etree.parse(str(f)).getroot().iter(f"{{{NS['a']}}}schemeClr"):
            v = el.get("val")
            if v:
                keys.add(SCHEME_ALIASES.get(v, v))
    return keys


def build_model(paths: DeckPaths,
                drop_slides: frozenset[int] = frozenset()) -> tuple[dict, set, set]:
    """`drop_slides` holds SOURCE slide numbers the client asked to omit.

    Dropping happens here, not in a renderer, so a dropped slide never reaches
    the model, never contributes to `used_assets`, and cannot be resurrected by
    a re-render. Remaining slides are renumbered 1..N so the editor's rail,
    counter and `data-slide` ordinals stay sequential (rules 22/30), and each
    carries `src_n` so it can still be traced to the source deck.

    This is NOT rule 30's mobile merge, which collapses a section to zero height
    and must never remove it. That rule protects the editor's slide list from
    diverging between breakpoints. This removes a slide from the DELIVERABLE at
    every breakpoint, on the client's instruction, which is a different act.
    """
    ctx = Ctx(paths)
    theme_dir = paths.raw / "ppt" / "theme"

    # Rule 1 applied to themes: resolve by relationship, not by filename.
    theme_path = _slide_master_theme(paths)
    theme = parse_theme(theme_path.read_bytes())

    # Deck 9 is the first deck in the corpus whose themes DISAGREE, closing an
    # open gap that stood through P&G, SHELFBEAUTY and Olay. The original check
    # compared every theme in the package and refused to build on any
    # difference. That is too strict, and for the wrong reason: theme2 there
    # belongs to the NOTES master, which never renders. What actually matters is
    # whether the parts that DO render name a token the themes disagree on.
    #
    # So: compare only on referenced tokens. A conflict on one of those is still
    # a hard failure -- it would silently paint a wrong colour, which is what
    # this assertion exists to prevent. A difference confined to tokens nothing
    # references is recorded and built through.
    referenced = _referenced_scheme_keys(paths)
    others = sorted(p for p in theme_dir.glob("theme*.xml") if p != theme_path)
    tvals = asdict(theme)
    differing, conflicts = set(), {}
    for op in others:
        ovals = asdict(parse_theme(op.read_bytes()))
        for k in set(tvals) | set(ovals):
            if isinstance(tvals.get(k), dict) or isinstance(ovals.get(k), dict):
                continue
            if tvals.get(k) != ovals.get(k):
                differing.add(k)
                if k in referenced:
                    conflicts[k] = {"slide_theme": tvals.get(k),
                                    op.name: ovals.get(k)}
    assert not conflicts, (
        f"themes disagree on a token the deck actually renders: {conflicts}. "
        f"Slide master uses {theme_path.name}; resolving with it would paint a "
        f"different colour than another theme in the package specifies.")

    theme_audit = {
        "slide_theme": theme_path.name,
        "other_themes": [p.name for p in others],
        "referenced_tokens": sorted(referenced),
        "differing_tokens": sorted(differing),
        "conflicts_on_referenced": conflicts,
    }
    themes_agree = None if not others else not differing
    ctx.theme = theme

    troot = etree.parse(str(theme_path)).getroot()
    tdict = asdict(theme)
    tdict.update({k: getattr(theme, v) for k, v in SCHEME_ALIASES.items()})
    ctx.cr = ColorResolver(tdict)
    ctx.fsl = troot.find(".//a:fmtScheme/a:fillStyleLst", NS)

    masters = sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml"))
    m = etree.parse(str(masters[0])).getroot()
    lvl1 = m.find("p:txStyles/p:otherStyle/a:lvl1pPr", NS)
    defr = lvl1.find("a:defRPr", NS) if lvl1 is not None else None
    ctx.inherited["size_pt"] = float(defr.get("sz")) / 100.0 if defr is not None and defr.get("sz") else 18.0
    ctx.inherited["color"] = ctx.solid(defr.find("a:solidFill", NS))[0] if defr is not None else None
    minor = troot.find(".//a:fontScheme/a:minorFont/a:latin", NS)
    major = troot.find(".//a:fontScheme/a:majorFont/a:latin", NS)
    ctx.inherited["typeface"] = minor.get("typeface") if minor is not None else None
    major_face = major.get("typeface") if major is not None else None

    m_bg = m.find("p:cSld/p:bg", NS)
    master_bg = "#FFFFFF"
    if m_bg is not None:
        ref = m_bg.find("p:bgRef/a:schemeClr", NS)
        direct, _ = ctx.solid(m_bg.find(".//a:solidFill", NS))
        master_bg = direct or ("#" + theme.resolve(ref.get("val")) if ref is not None else "#FFFFFF")

    pres = etree.parse(str(paths.raw / "ppt" / "presentation.xml")).getroot()
    prels = {r.get("Id"): r.get("Target") for r in
             etree.parse(str(paths.raw / "ppt" / "_rels" / "presentation.xml.rels")).getroot()}
    order = [os.path.basename(prels[s.get(R + "id")]) for s in pres.find("p:sldIdLst", NS)]
    sz = pres.find("p:sldSz", NS)
    W, H = int(sz.get("cx")) / EMU_PT, int(sz.get("cy")) / EMU_PT

    deck = {"slug": paths.slug, "w_pt": W, "h_pt": H, "theme": asdict(theme),
            "master_bg": master_bg, "themes_agree": themes_agree,
            "theme_audit": theme_audit,
            "inherited": dict(ctx.inherited), "major_face": major_face,
            "slides": [], "coverage": []}
    used_images, used_videos = set(), set()
    ph_geo = build_ph_geometry(paths)

    kept, dropped = [], []
    for src_n, fname in enumerate(order, 1):
        (dropped if src_n in drop_slides else kept).append((src_n, fname))
    assert not (drop_slides - {n for n, _ in dropped}), \
        f"drop_slides names slides that do not exist: {sorted(drop_slides - {n for n, _ in dropped})}"
    deck["dropped_slides"] = [{"src_n": n, "file": f} for n, f in dropped]

    for idx, (src_n, fname) in enumerate(kept, 1):
        root = etree.parse(str(paths.slide_xml(fname))).getroot()
        rl = _rels(paths, int("".join(c for c in fname if c.isdigit())))
        layout_name = next((os.path.basename(v["target"]) for v in rl.values()
                            if v["type"] == "slideLayout"), None)
        bg_el = root.find("p:cSld/p:bg", NS)
        bg_hex, bg_a = ctx.solid(bg_el.find(".//a:solidFill", NS)) if bg_el is not None else (None, None)
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
                inh = resolve_ph_geometry(el, layout_name, ph_geo)
                if inh is None:
                    skipped.append({"name": name, "kind": fs.kind, "why": "no xfrm"})
                    continue
                geo = dict(x=inh[0], y=inh[1], w=inh[2], h=inh[3], z=fs.z)
                geo["geom_from"] = "layout"
            geo["rot"] = _rot_deg(el)

            if fs.kind == "graphicFrame":
                tbl = _table(ctx, el)
                if tbl is None:
                    skipped.append({"name": name, "kind": fs.kind, "why": "graphicFrame, not a table"})
                    continue
                shapes.append({"type": "table", "name": name, **geo, "table": tbl})
                continue

            if fs.kind == "pic":
                blip = el.find(".//a:blip", NS)
                svg = el.find(".//asvg:svgBlip", ASVG)
                vid = el.find(".//a:videoFile", NS)
                emb = blip.get(R + "embed") if blip is not None else None
                svg_emb = svg.get(R + "embed") if svg is not None else None
                poster = os.path.basename(rl.get(emb, {}).get("target")) if emb else None
                svg_src = os.path.basename(rl.get(svg_emb, {}).get("target")) if svg_emb else None
                rec = {"type": "video" if vid is not None else "image", "name": name,
                       **geo, "crop": _srcrect(el), "poster": poster, "svg": svg_src}
                if vid is not None:
                    tgt = (rl.get(vid.get(R + "link"), {}).get("target")
                           or rl.get(vid.get(R + "embed"), {}).get("target"))
                    rec["video"] = os.path.basename(tgt) if tgt else None
                    if not rec["video"]:
                        skipped.append({"name": name, "kind": "pic", "why": "video rId unresolved"})
                        continue
                    used_videos.add(rec["video"])
                    if poster:
                        used_images.add(poster)
                else:
                    if not poster and not svg_src:
                        skipped.append({"name": name, "kind": "pic", "why": "no resolvable image rId"})
                        continue
                    if poster:
                        used_images.add(poster)
                    if svg_src:
                        used_images.add(svg_src)
                shapes.append(rec)
                continue

            if fs.kind == "sp":
                tx = el.find("p:txBody", NS)
                paras = _paras_of(ctx, tx) if tx is not None else []
                has_text = any(r["text"].strip() for p in paras for r in p["runs"])
                sp_hex, sp_a = ctx.solid(el.find("p:spPr/a:solidFill", NS))
                style_fill, style_font = _style_colors(ctx, el)
                from_style = False
                if sp_hex is None and style_fill:
                    sp_hex, from_style = style_fill, True
                if style_font:
                    for p in paras:
                        for r_ in p["runs"]:
                            if not r_.get("declared_color"):
                                r_["color"] = style_font
                bp = tx.find("a:bodyPr", NS) if tx is not None else None
                geom = el.find("p:spPr/a:prstGeom", NS)
                prst = geom.get("prst") if geom is not None else "rect"
                sp_pr = el.find("p:spPr", NS)
                grad = _grad(ctx, sp_pr)
                stroke = _stroke(ctx, sp_pr)
                if has_text:
                    ins = {k: float(bp.get(a_, d)) / EMU_PT for k, a_, d in
                           (("l", "lIns", 91440), ("r", "rIns", 91440),
                            ("t", "tIns", 45720), ("b", "bIns", 45720))} if bp is not None else {}
                    autofit = bp is not None and bp.find("a:spAutoFit", NS) is not None
                    shapes.append({"type": "text", "name": name, **geo, "paras": paras,
                                   "fill": sp_hex, "fill_alpha": sp_a, "insets": ins,
                                   "anchor": bp.get("anchor") if bp is not None else None,
                                   "wrap": bp.get("wrap", "square") if bp is not None else "square",
                                   "autofit": autofit, "prst": prst,
                                   "grad": grad, "stroke": stroke,
                                   "review_sticker": _is_review_sticker(
                                       ctx, paras, sp_hex, from_style, style_font, autofit)})
                elif sp_hex or grad or stroke:
                    # rule 18 in full: a shape is inert only when it paints
                    # NOTHING. A gradient-only wedge and a stroke-only ellipse
                    # both paint, and both were being dropped.
                    shapes.append({"type": "rect", "name": name, **geo,
                                   "fill": sp_hex, "fill_alpha": sp_a, "prst": prst,
                                   "grad": grad, "stroke": stroke})
                else:
                    skipped.append({"name": name, "kind": "sp",
                                    "why": "no fill, no gradient, no line, no text"})
                continue

            skipped.append({"name": name, "kind": fs.kind, "why": "unhandled kind"})

        _mark(ctx, shapes, W, H)
        bound = {s.get("poster") for s in shapes} | {s.get("svg") for s in shapes} | {s.get("video") for s in shapes}
        if bg_img:
            bound.add(bg_img["src"])
        unbound = sorted({v["target"].split("/")[-1] for v in rl.values()
                          if v["type"] in ("image", "video", "media", "hdphoto")
                          and v["target"].split("/")[-1] not in bound})
        lockers = sum(1 for c in root.find("p:cSld/p:spTree", NS).iter()
                      if etree.QName(c).localname in ("sp", "pic") and _is_design_locker(c))
        deck["coverage"].append({"slide": idx, "shapes": len(shapes), "skipped": skipped,
                                 "design_lockers": lockers, "unbound_rels": unbound})
        deck["slides"].append({"n": idx, "src_n": src_n, "file": fname, "bg": bg_hex, "bg_alpha": bg_a,
                               "bg_image": bg_img, "shapes": shapes})
    return deck, used_images, used_videos


def write_model(paths: DeckPaths, drop_slides: frozenset[int] = frozenset()):
    deck, imgs, vids = build_model(paths, drop_slides=drop_slides)
    paths.out.mkdir(parents=True, exist_ok=True)
    (paths.out / "model.json").write_text(json.dumps(deck, indent=1))
    (paths.out / "used_assets.json").write_text(
        json.dumps({"images": sorted(imgs), "videos": sorted(vids)}, indent=1))
    return deck, imgs, vids
