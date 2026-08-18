"""Mobile layout helpers — vw-based typography + word-fit sizing.

Mobile uses `vw` units (% of viewport width) for typography rather than
cqw, because the mobile panel fills the viewport rather than living
inside a constrained canvas.

The word-fitting formula from the spec prevents long single words
from clipping the panel edges.
"""
from __future__ import annotations


def word_fit_vw(text: str, default_vw: float = 18.0, factor: float = 0.8) -> float:
    """Return font-size in vw such that the longest word fits the panel.

    Per the spec:
        font-size: min(default_vw, 100 / (max_word_chars * factor))vw

    Empirical examples:
        'OMNICHANNEL' (11 chars) → 100/(11*0.8) ≈ 11.36 vw
        'RETAIL'      (6 chars)  → 100/(6*0.8)  ≈ 20.83, capped at 18 vw
    """
    longest = max((len(w) for w in text.split() if w), default=1)
    return min(default_vw, 100 / (longest * factor))
