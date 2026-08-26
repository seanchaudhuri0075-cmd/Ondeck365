# Deck 9 — Venus / Hestia — Session Handoff

Paste this at the start of a fresh session to restore context. Written
2026-08-26 at the end of the diagnostic session, **before any building**.

Read alongside: `PHASE_1C_HANDOFF.md`, `PHASE_1C_ARCHITECTURE.md`,
`LEARNINGS.md` (36 rules), `NOTES.md` (deck 9 section starts at
"# Deck 9 — Venus / Hestia").

**Status: diagnostics complete, nothing built, nothing uploaded, nothing
published.** No `phase_1c/venus_hestia/` directory exists yet.

---

## 1. Source file — settled

**Canonical:** `~/Downloads/Venus_Hestia_Photoshoot_GenAI_CreativeAds_OSR.pptx`

```
sha256   32689c7c0d8e84793f8c91a44fc41bc6689b25566f5f76c3ae505c90f09d1162
size     958,639,589 bytes
modified 2026-08-26 01:37:45
slides   65
```

**Ignore entirely:** `041626_Venus_Hestia_Photoshoot_GenAI_CreativeAds_R4.pptx`
(958,571,645 B, 2026-08-18, 63 slides, sha256 `aa876bfd843be33f…`).

`_OSR` is this client's standard delivery suffix, not a one-off export — the
same folder holds `FACTORY_EXPANDED_OSR.pptx` and
`GIF2026_3D_CGVFX_AI_Presentation_OSR.pptx`. R4 is the superseded revision.

**Never mix the two.** OSR is a strict superset — 224 of its 226 media contents
also exist in R4, none of R4's are missing from OSR, and it adds slides 64/65
plus 2 media. But **the media are renumbered by one**: `OSR image101.jpeg ==
R4 image100.jpeg`, and 170 of 226 files carry identical bytes under a different
name. The Deck Editor derives R2 keys from media ordinals, so building from one
file and later switching would move 170 assets to different keys under
`Cache-Control: max-age=31536000, immutable`. **The source choice fixes the
asset key space for the life of the deck.**

---

## 2. Diagnostics run, and what they found

### Scale

| type | files | bytes |
|---|---|---|
| **mp4** | **53** | **845.55 MB (88%)** |
| png | 69 | 84.42 MB |
| jpeg | 46 | 22.75 MB |
| jpg | 57 | 5.66 MB |
| wdp | 1 | 0.04 MB |
| **total** | **226** | **958.42 MB** |

65 slides. 186 picture references over 172 distinct image assets (5 reused —
logos). 54 video references over 53 files (one used twice).

### Video

All **h264, 30 fps**. Three aspect families: **1080×1080 ×20, 1080×1920 ×20,
1920×1080 ×13**. Durations 3–8 s, median 4 s. **Only 282.4 s (4.7 min) of
footage for 845 MB — a 24 Mbps average**, wildly over-encoded for web.
**No GIFs.**

### Rules 20 / 35 / 28 — nothing to check

- **No slide carries a `<p:bg>` at all.** Zero translucent slide backgrounds.
- **Zero colour transforms deck-wide** (`lumMod`/`lumOff`/`tint`/`shade`/
  `satMod`): no `<a:solidFill>` carries one.
- Background comes only from the single master; 0 of 5 layouts override it.

So rules 20/35 have no surface, and rule 28's `_solid_color` class has none
either. Cleanest deck yet on colour. **Still route colour through
`ColorResolver` in the new builder** so deck 10 inherits a correct template.

### Producer / consumer sweep — clean

`--ms`, `--car`, `--ar` are matched in every existing builder.

**Correction worth keeping:** an initial sweep flagged `data-ar` as
"consumer, no producer" in HenHouse (1) and Old Spice (18). **False positive** —
the regex matched `data-arche` / `data-arch`, the archetype attributes. There is
no `data-ar` mismatch anywhere; the HenHouse defect was genuinely fixed.

### Crops / carousels / brochures — none

- No slide has ≥3 crops (no carousel/strip signature).
- No slide has ≥2 full-bleed pictures (no spread signature).
- **All 48 `srcRect` crops are no-ops** — visible fraction exactly 1.0 × 1.0.
- **Zero split signatures**: no asset appears under two different crops.

### `url(data:)` audit — no path exists

**Zero `url(` emissions in any builder's `render.py`.** Checked every CSS
property that can carry one: `background-image`, `background`,
`list-style-image`, `cursor`, `border-image`, `mask`, `mask-image`, `content`,
`src` — all zero.

Only two paths exist pipeline-wide:
1. `ondeck/render/fonts.py::font_face_css()` — `@font-face { src: url(data:…) }`.
   Always present, no element can carry a font, **rule 36 exempts it**.
2. `embed.py`'s crop-half dedupe (`--aN:url(data:…)` in `:root`) — added by the
   *embed* step, not the renderer, and only when `DEDUPE_CROP_HALVES` is on
   **and** crop halves exist.

Deck 9 has no crop halves ⇒ with the flag off, **no path at all**. Verified on
real output: HenHouse and Olay both show `url(data:) in CSS = 2, inside
@font-face = 2, OUTSIDE = 0`.

---

## 3. THE ASPECT FINDING — largest change, easiest to lose

**Slide size is 1224 × 792 pt — aspect 1.5455.** That is **17 × 11 inches,
tabloid landscape** — a print page size. This deck is photoshoot visual boards
laid out for large-format review. **Every previous deck was 960 × 540 (16:9).**

**Decision: build at the true 1224 × 792.** Do not force 16:9 — stretching
distorts and padding recomposes, both break source fidelity. Pillar-boxing on a
16:9 monitor is correct behaviour. **Do not hardcode 1.5455 either** — slide
dimensions are a measured signature, read them from `presentation.xml`
(`p:sldSz`) at build time.

### Where the assumption is baked in — complete audit

**Already correct, reads from the PPTX, NO CHANGE NEEDED:**

| location | what it does |
|---|---|
| `phase_1c/deckkit/model.py:456` | reads `p:sldSz` → `w_pt`/`h_pt` |
| `phase_1c/olay/model.py:351` | same |
| `phase_1c/oldspice/model.py:272` | same |
| all three renderers | `x/W*100`, `y/H*100`, `size_pt/W*100` → cqw — **already aspect-agnostic** |
| `ondeck/render/desktop.py::canvas_aspect_css()` | takes `slide_w_pt, slide_h_pt`, derives both clamps. 16:9 appears **only in the docstring example** |
| `phase_1c/henhouse/render.py:828` | `ratio = W / H` → emitted as `--ratio` |
| `phase_1c/henhouse/render.py:847-848` | `width:min(100vw, calc(100svh * var(--ratio))); aspect-ratio:var(--ratio)` — **already fully general; this is the template to adopt** |

**THE ONLY REAL BAKES — two literals:**

| location | current | change to |
|---|---|---|
| `phase_1c/olay/render.py:316` | `aspect-ratio:16/9;container-type:size` | `aspect-ratio:var(--ratio)` |
| `phase_1c/oldspice/render.py:264` | `aspect-ratio:16/9;container-type:size` | `aspect-ratio:var(--ratio)` |

**Documentation bakes:**

- **`LEARNINGS.md` rule 15** — says *"absolutely-positioned **16:9** canvas"*.
  **The spec is where the assumption actually lives.** Amend to: the deck's own
  aspect, read from `p:sldSz`.
- Docstring headers in all three `render.py` files say "16:9 canvas".

**Benign, review but probably leave:**

- `phase_1c/henhouse/render.py:928` — `aspect-ratio:var(--ar,16/9)`. This is a
  *video* fallback, not the canvas.

**The positioning and type maths were never 16:9-dependent.** The work is:
adopt `--ratio`, fix two literals, amend rule 15.

### Rule 15 also prescribes the scroll defect

While amending rule 15 for aspect, note it **also** prescribes
`scroll-snap-stop: always`. That is not three builders making the same mistake —
**the rule mandates it.** HenHouse and Olay both shipped it and were fixed only
after live review rounds. **Amend rule 15 on both counts** or deck 10 inherits
it again.

---

## 4. Settled decisions

| decision | value |
|---|---|
| **Bitrate** | **5 Mbps.** Deciding factor: the square 1080×1080 clip is the busiest frame — fine type on the bottle labels ("Sheo Butter", "Pro-Vitamin B5") plus water droplets — and 3 Mbps softens it first. These are client ad boards. |
| **Aspect** | Adopt `--ratio` from HenHouse; fix the two `16/9` literals; read dimensions from `presentation.xml`; **never hardcode 1.5455**. Amend rule 15 for aspect **and** for `scroll-snap-stop`. |
| **`DEDUPE_CROP_HALVES`** | **Off.** Audit confirmed no path emits `url(data:)` outside `@font-face` for this deck. |
| **Scroll gate** | Emitted in deck 9's `render.py` **from the first draft, written in not copied**: `#deck{scroll-snap-type:none}` and `section.slide{scroll-snap-stop:normal}` under `@media (max-width:820px)`; desktop keeps `y mandatory` / `always`. |
| **Slug** | **`venus-hestia`** |

### Encode samples measured (libx264, preset medium, bitrate-capped)

| family | source | 5 Mbps | 3 Mbps |
|---|---|---|---|
| square 1080×1080 (4.7 s) | 25.31 MB | **2.89 MB** | 1.70 MB |
| vertical 1080×1920 (8.0 s) | 24.77 MB | **5.20 MB** | 3.06 MB |
| landscape 1920×1080 (8.0 s) | 33.29 MB | **4.88 MB** | 2.81 MB |

Extrapolated across all 53: **~176 MB at 5 Mbps** (vs 845 MB source, ~4.8×).

**Comparison frames are committed at
`phase_1c/fixtures/deck9_encode_samples/`** — three `CMP_<family>.png`
side-by-side strips (SRC | 5Mbps | 3Mbps) plus the nine full-resolution
frames behind them. The full-resolution frames are the ones that support the
decision; the downscaled strips lose the fine label type that separates 3 from
5 Mbps. See the `README.md` in that directory for the source clip ordinals and
the exact ffmpeg commands.

The `.mp4` encodes are deliberately **not** committed (~104 MB including
sources) — regenerate from the README if needed.

### R2 prefix — read the dialog before typing

**Deck Name (folder prefix) = `venus-hestia`.**

The field **is pre-filled and does NOT reset between sessions**, and currently
reads **`olay-v2`** from the last publish. Read it, clear it, type
`venus-hestia`, verify, then upload. This exact field put another client's
packaging on Olay's slides 2–6 for four days.

Must not collide with: `olay`, `olay-v2`, `oldspicepackaging`,
`hh-creativestrategy`, `pgdigital`.

---

## 5. Open — resolve at the start of the next session, BEFORE any video work

### 5a. Does Deck Editor v14 tolerate a `<script>` tag?

**Do not decide this by reasoning about DOMParser.** Test it:

1. Take one existing HenHouse slide.
2. Add an inert `<script>` tag.
3. Run it through a **real editor import**.
4. Report whether the script survives the round-trip, and whether the rest of
   the document is unaffected.

**This gates the IntersectionObserver approach.** All four previous decks ship
zero `<script>`, deliberately, for editor compatibility.

**Proposed strategy if scripts survive** — 53 videos, 40 of them square or
vertical, ~176 MB at 5 Mbps:

- Every `<video>` ships `preload="none"` + a real `poster` frame, **no `autoplay`**.
- `IntersectionObserver` starts playback at ≥50% visible; pauses and resets on exit.
- **Cap concurrent playback at 2–3.** Slides 49–64 carry *three videos each*.
- Reserve the box from `--ar` so nothing collapses while the poster loads.

### 5b. If the editor rejects scripts

**The fallback is NOT lower bitrate.** It is **fewer simultaneous videos per
slide on mobile — a layout decision.** Slides 49–64 carry three videos each.
**Propose that separately** before building.

(The script-free pattern HenHouse used — `preload="none"` + `autoplay muted loop
playsinline` — worked at 7 videos. At 53, three per slide, browser autoplay
deferral is unspecified and varies; do not trust it without the layout change.)

### 5c. Flag at desktop review

**Slides 64 and 65** are the entire content difference from R4 and their
contents are not yet known. Surface them to Sean at desktop review. Do not block
on them.

---

## 6. Do not lose

- **This deck likely cannot use the self-contained embedded artefact.** At 845 MB
  source it is impossible (base64 > 1.1 GB); even at ~176 MB post-transcode it
  inlines to ~235 MB. Plan external media from the start — a departure from all
  four previous decks, and it needs explicit agreement.
- **This is the fourth per-deck `render.py`.** The scroll defect had to be fixed
  independently in two of them because nothing is shared. Lifting the common
  mobile CSS into `deckkit` is cheaper before deck 9 is written than after.
- **Old Spice still carries rule 36's problem** — 3.45 MB of its 3.51 MB
  published file is inline `url(data:)` the editor won't externalise. Flagged in
  NOTES for re-import once the editor is fixed. Unrelated to deck 9.
