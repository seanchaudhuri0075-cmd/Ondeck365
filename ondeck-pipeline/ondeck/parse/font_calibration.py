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
#   univers / univers condensed / univers condensed light → Barlow Condensed (P&G)
#
# Add new pairs as new decks are validated. The value side is
# informational (kept for documentation); render-side font-family
# strings are constructed elsewhere.
MATCHED_METRIC_SUBS = {
    "univers": "barlow condensed",
    "univers condensed": "barlow condensed",
    "univers condensed light": "barlow condensed",
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
    name = typeface.lower()
    if name in WEB_AVAILABLE_TYPEFACES:
        return "web"
    if name in MATCHED_METRIC_SUBS:
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
