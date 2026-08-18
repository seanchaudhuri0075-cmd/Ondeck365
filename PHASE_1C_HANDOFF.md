# Phase 1C — Session Handoff

Paste this at the start of a fresh session (chat or Claude Code) to restore
context without re-explaining from scratch.

---

**Who/what:** Sean, non-technical founder of On-Deck — a SaaS product
converting PowerPoint decks to pixel-faithful, mobile-responsive HTML.
Works across timezones/sessions; this doc plus `PHASE_1C_ARCHITECTURE.md`
are the persistent record — don't rely on chat history to carry this
forward.

**Where things stand:** Five decks have gone through this pipeline —
P&G, FrameTag, Wheeber, Global Image Factory, SHELFBEAUTY. Desktop
fidelity is in good shape (`LEARNINGS.md`, 20+ rules, each backed by a
real deck + fixture). Mobile got extensive work on both P&G and
SHELFBEAUTY specifically.

**The core finding (from the P&G work, re-confirmed via SHELFBEAUTY):**
Decks split into two archetypes needing different pipelines:
- **Corporate** (P&G, Global Image) — reliable master/layout
  inheritance, low per-slide variance, deck-token extraction works well
- **Creative/pitch** (FrameTag, Wheeber, SHELFBEAUTY) — every slide is a
  hand-built canvas, real per-slide OOXML walk has to be primary

**The one thing to not lose:** the classifier that sorts a deck into one
of these two buckets must be **advisory, never authoritative** — it
routes how much QA effort a deck gets before shipping, and must never
change how a slide actually renders. A misclassified deck that gets
*trusted* instead of *checked* would silently flatten real design intent
— worse than fully manual. This constraint is written into
`PHASE_1C_ARCHITECTURE.md` as a hard rule, not a suggestion. If a future
version of this pipeline ever lets classification skip verification,
that's a bug against that doc.

**What's already shipped and doesn't need to wait on any of this:**
- Dual-build: `#deck-desktop` (absolute-positioned, `cqw` units) +
  separate `#deck-mobile` DOM
- Color resolver (`ColorResolver`, `theme_from_pptx()`), fixture-backed
- Shape-level archetype library (`ondeck/layout/archetype.py`) — a
  *different, complementary* layer to the deck-level classifier below.
  Classifies individual slides by shape signature (photo-bleed,
  ghost-bleed, on-canvas-acrostic-over-photo, bulleted list) and routes
  each to a matching mobile treatment. This is what actually compounds
  deck-over-deck on the creative side.

**The actual next step:** Build and validate the deck-level classifier
against the five decks already on hand — P&G + Global Image as the
corporate baseline, FrameTag/Wheeber/SHELFBEAUTY as the creative
baseline — *before* trusting it on a new upload. Starting heuristic
(variance in per-slide overrides + animation presence) is written up in
`PHASE_1C_ARCHITECTURE.md` but unvalidated. If it doesn't cleanly sort
the five known decks, the heuristic needs rework before anything ships,
not after.

**Read next, in order:** `PHASE_1C_ARCHITECTURE.md` (full spec) →
`LEARNINGS.md` (desktop-fidelity rules, if touching rendering) →
`ondeck/layout/archetype.py` (existing shape-level pattern, for
reference/reuse before building the deck-level one).
