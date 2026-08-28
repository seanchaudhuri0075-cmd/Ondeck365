"""Deck-agnostic MARKUP primitives, shared by the per-deck builders.

Separate from `css.py` because that module's scope is stated as CSS primitives
-- a number, a custom property, an expression, a two-line gate -- and this
emits HTML. Same argument for existing, different kind of output.

Why this module exists at all: `<a:br/>`.

`deckkit.model._runs_of` has recorded authored hard line breaks as
`br_after: True` since HenHouse (deck 8), where slide 3's beef-cut names
concatenated into "RibeyeStripChuck Eye..." because `findall("a:r")` skipped
the `<a:br>` elements between them. The MODEL layer was fixed then. The
RENDERERS were not: HenHouse consumes `br_after` at `render.py:688` and
**olay, oldspice, venus_hestia and secret do not read it at all**, so every one
of them silently discards authored breaks.

Deck 10 (Secret) is where that surfaced again: its divider titles are authored
`COLOR+` <a:br/> `TREATMENT` and `INGREDIENT` <a:br/> `LED`. Dropping the break
fused each into one unbreakable token, which then either broke at an arbitrary
point (`COLOR+TREA` / `TMENT`) or overhung its column by 84%. The break
opportunity was authored all along and the renderer was throwing it away.

That makes `br_after` the FIFTH fix that lived in one builder and not the
others, after the mobile scroll gate, the `--ar` consumer, the crop-frame clip
and `prst="ellipse"`. Four of the five surfaced on deck 10 alone.
"""
from __future__ import annotations

import html
from typing import Callable, Iterable, Optional


def esc(s: Optional[str]) -> str:
    """HTML-escape, with `None` as empty. Attribute-safe (quotes escaped)."""
    return html.escape(s or "", quote=True)


def runs_html(runs: Iterable[dict],
              style_for: Callable[[dict], str],
              escape: Callable[[Optional[str]], str] = esc) -> str:
    """A paragraph's runs as spans, with `<br>` after any run marked `br_after`.

    Behaviour is deliberately IDENTICAL to HenHouse's inline loop
    (`phase_1c/henhouse/render.py`, ~line 685-689) so that builder can be
    migrated onto this helper later without moving a single byte of its output:
    emit the span, then emit `<br>` immediately after it when `br_after` is
    truthy. Nothing else about the run is interpreted here.

    One deliberate difference from a naive `if r.get("text")` filter: the
    `br_after` flag is honoured EVEN IF the run carries no text. A break
    recorded against an empty run is still an authored break, and skipping the
    run must not silently skip the break with it.

    `style_for(run)` returns the span's inline style. It stays a callback
    because run styling is per-deck -- font stacks, weight resolution and cqw
    sizing all differ between builders -- and folding it in here would be the
    restructure LEARNINGS warns against rather than the de-duplication this is.
    """
    out = []
    for r in runs:
        text = r.get("text")
        if text:
            out.append(f'<span style="{style_for(r)}">{escape(text)}</span>')
        if r.get("br_after"):
            out.append("<br>")
    return "".join(out)
