"""Font substitution calibration — EMPIRICAL MAGIC, kept here so it's findable.

When a deck's source font (e.g. Univers Condensed) is not web-available
and we substitute, there are TWO cases that need different handling:

  MATCHED-METRIC SUBSTITUTION
    Source and target faces share metrics (x-height, advance width,
    proportions). Example: Univers Condensed → Barlow Condensed (both
    condensed sans-serifs with comparable widths). The substituted text
    occupies the same visual footprint, so declared size renders 1:1
    with NO scaling.

  CROSS-METRIC SUBSTITUTION
    Source and target have different metrics. Example: Univers
    Condensed → Arial (condensed → regular width). At the same
    nominal size, the substitute reads visually smaller because the
    proportions differ. PowerPoint compensates with an undocumented
    ~1.36× scale-up, and very large explicit sizes (>=88pt) instead
    use a CSS text-shadow blur to fill out the spacing without scaling.

P&G is MATCHED-METRIC: Univers Condensed → Barlow Condensed via Google
Fonts (the bundle ships `<link href="...Barlow+Condensed...">` and a
fallback chain `Barlow Condensed → Univers Condensed → Arial Narrow`).
The bundle's CSS confirms 1:1 rendering across slides 1, 8, 22, 23 at
all observed declared sizes (44pt, 66pt, 88pt) and a 16pt regular /
18pt bold default for inherited sizes (sz attribute absent on rPr).

The CROSS_METRIC_SCALE constant below preserves the handoff's 1.36×
rule for the future case when a deck uses a substitution we haven't
validated. It fires ONLY when `classify_substitution()` returns 'cross',
which is only true for typefaces not in MATCHED_METRIC_SUBS. Add new
matched-metric pairs there as new decks are validated.

If you're future-Claude reading this: re-check rendered output against
the actual bundle slide CSS before changing any constant. The numbers
have been load-bearing for slide-by-slide pixel parity.
"""
from __future__ import annotations

from typing import Optional


# Fonts we serve directly via @font-face or system stack — no
# substitution at all. Keys are lowercased typeface names.
WEB_AVAILABLE_TYPEFACES = {
    "barlow",
    "barlow condensed",
    "inter",
    "arial",
    "helvetica",
    "georgia",
    "times new roman",
    "verdana",
    "tahoma",
    "courier new",
    "trebuchet ms",
}


# Matched-metric substitution pairs: source typeface (lowercased) →
# target web font that preserves visual footprint. When a source is in
# this table, the substitution renders 1:1 with no scaling.
#
# Validated pairs (decks where bundle CSS confirms 1:1 rendering):
#   univers condensed / univers condensed light → Barlow Condensed (P&G)
#
# NOT every entry below is validated. Two classes live here, and the
# difference matters: a validated pair renders 1:1 because that was MEASURED,
# a provisional pair renders 1:1 because 1.36x cross-metric scaling would be
# worse — a defensible default, not a proof. Provisional entries say so.
#
# Add new pairs as new decks are validated. The value side is
# informational (kept for documentation); render-side font-family
# strings are constructed elsewhere.
MATCHED_METRIC_SUBS = {
    # Deck 10 (Secret), 2026-08-27. CORRECTED: this key read "barlow condensed"
    # from the first version of this table, where it sat on the same line as its
    # two condensed siblings under a "validated (P&G)" heading. It was never
    # validated. P&G names plain Univers ZERO times — only "Univers Condensed"
    # (8) and "Univers Condensed Light" (1) — so the entry inherited a
    # validation belonging to a different face and mapped a NORMAL-WIDTH
    # grotesque onto a CONDENSED substitute.
    #
    # Measured from deck 10's own embedded fonts (LEARNINGS rule 38 — header
    # only, never the glyph data): PANOSE proportion is 3 = Modern for Univers
    # and 6 = Condensed for Univers Condensed. Two width classes, stated by the
    # file. Barlow Condensed measures usWidthClass 3 / PANOSE 6, advance H
    # 0.472em — roughly a third narrow for 128 slide references.
    #
    # It never fired: deck 10 is the ONLY deck of 68 scanned that names plain
    # Univers, so no shipped deck is affected and nothing needs re-baselining.
    #
    # ARCHIVO IS A JUDGEMENT CALL, NOT A MEASUREMENT. Say so out loud, because
    # rule 34 exists precisely because a lineage argument once read as proof.
    # There is NO oracle here: deck 10 has 4 <a:spAutoFit/> boxes, all carry
    # wrap="none" (nullifying the width test, the Old Spice condition), and all
    # 4 are Univers CONDENSED — zero surface for the face that matters. The
    # grounds, in full:
    #   * H advance 0.732em, closest of the three bundled normal-width
    #     candidates (Poppins 0.717, Montserrat 0.806).
    #   * Same class of form. Univers is a neutral Swiss grotesque; Archivo is
    #     a grotesque. Poppins is geometric with circular bowls and would read
    #     visibly different at the 8pt plate labels that dominate this deck
    #     (87 of 132 sized runs). Montserrat at 0.806 would run 128 refs long.
    #   * Already bundled, and already carrying deck 9's Helvetica Light at
    #     weight 300 (phase_1c/venus_hestia/roles.py) — one family, not a
    #     second binary.
    # Provisional in the same sense as "boston semibold" and "gotham" below.
    # Listed under LEARNINGS "Open gaps".
    "univers": "archivo",
    "univers condensed": "barlow condensed",
    "univers condensed light": "barlow condensed",
    # Olay (Aug 2026). See SOURCE_LINE_HEIGHT_RATIOS / MATCHED_METRIC_AXES
    # below for how these two were derived — the first by measurement, the
    # second by design class only.
    "franklin gothic book": "archivo",
    "boston semibold": "poppins",
    # Theme minor-latin default on the Olay deck; its inherited runs resolve
    # to Aptos, a neo-grotesque, which Archivo matches at its natural width.
    "aptos": "archivo",
    # Old Spice (Aug 2026). Condensed -> condensed, the same substitution class
    # as the bundle-validated univers condensed -> barlow condensed pair, so it
    # renders 1:1. NOT width-verified: all three <a:spAutoFit/> frames in that
    # deck carry wrap="none", so the box width constrains nothing and the rule
    # 17 oracle yields only a line-height ratio. Recorded as provisional.
    "din condensed": "barlow condensed",
    # HenHouse (deck 8). Gotham is unlicensed; reached via the weight-token
    # fallback in classify_substitution() ("Gotham Black" -> family "gotham").
    # Montserrat is the geometric-sans design class AND the measured fit: the
    # authored spAutoFit box for "MAKES" at 60pt leaves 228.8pt of inner width,
    # and Montserrat at wght=800 renders it in 228.7pt — 0.1pt spare. wght=900
    # needs 231.3pt and would have wrapped, which the box's one-line height
    # rules out. Provisional in the same sense as boston semibold: the oracle
    # gives an upper bound, so 600/700 also fit; 800 is the tightest fit
    # consistent with the box the designer drew.
    "gotham": "montserrat",
    # Aptos Display is the theme's major font (title placeholders on s2/s4
    # resolve +mj-lt to it). Same design as Aptos, which already maps to
    # Archivo; registering it keeps one family across the deck instead of
    # letting the display cut fall to `cross` and take the 1.36x.
    "aptos display": "archivo",
}


# Line-height ratio of the SOURCE face, recovered from the deck rather than
# from the substitute. A text box carrying <a:spAutoFit/> was auto-sized by
# PowerPoint to exactly fit its wrapped text, so
#
#     box_height = tIns + bIns + line_count * (ratio * font_size)
#
# and a deck with boxes at several different line counts over-determines
# `ratio`. Olay's boxes step in exact 16.97pt increments at 14pt, giving
# 1.2121 for Franklin Gothic Book; the two 20pt boxes give 1.2140 for
# Boston SemiBold.
#
# This matters because the substitute's own line height is NOT the source's:
# Archivo's intrinsic hhea ratio is 1.088, which would set this deck's body
# copy 11% too tight. Emit line-height explicitly from this table instead of
# letting the substitute's metrics decide.
SOURCE_LINE_HEIGHT_RATIOS = {
    "franklin gothic book": 1.2121,
    "boston semibold": 1.2140,
    # Old Spice: two 28pt frames both autofit to h=41.2pt = 7.2 + 1 x 34.0pt.
    # Corroborated by a third frame at the inherited size (21.9 / 1.2143 =
    # 18.03pt, independently confirming the master's 18pt default).
    "din condensed": 1.2143,
    # Measured on this deck's autofit boxes: Gotham Black 60pt -> 1.2129,
    # and the inherited Aptos runs -> 1.2161 (16pt) / 1.2132 (24pt).
    # NOTE those three agree with Olay's Franklin Gothic Book (1.2121) and
    # Old Spice's DIN Condensed (1.2143). Five unrelated faces, one number:
    # this ratio is PowerPoint's autofit line spacing, NOT a font metric, so
    # it cannot be used to identify a substitute. Rule 17's line-COUNT test
    # still discriminates (it measures wrapping, which is face-specific);
    # its ratio test does not. Recorded here so line-height is set explicitly
    # rather than inherited from the substitute.
    "gotham": 1.2129,
    "aptos": 1.2132,
}


# Variable-axis settings that make a substitute metric-matched. Solved
# against the same spAutoFit oracle: at these axis values the substitute
# wraps every authored string to the same line count the original did.
#
#   franklin gothic book -> Archivo wdth=94   20/20 boxes exact
#                                             (valid window 93.5-95.0;
#                                              wdth=100 scores 9/20)
#
# Absent from this table means "use the substitute's default axes".
# Deliberately NOT applied to boston semibold: that pairing rests on design
# class, not measurement (52 characters across three short strings, all of
# which fit with 20-30% width to spare, so the oracle cannot discriminate).
# Treat the Boston rendering as provisional and swap in the licensed face
# if it becomes available.
MATCHED_METRIC_AXES = {
    "franklin gothic book": {"wdth": 94, "wght": 400},
    # HenHouse: "Gotham Black" -> family gotham, weight token 900. Montserrat
    # at wght=900 renders "MAKES"@60pt in 231.3pt against 228.8pt of authored
    # inner width and would have wrapped; wght=800 renders it in 228.7pt.
    # The authored box is the measurement, so 800 is what ships.
    "gotham": {"wght": 800},
}


# Inherited-size defaults (sz attribute absent on rPr). Bundle-derived:
#   bold runs    → 18pt   evidence: P&G slide 23 "FOR BUSINESS QUERIES"
#                                   (rendered at 1.406cqw × 12.8 = 18pt)
#   regular runs → 16pt   evidence: P&G slide 22 stakeholder names,
#                                   slide 23 contact lines
#                                   (rendered at 1.250cqw × 12.8 = 16pt)
#
# An earlier draft of the handoff had these as 28 / 22 — both numbers
# were wrong against the bundle. Bundle wins.
INHERITED_SIZE_BOLD_PT = 18.0
INHERITED_SIZE_REG_PT = 16.0


# === Cross-metric path constants (preserved from handoff, NOT active for P&G) ===
#
# These fire only when classify_substitution() returns 'cross', which
# happens only for typefaces absent from both WEB_AVAILABLE_TYPEFACES
# and MATCHED_METRIC_SUBS. They are unverified against any deck in this
# rebuild; preserved so the future case is ready.

# Below this declared size, cross-metric substitution scales up.
# At/above, the rendered text relies on a CSS text-shadow blur to fill
# out spacing without further scaling. (Handoff observation: PowerPoint
# scales sz=44 to ~60pt visually but renders sz=88 at ~88pt with shadow.)
CROSS_METRIC_SHADOW_THRESHOLD_PT = 88.0

# Multiplier for cross-metric substitution below the shadow threshold.
# Empirical from PowerPoint observation: 44 × 1.36 ≈ 60pt visual size.
CROSS_METRIC_SCALE = 1.36


# Foundry / release-family tokens that name a licensing cut, not a design.
# "DIN Pro Condensed" and "DIN Condensed" are the same face for substitution
# purposes; the suffix only says which package it shipped in.
#
# Stripped as whole TOKENS, never as substrings — "Proxima Nova" must not lose
# its "Pro", and "Standard Sans" must not lose its "Std"-looking prefix.
_FOUNDRY_TOKENS = {
    "pro", "std", "lt", "mt", "ps", "ef", "com", "cyr", "ce", "w1g",
    "paneuropean", "opentype", "otf", "ttf",
}


def normalize_typeface(typeface: Optional[str]) -> Optional[str]:
    """Lowercase a typeface name and drop foundry/release tokens.

    Added for Old Spice (deck 7), whose "DIN Pro Condensed" matched neither
    MATCHED_METRIC_SUBS nor BUNDLED_FALLBACKS — both of which already carry a
    "din condensed" entry — and so fell to the `cross` path and would have been
    scaled 1.36x, i.e. rule 10's exact failure. Fixed here as normalization
    rather than by adding a "din pro condensed" key, because a key clears one
    deck and leaves the next Std/LT/MT cut of the same family failing the same
    way. Every lookup against those tables should go through this.
    """
    if typeface is None:
        return None
    tokens = [t for t in typeface.lower().replace("-", " ").split() if t]
    kept = [t for t in tokens if t not in _FOUNDRY_TOKENS]
    return " ".join(kept) if kept else typeface.lower()


# Weight tokens that name a WEIGHT, not a family. Unlike the foundry tokens
# above these must NEVER be stripped unconditionally: "Boston SemiBold" and
# "Franklin Gothic Book" are registered under their full names and stripping
# would break both. They are used only as a FALLBACK — see
# family_and_weight() and classify_substitution().
#
# Added for HenHouse (deck 8), whose only declared face is "Gotham Black".
# The full name matches nothing, so it classified `cross` and 1.36x would
# have fired on three 60/66pt display runs (-> 81.6/89.8pt). "Gotham" is the
# family; "Black" is weight 900, which LEARNINGS rule 11 says to read off the
# typeface name rather than the b flag.
_WEIGHT_TOKENS = {
    "thin": 100, "hairline": 100,
    "extralight": 200, "ultralight": 200,
    "light": 300,
    "book": 400, "regular": 400, "normal": 400, "roman": 400,
    "medium": 500,
    "semibold": 600, "demibold": 600, "demi": 600,
    "bold": 700,
    "extrabold": 800, "ultrabold": 800,
    "black": 900, "heavy": 900, "ultra": 900, "fat": 900,
}


def family_and_weight(typeface: Optional[str]):
    """Split a typeface name into (family, weight or None).

    'Gotham Black' -> ('gotham', 900).  'Arial Black' -> ('arial', 900).
    'Univers Condensed' -> ('univers condensed', None) — 'condensed' is a
    width, not a weight, and stays with the family.

    Returns the normalized full name as the family when no weight token is
    present, so callers can use this unconditionally.
    """
    name = normalize_typeface(typeface)
    if name is None:
        return None, None
    tokens = name.split()
    weight = None
    kept = []
    for t in tokens:
        w = _WEIGHT_TOKENS.get(t)
        if w is not None and weight is None and len(tokens) > 1:
            weight = w
        else:
            kept.append(t)
    return (" ".join(kept) if kept else name), weight


def classify_substitution(typeface: Optional[str]) -> str:
    """Decide which calibration path applies for a typeface.

    Returns one of:
        'inherited'  — typeface is None (run inherits from layout/master)
        'web'        — typeface is web-served directly, no sub at all
        'matched'    — known matched-metric substitution, render 1:1
        'cross'      — fallback / unknown source, apply cross-metric rules
    """
    if typeface is None:
        return "inherited"
    name = normalize_typeface(typeface)
    # Exact name first — "boston semibold" and "franklin gothic book" are
    # registered whole, and must keep winning over any weight-stripped form.
    if name in WEB_AVAILABLE_TYPEFACES:
        return "web"
    if name in MATCHED_METRIC_SUBS:
        return "matched"
    # Only then: drop a trailing weight token and retry the family.
    family, weight = family_and_weight(typeface)
    if weight is not None and family != name:
        if family in WEB_AVAILABLE_TYPEFACES:
            return "web"
        if family in MATCHED_METRIC_SUBS:
            return "matched"
    return "cross"


def calibrate_size_pt(
    typeface: Optional[str],
    declared_size_pt: Optional[float],
    bold: Optional[bool],
) -> float:
    """Compute the size (in points) at which a run should be rendered.

    Behavior by classification:
      * web / matched / inherited  → declared size 1:1 (or inherited default)
      * cross                       → cross-metric scale rules (legacy handoff)

    Returns a positive float. Never None — callers can put this straight
    into CSS without further checking.
    """
    path = classify_substitution(typeface)

    if path in ("web", "matched", "inherited"):
        if declared_size_pt is not None:
            return float(declared_size_pt)
        return INHERITED_SIZE_BOLD_PT if bold else INHERITED_SIZE_REG_PT

    # 'cross' path — preserved for future decks, not exercised by P&G
    if declared_size_pt is None:
        return INHERITED_SIZE_BOLD_PT if bold else INHERITED_SIZE_REG_PT
    if declared_size_pt >= CROSS_METRIC_SHADOW_THRESHOLD_PT:
        return float(declared_size_pt)
    return declared_size_pt * CROSS_METRIC_SCALE
