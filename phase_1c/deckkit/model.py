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
        self.inherited = {"size_pt": None, "typeface": None, "color": None,
                          "color_alpha": None}

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
    out = {"hex": hexv, "alpha": alpha, "w_pt": (int(w) / EMU_PT) if w else 1.0}
    # Dash, cap and compound are recorded even where CSS cannot express them.
    # A border has no cap control at all and `cmpd` beyond "sng" needs a
    # different construct entirely; carrying the authored values means the gap
    # is visible in model.json rather than being an unrecorded silent drop.
    d = ln.find("a:prstDash", NS)
    if d is not None and d.get("val"):
        out["dash"] = d.get("val")
    for a_ in ("cap", "cmpd"):
        if ln.get(a_):
            out[a_] = ln.get(a_)
    return out


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


# A placeholder inherits from the master placeholder of its FAMILY, not of its
# own literal type: ctrTitle and title both resolve against the master's title
# placeholder, subTitle and body against its body placeholder. Deck 10's cover
# is a `ctrTitle` and the master only declares `title`, so without this the
# walk stopped one level short and fell through to the deck default.
_PH_FAMILY = {"ctrTitle": "title", "title": "title",
              "subTitle": "body", "body": "body"}


def resolve_ph_text(ph_text, layout_name, master_name, ph_type, lvl,
                    tx_defaults=None):
    """Placeholder text properties for one level: layout first, then master,
    then -- for bullet keys only -- the master's txStyles and the presentation
    default. Nearest level wins, per key."""
    fam = _PH_FAMILY.get(ph_type or "body", ph_type or "body")
    out = {}
    for src, key in ((layout_name, ph_type or "body"), (master_name, fam)):
        ent = (ph_text.get(src, {}).get(key) or {})
        lv = ent.get(lvl) or ent.get(0) or {}
        # `is not None`, not truthiness: `marL="0"` and `indent="0"` are
        # meaningful RESETS of an inherited indent, and a truthiness test drops
        # them and lets the outer level win. No behaviour change for sz/face/
        # lnspc -- build_ph_textstyles only records those when already truthy.
        for k in ("sz", "face", "lnspc", "algn", "marL", "indent") + BULLET_KEYS:
            if k not in out and lv.get(k) is not None:
                out[k] = lv[k]
    # Levels 5 and 6. `other` is the fallback family for a shape that is not a
    # placeholder at all, which is why it is consulted last rather than never.
    for key in (fam if fam in ("title", "body") else "other", "pres"):
        ent = (tx_defaults or {}).get(key) or {}
        lv = ent.get(lvl) or ent.get(0) or {}
        for k in BULLET_KEYS:
            if k not in out and lv.get(k) is not None:
                out[k] = lv[k]
    return out


def build_ph_bodypr(paths: DeckPaths) -> dict:
    """{layout filename: {ph type: {anchor, wrap, insets}}} from each layout
    placeholder's <a:bodyPr>.

    Deck 10's slide-level bodyPr is literally `<a:bodyPr/>` -- empty -- on
    every divider title. Everything that governs how the text sits in its box
    lives on the LAYOUT placeholder: `anchor="ctr"` and all four insets at
    91425 EMU. Reading only the slide's copy meant defaulting to top-anchored
    with no padding, and with 73pt type in a 68.5pt box the anchor decides
    where the overflow goes -- centred it splits above and below, top-anchored
    it all falls into the badge column underneath.

    This is the same chain as build_ph_textstyles and the layout background:
    slide -> layout -> master. That chain is not three properties, it is every
    inherited property, and fixing it three at a time is how deck 10 needed
    three review rounds.
    """
    out = {}
    for src in sorted((paths.raw / "ppt" / "slideLayouts").glob("slideLayout*.xml")):
        root = etree.parse(str(src)).getroot()
        per = {}
        for sp in root.iter():
            if etree.QName(sp).localname != "sp":
                continue
            ph = sp.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
            bp = sp.find("p:txBody/a:bodyPr", NS)
            if ph is None or bp is None:
                continue
            per[ph.get("type") or "body"] = {
                "anchor": bp.get("anchor"),
                "wrap": bp.get("wrap"),
                "insets": {k: (float(bp.get(a_)) / EMU_PT if bp.get(a_) else None)
                           for k, a_ in (("l", "lIns"), ("r", "rIns"),
                                         ("t", "tIns"), ("b", "bIns"))},
            }
        out[src.name] = per
    return out


# Bullet properties inherit INDEPENDENTLY of one another in OOXML: a layout may
# state only `buFont` and still take its `buChar` from the master. So these are
# merged per-key like `sz`/`face`, with one exception -- the KIND of bullet
# (`buNone` / `buChar` / `buAutoNum`) is a single atomic choice, and the nearest
# level that states any of the three settles it. That is what makes `buNone`
# suppress: it is not an absence, it is a stated value that wins at its level.
BULLET_KEYS = ("bu", "bufont", "buszpct", "buszpt", "buclr_el")


def _bullet_ent(lvl) -> dict:
    """Bullet properties off ONE pPr-shaped element (a paragraph's own `pPr` or
    any `lvl{i}pPr`). `buClr` is kept as the ELEMENT, not a hex string: colour
    needs the theme and the clrMap, and those live on Ctx. Resolving it here
    would mean re-deriving the theme in a function that has no business knowing
    about it. The dict never reaches JSON, so holding an lxml node is free."""
    if lvl is None:
        return {}
    ent = {}
    if lvl.find("a:buNone", NS) is not None:
        ent["bu"] = ("none", None)
    else:
        bc, ba = lvl.find("a:buChar", NS), lvl.find("a:buAutoNum", NS)
        if bc is not None and bc.get("char"):
            ent["bu"] = ("char", bc.get("char"))
        elif ba is not None:
            ent["bu"] = ("autonum", ba.get("type") or "arabicPeriod")
    bf = lvl.find("a:buFont", NS)
    if bf is not None and bf.get("typeface"):
        ent["bufont"] = bf.get("typeface")
    bp = lvl.find("a:buSzPct", NS)
    if bp is not None and bp.get("val"):
        ent["buszpct"] = int(bp.get("val")) / 100000.0
    # buSzPts is the absolute-points sibling of buSzPct and is what THIS deck
    # actually uses -- every buSz in the package is buSzPts. Reading only the
    # percentage form would have found nothing.
    bt = lvl.find("a:buSzPts", NS)
    if bt is not None and bt.get("val"):
        ent["buszpt"] = float(bt.get("val")) / 100.0
    bcl = lvl.find("a:buClr", NS)
    if bcl is not None and len(bcl):
        ent["buclr_el"] = bcl
    return ent


def _lvl_ent(lvl) -> dict:
    """Every authored property on ONE `lvl{i}pPr` -- the element's own
    attributes, its `lnSpc`, its `defRPr` and its bullet block.

    Hoisted out of `build_ph_textstyles` so the SHAPE's own `<a:lstStyle>` is
    read by literally the same code as the layout's and the master's, rather
    than by a copy of it that drifts. A non-placeholder text box gets no
    placeholder chain at all (`_lv` is None), so before this its `lstStyle` was
    the only statement of its own type and geometry and it was being ignored:
    deck 10's slide 30 has two `txBox="1"` shapes declaring 15pt Darker
    Grotesque Medium, centred, 80% spacing, 36pt/-25pt indents, and they
    rendered 14pt Liberation Sans flush left with no indent -- six authored
    properties dropped per paragraph, beside a third paragraph that IS a
    placeholder and resolved all six correctly.

    `lnSpc` hangs off the `lvl{i}pPr` ITSELF, not off its `defRPr` -- which is
    why reading only `defRPr` silently dropped it. Deck 10 declares the divider
    titles' 73pt and their 75% line spacing on the SAME element; the size was
    read and the spacing was not, so `line-height` fell to the substitute
    font's own natural metric (Anton, 1.5054 -- double the authored value).
    That is LEARNINGS rule 17/34's failure exactly.

    `algn`, `marL` and `indent` are likewise ATTRIBUTES of the element, missed
    the same way (rule 41(d)): slideLayout2/3 declare `algn="ctr"` on their
    title and subTitle placeholders and the master's body placeholder declares
    `marL="457200" indent="-317500"`, none of which reached the model.
    """
    if lvl is None:
        return {}
    ent = {}
    sp_ = lvl.find("a:lnSpc/a:spcPct", NS)
    if sp_ is not None and sp_.get("val"):
        ent["lnspc"] = int(sp_.get("val")) / 100000.0
    if lvl.get("algn"):
        ent["algn"] = lvl.get("algn")
    # EMU, like every other measurement in this module. Raw values here would
    # be 36x too large and silently plausible.
    for _a in ("marL", "indent"):
        if lvl.get(_a) is not None:
            ent[_a] = float(lvl.get(_a)) / EMU_PT
    d = lvl.find("a:defRPr", NS)
    if d is not None:
        lat = d.find("a:latin", NS)
        if d.get("sz"):
            ent["sz"] = float(d.get("sz")) / 100.0
        if lat is not None and lat.get("typeface"):
            ent["face"] = lat.get("typeface")
    ent.update(_bullet_ent(lvl))
    return ent


def build_txstyle_defaults(paths: DeckPaths) -> dict:
    """Levels 5 and 6 of the chain -- the master's <p:txStyles> and the
    presentation's <p:defaultTextStyle> -- for BULLET KEYS ONLY.

    Deliberately narrower than the placeholder walk. Those two levels also
    carry `algn`, `sz` and `defRPr` for every paragraph in the deck that states
    none, so widening this to all keys is its own blast radius and its own
    review; it is not a side effect to smuggle in with a bullet fix.
    """
    out = {}
    mr = sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml"))
    if mr:
        root = etree.parse(str(mr[0])).getroot()
        for key, tag in (("title", "titleStyle"), ("body", "bodyStyle"),
                         ("other", "otherStyle")):
            st = root.find(f"p:txStyles/p:{tag}", NS)
            if st is None:
                continue
            out[key] = {i - 1: _bullet_ent(st.find(f"a:lvl{i}pPr", NS))
                        for i in range(1, 10)
                        if st.find(f"a:lvl{i}pPr", NS) is not None}
    pres = paths.raw / "ppt" / "presentation.xml"
    if pres.exists():
        dts = etree.parse(str(pres)).getroot().find("p:defaultTextStyle", NS)
        if dts is not None:
            out["pres"] = {i - 1: _bullet_ent(dts.find(f"a:lvl{i}pPr", NS))
                           for i in range(1, 10)
                           if dts.find(f"a:lvl{i}pPr", NS) is not None}
    return out


def build_ph_textstyles(paths: DeckPaths) -> dict:
    """{layout filename: {ph type: {lvl (0-based): size_pt}}} from each layout
    placeholder's own <a:lstStyle>.

    NOTES records this walk (P&G, `_shared.resolve_inherited_size`) with its
    layout step "deferred -- no slide currently in scope uses layout
    overrides; placeholder for future expansion". Deck 10 is that expansion.
    Its divider titles carry `<a:rPr lang="en-US" dirty="0">` -- no `sz` at
    all -- and the size lives on slideLayout3's title placeholder as
    `sz="7300"`. Without this walk the run falls all the way through to the
    deck default (14pt here) and a 73pt display title renders at a fifth of
    its authored size, which is what the first render did.

    Captures SIZE and FACE. Colour keeps its existing fallback.

    FACE was deliberately excluded on the first pass and that was wrong. Deck
    10's master `title` placeholder declares `Bebas Neue Regular` and its
    `body` placeholder declares `Darker Grotesque Medium`, both in their OWN
    <a:lstStyle> -- while the master's <p:txStyles> says Arial. 11 runs declare
    no face and inherit; reading only txStyles put every one of them in Arial,
    which for BEAUTY needs 4.001em against a 2.947em box and cannot fit. The
    SLIDE MASTER's placeholders are part of this walk, not just the layouts'.
    """
    out = {}
    srcs = (sorted((paths.raw / "ppt" / "slideLayouts").glob("slideLayout*.xml"))
            + sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml")))
    for src in srcs:
        root = etree.parse(str(src)).getroot()
        per = {}
        for sp in root.iter():
            if etree.QName(sp).localname != "sp":
                continue
            ph = sp.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
            ls = sp.find("p:txBody/a:lstStyle", NS)
            if ph is None or ls is None:
                continue
            lvls = {}
            for i in range(1, 10):
                lvl = ls.find(f"a:lvl{i}pPr", NS)
                if lvl is None:
                    continue
                ent = _lvl_ent(lvl)
                if ent:
                    lvls[i - 1] = ent
            if lvls:
                per[ph.get("type") or "body"] = lvls
        out[src.name] = per
    return out


def build_layout_index(paths: DeckPaths) -> dict:
    """{layout filename: {"name": authored <p:cSld name>, "type": sldLayout type}}.

    The layout a slide inherits is the deck author's own structural statement,
    and until deck 10 nothing read it. Deck 10 (Secret) names its five chapter
    dividers by giving them a layout called SECTION_TITLE_AND_DESCRIPTION --
    a cleaner marker than pgdigital's `k-divider` class, because the author
    typed it rather than a converter inferring it.

    Read, never interpreted. What a given name MEANS is a per-deck declaration
    (the deck's own roles.py), for the same reason PHASE_1C_ARCHITECTURE.md
    gives for the deck classifier: a shared table that guessed would eventually
    guess wrong on an unseen deck, and a wrong archetype is exactly the
    "trusted instead of checked" failure that doc names.
    """
    out = {}
    for src in sorted((paths.raw / "ppt" / "slideLayouts").glob("slideLayout*.xml")):
        root = etree.parse(str(src)).getroot()
        cs = root.find("p:cSld", NS)
        out[src.name] = {"name": cs.get("name") if cs is not None else None,
                         "type": root.get("type")}
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


def _runs_of(ctx: Ctx, p_el, ph_size=None, ph_face=None):
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
        # THE SECOND ELEMENT IS NOT SPARE. `ctx.solid` returns (hex, alpha) and
        # this discarded the alpha with `col, _`, so every authored <a:alpha> on a
        # RUN fill was dropped between the parser and the model -- which is also
        # why the run schema had no alpha field to consume. Deck 10 carries eight:
        # slide 3's four agenda numerals (dk2 @ 50%) and the chapter numerals on
        # slides 4/9/14/21 (bg2 @ 50%). All eight rendered pure white, i.e. at
        # twice their authored weight against the photograph behind them.
        # Shapes have carried `fill` + `fill_alpha` since the first builder; runs
        # now carry the same pair under the same naming.
        col, col_a = (ctx.solid(rPr.find("a:solidFill", NS))
                      if rPr is not None else (None, None))
        t = r_.find("a:t", NS)
        runs.append({"text": (t.text or "") if t is not None else "",
                     "typeface": face or ph_face or ctx.inherited["typeface"],
                     "declared_face": face, "ph_face": ph_face,
                     "size_pt": size or ph_size or ctx.inherited["size_pt"],
                     "declared_size": size, "ph_size": ph_size,
                     "bold": (rPr.get("b") == "1") if rPr is not None else False,
                     "italic": (rPr.get("i") == "1") if rPr is not None else False,
                     "color": col or ctx.inherited["color"],
                     "declared_color": col,
                     # The alpha travels with the colour it belongs to: a run that
                     # declares its own fill takes that fill's alpha (which may be
                     # None, meaning opaque) and never the inherited one.
                     "color_alpha": col_a if col else ctx.inherited["color_alpha"],
                     "declared_color_alpha": col_a})
    return runs


def _paras_of(ctx: Ctx, tx, ph_lvls=None):
    """Paragraphs with bullet, alignment and indent. <a:buNone/> is an explicit
    'no bullet' and must not be read as 'no bullet property stated'."""
    out = []
    for p in tx.findall("a:p", NS):
        pPr = p.find("a:pPr", NS)
        lvl = int(pPr.get("lvl") or 0) if pPr is not None else 0
        # PRECEDENCE, nearest first: the paragraph's own pPr (applied per-key
        # below), then the SHAPE's own lstStyle, then the placeholder chain.
        # The shape level sits here rather than in resolve_ph_text because it
        # is per-shape, not per-placeholder-type -- and because a shape that is
        # NOT a placeholder has no chain to sit in: `_lv` is None for it, which
        # is exactly the case that was dropping six properties a paragraph.
        _ph = (ph_lvls or {}).get(lvl) or (ph_lvls or {}).get(0) or {}
        _sh = _lvl_ent(tx.find(f"a:lstStyle/a:lvl{lvl + 1}pPr", NS))
        _e = dict(_ph)
        _e.update({k: v for k, v in _sh.items() if v is not None})
        ph_size, ph_face = _e.get("sz"), _e.get("face")
        ph_lnspc = _e.get("lnspc")
        ph_algn, ph_marL, ph_indent = (_e.get("algn"), _e.get("marL"),
                                       _e.get("indent"))
        # Bullets resolve through the SAME chain as algn/marL/indent, with two
        # levels this function can see that resolve_ph_text cannot: the
        # paragraph's own pPr, and the SHAPE's own lstStyle. Reading only the
        # first of those (what this did) made every `buNone` at layout, master
        # or shape level invisible -- 54 of them in deck 10 -- and reached the
        # right answer only because an unseen `buNone` and an unseen `buChar`
        # both come out as "no bullet" when neither is read.
        bu_src = {}
        for _src in (_bullet_ent(pPr), _e):
            for _k in BULLET_KEYS:
                if _k not in bu_src and _src.get(_k) is not None:
                    bu_src[_k] = _src[_k]
        bu_kind, bu_val = bu_src.get("bu", (None, None))
        # buNone anywhere in the chain suppresses, and suppression is recorded
        # rather than merely resulting in None -- "the source says no bullet"
        # and "the source says nothing" are different facts about the deck.
        bullet = bu_val if bu_kind == "char" else None
        bu_clr = (ctx.solid(bu_src["buclr_el"])[0]
                  if bu_src.get("buclr_el") is not None else None)
        ln = pPr.find("a:lnSpc/a:spcPct", NS) if pPr is not None else None
        # Same precedence as line_pct throughout: a value the PARAGRAPH states
        # itself always wins, and the placeholder only fills a gap. Slide 4's
        # Subtitle 4 states `algn="l"` against a layout that says `ctr`, and
        # must stay left; slide 1's BEAUTY states marL="0" indent="0" against a
        # master that says 36pt/-25pt, and must stay flush.
        out.append({"align": (pPr.get("algn") if pPr is not None else None)
                             or ph_algn,
                    "bullet": bullet,
                    "bullet_suppressed": bu_kind == "none",
                    # Recorded, not rendered: a numbered bullet needs a counter
                    # per list, and no deck in the corpus declares one yet.
                    "bullet_autonum": bu_val if bu_kind == "autonum" else None,
                    "bullet_font": bu_src.get("bufont"),
                    "bullet_size_pt": bu_src.get("buszpt"),
                    "bullet_size_pct": bu_src.get("buszpct"),
                    "bullet_color": bu_clr,
                    # own lnSpc wins; otherwise the placeholder's, which is
                    # authored just as much and was previously invisible.
                    "line_pct": (int(ln.get("val")) / 100000.0 if ln is not None
                                 else ph_lnspc),
                    "marL": (float(pPr.get("marL")) / EMU_PT
                             if pPr is not None and pPr.get("marL") is not None
                             else ph_marL),
                    # New key. There was no `indent` in the model schema at
                    # all, so a hanging indent had nowhere to land even once
                    # the walk found one.
                    "indent": (float(pPr.get("indent")) / EMU_PT
                               if pPr is not None and pPr.get("indent") is not None
                               else ph_indent),
                    "runs": _runs_of(ctx, p, ph_size, ph_face)})
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
        # Two independent ways a picture can fail to hide what is under it, and
        # the occlusion test has to see both: transparency baked into the FILE
        # (opaque_fraction, an alpha-channel measurement) and transparency
        # applied to the FILL (alphaModFix). Reading only the first made deck
        # 10's slide 30 report an opaque JPEG at 12% opacity as full cover, so
        # everything beneath it -- including layout3's #A7C6ED panel, half the
        # slide's composition -- was flagged occluded and dropped. Effective
        # opacity is the product; one rule, one threshold.
        eff = s.get("opacity")
        return (bool(src) and ctx.opaque_fraction(src)
                * (1.0 if eff is None else eff) >= OPAQUE_MIN)
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


def _slide_master_themes(paths: DeckPaths) -> set:
    """Every theme reachable from a SLIDE master — the only themes that can paint.

    A package theme is not automatically a rendering surface. A notes master
    carries its own theme and Office gives it the stock "Default" scheme, which
    differs from a designed slide theme on almost every token by construction.
    Comparing against it asks whether two unrelated documents agree.
    """
    out = set()
    for m in sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml")):
        rp = m.parent / "_rels" / (m.name + ".rels")
        if not rp.exists():
            continue
        for r in etree.parse(str(rp)).getroot():
            if r.get("Type").rsplit("/", 1)[-1] == "theme":
                out.add((m.parent / r.get("Target")).resolve())
    return out


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
    # NARROWED AGAIN, deck 10 (Secret), 2026-08-27. The deck-9 pass above
    # narrowed this to referenced TOKENS but kept comparing against every theme
    # in the package -- and deck 10 shows that was the wrong axis. Its themes
    # disagree on five tokens the slides genuinely reference (dk1/lt1/dk2/lt2/
    # accent1), so the token filter does not save it, and the build failed on a
    # comparison that should never have been made: theme2 is the NOTES master's
    # theme (Office's stock "Default" scheme) and cannot paint a slide.
    #
    # The right question is not "do the packaged themes agree" but "can more
    # than one theme paint a slide, and do those agree". Compare only themes
    # reachable from a slide master. With one slide master the check is vacuous,
    # which is correct: there is nothing that could disagree. A deck with two
    # slide masters on different themes still fails hard, which is the case the
    # assertion was written for.
    #
    # Same family as LEARNINGS rule 35's sibling instance and the Patchology
    # 767/768 sliver: a declaration existing is not a consumer existing.
    referenced = _referenced_scheme_keys(paths)
    painting = _slide_master_themes(paths)
    others = sorted(p for p in painting if p != theme_path)
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

    ignored = sorted(p.name for p in theme_dir.glob("theme*.xml")
                     if p not in painting)
    theme_audit = {
        "non_painting_themes_ignored": ignored,
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
    _inh_col, _inh_a = (ctx.solid(defr.find("a:solidFill", NS))
                        if defr is not None else (None, None))
    ctx.inherited["color"], ctx.inherited["color_alpha"] = _inh_col, _inh_a
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
    layout_index = build_layout_index(paths)
    ph_text = build_ph_textstyles(paths)
    # Levels 5 and 6, bullet keys only -- see build_txstyle_defaults.
    tx_defaults = build_txstyle_defaults(paths)
    ph_body = build_ph_bodypr(paths)
    _masters = sorted((paths.raw / "ppt" / "slideMasters").glob("slideMaster*.xml"))
    master_name = _masters[0].name if _masters else None

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
        # Background inheritance is slide -> LAYOUT -> master. The layout link
        # was missing and nothing had needed it: the four PowerPoint-authored
        # decks put backgrounds on the slide or the master. This Google Slides
        # export puts them on the layout -- slideLayout2 declares
        # <p:bg> #A7C6ED -- so four slides rendered the master's yellow instead
        # of the deck's blue until this walked the middle link.
        #
        # <a:noFill/> is an explicit "this level paints nothing", NOT "this
        # level says nothing": layouts 3 and 4 carry it, and both correctly
        # fall through to the master rather than being treated as a blue
        # they never declared.
        bg_el = root.find("p:cSld/p:bg", NS)
        bg_src = "slide"
        if bg_el is None or bg_el.find(".//a:solidFill", NS) is None:
            bg_src = "master"
            _lp = (paths.raw / "ppt" / "slideLayouts" / layout_name) if layout_name else None
            if _lp is not None and _lp.exists():
                _lbg = etree.parse(str(_lp)).getroot().find("p:cSld/p:bg", NS)
                if _lbg is not None:
                    if _lbg.find("p:bgPr/a:noFill", NS) is not None:
                        # JUDGEMENT, not spec. <a:noFill/> on a layout is read
                        # as "this level paints NOTHING", so no ground is drawn
                        # at all -- NOT as "say nothing, inherit the master".
                        # ECMA-376 does not settle which it means. See the
                        # LEARNINGS entry; do not read this as proven.
                        bg_src = "none"
                    elif _lbg.find(".//a:solidFill", NS) is not None:
                        bg_el, bg_src = _lbg, "layout"
        bg_hex, bg_a = ctx.solid(bg_el.find(".//a:solidFill", NS)) if bg_el is not None else (None, None)
        bg_img = _bg_image(bg_el, rl)
        if bg_img:
            used_images.add(bg_img["src"])

        # Inherited layout shapes. PowerPoint paints the layout before the
        # slide, so these go FIRST and every slide shape stacks above them --
        # which under rule 21 (paint order IS DOM order, no z-index) is exactly
        # what emitting them first achieves.
        #
        # ALL non-placeholder layout shapes render, not only those that would
        # sit beneath slide content. The format has no such condition: the
        # layout renders regardless of z-position, so a "beneath content" rule
        # would invent a constraint OOXML does not have, and it would buy
        # nothing here (the 19 BLANK plate slides carry no layout shapes at
        # all) while failing silently on a deck that does rely on one.
        # Placeholders are excluded because the SLIDE supplies their content;
        # drawing the layout's copy would double every title.
        lay_shapes = []
        if layout_name:
            _lp = paths.raw / "ppt" / "slideLayouts" / layout_name
            if _lp.exists():
                _lr = etree.parse(str(_lp)).getroot()
                lay_shapes = [f for f in flatten_slide(_SlideShim(_lr))
                              if f.element.find(".//p:nvSpPr/p:nvPr/p:ph", NS) is None
                              and f.element.find(".//p:nvPicPr/p:nvPr/p:ph", NS) is None]

        shapes, skipped = [], []
        for _from_layout, fs in ([(True, f) for f in lay_shapes]
                                 + [(False, f) for f in flatten_slide(_SlideShim(root))]):
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

            if fs.kind == "cxnSp":
                # A CONNECTOR IS A STROKE, NOT A BOX. Both of deck 10's rules
                # are cx=624000 by cy=0 with <a:noFill/>: the entire visible
                # mark is the <a:ln>, so a shape with no line is genuinely
                # nothing and is skipped for that reason rather than for its
                # kind. Falling to the unhandled-kind branch silently dropped
                # all 8 in this deck, including the two that bracket slide 30's
                # EXECUTION headline above and below.
                _st = _stroke(ctx, el.find("p:spPr", NS))
                if _st is None:
                    skipped.append({"name": name, "kind": fs.kind,
                                    "why": "connector with no line"})
                    continue
                _pg = el.find("p:spPr/a:prstGeom", NS)
                _xf = el.find("p:spPr/a:xfrm", NS)
                shapes.append({"type": "line", "name": name, **geo,
                               "prst": _pg.get("prst") if _pg is not None else None,
                               "stroke": _st,
                               "flip_h": (_xf is not None and _xf.get("flipH") == "1"),
                               "flip_v": (_xf is not None and _xf.get("flipV") == "1"),
                               "from_layout": _from_layout})
                continue

            if fs.kind == "graphicFrame":
                tbl = _table(ctx, el)
                if tbl is None:
                    skipped.append({"name": name, "kind": fs.kind, "why": "graphicFrame, not a table"})
                    continue
                shapes.append({"type": "table", "name": name, **geo, "table": tbl,
                               "from_layout": _from_layout})
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
                # <a:alphaModFix> is a PICTURE-FILL effect: it scales the whole
                # blip's alpha, and it is the only mechanism this corpus uses to
                # wash a photograph back. `amt` is in thousandths of a percent,
                # so 12000 is 12% opacity; the attribute is OPTIONAL and its
                # default is 100000, which is why an absent `amt` must read as
                # fully opaque rather than as zero.
                _am = blip.find("a:alphaModFix", NS) if blip is not None else None
                if _am is not None:
                    rec["opacity"] = (int(_am.get("amt")) / 100000.0
                                      if _am.get("amt") else 1.0)
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
                rec["from_layout"] = _from_layout
                shapes.append(rec)
                continue

            if fs.kind == "sp":
                tx = el.find("p:txBody", NS)
                # A placeholder with no declared run size inherits from its
                # LAYOUT's placeholder lstStyle before the deck default.
                _ph = el.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
                _pt = _ph.get("type") if _ph is not None else None
                _lv = ((lambda: {i: resolve_ph_text(ph_text, layout_name, master_name, _pt, i,
                                                 tx_defaults)
                                 for i in range(9)})()
                       if _ph is not None else None)
                paras = _paras_of(ctx, tx, _lv) if tx is not None else []
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
                # bodyPr inherits slide -> layout placeholder -> OOXML default.
                # The slide's own copy is often `<a:bodyPr/>`, which states
                # nothing; the layout placeholder is where anchor, wrap and
                # insets actually live on this deck.
                _lb = (ph_body.get(layout_name, {}).get(_ph.get("type") or "body")
                       if _ph is not None else None) or {}
                if has_text:
                    _li_ins = _lb.get("insets") or {}
                    ins = {}
                    for k, a_, dflt in (("l", "lIns", 91440), ("r", "rIns", 91440),
                                        ("t", "tIns", 45720), ("b", "bIns", 45720)):
                        if bp is not None and bp.get(a_) is not None:
                            ins[k] = float(bp.get(a_)) / EMU_PT
                        elif _li_ins.get(k) is not None:
                            ins[k] = _li_ins[k]
                        else:
                            ins[k] = dflt / EMU_PT
                    autofit = bp is not None and bp.find("a:spAutoFit", NS) is not None
                    shapes.append({"type": "text", "name": name, **geo, "paras": paras,
                                   "from_layout": _from_layout,
                                   "fill": sp_hex, "fill_alpha": sp_a, "insets": ins,
                                   "anchor": ((bp.get("anchor") if bp is not None else None)
                                              or _lb.get("anchor")),
                                   "wrap": ((bp.get("wrap") if bp is not None else None)
                                            or _lb.get("wrap") or "square"),
                                   "autofit": autofit, "prst": prst,
                                   "grad": grad, "stroke": stroke,
                                   "review_sticker": _is_review_sticker(
                                       ctx, paras, sp_hex, from_style, style_font, autofit)})
                elif sp_hex or grad or stroke:
                    # rule 18 in full: a shape is inert only when it paints
                    # NOTHING. A gradient-only wedge and a stroke-only ellipse
                    # both paint, and both were being dropped.
                    shapes.append({"type": "rect", "name": name, **geo,
                                   "from_layout": _from_layout,
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
        for _r in shapes:
            _r.setdefault("from_layout", False)
        _li = layout_index.get(layout_name, {})
        deck["slides"].append({"n": idx, "src_n": src_n, "file": fname, "bg": bg_hex, "bg_alpha": bg_a, "bg_from": bg_src,
                               "bg_image": bg_img,
                               "layout": layout_name,
                               "layout_name": _li.get("name"),
                               "layout_type": _li.get("type"),
                               "shapes": shapes})
    return deck, used_images, used_videos


def write_model(paths: DeckPaths, drop_slides: frozenset[int] = frozenset()):
    deck, imgs, vids = build_model(paths, drop_slides=drop_slides)
    paths.out.mkdir(parents=True, exist_ok=True)
    (paths.out / "model.json").write_text(json.dumps(deck, indent=1))
    (paths.out / "used_assets.json").write_text(
        json.dumps({"images": sorted(imgs), "videos": sorted(vids)}, indent=1))
    return deck, imgs, vids
