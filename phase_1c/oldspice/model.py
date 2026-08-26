"""Old Spice slide model. Same shape as the Olay builder, three additions.

  * TABLES — slide 3 is a real <a:tbl> inside a <p:graphicFrame>. The Olay
    model classified graphicFrame as "unhandled kind" and dropped it, which
    here would silently lose the deck's densest slide (4x5 grid, 458 chars).
  * SVG-ONLY PICTURES — the wordmark's <a:blip> carries NO r:embed, only an
    asvg:svgBlip in its extLst. An a:blip/@r:embed lookup returns None and the
    logo vanishes. Rule 6 requires the vector to be embedded.
  * SINGLE THEME — this deck ships theme1.xml only. Olay asserted
    theme1 == theme2; that assertion has to tolerate a one-theme deck rather
    than crash, while still catching a real disagreement when both exist.

Rules carried unchanged from Olay: 1 (rels-bound media), 2 (real parser),
3 (coverage map), 4/5 (z-order), 14 (verbatim text), 18 (locker predicate),
19 (p:style fills), 23 (review stickers), 24 (occlusion + backdrop).
"""
from __future__ import annotations

import json, os, sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from lxml import etree
from PIL import Image

sys.path.insert(0, "/Users/gif025/Downloads/ondeck-pipeline")
from ondeck.parse.shapes import flatten_slide
from ondeck.parse.slide import NS, _is_design_locker
from ondeck.parse.theme import parse_theme, SCHEME_ALIASES
from ondeck.parse.color import ColorResolver

RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/oldspice/raw")
OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ASVG = {"asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main"}
EMU_PT = 12700.0
A = NS["a"]
OPAQUE_MIN = 0.999

INHERITED = {"size_pt": None, "typeface": None, "color": None}


class _SlideShim:
    def __init__(self, root): self.element = root


@lru_cache(maxsize=256)
def _opaque_fraction(src: str) -> float:
    p = RAW / "ppt" / "media" / src
    if p.suffix.lower() == ".svg":
        return 0.0
    im = Image.open(p)
    if im.mode not in ("RGBA", "LA"):
        return 1.0
    h = im.getchannel("A").histogram()
    return h[255] / float(sum(h))


def _rels(n: int) -> dict:
    p = RAW / "ppt" / "slides" / "_rels" / f"slide{n}.xml.rels"
    return {r.get("Id"): {"target": r.get("Target"), "type": r.get("Type").rsplit("/", 1)[-1]}
            for r in etree.parse(str(p)).getroot()} if p.exists() else {}


# Set once in build(): a ColorResolver whose theme dict carries the bg1/tx1
# aliases, which ColorResolver itself does not know (Theme.resolve does).
_CR = None


def _solid(fill_el, theme):
    """Resolve a fill through ColorResolver so lumMod/shade/tint actually apply.

    The Olay model read the scheme name and stopped there, which was harmless
    on a deck whose colours carried no transforms. This deck has 63 lumMod
    uses: the variant table's body text is bg1 + lumMod 50% (mid grey), and
    ignoring the transform resolved it to plain bg1 — white text on white
    cells, i.e. the table looked empty while every character was present in
    the DOM. Transform handling is rule 13's whole point; use the resolver
    that implements it rather than a second, weaker reading of the XML.
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
    if _CR is not None:
        try:
            return _CR.resolve(fill_el).get("final_hex"), alpha
        except KeyError:
            pass
    hexv = (node.get("val") if etree.QName(node).localname == "srgbClr"
            else theme.resolve(node.get("val")))
    return "#" + hexv.upper().lstrip("#"), alpha


def _srcrect(el):
    sr = el.find(".//a:srcRect", NS)
    if sr is None:
        return None
    d = {k: int(sr.get(k, 0)) / 100000.0 for k in ("l", "t", "r", "b")}
    return d if any(d.values()) else None


def _runs_of(p_el, theme):
    runs = []
    for r_ in p_el.findall("a:r", NS):
        rPr = r_.find("a:rPr", NS)
        lat = rPr.find("a:latin", NS) if rPr is not None else None
        face = lat.get("typeface") if lat is not None else None
        size = float(rPr.get("sz")) / 100 if rPr is not None and rPr.get("sz") else None
        col, _ = _solid(rPr.find("a:solidFill", NS), theme) if rPr is not None else (None, None)
        runs.append({"text": r_.find("a:t", NS).text or "",
                     "typeface": face or INHERITED["typeface"], "declared_face": face,
                     "size_pt": size if size else INHERITED["size_pt"], "declared_size": size,
                     "bold": (rPr.get("b") == "1") if rPr is not None else False,
                     "color": col or INHERITED["color"], "declared_color": col})
    return runs


def _paras_of(tx, theme):
    """Paragraphs with their bullet, if any.

    This deck bullets 12 paragraphs, all inside the variant table
    (<a:buChar char="/u2022">). Olay had none, so the Olay model never read
    them; dropping them here would quietly flatten a list into run-on lines.
    <a:buNone/> is an explicit "no bullet" and must not be confused with
    "no bullet property stated".
    """
    out = []
    for p in tx.findall("a:p", NS):
        pPr = p.find("a:pPr", NS)
        bullet = None
        if pPr is not None and pPr.find("a:buNone", NS) is None:
            bc = pPr.find("a:buChar", NS)
            if bc is not None:
                bullet = bc.get("char")
        out.append({"align": pPr.get("algn") if pPr is not None else None,
                    "bullet": bullet,
                    "marL": float(pPr.get("marL")) / EMU_PT if pPr is not None and pPr.get("marL") else None,
                    "runs": _runs_of(p, theme)})
    return out


def _table(el, theme):
    """<p:graphicFrame> -> a real table model. Cells keep their own runs so the
    editor can address each one, and the grid keeps its authored proportions."""
    tbl = el.find(".//a:tbl", NS)
    if tbl is None:
        return None
    grid = [int(gc.get("w")) / EMU_PT for gc in tbl.findall("a:tblGrid/a:gridCol", NS)]
    rows = []
    for tr in tbl.findall("a:tr", NS):
        cells = []
        for tc in tr.findall("a:tc", NS):
            tx = tc.find("a:txBody", NS)
            fill, alpha = _solid(tc.find("a:tcPr/a:solidFill", NS), theme)
            cells.append({"paras": _paras_of(tx, theme) if tx is not None else [],
                          "fill": fill, "fill_alpha": alpha,
                          "grid_span": int(tc.get("gridSpan", 1)),
                          "h_merge": tc.get("hMerge") == "1"})
        rows.append({"h_pt": int(tr.get("h", 0)) / EMU_PT, "cells": cells})
    return {"grid_pt": grid, "rows": rows}


def _covers(s, W, H, tol=1.0):
    return (s["x"] <= tol and s["y"] <= tol
            and s["x"] + s["w"] >= W - tol and s["y"] + s["h"] >= H - tol)


def _opaque(s):
    if s["type"] == "rect":
        return bool(s.get("fill")) and (s.get("fill_alpha") is None or s["fill_alpha"] >= 1.0)
    if s["type"] in ("image", "video"):
        src = s.get("poster")
        return bool(src) and _opaque_fraction(src) >= OPAQUE_MIN
    return False


def _mark(shapes, W, H):
    for s in shapes:
        s["occluded"] = False; s["backdrop"] = False
    covers = [i for i, s in enumerate(shapes) if _covers(s, W, H) and _opaque(s)]
    start = max(covers) if covers else 0
    for s in shapes[:start]:
        s["occluded"] = True
    for s in shapes[start:]:
        if s["type"] in ("image", "video"):
            if not _covers(s, W, H): break
            s["backdrop"] = True
        elif s["type"] == "rect":
            if not (s["y"] <= 1 and s["y"] + s["h"] >= H - 1): break
            s["backdrop"] = True
        else:
            break


def _style_colors(el, cr, fsl):
    st = el.find("p:style", NS)
    if st is None:
        return None, None
    fill_hex = font_hex = None
    sp_pr = el.find("p:spPr", NS)
    explicit = sp_pr is not None and any(
        sp_pr.find(f"a:{k}", NS) is not None
        for k in ("solidFill", "noFill", "gradFill", "blipFill", "pattFill"))
    fr = st.find("a:fillRef", NS)
    if fr is not None and not explicit and len(fr) and fsl is not None:
        idx = int(fr.get("idx", 0))
        if 1 <= idx <= len(fsl) and etree.QName(fsl[idx - 1]).localname == "solidFill":
            fill_hex = cr.resolve_with_theme(fr, fsl[idx - 1]).get("final_hex")
    fo = st.find("a:fontRef", NS)
    if fo is not None and len(fo):
        font_hex = cr.resolve(fo).get("final_hex")
    return fill_hex, font_hex


def _is_review_sticker(paras, fill_hex, from_style, style_font, autofit, theme):
    """LEARNINGS rule 23. Detection only — suppression is roles.py's call."""
    if not fill_hex or not from_style or not style_font or autofit:
        return False
    accents = {("#" + getattr(theme, f"accent{i}").lstrip("#")).upper() for i in range(1, 7)}
    if fill_hex.upper() not in accents:
        return False
    runs = [r for p in paras for r in p["runs"]]
    if not runs:
        return False
    return not any(r.get("declared_face") or r.get("declared_size") or r.get("declared_color")
                   for r in runs)


def build():
    theme = parse_theme((RAW / "ppt" / "theme" / "theme1.xml").read_bytes())
    t2 = RAW / "ppt" / "theme" / "theme2.xml"
    if t2.exists():
        assert asdict(theme) == asdict(parse_theme(t2.read_bytes())), \
            "theme1/theme2 disagree — the resolver path is unverified for that case"
        themes_agree = True
    else:
        themes_agree = None          # single-theme deck; nothing to compare
    troot = etree.parse(str(RAW / "ppt" / "theme" / "theme1.xml")).getroot()
    tdict = asdict(theme)
    tdict.update({k: getattr(theme, v) for k, v in SCHEME_ALIASES.items()})
    cr = ColorResolver(tdict)
    global _CR
    _CR = cr
    fsl = troot.find(".//a:fmtScheme/a:fillStyleLst", NS)

    m = etree.parse(str(RAW / "ppt" / "slideMasters" / "slideMaster1.xml")).getroot()
    lvl1 = m.find("p:txStyles/p:otherStyle/a:lvl1pPr", NS)
    defr = lvl1.find("a:defRPr", NS)
    INHERITED["size_pt"] = float(defr.get("sz")) / 100.0
    INHERITED["color"] = _solid(defr.find("a:solidFill", NS), theme)[0]
    minor = troot.find(".//a:fontScheme/a:minorFont/a:latin", NS)
    INHERITED["typeface"] = minor.get("typeface") if minor is not None else None

    m_bg = m.find("p:cSld/p:bg", NS)
    master_bg = "#FFFFFF"
    if m_bg is not None:
        ref = m_bg.find("p:bgRef/a:schemeClr", NS)
        direct, _ = _solid(m_bg.find(".//a:solidFill", NS), theme)
        master_bg = direct or ("#" + theme.resolve(ref.get("val")) if ref is not None else "#FFFFFF")

    pres = etree.parse(str(RAW / "ppt" / "presentation.xml")).getroot()
    prels = {r.get("Id"): r.get("Target")
             for r in etree.parse(str(RAW / "ppt" / "_rels" / "presentation.xml.rels")).getroot()}
    order = [os.path.basename(prels[s.get(R + "id")]) for s in pres.find("p:sldIdLst", NS)]
    sz = pres.find("p:sldSz", NS)
    W, H = int(sz.get("cx")) / EMU_PT, int(sz.get("cy")) / EMU_PT

    deck = {"w_pt": W, "h_pt": H, "theme": asdict(theme), "master_bg": master_bg,
            "themes_agree": themes_agree, "inherited": dict(INHERITED),
            "slides": [], "coverage": []}
    used = set()

    for idx, fname in enumerate(order, 1):
        root = etree.parse(str(RAW / "ppt" / "slides" / fname)).getroot()
        rl = _rels(idx)
        bg_el = root.find("p:cSld/p:bg", NS)
        bg_hex, bg_a = _solid(bg_el.find(".//a:solidFill", NS), theme) if bg_el is not None else (None, None)

        shapes, skipped = [], []
        for fs in flatten_slide(_SlideShim(root)):
            el = fs.element
            nv = el.find(".//p:cNvPr", NS)
            name = nv.get("name") if nv is not None else ""
            geo = dict(x=fs.x_pt, y=fs.y_pt, w=fs.w_pt, h=fs.h_pt, z=fs.z)
            if fs.x_pt is None:
                skipped.append({"name": name, "kind": fs.kind, "why": "no xfrm"}); continue

            if fs.kind == "graphicFrame":
                tbl = _table(el, theme)
                if tbl is None:
                    skipped.append({"name": name, "kind": fs.kind, "why": "graphicFrame, not a table"})
                    continue
                shapes.append({"type": "table", "name": name, **geo, "table": tbl})
                continue

            if fs.kind == "pic":
                blip = el.find(".//a:blip", NS)
                svg = el.find(".//asvg:svgBlip", ASVG)
                emb = blip.get(R + "embed") if blip is not None else None
                svg_emb = svg.get(R + "embed") if svg is not None else None
                src = os.path.basename(rl.get(emb, {}).get("target")) if emb else None
                svg_src = os.path.basename(rl.get(svg_emb, {}).get("target")) if svg_emb else None
                if not src and not svg_src:
                    skipped.append({"name": name, "kind": "pic", "why": "no resolvable image rId"})
                    continue
                if src: used.add(src)
                if svg_src: used.add(svg_src)
                shapes.append({"type": "image", "name": name, **geo, "crop": _srcrect(el),
                               "poster": src, "svg": svg_src})
                continue

            if fs.kind == "sp":
                tx = el.find("p:txBody", NS)
                paras = _paras_of(tx, theme) if tx is not None else []
                has_text = any(r["text"].strip() for p in paras for r in p["runs"])
                sp_hex, sp_a = _solid(el.find("p:spPr/a:solidFill", NS), theme)
                style_fill, style_font = _style_colors(el, cr, fsl)
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
                                   "review_sticker": _is_review_sticker(
                                       paras, sp_hex, from_style, style_font, autofit, theme)})
                elif sp_hex:
                    shapes.append({"type": "rect", "name": name, **geo,
                                   "fill": sp_hex, "fill_alpha": sp_a, "prst": prst})
                else:
                    skipped.append({"name": name, "kind": "sp", "why": "no fill, no text"})
                continue

            skipped.append({"name": name, "kind": fs.kind, "why": "unhandled kind"})

        _mark(shapes, W, H)
        bound = {s.get("poster") for s in shapes} | {s.get("svg") for s in shapes}
        unbound = sorted({v["target"].split("/")[-1] for v in rl.values()
                          if v["type"] in ("image", "video", "media", "hdphoto")
                          and v["target"].split("/")[-1] not in bound})
        lockers = sum(1 for c in root.find("p:cSld/p:spTree", NS).iter()
                      if etree.QName(c).localname in ("sp", "pic") and _is_design_locker(c))
        deck["coverage"].append({"slide": idx, "shapes": len(shapes), "skipped": skipped,
                                 "design_lockers": lockers, "unbound_rels": unbound})
        deck["slides"].append({"n": idx, "file": fname, "bg": bg_hex, "bg_alpha": bg_a,
                               "bg_image": None, "shapes": shapes})
    return deck, used


if __name__ == "__main__":
    deck, used = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model.json").write_text(json.dumps(deck, indent=1))
    (OUT / "used_images.json").write_text(json.dumps(sorted(used)))
    tot = sum(len(s["shapes"]) for s in deck["slides"])
    sk = sum(len(c["skipped"]) for c in deck["coverage"])
    lk = sum(c["design_lockers"] for c in deck["coverage"])
    st = sum(1 for s in deck["slides"] for x in s["shapes"] if x.get("review_sticker"))
    oc = [(s["n"], x["name"]) for s in deck["slides"] for x in s["shapes"] if x.get("occluded")]
    tb = [(s["n"], x["name"]) for s in deck["slides"] for x in s["shapes"] if x["type"] == "table"]
    sv = [(s["n"], x["svg"]) for s in deck["slides"] for x in s["shapes"] if x.get("svg")]
    print(f"slides={len(deck['slides'])} shapes={tot} skipped={sk} lockers={lk} assets={len(used)}")
    print(f"themes_agree={deck['themes_agree']} (None = single-theme deck)")
    print(f"inherited={deck['inherited']}  master_bg={deck['master_bg']}")
    print(f"review stickers={st}  occluded={oc}")
    print(f"tables={tb}  svg={sv}")
    for c in deck["coverage"]:
        if c["skipped"] or c["unbound_rels"]:
            print(f"  slide {c['slide']}: skipped={[(x['name'],x['why']) for x in c['skipped']]} "
                  f"unbound={c['unbound_rels']}")
