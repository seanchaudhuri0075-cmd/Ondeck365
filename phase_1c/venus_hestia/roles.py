"""Deck 9 constants: title, font substitution, and the measured line-height.

FONT SUBSTITUTION — measured, per rules 10 / 17 / 34.

The deck is 95% one face: Helvetica Light (1,642 of 1,728 runs), plus Arial
(75), Times New Roman (6) and Gilroy-Medium (5). None is web-available.

Rule 17's line-count oracle SATURATED on this deck and could not choose. 166
autofit boxes read cleanly, but 147 are single-line with width to spare, so
every candidate scored an identical 159/161 -- Helvetica Neue Light, Liberation
Sans, Arial and Archivo at four weights all tied. That is the same dead end
LEARNINGS records for Boston SemiBold -> Poppins, and per rule 34 a tie is not
evidence.

So the choice rests on DIRECT ADVANCE-WIDTH measurement instead, which is the
face-specific quantity the line-count test measures indirectly. 182 authored
strings were rendered at their authored sizes in each candidate and compared
against macOS Helvetica Neue Light:

    Archivo 300              +0.89%   <-- chosen
    Archivo 350              +1.81%
    Archivo 400              +2.72%
    Liberation Sans 400      +3.11%
    Arial 400                +3.11%   (identical to Liberation Sans, which is
                                       the metric-compatibility guarantee
                                       showing up in the data -- a second
                                       check that the harness is sound)
    Archivo 300 wdth=94      -4.30%

Two honest limits on that number, both for review:
  * The reference is Helvetica NEUE Light. "Helvetica Light" is not installed
    on any machine here and is not the same face. Neue is the closest real
    reference available, same family lineage.
  * Mean deviation is 0.89% but the per-string spread is 0.93x..1.18x, so a
    few short strings are noticeably wider. Watch the small labels at review.

LINE HEIGHT — 1.2124, recovered from this deck's own 353 autofit boxes and set
EXPLICITLY. Per rule 34 this is PowerPoint's autofit line spacing, not the
font's, so it says nothing about which face is right -- it is the value to
RENDER with so Archivo's own metrics are not inherited. Deck 9 is now the sixth
independent confirmation of that constant:

    Franklin Gothic Book  Olay        1.2121
    Helvetica Light       Venus       1.2124   <-- this deck
    Gotham Black          HenHouse    1.2129
    Aptos                 HenHouse    1.2132
    Boston SemiBold       Olay        1.2140
    DIN Condensed         Old Spice   1.2143
"""
from __future__ import annotations

DECK_TITLE = "Venus / Hestia — Photoshoot GenAI Creative Ads"

# Recovered from 353 spAutoFit boxes; 154 single-line boxes median 1.2124.
SOURCE_LINE_HEIGHT = 1.2124

# Substitutions. Every one is a measurement or an existing pipeline mapping;
# none is a lineage guess. `weight` overrides the run's own where the source
# face encodes weight in its NAME rather than in b="1" (rule 11).
SUBS = {
    "helvetica light":  {"stack": "'Archivo'", "weight": 300},
    "helvetica neue":   {"stack": "'Archivo'", "weight": 300},
    "helvetica":        {"stack": "'Liberation Sans'", "weight": None},
    "arial":            {"stack": "'Liberation Sans'", "weight": None},
    "times new roman":  {"stack": "Times, 'Times New Roman', serif", "weight": None},
    # 5 runs. Gilroy is a geometric sans and Poppins is the bundled geometric.
    # Chosen on design class, not measurement -- PROVISIONAL, same standing as
    # Olay's Boston SemiBold pairing. Too few characters for the oracle.
    "gilroy-medium":    {"stack": "'Poppins'", "weight": 500},
}

# NEVER emit a bare family name. An unknown or unembedded family with nothing
# after it falls through to the browser default, which is a SERIF -- the same
# defect as Olay's transposed cards rendering in Times (NOTES, mobile round 4).
# The first render of this deck hit it: Arial runs resolved to 'Liberation
# Sans', which was named in the CSS but not in the opt-in font set, so 75 runs
# and every headline on slide 3 rendered in Times against an otherwise
# grotesque deck. Both halves are fixed -- the family is embedded now, AND
# every stack ends in a real chain so a future miss degrades to a sans.
FALLBACK = "Helvetica, Arial, sans-serif"
BODY_STACK = f"'Archivo', 'Liberation Sans', {FALLBACK}"

# Families whose binaries must be inlined (ondeck.render.fonts opt-in set).
# Liberation Sans is in the DEFAULT bundle, not the opt-in one, so opting in to
# Archivo silently dropped it. It has to be listed explicitly.
FONT_FAMILIES = ("Archivo", "Poppins", "Liberation Sans")


def sub_for(typeface: str | None) -> dict:
    """Resolve a declared typeface to its substitute stack and weight override.

    The returned stack always ends in FALLBACK. A declared face with no entry
    here also returns None, so the run inherits BODY_STACK from `body` rather
    than naming a family the document never embeds.
    """
    if not typeface:
        return {"stack": None, "weight": None}       # inherited; body stack applies
    hit = SUBS.get(typeface.strip().lower())
    if hit is None:
        return {"stack": None, "weight": None}
    return {"stack": f"{hit['stack']}, {FALLBACK}", "weight": hit["weight"]}


# ---------------------------------------------------------------------------
# MOBILE: the format contact sheet
#
# 44 of the 64 slides — 69% — are the same idiom: one creative shown in two or
# three DELIVERY ASPECT RATIOS side by side, each captioned with its ratio
# ("1x1", "9x16", "16x9"), under a heading ("REVISED AD CREATIVES" or
# "VIDEO ASSETS"). 30 are two-up, 14 are three-up.
#
# That is a spec sheet, not a composition, and it is exactly what this
# pipeline's carousel idiom exists for (rule 31; Olay strips, Old Spice plates).
# Reproducing the authored 3-up at 390px gives the 16x9 tile about 180x101px —
# rule 29's failure verbatim. One cell per screen also drops effective
# simultaneous video decode from three to one, which matters more than the
# player's cap of 3 (3 x 1080p at 5 Mbps is ~15 Mbps sustained for one slide).
#
# Desktop keeps the authored arrangement exactly.
#
# DETECTED BY MEASUREMENT, never by slide number or by matching the caption
# strings: a slide qualifies when every one of its media shapes has a box aspect
# within 6% of a known delivery ratio AND those ratios are pairwise distinct.
# On this deck that separates 44 from 20 with no false positives, and the 44
# split exactly 30/14 as the survey said they should.
DELIVERY_RATIOS = {"1x1": 1.0, "9x16": 0.5625, "16x9": 1.7778}
DELIVERY_TOL = 0.06
CAPTION_MAX_CHARS = 6          # "16x9" is 4; the headings are 12 and 20


def delivery_tag(shape: dict) -> str | None:
    """Which delivery ratio this shape's BOX matches, or None."""
    if not shape.get("w") or not shape.get("h"):
        return None
    a = shape["w"] / shape["h"]
    for name, ratio in DELIVERY_RATIOS.items():
        if abs(a - ratio) / ratio <= DELIVERY_TOL:
            return name
    return None


def shape_text(shape: dict) -> str:
    return "".join(r.get("text", "")
                   for p in (shape.get("paras") or [])
                   for r in (p.get("runs") or [])).strip()


def contact_sheet(slide: dict):
    """Return [(media, caption_or_None), ...] if this slide is a contact sheet.

    Captions pair to tiles by nearest horizontal centre — a measurement, not a
    hand-tagged mapping.
    """
    media = [s for s in slide["shapes"] if s["type"] in ("image", "video")]
    tags = [delivery_tag(s) for s in media]
    if len(media) < 2 or not all(tags) or len(set(tags)) != len(tags):
        return None
    captions = [s for s in slide["shapes"]
                if s["type"] == "text" and len(shape_text(s)) <= CAPTION_MAX_CHARS]
    pairs, used = [], set()
    for m in media:
        centre = m["x"] + m["w"] / 2
        free = [c for c in captions if id(c) not in used]
        best = min(free, key=lambda c: abs((c["x"] + c["w"] / 2) - centre)) if free else None
        if best is not None:
            used.add(id(best))
        pairs.append((m, best))
    return pairs
