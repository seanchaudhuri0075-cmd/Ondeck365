# Phase 1C — Deck-Level Architecture

**Status:** Planning, consolidated 2026-08-08. Not yet implemented.
**Goal:** Move from "every deck needs a manual pass" → self-serve SaaS pipeline,
without the classifier itself becoming a source of visual distortion.
**Audience:** Future-self + whoever picks this up next, possibly in a
different session/timezone. This doc is the persistent record — don't
rely on chat history to carry this forward.

---

## Why this exists

This was scoped once already, during the P&G Phase 1B work (May 2026), and
never actually built — work went straight into more individual deck
conversions (GIF batch, then a deep SHELFBEAUTY session) instead. The
SHELFBEAUTY session independently re-derived the same need from scratch,
which is exactly the failure mode this doc is meant to prevent: losing the
plan between sessions and re-paying the diagnosis cost.

Five decks have gone through this pipeline so far: **P&G**, **FrameTag**,
**Wheeber**, **Global Image Factory**, and **SHELFBEAUTY**. That's enough
real variety to build the classifier against actual evidence instead of
guessing.

---

## The core distinction (established, P&G work, May 2026)

**Corporate decks** (P&G, Global Image Factory)
- Author respects PowerPoint's master/layout system
- Per-slide overrides are rare and intentional
- Low variance between slides
- Deck-token extraction (read the theme once) is high-signal, low-noise

**Creative / pitch decks** (FrameTag, Wheeber, SHELFBEAUTY)
- Every slide is hand-built as its own canvas
- Manual tab-positioning, off-canvas bleed elements, photo-overlay text,
  one-off accent styling — master inheritance is aspirational, not
  load-bearing
- Deck-token extraction alone produces a baseline half the slides ignore
- Real per-slide OOXML walk has to be the primary path, not a fallback

SHELFBEAUTY (Aug 2026 session) is a clean real-world confirmation of the
creative archetype — tabs for positioning, off-canvas decorative bleed,
on-canvas text-over-photo, per-run accent-color styling — all patterns
that don't show up in the corporate decks at all.

---

## The critical safeguard (added Aug 2026, do not skip this)

**The classifier must never change how a slide renders.** Every slide is
still built from its own real XML, regardless of classification. This
was flagged directly as a real risk: a wrong or overconfident
classification that causes the pipeline to *trust* deck tokens over a
slide's actual content would silently flatten real design intent —
worse than the current fully-manual state, not better. This is
especially true for agency-sourced decks, where "every deck is unique"
is a design choice, not an inconsistency to normalize away.

**What the classifier is allowed to change: where QA effort goes before
shipping, not what gets rendered.**

- Corporate-leaning signal → an automated pass is *likely* clean, gets
  spot-checked, never blindly trusted outright
- Creative-leaning signal → flagged honestly at upload as needing a full
  manual pass, before a customer sees it — not discovered as a surprise
  slide-by-slide the way SHELFBEAUTY was

The classifier is advisory (informs workflow) not authoritative (never
overrides real content). If a future implementation ever lets "corporate"
classification skip verification, that's a bug against this doc, not a
valid optimization.

---

## Classification heuristic (spec'd May 2026, not yet coded)

```python
def classify_deck_archetype(slides, deck_tokens):
    explicit_overrides_per_slide = count_explicit_size_overrides_per_slide(slides)
    layout_diversity = count_unique_layouts_used(slides)
    animation_count = count_animations(slides)

    if avg(explicit_overrides_per_slide) > THRESHOLD or animation_count > 0:
        return "creative"
    return "corporate"
```

Threshold and exact signal weights are unvalidated — this was written as a
starting hypothesis, not tuned against real deck data. Validating it
against the five decks already on hand (P&G + Global Image as the
corporate baseline, FrameTag/Wheeber/SHELFBEAUTY as the creative baseline)
should be the first implementation step, before trusting it on a new
upload.

---

## What already exists and works today (as of Aug 2026)

This is real, shipped, and doesn't need to wait on the classifier:

- **Dual-build architecture**: `#deck-desktop` (absolute-positioned 16:9
  canvas, `cqw` units) + separate `#deck-mobile` DOM. Proven across P&G,
  Global Image (continuous-scroll variant), and SHELFBEAUTY.
- **Color resolver**: `ColorResolver` + `theme_from_pptx()`, locked by
  real fixtures from P&G and SHELFBEAUTY themes (see `phase_1c/fixtures/`
  and `tests/test_color_resolver.py`).
- **Shape-level archetype library** (`ondeck/layout/archetype.py`, built
  during the SHELFBEAUTY session): classifies individual *slides* by
  shape signature — photo-bleed, ghost-bleed, on-canvas-acrostic-over-
  photo, bulleted list — and routes each to a matching mobile treatment.
  This is a different, complementary layer to the deck-level classifier
  above: it doesn't decide corporate-vs-creative, it makes creative-deck
  slides that share a pattern cheaper to handle the second time. This is
  what actually compounds deck-over-deck within the creative path, since
  creative decks won't become zero-touch by nature — there's no ground
  truth to check a design decision against, only taste.
- **LEARNINGS.md**: 20+ rules in symptom/root-cause/rule/assertion format,
  each backed by a real deck and (where applicable) a fixture. This is
  the desktop-fidelity side of "don't re-pay the same diagnosis cost."

---

## Open questions for whoever picks this up next

1. **Build and validate the classifier** against the five decks already
   on hand, before trusting it on a new upload. Corporate/creative should
   sort cleanly given how different P&G/Global Image are from
   FrameTag/Wheeber/SHELFBEAUTY structurally — if it doesn't sort
   cleanly, the heuristic needs rework before it ships, not after.
2. **`theme_from_pptx()` gap**: still only verified against decks where
   theme1 and theme2 agree on colors (P&G, SHELFBEAUTY both happen to
   match). A deck where they disagree is unverified.
3. **Cloudflare CDN migration** (Phase 2+, separate from this doc):
   designed as a non-rewrite migration — `inline_optimized_data_url`
   is a transport abstraction, swapping local-file for CDN-URL doesn't
   touch templates/validator/manifest. Documented in `NOTES.md`, not
   started.
4. **Whether "creative decks stay manual-pass-required forever" is the
   right permanent answer**, or whether the shape-level library
   eventually gets broad enough that creative decks converge toward
   corporate-deck levels of automation too. Genuinely open — revisit
   once the classifier has real data from a handful of new decks.
