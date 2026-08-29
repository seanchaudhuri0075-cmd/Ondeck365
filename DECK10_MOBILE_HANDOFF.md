# Deck 10 (Secret) — mobile handoff

Written 2026-08-28. Every number here is measured from `out/secret/model.json`
and the rendered `out/secret/index.html` at the commits named below. Nothing in
this document is estimated.

**No mobile CSS exists for deck 10 yet.** This handoff is the ground truth to
build it against, not a record of it.

---

## 1. What is on origin

Two commits, both pushed to `origin/main` (`2d677d2..aac6fc3`).

### `91e9d3b` — deck10: carry authored run-fill alpha from parser to CSS

`phase_1c/deckkit/model.py` + `phase_1c/secret/render.py`, 29 insertions / 5
deletions.

`ctx.solid()` returns `(hex, alpha)`. `_runs_of` discarded the alpha half with
`col, _ = ctx.solid(...)`, so every authored `<a:alpha>` on a **run** fill was
lost between the parser and the model, and the run schema had no field to hold
one. Runs now carry `color_alpha` / `declared_color_alpha` — the same pair
shape fills have had since the first builder — and `run_css` sends the colour
through the same `rgba()` helper every other fill in the renderer uses.

The two files are one commit because `render.py` reads `color_alpha`, a key
that only exists after `model.py`'s change. Splitting them would put a broken
commit on `main`.

### `aac6fc3` — deck editor: one predicate for which images are editable

`tools/deck_editor/Deck_Editor_v14.html`, 26 insertions / 7 deletions.
Unrelated to deck 10; committed separately for that reason.

Three call sites disagreed on which `<img>` elements are swappable.
`silentParse` pushed only srcs matching `(r2.dev|http|data:)` but recorded
`index` from the **unfiltered** NodeList; `saveDeck` and `deleteImage` rebuilt
the list filtering only the 252×81 placeholder PNG. On any deck holding a
relative src — every external-media deck, e.g. `assets/img_*.webp` — the lists
differ, so `s.images[i]` and `imgs[i]` are different elements and an edit or a
delete lands on the wrong image. `applySlideToDOM` already used the parse
predicate, so `editableImgs()` makes the other three agree with it rather than
inventing a fourth.

---

## 2. How the alpha fix was verified

Verified against rendered output, not source. `out/secret` could not be trusted
as a baseline — its mtime was one second after the `model.py` edit — so the
deck was built **twice** from the same source `.pptx` tree (31 slides, no
drops):

* **pre-fix** — throwaway git worktree at `d38a1eb`, the commit before the fix
* **post-fix** — current `HEAD`, written to `out/secret`

Both served over HTTP on separate ports with cache-busting query strings, then
measured with `getComputedStyle` in Chrome at 1680×962.

The post-fix build came out byte-identical to the pre-existing
`out/secret/index.html` (709,447 bytes both), so that copy did already contain
the fix.

### The eight runs

Authored XML → model → emitted CSS → computed, all agreeing:

| Slide | Run | Authored `<a:alpha>` | Scheme | Model `color_alpha` | Emitted CSS | Chrome computed |
|--:|:--|--:|:--|--:|:--|:--|
| 3 | `04` | 50000 | dk2 | 0.5 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 3 | `03` | 50000 | dk2 | 0.5 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 3 | `02` | 50000 | dk2 | 0.5 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 3 | `01` | 50211 | dk2 | 0.50211 | `rgba(255,255,255,0.5021)` | `rgba(255, 255, 255, 0.5)` |
| 4 | `01` | 50004 | bg2 | 0.50004 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 9 | `02` | 50004 | bg2 | 0.50004 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 14 | `03` | 50004 | bg2 | 0.50004 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |
| 21 | `04` | 50004 | bg2 | 0.50004 | `rgba(255,255,255,0.5)` | `rgba(255, 255, 255, 0.5)` |

Pre-fix, all eight computed to `rgb(255, 255, 255)` — the deck contained **zero**
translucent text. Post-fix it contains exactly eight, and they are exactly
these. All eight are at their authored alpha.

One caveat on slide 3's `01`. It is authored at 50211 and the pipeline carries
that faithfully to `color:rgba(255,255,255,0.5021)` in the file; Chrome reports
it back as `0.5`. That is the browser, not the pipeline — a synthetic probe
element with a specified `0.5021` also computes to `0.5`, because Chrome
quantises alpha to 8 bits (0.5021 × 255 = 128.035 → 128 → 0.50196). The CSSOM
normalises it identically. The authored value is intact in the output and the
difference is not observable on screen.

`NOTES.md` recorded this defect as affecting the four chapter numerals. The
measurement found **eight** runs — the four agenda numerals on slide 3 carry it
too, at dk2 rather than bg2.

### dk2 and bg2 both resolve to `#FFFFFF`

The four agenda numerals name `dk2`; the four chapter numerals name `bg2`. In
this deck's theme **both tokens resolve to `#FFFFFF`**. All eight numerals are
therefore white at 50%, not a tinted blue, despite naming two different scheme
colours. The measured post-fix palette for the whole deck is four values:

```
rgb(17, 17, 17)   rgb(255, 255, 255)   rgba(255, 255, 255, 0.5)   rgb(0, 32, 96)
```

Do not assume the two tokens are interchangeable elsewhere — they are equal
here, and that is a property of this theme, not of the tokens.

Over the `#A7C6ED` panel on slides 4/9/14/21 the 50% white composites to
`#D3E3F6`. On slide 3 the same 50% white sits over a **photograph**, so it has
no single composited value.

### The unchanged runs are byte-identical

Confirmed three independent ways.

**Declaration census** across the two builds:

```
              #002060   #111   #FFFFFF   rgba(...)
pre-fix          33       1      118         0
post-fix         33       1      110         8
```

151 colour declarations in the deck; 143 unchanged, 8 moved from `#FFFFFF` to
rgba. No other colour shifted value.

**Character-level diff** of the two 709 KB documents:

```
changed regions: 8   (all `replace`, all #FFFFFF -> rgba(...))
  pre[634286] pre[634635] pre[634984] pre[635333]   <- slide 3, four agenda numerals
  pre[642102] pre[659331] pre[672697] pre[689695]   <- slides 4, 9, 14, 21 chapter numerals
total characters touched: 171 of 709,443 (0.0241%)
```

Every changed region is a `replace`. Nothing was inserted, removed or
reordered anywhere in the document, so nothing downstream of those spans
shifted position.

(709,443 is a character count from a text-mode read; 709,447 is the on-disk
byte count. The deck holds 4 multi-byte UTF-8 characters. Both are correct for
what they measure.)

**Computed-style hash** over all 232 text leaves in both builds, covering
background-color, font-size, font-weight, font-family, opacity and text
content — everything except colour:

```
pre-fix   264907a01b78650fbe76916704fee76e449cd915e588548b5a6369ffa2af6882
post-fix  264907a01b78650fbe76916704fee76e449cd915e588548b5a6369ffa2af6882
```

Identical. Same leaf count, same order, no layout or typography movement —
consistent with `rgba()` returning the bare hex when alpha is `None`.

---

## 3. The correct tree for deck 10

Deck 10's build lives entirely in **`phase_1c/`**.

| Path | Role |
|:--|:--|
| `phase_1c/deckkit/model.py` | shared OOXML parser → `model.json`. **Modified by `91e9d3b`.** |
| `phase_1c/secret/render.py` | deck 10's renderer, `model.json` → `index.html`. **Modified by `91e9d3b`.** |
| `phase_1c/secret/roles.py` | deck 10 font stacks, `SLUG = "secret"` |
| `phase_1c/secret/validate.py` | deck 10 validators |
| `phase_1c/deckkit/paths.py` | `DeckPaths`; `out/` resolves to `<repo>/out/<slug>` |
| `phase_1c/deckkit/css.py`, `markup.py`, `assets.py` | shared render helpers |

**`ondeck/render/templates/freeform.py` is the Phase 1B builder and is not part
of this line.** It is the per-deck freeform builder used for deck 6 (Olay) and
the P&G cohort. It has no uncommitted changes and was last modified
2026-08-21 02:16:32, a week before the deck 10 work began. Do not edit it for
deck 10 and do not read it as a model for what deck 10 does — deck 10 renders
through `phase_1c/secret/render.py` against the shared `deckkit` parser, which
is a different architecture.

There is no `deckkit/` at the repo root; it is `phase_1c/deckkit/`. Two other
`model.py` files exist (`phase_1c/olay/model.py`, `phase_1c/oldspice/model.py`)
and are unrelated.

### Build sequence

`render.main()` only reads `model.json` and writes `index.html` — it does not
rebuild the model. The full rebuild is two steps:

1. `phase_1c.deckkit.model.write_model(paths)` → `model.json`, `used_assets.json`
2. `phase_1c.secret.render.build_html(deck, manifest)` → `index.html`

with

```
DeckPaths.for_deck("secret", f"{SCR}/secret/raw", f"{SCR}/secret/shots")
```

`SCR` is hardcoded at `phase_1c/secret/render.py:35` and points at a **prior
session's** scratchpad:

```
/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/be9bf97d-d1ac-4401-9e81-272f6261d537/scratchpad
```

The raw tree still exists there (31 slide XMLs). It is temp storage and will
not survive indefinitely — if it disappears, the `.pptx` must be re-unzipped
and `SCR` repointed. Nothing calls `write_model` from anywhere in the repo;
both steps were driven ad hoc.

---

## 4. Where measurement contradicted the written spec

### 4.1 The divider slides group; slide 3 does not

Measured and confirmed. Canvas is 720 × 405 pt.

Slides **4, 9, 14, 21** share layout `SECTION_TITLE_AND_DESCRIPTION` and are
geometrically identical in their frame:

| Element | x pt | w pt | x% | w% |
|:--|--:|--:|--:|--:|
| `Picture 7` (photo, left) | −15.03 | 375.03 | −2.09 | **52.09** |
| `Google Shape;37;p9` (panel, right, from layout, `#A7C6ED`) | 360.00 | 360.00 | 50.00 | **50.00** |

The photo is **52.09% wide and starts 15.03 pt off-canvas to the left**; the
panel is a clean 50% starting at dead centre. They **overlap by 15.03 pt
(2.09%)** — the photo's right edge lands at 360.00 pt, exactly the panel's left
edge, only because the off-canvas bleed absorbs the excess. The two do not sum
to 100%; they sum to 102.09% with 2.09% falling outside the canvas.

Slide **3** is not in this group. It is layout `CUSTOM`, and its photo is
**full-bleed and overscanned**:

| Element | x pt | y pt | w pt | h pt | w% | h% |
|:--|--:|--:|--:|--:|--:|--:|
| `Picture 2` | 0.00 | −11.25 | 746.00 | 416.25 | **103.61** | **102.78** |

over which sit **four numeral + label pairs in a 2 × 2 grid**, measured at two
column origins (x ≈ 19.83% and x ≈ 52.14%) and two row origins (y ≈ 137.36 pt
and y ≈ 261.49 pt). Slide 3 has 16 shapes; the divider slides have 11–15.

Consequence for mobile: slides 4/9/14/21 can share one stacking rule keyed to
the 52.09/50.00 split, and **slide 3 needs its own** — a full-bleed photo with
a 2 × 2 grid over it does not reduce to a photo-then-panel stack.

### 4.2 The second contradiction is not on record

**I cannot restate this one, because I never derived it.** No shape-inventory
comparison against a written mobile spec was performed in the session that
produced the two commits above, and there is no written deck 10 mobile spec
anywhere in this repo to have compared against — `NOTES.md`, `LEARNINGS.md`,
`DECK9_HANDOFF.md`, `FRAGMENT_NAV_HANDOFF.md`, `PHASE_1C_HANDOFF.md` and
`PHASE_1C_ARCHITECTURE.md` contain no mobile spec for deck 10. The only "52.1"
in the tree is `phase_1c/henhouse/render.py:346`, about a different deck.

Section 4.1 above is stated because it re-measures cleanly from `model.json`
today, not because it was carried forward from earlier work.

Rather than invent a second one, here is a real conflict the inventory
surfaced, **newly measured today** and not previously recorded anywhere:

#### Slide 30 wears the divider layout but is not a divider

Five slides carry `SECTION_TITLE_AND_DESCRIPTION`, not four: **4, 9, 14, 21 and
30.** Slide 30 inherits the identical 50% `#A7C6ED` panel from the layout, so
any rule keyed on layout name will sweep it in. Its geometry says otherwise:

| Slide | photo x% | photo w% | images | `TextBox 5` (chapter numeral) | shapes |
|--:|--:|--:|--:|:--|--:|
| 4 | −2.09 | 52.09 | 1 | present | 14 |
| 9 | −2.09 | 52.09 | 1 | present | 15 |
| 14 | −2.09 | 52.09 | 1 | present | 15 |
| 21 | −2.09 | 52.09 | 1 | present | 11 |
| **30** | **0.00** | **100.00** | **2** | **absent** | 9 |

Slide 30's primary photo is **full-width (720.00 pt, 100%)**, not 52.09%, it
carries a **second** image at 38.90% width, and it has **no chapter numeral** —
which is also why it contributed none of the eight alpha runs. Key the mobile
divider rule on the measured 52.09/50.00 geometry or on the presence of
`TextBox 5`, **not** on `layout_name`, or slide 30 will be stacked as a divider
it is not.

---

## 5. Current state

**Built** — `out/secret/`, rebuilt 2026-08-28 14:09 from `HEAD` (`aac6fc3`):

| File | Bytes | md5 |
|:--|--:|:--|
| `index.html` | 709,447 | `e51ef0568359c5c827b4a1683ff7558a` |
| `model.json` | 241,791 | `f4a09f355bdb07d97a7d090ba057f94d` |
| `used_assets.json` | 1,242 | — |
| `asset_manifest.json` | 16,735 | — (not regenerated; dates 2026-08-27 14:57) |
| `assets/` | 72 files | — |

31 sections, 65 images, 7 videos. `out/` is gitignored — these artifacts are
not in version control.

**Served** — `python3 -m http.server 8917`, serving `out/secret/` at
`http://127.0.0.1:8917/index.html`. Verified HTTP 200, 709,447 bytes. The
pre-fix comparison server that ran on **8918** during verification has been
stopped, and its worktree removed (`git worktree list` shows only the main
checkout).

**Mobile CSS** — none. `grep -c "@media" out/secret/index.html` returns **0**.
The deck has no breakpoint, no stacking rule and no mobile path of any kind.
Everything is the desktop container-query layout in `cqw` units against the
720 × 405 pt canvas.

**Repo** — `main` level with `origin/main` at `aac6fc3`, working tree clean.

### Open items carried from `NOTES.md`

Not addressed by either commit above:

* `Title 3` overflows ~123 pt on slides 4, 9, 14, 21; `EXECUTION` overflows
  ~52 pt on slide 30. Both trace to the Aura AT → Anton substitution. Awaiting
  PowerPoint screenshots; not to be judged against LibreOffice.
* Badge circles vertically misaligned against their labels on the divider
  slides. Spotted, not investigated.
* Images on one slide appear vertically compressed. Slide not yet identified.
* Two boxes overrun the canvas: s21 `Title 3`'s right edge sits exactly on the
  canvas edge; s4 `Subtitle 4` extends 75.7 px past it at 1280. Both predate
  this session.
* PT Sans Narrow 400 ships against a source `b="1"`, so the chapter numerals'
  bold is browser-synthesised. Measured advance is exactly 0.900000 em, so it
  widens nothing — a pure fidelity gap. Fix is to bundle the real bold cut.

---

## 6. Measured shape inventory — all 31 slides

Canvas **720.0 × 405.0 pt**. **211 shapes total**: 124 text, 61 image, 11 rect,
8 line, 7 video. Per-slide counts, slides 1→31:

```
8, 4, 16, 14, 9, 6, 9, 6, 15, 2, 7, 3, 4, 15, 8,
2, 4, 6, 6, 8, 11, 4, 2, 4, 4, 6, 3, 4, 5, 9, 7
```

Layouts: `BLANK`/blank ×19, `SECTION_TITLE_AND_DESCRIPTION` ×5,
`SECTION_HEADER`/secHead ×4, `TITLE`/title ×2, `CUSTOM` ×1.

`src` is `layout` where the shape is inherited from the slide layout and
`slide` where it is authored on the slide. Percentages are of the 720 × 405 pt
canvas. `runs` is the count of text runs in the shape.

### Slide 1  ·  `slide1.xml`

layout `TITLE` · layout_type `title` · bg `#A7C6ED` (from `slide`) · bg_image no · **8 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | text | `Google Shape;133;p29` | 196.66 | 278.28 | 314.27 | 37.46 | 27.31 | 68.71 | 43.65 | 9.25 | 0 | slide | — | 1 | KEY VISUALS |
| 1 | line | `Google Shape;134;p29` | 193.57 | 306.11 | 49.13 | 0.00 | 26.88 | 75.58 | 6.82 | 0.00 | 1 | slide | — | 0 |  |
| 2 | line | `Google Shape;135;p29` | 464.88 | 306.11 | 49.13 | 0.00 | 64.57 | 75.58 | 6.82 | 0.00 | 2 | slide | — | 0 |  |
| 3 | rect | `Google Shape;12;p2` | -0.00 | 0.04 | 720.00 | 281.41 | -0.00 | 0.01 | 100.00 | 69.48 | 3 | slide | — | 0 |  |
| 4 | text | `Google Shape;131;p29` | 356.51 | 130.03 | 309.11 | 133.01 | 49.51 | 32.11 | 42.93 | 32.84 | 4 | slide | — | 1 | BEAUTY |
| 5 | image | `Picture 1` | 70.89 | 91.94 | 352.37 | 182.52 | 9.85 | 22.70 | 48.94 | 45.07 | 5 | slide | — | 0 |  |
| 6 | image | `Picture 2` | 1102.49 | 13.80 | 111.39 | 40.87 | 153.12 | 3.41 | 15.47 | 10.09 | 6 | slide | — | 0 |  |
| 7 | image | `Picture 3` | 649.01 | 7.71 | 66.20 | 24.29 | 90.14 | 1.90 | 9.19 | 6.00 | 7 | slide | — | 0 |  |

### Slide 2  ·  `slide2.xml`

layout `SECTION_HEADER` · layout_type `secHead` · bg `#A7C6ED` (from `layout`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;16;p3` | 0.00 | 79.71 | 720.00 | 325.25 | 0.00 | 19.68 | 100.00 | 80.31 | 2 | layout | — | 0 |  |
| 1 | image | `Picture 4` | 0.00 | 0.00 | 722.36 | 246.62 | 0.00 | 0.00 | 100.33 | 60.89 | 0 | slide | — | 0 |  |
| 2 | text | `Title 1` | 105.88 | 258.97 | 508.24 | 91.95 | 14.71 | 63.94 | 70.59 | 22.70 | 1 | slide | — | 1 | OBJECTIVE |
| 3 | text | `Subtitle 2` | 156.52 | 336.03 | 406.97 | 56.17 | 21.74 | 82.97 | 56.52 | 13.87 | 2 | slide | — | 1 | Explore possibilities to transform the curre |

### Slide 3  ·  `slide3.xml`

layout `CUSTOM` · layout_type `None` · bg `#A7C6ED` (from `slide`) · bg_image no · **16 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 0.00 | -11.25 | 746.00 | 416.25 | 0.00 | -2.78 | 103.61 | 102.78 | 0 | slide | — | 0 |  |
| 1 | text | `Google Shape;148;p31` | 375.39 | 261.49 | 91.63 | 53.32 | 52.14 | 64.57 | 12.73 | 13.16 | 1 | slide | — | 1 | 04 |
| 2 | text | `Google Shape;149;p31` | 142.78 | 261.49 | 94.60 | 53.32 | 19.83 | 64.57 | 13.14 | 13.16 | 2 | slide | — | 1 | 03 |
| 3 | text | `Google Shape;150;p31` | 373.90 | 137.36 | 93.50 | 53.32 | 51.93 | 33.92 | 12.99 | 13.16 | 3 | slide | — | 1 | 02 |
| 4 | text | `Google Shape;151;p31` | 142.78 | 137.36 | 79.68 | 53.32 | 19.83 | 33.92 | 11.07 | 13.16 | 4 | slide | — | 1 | 01 |
| 5 | text | `Google Shape;152;p31` | 200.69 | 50.48 | 318.64 | 63.73 | 27.87 | 12.46 | 44.26 | 15.74 | 5 | slide | — | 1 | VISUAL HOOKS |
| 6 | text | `Google Shape;153;p31` | 167.49 | 194.65 | 182.55 | 51.28 | 23.26 | 48.06 | 25.35 | 12.66 | 6 | slide | — | 1 | Single product spotlight and how it interact |
| 7 | text | `Google Shape;154;p31` | 392.21 | 151.80 | 183.66 | 37.54 | 54.47 | 37.48 | 25.51 | 9.27 | 7 | slide | — | 1 | GROUP SHOTS |
| 8 | text | `Google Shape;155;p31` | 388.02 | 194.65 | 206.40 | 51.28 | 53.89 | 48.06 | 28.67 | 12.66 | 8 | slide | — | 1 | Product variants or combo pack shots that ex |
| 9 | text | `Google Shape;156;p31` | 166.93 | 275.99 | 183.66 | 37.54 | 23.18 | 68.15 | 25.51 | 9.27 | 9 | slide | — | 1 | INGREDIENT LED |
| 10 | text | `Google Shape;157;p31` | 393.41 | 275.99 | 182.55 | 37.54 | 54.64 | 68.15 | 25.35 | 9.27 | 10 | slide | — | 1 | COLOR + TREATMENT |
| 11 | text | `Google Shape;158;p31` | 166.93 | 319.08 | 183.66 | 51.28 | 23.18 | 78.79 | 25.51 | 12.66 | 11 | slide | — | 1 | Scent notes and cues composites that complem |
| 12 | text | `Google Shape;159;p31` | 394.51 | 319.08 | 182.55 | 51.28 | 54.79 | 78.79 | 25.35 | 12.66 | 12 | slide | — | 1 | Lighting, tones, caustics, hues and overall  |
| 13 | text | `Google Shape;160;p31` | 168.54 | 151.79 | 180.45 | 37.54 | 23.41 | 37.48 | 25.06 | 9.27 | 13 | slide | — | 1 | PRODUCT SILOS |
| 14 | line | `Google Shape;161;p31` | 557.58 | 70.84 | 49.13 | 0.00 | 77.44 | 17.49 | 6.82 | 0.00 | 14 | slide | — | 0 |  |
| 15 | line | `Google Shape;162;p31` | 119.30 | 70.84 | 49.13 | 0.00 | 16.57 | 17.49 | 6.82 | 0.00 | 15 | slide | — | 0 |  |

### Slide 4  ·  `slide4.xml`

layout `SECTION_TITLE_AND_DESCRIPTION` · layout_type `None` · bg `—` (from `none`) · bg_image no · **14 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;37;p9` | 360.00 | -0.01 | 360.00 | 405.00 | 50.00 | -0.00 | 50.00 | 100.00 | 0 | layout | #A7C6ED | 0 |  |
| 1 | text | `Title 3` | 395.80 | 109.32 | 288.43 | 68.46 | 54.97 | 26.99 | 40.06 | 16.90 | 0 | slide | — | 1 | PRODUCT SILOS |
| 2 | text | `Subtitle 4` | 474.18 | 196.89 | 288.43 | 181.15 | 65.86 | 48.61 | 40.06 | 44.73 | 1 | slide | — | 8 | Extreme closeups / Mid range camera shots /  |
| 3 | text | `TextBox 5` | 514.82 | 9.28 | 50.39 | 55.74 | 71.50 | 2.29 | 7.00 | 13.76 | 2 | slide | — | 1 | 01 |
| 4 | image | `Picture 7` | -15.03 | 0.00 | 375.03 | 405.00 | -2.09 | 0.00 | 52.09 | 100.00 | 3 | slide | — | 0 |  |
| 5 | text | `Oval 9` | 467.48 | 210.85 | 16.74 | 16.74 | 64.93 | 52.06 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | A |
| 6 | text | `Oval 10` | 467.48 | 232.71 | 16.74 | 16.74 | 64.93 | 57.46 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | B |
| 7 | text | `Oval 11` | 467.48 | 254.57 | 16.74 | 16.74 | 64.93 | 62.86 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | C |
| 8 | text | `Oval 12` | 467.48 | 276.44 | 16.74 | 16.74 | 64.93 | 68.26 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | D |
| 9 | text | `Oval 13` | 467.48 | 298.30 | 16.74 | 16.74 | 64.93 | 73.65 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | E |
| 10 | text | `Oval 14` | 467.48 | 320.16 | 16.74 | 16.74 | 64.93 | 79.05 | 2.33 | 4.13 | 9 | slide | #1665BA | 1 | F |
| 11 | text | `Oval 15` | 467.48 | 342.02 | 16.74 | 16.74 | 64.93 | 84.45 | 2.33 | 4.13 | 10 | slide | #1665BA | 1 | G |
| 12 | text | `Oval 16` | 467.48 | 363.89 | 16.74 | 16.74 | 64.93 | 89.85 | 2.33 | 4.13 | 11 | slide | #1665BA | 1 | H |
| 13 | text | `Oval 17` | 13.32 | 24.28 | 16.74 | 16.74 | 1.85 | 5.99 | 2.33 | 4.13 | 12 | slide | #1665BA | 1 | A |

### Slide 5  ·  `slide5.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **9 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 10` | 11.62 | 9.83 | 224.98 | 385.33 | 1.61 | 2.43 | 31.25 | 95.14 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 8` | 247.82 | 9.83 | 224.27 | 385.33 | 34.42 | 2.43 | 31.15 | 95.14 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 483.27 | 9.83 | 225.76 | 186.65 | 67.12 | 2.43 | 31.36 | 46.09 | 2 | slide | — | 0 |  |
| 3 | image | `Picture 6` | 483.27 | 207.09 | 225.76 | 188.07 | 67.12 | 51.13 | 31.36 | 46.44 | 3 | slide | — | 0 |  |
| 4 | text | `Oval 2` | 493.48 | 23.57 | 16.74 | 16.74 | 68.54 | 5.82 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | C |
| 5 | text | `Oval 3` | 679.48 | 225.44 | 16.74 | 16.74 | 94.37 | 55.66 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | D |
| 6 | text | `Oval 5` | 258.48 | 21.30 | 16.74 | 16.74 | 35.90 | 5.26 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | E |
| 7 | text | `Oval 7` | 203.48 | 367.89 | 16.74 | 16.74 | 28.26 | 90.84 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | E |
| 8 | text | `Oval 9` | 181.48 | 367.89 | 16.74 | 16.74 | 25.21 | 90.84 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | H |

### Slide 6  ·  `slide6.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **6 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 6` | 11.37 | 10.14 | 224.01 | 384.72 | 1.58 | 2.50 | 31.11 | 94.99 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 2` | 247.12 | 10.14 | 225.76 | 384.72 | 34.32 | 2.50 | 31.36 | 94.99 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 483.55 | 10.14 | 224.35 | 384.72 | 67.16 | 2.50 | 31.16 | 94.99 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 199.48 | 362.71 | 16.74 | 16.74 | 27.71 | 89.56 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | B |
| 4 | text | `Oval 3` | 446.48 | 20.44 | 16.74 | 16.74 | 62.01 | 5.05 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | D |
| 5 | text | `Oval 5` | 678.32 | 24.28 | 16.74 | 16.74 | 94.21 | 5.99 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | A |

### Slide 7  ·  `slide7.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **9 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 11.62 | 9.83 | 224.98 | 385.33 | 1.61 | 2.43 | 31.25 | 95.14 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 8` | 247.82 | 9.83 | 224.27 | 385.33 | 34.42 | 2.43 | 31.15 | 95.14 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 483.27 | 9.83 | 225.76 | 186.65 | 67.12 | 2.43 | 31.36 | 46.09 | 2 | slide | — | 0 |  |
| 3 | image | `Picture 6` | 483.27 | 207.09 | 225.76 | 188.07 | 67.12 | 51.13 | 31.36 | 46.44 | 3 | slide | — | 0 |  |
| 4 | text | `Oval 1` | 495.32 | 370.44 | 16.74 | 16.74 | 68.79 | 91.47 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | A |
| 5 | text | `Oval 3` | 515.48 | 370.44 | 16.74 | 16.74 | 71.59 | 91.47 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | D |
| 6 | text | `Oval 7` | 492.48 | 23.57 | 16.74 | 16.74 | 68.40 | 5.82 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | C |
| 7 | text | `Oval 9` | 260.48 | 370.16 | 16.74 | 16.74 | 36.18 | 91.40 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | F |
| 8 | text | `Oval 10` | 25.48 | 363.89 | 16.74 | 16.74 | 3.54 | 89.85 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | H |

### Slide 8  ·  `slide8.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **6 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 6` | 11.37 | 10.14 | 224.01 | 384.72 | 1.58 | 2.50 | 31.11 | 94.99 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 4` | 247.12 | 10.14 | 225.76 | 384.72 | 34.32 | 2.50 | 31.36 | 94.99 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 2` | 483.55 | 10.14 | 224.35 | 384.72 | 67.16 | 2.50 | 31.16 | 94.99 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 446.48 | 365.57 | 16.74 | 16.74 | 62.01 | 90.27 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | C |
| 4 | text | `Oval 3` | 207.48 | 15.16 | 16.74 | 16.74 | 28.82 | 3.74 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | F |
| 5 | text | `Oval 5` | 680.48 | 366.89 | 16.74 | 16.74 | 94.51 | 90.59 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | H |

### Slide 9  ·  `slide9.xml`

layout `SECTION_TITLE_AND_DESCRIPTION` · layout_type `None` · bg `—` (from `none`) · bg_image no · **15 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;37;p9` | 360.00 | -0.01 | 360.00 | 405.00 | 50.00 | -0.00 | 50.00 | 100.00 | 0 | layout | #A7C6ED | 0 |  |
| 1 | text | `Title 3` | 395.80 | 109.32 | 288.43 | 68.46 | 54.97 | 26.99 | 40.06 | 16.90 | 0 | slide | — | 1 | GROUP SHOTS |
| 2 | text | `Subtitle 4` | 474.18 | 196.89 | 288.43 | 181.15 | 65.86 | 48.61 | 40.06 | 44.73 | 1 | slide | — | 8 | Extreme closeups / Mid range camera shots /  |
| 3 | text | `TextBox 5` | 514.82 | 9.28 | 50.39 | 55.74 | 71.50 | 2.29 | 7.00 | 13.76 | 2 | slide | — | 1 | 02 |
| 4 | image | `Picture 7` | -15.03 | 0.00 | 375.03 | 405.00 | -2.09 | 0.00 | 52.09 | 100.00 | 3 | slide | — | 0 |  |
| 5 | text | `Oval 9` | 467.48 | 210.85 | 16.74 | 16.74 | 64.93 | 52.06 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | A |
| 6 | text | `Oval 10` | 467.48 | 232.71 | 16.74 | 16.74 | 64.93 | 57.46 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | B |
| 7 | text | `Oval 11` | 467.48 | 254.57 | 16.74 | 16.74 | 64.93 | 62.86 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | C |
| 8 | text | `Oval 12` | 467.48 | 276.44 | 16.74 | 16.74 | 64.93 | 68.26 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | D |
| 9 | text | `Oval 13` | 467.48 | 298.30 | 16.74 | 16.74 | 64.93 | 73.65 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | E |
| 10 | text | `Oval 14` | 467.48 | 320.16 | 16.74 | 16.74 | 64.93 | 79.05 | 2.33 | 4.13 | 9 | slide | #1665BA | 1 | F |
| 11 | text | `Oval 15` | 467.48 | 342.02 | 16.74 | 16.74 | 64.93 | 84.45 | 2.33 | 4.13 | 10 | slide | #1665BA | 1 | G |
| 12 | text | `Oval 16` | 467.48 | 363.89 | 16.74 | 16.74 | 64.93 | 89.85 | 2.33 | 4.13 | 11 | slide | #1665BA | 1 | H |
| 13 | text | `Oval 17` | 13.32 | 24.57 | 16.74 | 16.74 | 1.85 | 6.07 | 2.33 | 4.13 | 12 | slide | #1665BA | 1 | B |
| 14 | text | `Oval 1` | 33.48 | 24.57 | 16.74 | 16.74 | 4.65 | 6.07 | 2.33 | 4.13 | 13 | slide | #1665BA | 1 | C |

### Slide 10  ·  `slide10.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **2 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 11.63 | 10.25 | 696.75 | 384.61 | 1.61 | 2.53 | 96.77 | 94.97 | 0 | slide | — | 0 |  |
| 1 | text | `Oval 1` | 467.48 | 63.16 | 16.74 | 16.74 | 64.93 | 15.60 | 2.33 | 4.13 | 1 | slide | #1665BA | 1 | F |

### Slide 11  ·  `slide11.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **7 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 3` | 11.28 | 10.14 | 343.30 | 361.95 | 1.57 | 2.50 | 47.68 | 89.37 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 5` | 365.96 | 10.14 | 342.76 | 187.29 | 50.83 | 2.50 | 47.60 | 46.24 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 7` | 365.96 | 207.57 | 341.72 | 164.52 | 50.83 | 51.25 | 47.46 | 40.62 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 23.48 | 26.71 | 16.74 | 16.74 | 3.26 | 6.60 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | B |
| 4 | text | `Oval 2` | 673.48 | 27.57 | 16.74 | 16.74 | 93.54 | 6.81 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | C |
| 5 | text | `Oval 4` | 390.15 | 224.83 | 16.74 | 16.74 | 54.19 | 55.51 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | F |
| 6 | text | `Oval 6` | 467.48 | 342.02 | 16.74 | 16.74 | 64.93 | 84.45 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | G |

### Slide 12  ·  `slide12.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **3 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 10.65 | 9.54 | 698.45 | 385.87 | 1.48 | 2.35 | 97.01 | 95.28 | 0 | slide | — | 0 |  |
| 1 | text | `Oval 1` | 648.22 | 215.54 | 16.74 | 16.74 | 90.03 | 53.22 | 2.33 | 4.13 | 1 | slide | #1665BA | 1 | A |
| 2 | text | `Oval 3` | 676.73 | 215.54 | 16.74 | 16.74 | 93.99 | 53.22 | 2.33 | 4.13 | 2 | slide | #1665BA | 1 | F |

### Slide 13  ·  `slide13.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 11.51 | 10.25 | 460.82 | 384.61 | 1.60 | 2.53 | 64.00 | 94.97 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 4` | 483.40 | 10.03 | 224.86 | 384.82 | 67.14 | 2.48 | 31.23 | 95.02 | 1 | slide | — | 0 |  |
| 2 | text | `Oval 1` | 437.11 | 353.42 | 16.74 | 16.74 | 60.71 | 87.27 | 2.33 | 4.13 | 2 | slide | #1665BA | 1 | E |
| 3 | text | `Oval 3` | 496.73 | 86.46 | 16.74 | 16.74 | 68.99 | 21.35 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | B |

### Slide 14  ·  `slide14.xml`

layout `SECTION_TITLE_AND_DESCRIPTION` · layout_type `None` · bg `—` (from `none`) · bg_image no · **15 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;37;p9` | 360.00 | -0.01 | 360.00 | 405.00 | 50.00 | -0.00 | 50.00 | 100.00 | 0 | layout | #A7C6ED | 0 |  |
| 1 | text | `Title 3` | 360.00 | 109.32 | 360.00 | 68.46 | 50.00 | 26.99 | 50.00 | 16.90 | 0 | slide | — | 2 | INGREDIENT / LED |
| 2 | text | `Subtitle 4` | 494.43 | 196.89 | 288.43 | 181.15 | 68.67 | 48.61 | 40.06 | 44.73 | 1 | slide | — | 8 | Extreme closeups / Mid range camera shots /  |
| 3 | text | `TextBox 5` | 514.82 | 9.28 | 50.39 | 55.74 | 71.50 | 2.29 | 7.00 | 13.76 | 2 | slide | — | 1 | 03 |
| 4 | image | `Picture 7` | -15.03 | 0.00 | 375.03 | 405.00 | -2.09 | 0.00 | 52.09 | 100.00 | 3 | slide | — | 0 |  |
| 5 | text | `Oval 9` | 487.73 | 210.85 | 16.74 | 16.74 | 67.74 | 52.06 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | A |
| 6 | text | `Oval 10` | 487.73 | 232.71 | 16.74 | 16.74 | 67.74 | 57.46 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | B |
| 7 | text | `Oval 11` | 487.73 | 254.57 | 16.74 | 16.74 | 67.74 | 62.86 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | C |
| 8 | text | `Oval 12` | 487.73 | 276.44 | 16.74 | 16.74 | 67.74 | 68.26 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | D |
| 9 | text | `Oval 13` | 487.73 | 298.30 | 16.74 | 16.74 | 67.74 | 73.65 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | E |
| 10 | text | `Oval 14` | 487.73 | 320.16 | 16.74 | 16.74 | 67.74 | 79.05 | 2.33 | 4.13 | 9 | slide | #1665BA | 1 | F |
| 11 | text | `Oval 15` | 487.73 | 342.02 | 16.74 | 16.74 | 67.74 | 84.45 | 2.33 | 4.13 | 10 | slide | #1665BA | 1 | G |
| 12 | text | `Oval 16` | 487.73 | 363.89 | 16.74 | 16.74 | 67.74 | 89.85 | 2.33 | 4.13 | 11 | slide | #1665BA | 1 | H |
| 13 | text | `Oval 17` | 13.32 | 24.57 | 16.74 | 16.74 | 1.85 | 6.07 | 2.33 | 4.13 | 12 | slide | #1665BA | 1 | B |
| 14 | text | `Oval 1` | 33.48 | 24.57 | 16.74 | 16.74 | 4.65 | 6.07 | 2.33 | 4.13 | 13 | slide | #1665BA | 1 | C |

### Slide 15  ·  `slide15.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **8 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 6` | 11.37 | 10.14 | 224.01 | 384.72 | 1.58 | 2.50 | 31.11 | 94.99 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 2` | 247.12 | 10.14 | 225.76 | 384.72 | 34.32 | 2.50 | 31.36 | 94.99 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 483.55 | 10.14 | 224.35 | 384.72 | 67.16 | 2.50 | 31.16 | 94.99 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 32.11 | 35.05 | 16.74 | 16.74 | 4.46 | 8.65 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | E |
| 4 | text | `Oval 3` | 52.36 | 35.05 | 16.74 | 16.74 | 7.27 | 8.65 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | G |
| 5 | text | `Oval 5` | 435.98 | 350.84 | 16.74 | 16.74 | 60.55 | 86.63 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | B |
| 6 | text | `Oval 7` | 675.61 | 122.95 | 16.74 | 16.74 | 93.83 | 30.36 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | C |
| 7 | text | `Oval 8` | 411.23 | 350.84 | 16.74 | 16.74 | 57.12 | 86.63 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | D |

### Slide 16  ·  `slide16.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **2 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 11.63 | 10.25 | 696.75 | 384.61 | 1.61 | 2.53 | 96.77 | 94.97 | 0 | slide | — | 0 |  |
| 1 | text | `Oval 1` | 675.61 | 362.57 | 16.74 | 16.74 | 93.83 | 89.52 | 2.33 | 4.13 | 1 | slide | #1665BA | 1 | C |

### Slide 17  ·  `slide17.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 4` | 11.07 | 10.04 | 224.74 | 384.82 | 1.54 | 2.48 | 31.21 | 95.02 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 2` | 246.80 | 10.04 | 462.13 | 384.82 | 34.28 | 2.48 | 64.18 | 95.02 | 1 | slide | — | 0 |  |
| 2 | text | `Oval 1` | 206.48 | 365.95 | 16.74 | 16.74 | 28.68 | 90.36 | 2.33 | 4.13 | 2 | slide | #1665BA | 1 | C |
| 3 | text | `Oval 3` | 678.98 | 365.80 | 16.74 | 16.74 | 94.30 | 90.32 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | E |

### Slide 18  ·  `slide18.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **6 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 6` | 11.37 | 10.14 | 224.01 | 384.72 | 1.58 | 2.50 | 31.11 | 94.99 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 4` | 247.12 | 10.14 | 225.76 | 384.72 | 34.32 | 2.50 | 31.36 | 94.99 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 2` | 483.55 | 10.14 | 224.35 | 384.72 | 67.16 | 2.50 | 31.16 | 94.99 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 25.36 | 306.32 | 16.74 | 16.74 | 3.52 | 75.64 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | C |
| 4 | text | `Oval 3` | 25.36 | 335.11 | 16.74 | 16.74 | 3.52 | 82.74 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | G |
| 5 | text | `Oval 5` | 25.36 | 363.89 | 16.74 | 16.74 | 3.52 | 89.85 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | H |

### Slide 19  ·  `slide19.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **6 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 11.37 | 10.14 | 224.01 | 384.72 | 1.58 | 2.50 | 31.11 | 94.99 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 6` | 247.12 | 10.14 | 225.76 | 384.72 | 34.32 | 2.50 | 31.36 | 94.99 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 483.55 | 10.14 | 224.35 | 384.72 | 67.16 | 2.50 | 31.16 | 94.99 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 1` | 25.36 | 306.32 | 16.74 | 16.74 | 3.52 | 75.64 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | C |
| 4 | text | `Oval 3` | 25.36 | 335.11 | 16.74 | 16.74 | 3.52 | 82.74 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | G |
| 5 | text | `Oval 5` | 25.36 | 363.89 | 16.74 | 16.74 | 3.52 | 89.85 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | H |

### Slide 20  ·  `slide20.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **8 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 4` | 11.62 | 9.83 | 224.98 | 385.33 | 1.61 | 2.43 | 31.25 | 95.14 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 2` | 247.82 | 9.83 | 224.27 | 385.33 | 34.42 | 2.43 | 31.15 | 95.14 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 8` | 483.27 | 9.83 | 225.76 | 186.65 | 67.12 | 2.43 | 31.36 | 46.09 | 2 | slide | — | 0 |  |
| 3 | image | `Picture 6` | 483.27 | 207.09 | 225.76 | 188.07 | 67.12 | 51.13 | 31.36 | 46.44 | 3 | slide | — | 0 |  |
| 4 | text | `Oval 1` | 25.36 | 302.49 | 16.74 | 16.74 | 3.52 | 74.69 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | C |
| 5 | text | `Oval 3` | 25.36 | 333.19 | 16.74 | 16.74 | 3.52 | 82.27 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | G |
| 6 | text | `Oval 5` | 25.36 | 363.89 | 16.74 | 16.74 | 3.52 | 89.85 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | H |
| 7 | text | `Oval 7` | 25.36 | 271.79 | 16.74 | 16.74 | 3.52 | 67.11 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | F |

### Slide 21  ·  `slide21.xml`

layout `SECTION_TITLE_AND_DESCRIPTION` · layout_type `None` · bg `—` (from `none`) · bg_image no · **11 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;37;p9` | 360.00 | -0.01 | 360.00 | 405.00 | 50.00 | -0.00 | 50.00 | 100.00 | 0 | layout | #A7C6ED | 0 |  |
| 1 | text | `Title 3` | 360.00 | 109.32 | 360.00 | 68.46 | 50.00 | 26.99 | 50.00 | 16.90 | 0 | slide | — | 2 | COLOR+ / TREATMENT |
| 2 | text | `TextBox 5` | 514.82 | 9.28 | 50.39 | 55.74 | 71.50 | 2.29 | 7.00 | 13.76 | 1 | slide | — | 1 | 04 |
| 3 | image | `Picture 7` | -15.03 | 0.00 | 375.03 | 405.00 | -2.09 | 0.00 | 52.09 | 100.00 | 2 | slide | — | 0 |  |
| 4 | text | `Subtitle 4` | 450.91 | 202.50 | 127.97 | 181.15 | 62.63 | 50.00 | 17.77 | 44.73 | 3 | slide | — | 5 | Standard Palette / Monochromatic / Multi-col |
| 5 | text | `Oval 18` | 439.36 | 218.09 | 16.74 | 16.74 | 61.02 | 53.85 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | 1 |
| 6 | text | `Oval 19` | 439.36 | 248.06 | 16.74 | 16.74 | 61.02 | 61.25 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | 2 |
| 7 | text | `Oval 20` | 439.36 | 278.02 | 16.74 | 16.74 | 61.02 | 68.65 | 2.33 | 4.13 | 6 | slide | #1665BA | 1 | 3 |
| 8 | text | `Oval 21` | 439.36 | 307.98 | 16.74 | 16.74 | 61.02 | 76.04 | 2.33 | 4.13 | 7 | slide | #1665BA | 1 | 4 |
| 9 | text | `Oval 22` | 439.36 | 337.94 | 16.74 | 16.74 | 61.02 | 83.44 | 2.33 | 4.13 | 8 | slide | #1665BA | 1 | 5 |
| 10 | text | `Oval 23` | 2.36 | 155.02 | 16.74 | 16.74 | 0.33 | 38.28 | 2.33 | 4.13 | 9 | slide | #1665BA | 1 | 3 |

### Slide 22  ·  `slide22.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 0.00 | 0.00 | 342.33 | 405.00 | 0.00 | 0.00 | 47.55 | 100.00 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 4` | 342.33 | 0.00 | 377.67 | 405.00 | 47.55 | 0.00 | 52.45 | 100.00 | 1 | slide | — | 0 |  |
| 2 | text | `Oval 6` | 13.36 | 48.09 | 16.74 | 16.74 | 1.86 | 11.87 | 2.33 | 4.13 | 2 | slide | #1665BA | 1 | 1 |
| 3 | text | `Oval 7` | 677.36 | 21.94 | 16.74 | 16.74 | 94.08 | 5.42 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | 5 |

### Slide 23  ·  `slide23.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **2 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 4` | 0.00 | 0.00 | 720.00 | 405.00 | 0.00 | 0.00 | 100.00 | 100.00 | 0 | slide | — | 0 |  |
| 1 | text | `Oval 5` | 680.36 | 366.06 | 16.74 | 16.74 | 94.49 | 90.38 | 2.33 | 4.13 | 1 | slide | #1665BA | 1 | 2 |

### Slide 24  ·  `slide24.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 0.00 | 0.00 | 227.89 | 405.00 | 0.00 | 0.00 | 31.65 | 100.00 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 6` | 385.88 | 0.00 | 353.25 | 405.00 | 53.59 | 0.00 | 49.06 | 100.00 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 4` | 215.30 | 0.00 | 289.40 | 405.00 | 29.90 | 0.00 | 40.19 | 100.00 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 7` | 680.36 | 366.06 | 16.74 | 16.74 | 94.49 | 90.38 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | 2 |

### Slide 25  ·  `slide25.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 2` | 0.00 | 0.00 | 304.59 | 405.00 | 0.00 | 0.00 | 42.30 | 100.00 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 4` | 304.59 | -4.50 | 415.41 | 415.41 | 42.30 | -1.11 | 57.70 | 102.57 | 1 | slide | — | 0 |  |
| 2 | text | `Oval 5` | 685.36 | 337.94 | 16.74 | 16.74 | 95.19 | 83.44 | 2.33 | 4.13 | 2 | slide | #1665BA | 1 | 5 |
| 3 | text | `Oval 6` | 19.36 | 16.06 | 16.74 | 16.74 | 2.69 | 3.96 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | 2 |

### Slide 26  ·  `slide26.xml`

layout `BLANK` · layout_type `blank` · bg `—` (from `none`) · bg_image no · **6 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | image | `Picture 4` | 220.01 | 0.00 | 405.23 | 405.00 | 30.56 | 0.00 | 56.28 | 100.00 | 0 | slide | — | 0 |  |
| 1 | image | `Picture 2` | 0.00 | 0.00 | 227.89 | 405.00 | 0.00 | 0.00 | 31.65 | 100.00 | 1 | slide | — | 0 |  |
| 2 | image | `Picture 6` | 519.81 | 0.00 | 200.19 | 405.00 | 72.20 | 0.00 | 27.80 | 100.00 | 2 | slide | — | 0 |  |
| 3 | text | `Oval 7` | 20.36 | 16.98 | 16.74 | 16.74 | 2.83 | 4.19 | 2.33 | 4.13 | 3 | slide | #1665BA | 1 | 4 |
| 4 | text | `Oval 8` | 247.36 | 238.02 | 16.74 | 16.74 | 34.36 | 58.77 | 2.33 | 4.13 | 4 | slide | #1665BA | 1 | 3 |
| 5 | text | `Oval 9` | 688.36 | 16.09 | 16.74 | 16.74 | 95.61 | 3.97 | 2.33 | 4.13 | 5 | slide | #1665BA | 1 | 1 |

### Slide 27  ·  `slide27.xml`

layout `SECTION_HEADER` · layout_type `secHead` · bg `#A7C6ED` (from `layout`) · bg_image no · **3 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;16;p3` | 0.00 | 79.71 | 720.00 | 325.25 | 0.00 | 19.68 | 100.00 | 80.31 | 2 | layout | — | 0 |  |
| 1 | text | `Title 1` | 105.88 | 147.97 | 508.24 | 91.95 | 14.71 | 36.54 | 70.59 | 22.70 | 0 | slide | — | 1 | VIDEOS |
| 2 | text | `Subtitle 2` | 156.52 | 225.03 | 406.97 | 56.17 | 21.74 | 55.56 | 56.52 | 13.87 | 1 | slide | — | 1 | References for animation styles, techniques  |

### Slide 28  ·  `slide28.xml`

layout `SECTION_HEADER` · layout_type `secHead` · bg `#A7C6ED` (from `layout`) · bg_image no · **4 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;16;p3` | 0.00 | 79.71 | 720.00 | 325.25 | 0.00 | 19.68 | 100.00 | 80.31 | 2 | layout | — | 0 |  |
| 1 | video | `From studio-like shots to bo` | 11.37 | 44.44 | 178.57 | 317.37 | 1.58 | 10.97 | 24.80 | 78.36 | 0 | slide | — | 0 |  |
| 2 | video | `LM_2024_FY25_Renewal_Oil_PDP` | 196.20 | 44.44 | 253.90 | 317.37 | 27.25 | 10.97 | 35.26 | 78.36 | 1 | slide | — | 0 |  |
| 3 | video | `LM_2025_FY26_AdHoc_Moisture_` | 456.74 | 44.44 | 253.90 | 317.37 | 63.44 | 10.97 | 35.26 | 78.36 | 2 | slide | — | 0 |  |

### Slide 29  ·  `slide29.xml`

layout `SECTION_HEADER` · layout_type `secHead` · bg `#A7C6ED` (from `layout`) · bg_image no · **5 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;16;p3` | 0.00 | 79.71 | 720.00 | 325.25 | 0.00 | 19.68 | 100.00 | 80.31 | 2 | layout | — | 0 |  |
| 1 | video | `PinDown.io_@clarinsespana_17` | 9.03 | 52.01 | 169.35 | 300.99 | 1.25 | 12.84 | 23.52 | 74.32 | 0 | slide | — | 0 |  |
| 2 | video | `PinDown.io_@dermstore_176174` | 185.24 | 52.01 | 169.35 | 300.99 | 25.73 | 12.84 | 23.52 | 74.32 | 1 | slide | — | 0 |  |
| 3 | video | `PinDown.io_@elementresolutio` | 361.45 | 52.01 | 169.35 | 300.99 | 50.20 | 12.84 | 23.52 | 74.32 | 2 | slide | — | 0 |  |
| 4 | video | `PinDown.io_@ShiseidoEurope_1` | 537.66 | 52.01 | 169.35 | 300.99 | 74.68 | 12.84 | 23.52 | 74.32 | 3 | slide | — | 0 |  |

### Slide 30  ·  `slide30.xml`

layout `SECTION_TITLE_AND_DESCRIPTION` · layout_type `None` · bg `#A7C6ED` (from `slide`) · bg_image no · **9 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | rect | `Google Shape;37;p9` | 360.00 | -0.01 | 360.00 | 405.00 | 50.00 | -0.00 | 50.00 | 100.00 | 0 | layout | #A7C6ED | 0 |  |
| 1 | image | `Picture 2` | 0.00 | -45.38 | 720.00 | 450.38 | 0.00 | -11.21 | 100.00 | 111.21 | 0 | slide | — | 0 |  |
| 2 | line | `Google Shape;215;p34` | 481.87 | 36.00 | 49.13 | 0.00 | 66.93 | 8.89 | 6.82 | 0.00 | 1 | slide | — | 0 |  |
| 3 | line | `Google Shape;216;p34` | 481.87 | 369.00 | 49.13 | 0.00 | 66.93 | 91.11 | 6.82 | 0.00 | 2 | slide | — | 0 |  |
| 4 | text | `Title 1` | 292.88 | 77.05 | 427.12 | 91.95 | 40.68 | 19.02 | 59.32 | 22.70 | 3 | slide | — | 1 | EXECUTION |
| 5 | text | `Subtitle 2` | 339.70 | 159.03 | 333.48 | 56.17 | 47.18 | 39.27 | 46.32 | 13.87 | 4 | slide | — | 1 | Use the Secret Primary Blue to create drench |
| 6 | text | `Subtitle 2` | 339.70 | 232.03 | 333.48 | 56.17 | 47.18 | 57.29 | 46.32 | 13.87 | 5 | slide | — | 1 | Create translucence and refractive index to  |
| 7 | text | `Subtitle 2` | 339.70 | 297.17 | 333.48 | 56.17 | 47.18 | 73.38 | 46.32 | 13.87 | 6 | slide | — | 1 | Use of props,  hand models for application s |
| 8 | image | `Picture 12` | 0.00 | 0.00 | 280.09 | 405.00 | 0.00 | 0.00 | 38.90 | 100.00 | 7 | slide | — | 0 |  |

### Slide 31  ·  `slide31.xml`

layout `TITLE` · layout_type `title` · bg `#A7C6ED` (from `slide`) · bg_image no · **7 shapes**

| # | type | name | x pt | y pt | w pt | h pt | x% | y% | w% | h% | z | src | fill | runs | text |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|--:|:--|
| 0 | text | `Google Shape;133;p29` | 196.66 | 278.28 | 314.27 | 37.46 | 27.31 | 68.71 | 43.65 | 9.25 | 0 | slide | — | 1 | THANK YOU |
| 1 | line | `Google Shape;134;p29` | 193.57 | 306.11 | 49.13 | 0.00 | 26.88 | 75.58 | 6.82 | 0.00 | 1 | slide | — | 0 |  |
| 2 | line | `Google Shape;135;p29` | 464.88 | 306.11 | 49.13 | 0.00 | 64.57 | 75.58 | 6.82 | 0.00 | 2 | slide | — | 0 |  |
| 3 | rect | `Google Shape;12;p2` | -0.00 | 0.04 | 720.00 | 281.41 | -0.00 | 0.01 | 100.00 | 69.48 | 3 | slide | — | 0 |  |
| 4 | text | `Google Shape;131;p29` | 356.51 | 130.03 | 309.11 | 133.01 | 49.51 | 32.11 | 42.93 | 32.84 | 4 | slide | — | 1 | BEAUTY |
| 5 | image | `Picture 1` | 70.89 | 91.94 | 352.37 | 182.52 | 9.85 | 22.70 | 48.94 | 45.07 | 5 | slide | — | 0 |  |
| 6 | image | `Picture 2` | 649.01 | 7.71 | 66.20 | 24.29 | 90.14 | 1.90 | 9.19 | 6.00 | 6 | slide | — | 0 |  |

---

## OPEN ITEM — the `p.t` strut is still live on desktop (820px–~1280px)

Fixed below the breakpoint in `add4538` (`.sh.tx p.t{font-size:0}`, inside the
`@media` block). **Not fixed above it**, and deliberately so: the fix there
changes the desktop build and moves the standing test's baseline, which does
not belong in the middle of a reflow pass.

`p.t` carries a unitless `line-height` but no `font-size` of its own, so it
inherits 16px from `body` and its strut computes as `ratio x 16px` — a fixed
pixel leading under text sized in `cqw`. A line box is the taller of the strut
and its inline content, so the two swap places at a threshold:

```
slide 4, runs at 1.25cqw, line-height 2.4961
strut            = 2.4961 x 16px            = 39.94px
text line box    = 1.25cqw x W/100 x 2.4961
equal when       W = 39.94 / (0.0125 x 2.4961) = 1280px canvas width
```

So **820–1280px of canvas width renders slide 4 strut-dominated on desktop**.
A 1000px-wide window is inside that band today. The deck's smallest run is
1.1111cqw, so other slides cross over even later.

Measured below the breakpoint before the fix (390px viewport, 219px canvas):
slide 4's eight paragraphs were **39.94px each instead of 12.16px** — 320px of
ink in a 98px box. Setting `p.t{font-size:4.875px}`, the size of its own span,
returned it to 12.16px, which is the proof.

**The fix when it is taken on:** emit a `font-size` on `p.t` from the
paragraph's own runs, so the ratio binds to the text it belongs to. That is a
desktop-visible change; expect the standing test to fail and its baseline to
be re-taken deliberately, not worked around.

Recorded as LEARNINGS rule 41(s).

---

# FINAL STATE — deck 10 mobile, 2026-08-29

## What shipped

All 31 slides reflow below `dkcss.MOBILE_BP` (820px). One `<section class="slide">`
per source slide; no second DOM.

| group | slides | treatment |
|---|---|---|
| cover | 1, 31 | positioned canvas; 31 rides slide 1's SELECTORS, not a copy |
| statement | 2 | positioned canvas, hero + derived wordmark |
| agenda | 3 | photo band, four numbered rows on the flat blue |
| dividers | 4, 9, 14, 21 | photo band + list on the blue, generated by `divider_css()` |
| plates | 5-8, 10-13, 15-20, 22-26 | each image its own full-bleed plate, `plate_css()` |
| video | 28, 29 | each video its own full-bleed plate |
| headers | 27, 30 | flowing text panel, generated by `header_css()` |

Three generators, not 31 hand-written blocks: `plate_css`, `divider_css`,
`header_css`. Each was hand-built on one slide first, then that slide was moved
onto the generator so its measured numbers are the regression check.

**Colour.** Nothing was recoloured except where the deck's own sibling settles
it. Slide 3's descriptions and slides 27/30's body went `#002060` because
slide 4 authors ITS reading text navy on the same `#A7C6ED` panel (8.68 vs
white's 1.76). Group B needed no change at all -- it was already navy. Display
type and the 50%-white numerals keep their authored white and their authored
1.76 / 1.34, because slide 4's do.

**No scrim and no halo anywhere.** Both were tried on slide 3 and removed; the
CSS carries a "DO NOT RE-ADD" note with the measurements.

**No scroll-snap anywhere.** Snapping only the five breakers was implemented,
shipped and pulled: the scoping worked, but any snap position in the run
re-targets a fling passing it, so the continuous plate scroll degrades even on
slides that were never snapped.

**Videos** carry the editor's attribute set (`Deck_Editor_v14.html:1318`):
`autoplay muted loop playsinline`, no `preload`. The authored `poster` is kept
-- a deliberate deviation, worth it when a browser refuses autoplay. Confirmed
playing on device. `tools/serve_deck.py` is now `ThreadingHTTPServer`: seven
autoplaying videos open six concurrent connections and a one-at-a-time server
stalls them all at `readyState 0`, which looks exactly like a broken deck.

## The standing test

Strip the `data-name` attributes, the `@media (max-width:820px)` block and its
comment, and the output must be CHARACTER-IDENTICAL to the desktop build.
**Passing.**

The baseline moved ONCE, deliberately, when the video attributes changed --
that is a desktop-visible fix and the old baseline was wrong, not the change.
Before re-taking it the divergence was verified to be exactly one region and
every difference a `<video>` tag. The reference is `aac6fc3`'s renderer plus
that single line.

## Artifacts

    out/secret/index.html              813,433 bytes   external assets/  <- SHIP THIS
    out/secret/assets/                  72 files, 19,306,734 bytes
    out/secret/index.standalone.html  26,929,867 bytes  everything inlined

`index.standalone.html` is the offline / Deck-Editor copy, NOT the phone build.
19.32 MB gzipped, all of it before anything renders -- roughly 16s of blank
screen on 10 Mbps, 31s on 5. The mp4s are already compressed so gzip only
claws back the base64 inflation. A data-URI video cannot range-request, so the
whole blob decodes before the first frame, times seven.

Verified against Deck_Editor_v14's OWN parse, not a browser: 31 slides (not
62 -- rule 22's failure mode, first artifact where it is actually tested), 68
images and 7 videos harvested against 68 and 7 in the document, live
characters 1,842 matching the model per slide, no `hdphoto`/`.wdp`.

**Inlining fixes a live editor defect.** Parse (line 766) only pushes an image
whose src is `http`, `r2.dev` or `data:`; write-back (line 1362) filters only
the placeholder PNG. On the relative build the parse harvests **0** images
against a write-back array of 68 -- the editor cannot see or edit any image,
and 30 of 31 slides disagree. With every src a data URI both arrays hold the
same 68 elements in the same order and all 31 slides agree.

## OPEN — the desktop `p.t` strut (unchanged)

Still live from 820px to ~1280px canvas width. See the OPEN ITEM above; fixing
it means emitting a `font-size` on `p.t` and re-taking the standing test
baseline a second time.

## OPEN — the source deck cannot be regenerated

**This is the most serious item here and it is not a rendering problem.**

The 31-slide source `SecretBeautyCreativeStrategy_OSR.pptx` is GONE from
`~/Downloads`, along with `SecretBeautyCreativeStrategy.pptx` and
`_Mobile_OSR.pptx` and `_Mobile_OSR1.pptx`. Only their `~$` lock files remain.
The one surviving deck, `_Mobile_OSR2.pptx` (Aug 29 03:20), is a **7-slide**
extract with 10 media files and NO videos -- not this build's source, and not
a clean subset either: 4 of its 7 slides differ in their text runs.

Meanwhile:

  * `phase_1c/secret/` has **no `model.py`**. Every other deck has one
    (`olay/model.py`, `oldspice/model.py`, `deckkit/model.py`). Secret's
    parser is not in this repository.
  * `out/` is gitignored -- **0 files tracked under `out/secret`**.
  * The raw extract the model was built from lived in a prior session's
    scratchpad and is gone.

So `model.json`, `asset_manifest.json` and the 72 assets exist only as
untracked files on one disk, produced by a parser that is not in the repo,
from a deck that no longer exists. `render.py` reads those files, so the deck
builds today -- but **if `out/secret/` is lost, nothing in this repository can
regenerate it.** Back up `out/secret/` and locate the 31-slide pptx before any
further work.
