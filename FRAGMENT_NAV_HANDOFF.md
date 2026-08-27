# Fragment navigation, slide identity & chapter anchors — Session Handoff

**Date:** 2026-08-27
**Status:** §1 FIXED (`4e10fd9`). §3 partly ADDRESSED via 1-based aliases
(`8cedd3b`) — the builder-side ordinal problem is still open. §8 mobile scroll
gate SHIPPED (`8c971d9`, revert target `8cedd3b`) and fully verified on a real
phone, diagonal-swipe check included.
§4 chapter anchors still open and now unblocked. Mobile below 900px remains UNVERIFIED for
§7's changes only — the aliases, the URL tracking and the hero footer.

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

1. ~~**Fix `scroll-behavior: smooth` on pgdigital's `#deck`** (§1).~~ **DONE
   2026-08-27** — `4e10fd9`. Fragment nav now lands exactly; the blocker on
   chapter-anchor work is cleared. Note the selector was `.deck`, not `#deck`.
   See `NOTES.md` §"pgdigital — `scroll-behavior` fixed".
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

**Satisfied as of `8cedd3b`** — see §7. The 1-based `#slideN` aliases are extra
elements, not renames; all 50 `slide-N` ids were verified still resolving, with
no duplicate ids in the document.


---

## 7. Counter, aliases and scroll-tracked URL — SHIPPED 2026-08-27

**Commit `8cedd3b`, revert target `4e10fd9`.** Full record: `NOTES.md`
§"pgdigital — counter diagnosis, 1-based aliases, scroll-tracked URL".

### The counter was never wired to anything

Static text baked per slide. The generator `foot(s, total)` exists but is **dead
code** — boot adopts the shipped markup rather than building. The whole file had
**one `addEventListener`, `keydown`**: no scroll, hash, popstate or history
handling anywhere. The counters were correct; nothing updated the URL, which is
what made the readout look stuck.

### Shipped

| | change | script? |
|---|---|---|
| aliases | zero-size `<span class="alias" id="slideN">` per slide, N = `data-n` | **none** |
| URL tracking | `replaceState` + IO over a midline band | ~11 lines |
| slide-1 | the missing `.foot`, `02 / 50` at 4% | none |

`#slide45` → the slide reading `45 / 50`. `#slide-N` untouched and still
resolving — verified for all 50, with no duplicate ids in the document.

**`replaceState`, never `location.hash`:** measured 0 vs 8 history entries for 8
slide changes. **Midline band, never a ratio threshold:** the five `.tall`
slides can never reach a high ratio — the same failure the deck 9 player hit
(§12 of `DECK9_HANDOFF.md`).

### slide-1 is `02 / 50`, not `01 / 50`

`slide-0` already carries `01 / 50` and slide-1 is `data-n="2"`. The requested
`01` would have shipped a duplicate to the client.

### UNVERIFIED — below 900px

The window resize bounced back on every attempt, twice now. **Aliases, URL
tracking and the new hero footer are all unconfirmed on mobile**, and the footer
is in flow below 900px so it takes 34px off the hero image. Needs a real phone.

### Two method traps, both of which recur

1. **A polluted tab lies.** 50 history entries from a `location.hash` test loop
   produced results drifting by one per call, and **assigning `location.hash`
   its current value is a no-op**, so jumps silently never fired. Verify
   fragment navigation with a **full page load in a fresh tab** — which is what
   a shared link does anyway.
2. **A dead IntersectionObserver is usually a tab that is not painting.** No
   observer fired, including ones with the page's own working options, with no
   console errors. `requestAnimationFrame` never fired in 45s — no render step
   means no IO callbacks, ever, and no video autoplay either. **Race a rAF
   against a timeout before debugging any observer.** Forcing a paint via
   screenshot proved the observer had been right all along. Same trap as the
   Venus mobile review.


---

## 8. Mobile scroll gate — SHIPPED 2026-08-27

**Commit `8c971d9`, revert target `8cedd3b`.** Full record: `NOTES.md`
§"pgdigital — mobile scroll gate ported from hh".

Sean confirmed on a real phone: on hh a flick carries through several slides, on
pgdigital every slide took a deliberate drag. Third deck with this symptom after
HenHouse and Olay; same fix signed off on both.

```css
@media (max-width:899px){
  .deck{scroll-snap-type:none}
  .slide{scroll-snap-stop:normal}
}
```

### The rule for the next deck — gate at ITS OWN mobile boundary

**Do not copy hh's `820`.** 820 is hh's mobile breakpoint; pgdigital's is
900/899. Copying the number would have left 821–899px in mobile layout with
desktop snap — the problem and none of the fix. The invariant is *release snap
wherever the deck is in mobile layout*. Read the target deck's breakpoint first.

### Why, and what it cost

Snap points sit exactly one viewport apart (895 == slide == gap), so `proximity`
has nowhere to rest outside its threshold and behaves as `mandatory`; `always`
then forbids passing even one. Geometry, not the keyword. Accepted cost, as on
hh: a flick can now rest mid-slide.

**Desktop verified unchanged** before pushing, since Sean had just signed it
off: at 1680px, snap-type `y`, stop `always`, and 10 wheel ticks travel exactly
895px snapped — matching pre-patch, current, and hh.

### Diagonal swipe — CHECKED AND CLEAR (2026-08-27)

**Verified on a real phone, on the carousel slides.** Momentum carries through
multiple slides, matching hh, and the diagonal swipe **stays put** — Chrome's
gesture direction locking contains it. Measured, not predicted.

The 13 `.artscroll` carousels keep their own x-axis snap (measured
before/after, all four properties unchanged). The risk was that removing the
vertical brake — which had masked the vertical component of a diagonal swipe —
would let it carry; `overscroll-behavior-x:contain` covers horizontal
end-of-travel only, and hh has no nested scrollers so its sign-off could not be
cited. That reasoning was sound; the containment simply comes from the browser.

**This narrows deck 9.** `DECK9_HANDOFF.md` §12 lists a horizontal scroller
nested inside a vertical one as a plausible cause of the Venus scroll
complaint. pgdigital now runs 13 such slides with a released vertical gate and
is signed off, so **the nesting alone is not sufficient** — look elsewhere
first.
