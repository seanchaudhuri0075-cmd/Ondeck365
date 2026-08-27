# Fragment navigation, slide identity & chapter anchors — Session Handoff

**Date:** 2026-08-27
**Status:** investigation complete. **Nothing implemented — deliberately.**

Scope: everything a shareable per-slide or per-chapter link depends on —
(1) does fragment navigation scroll at all, (2) do ids survive a Deck Editor
round-trip, (3) are ordinals stable, (4) where do chapter anchors come from,
(5) fragments or paths.

**Provenance.** These findings come from a session whose transcript was lost.
They were investigated and measured in a live browser against live files. They
are not reasoned. The one item that is a proposal rather than a measurement is
labelled as such. Full record: `NOTES.md`, §"Fragment navigation, slide
identity, chapter anchors (2026-08-27)".

---

## 0. Do these in order

1. **Fix `scroll-behavior: smooth` on pgdigital's `#deck`** (§1). Chapter
   anchors live on pgdigital and only pgdigital, and it is the one deck where
   fragment navigation does not work. **Anchor work cannot be verified until
   this lands.**
2. Decide the id scheme (§3) — the `s{src_n}` proposal, or an alternative.
3. Declare the divider archetype per builder (§4).

## 1. Fragment navigation — `scroll-behavior: smooth` is the whole cause

**pgdigital sets `scroll-behavior: smooth` on `#deck`. `hh`, `olay` and
`oldspice` use `auto`.** Fragment navigation and `scrollIntoView()` inherit the
container's value, and a smooth scroll over ~48,000px inside a snap container
is **cancelled** — the scroller never leaves 0.

### The hypothesis this kills

"Fragment navigation does not work inside an inner scroller" — **wrong.**
Three of the four decks are inner scrollers and their fragment navigation lands
exactly. Do not spend another session on scroller architecture; the defect is
one CSS declaration on one deck.

### Measured

| case | result |
|---|---|
| hh desktop, snap active, `#s40` | lands exactly, `targetTop` 0, 100% of viewport |
| hh mobile 390x844, gate released (`snap:none`, `stop:normal`) | lands exactly, `targetTop` 0 |
| cold load, both | zero drift, with 93 images still `incomplete` |
| pgdigital desktop, `#slide-45` | does not move — `deckScrollTop` 0, still on slide-0, target 43,290px below |

Image decode is excluded: every media box is reserved from `--ar`
(`imgs_without_reserved_box: 0`), so cold load drifts by zero even with 93
images outstanding.

### Mechanism, isolated on pgdigital desktop

| call | result |
|---|---|
| `deck.scrollTo({top, behavior:'smooth'})` | **FAILS** — stays 0 |
| `deck.scrollTo({top, behavior:'instant'})` | works — 43290 |
| `deck.scrollTop = top` | works — 43290 |

Same scroller, same target, two of three routes arrive. The variable is the
distance under `smooth`, nothing else.

### Fix direction

1. **Do not set `scroll-behavior: smooth` on a long snap scroller.** For
   pgdigital this is a one-line removal on `#deck`.
2. Where smooth motion is wanted, pass `behavior` explicitly per call so long
   jumps can use `instant`, instead of inheriting it from the container.
3. This repo emits no `scroll-behavior` anywhere (0 hits across all files
   excluding `.git`/`out.zip`, including built decks in `out/`), so decks built
   here already default to `auto`. **Keep it that way** — do not add the
   property to `deckkit` as a convenience.

## 2. Editor round-trip — ids survive, nothing to defend against

Import → `commitAll()` → `buildOutput()`, on live files:

| deck | ids | attributes | scripts |
|---|---|---|---|
| hh | 52 identical | `data-slide` 52 → 52 | — |
| pgdigital | 50 identical | `data-n` 55 → 55, rail 51 → 51 | both preserved |

Consistent with `DECK9_HANDOFF.md` §7 — five benign normalisations, no
sanitiser, no script-stripping path. **Anchors written into a deck survive an
editor pass unchanged.** No id-preservation shim is needed.

## 3. Ordinal stability — the builder is the hazard, not the editor

Both editor mutations were measured:

| mutation | result |
|---|---|
| delete slide 3 | ids become `s1`, `s2`, **`s4`**, `s5` — leaves a gap, does not renumber |
| `moveSlide(0,4)` | ids become `s2`, `s4`, `s5`, `s6`, **`s1`** — **ids travel with their content** |

**The editor is content-bound and is safe. Our builder is position-bound and is
what breaks shared links.** Deck 9 is the worked example: dropping source
slide 1 at build level (commit `3cf5ae1`) renumbered the rest 1..64, so **the
old `s2` became `s1`**. Every link shared before that build silently moved by
one slide.

Same failure class as the R4 → OSR media renumbering and the R2 prefix
collision (both in `NOTES.md`): one identifier silently meaning two different
things. Under `Cache-Control: max-age=31536000, immutable` the R2 variant of
this cannot be repaired in place.

### Proposal to implement — NOT yet implemented

```
id="s{src_n}"   →  bound to the SOURCE PPTX slide number
data-slide="{n}" →  bound to OUTPUT position
```

- Human-readable and guessable.
- Stable under the mutation that actually breaks links: dropping or inserting a
  source slide no longer moves any other slide's id.
- Output position remains available on the data attribute, where renumbering
  is harmless.

**No content hash — Sean rejected an opaque id.** Do not reintroduce one.

## 4. Chapter anchors

### pgdigital needs no authoring hint — the markup is already there

`class="slide k-divider"` marks **exactly 5 slides**, matching the five
chapters, with the full title in `data-slide-name`:

| slide | title | slug |
|---|---|---|
| `slide-4` | 01 / Omnichannel Meta Ads | `01-omnichannel-meta-ads` |
| `slide-9` | 02 / 3D CGI and GenAI Social Ads | `02-3d-cgi-genai-social-ads` |
| `slide-26` | 03 / CGI AI Scenes + Environments | `03-cgi-ai-scenes-environments` |
| `slide-37` | 04 / Display Banner Ads | `04-display-banner-ads` |
| `slide-39` | 05 / Sponsored Brand Videos | `05-sponsored-brand-videos` |

**No collisions at any length** — the numeric prefix makes collision
impossible. **Emit the full slug and resolve any unique prefix**, so both
`#01-omnichannel` and `#01-omnichannel-meta-ads` work.

Also measured: the chapter name appears as a **running kicker on every content
slide**, so chapter membership is recoverable for **every** slide, not only the
five dividers. A "which chapter am I in" affordance does not need extra markup.

### The other decks are not uniform — per-deck mapping, not per-slide hints

| deck | divider signal | chapters? |
|---|---|---|
| pgdigital | `class="slide k-divider"` ×5 | yes |
| oldspicepackaging | `data-arch=divider` ×3 | yes |
| hh-creativestrategy | none; closest is `data-arche=route` ×3 | — |
| olay | nothing (only `data-layout=strip`) | **no chapter structure to anchor** |

Each `phase_1c` builder already classifies archetypes. It only needs to
**declare which archetype means chapter divider**. Do not add per-slide
authoring markup to the decks — the classification already exists, it is just
not named. Note olay has nothing to anchor; do not force chapters onto it.

## 5. Fragments, not paths — confirmed against the live host

| URL | result |
|---|---|
| `/01-omnichannel` | **real 404**, GitHub's own error page |
| `/#01-omnichannel` | **200** |

**No SPA fallback exists.** Anchors must be fragments. A path-shaped share link
cannot work on this host without adding a fallback that is not there today.

## 6. Constraint — pgdigital's existing ids must not be renamed

pgdigital's ids are **`slide-N`, 0-based** (`slide-0` is the first slide; the
measured fragment above was `#slide-45`). **Do not rename them.** Links may
already have been shared against them, and per §5 this host returns a hard 404
rather than degrading — a renamed id fails outright. Any new scheme (§3) is
**additive** on pgdigital: `slide-N` must keep resolving.
