# On-deck — LEARNINGS

Hard-won lessons from PPTX→HTML deck conversions. Each entry is written so it can
become an **automated pipeline assertion**. The goal is to stop rediscovering these.

Format for every entry:
- **Symptom** — what went wrong / what we saw
- **Root cause** — why it happened
- **Rule** — what we now always do (phrased as an assertable invariant)
- **Proven by** — the deck(s) that taught it

Decks referenced: **Wheeber**, **FrameTag**, **Global ImAIge** (Global Image Factory),
**P&G** (Creative Deck / Retail Display), **CEEVUE**.

> Sourcing note: this file was consolidated from `phase_1c/transform_spec.md` and the
> deck-conversion conversation record. Where a finding was later revised (e.g. font
> scaling), the entry reflects the *current* resolution, not the superseded one.

---

## 1. Media bindings — resolve via `_rels`, never visual order

- **Symptom** — Videos and posters showed up on the wrong tiles. Slides 4, 6, 7
  had left/right media swapped; slide 8's 3×2 grid was not row-major
  (c1r1=media10, c2r1=media11, c3r1=media13, c1r2=media9, c2r2=media12, c3r2=media14).
- **Root cause** — We inferred which media belonged to which tile from left-to-right
  visual position. PPTX does **not** store media in visual order. The binding lives in
  `ppt/slides/_rels/slideN.xml.rels`, which maps relationship IDs to media files. The
  playing video is referenced by `<p:videoFile r:link="rIdX">` and its poster by
  `<a:blip r:embed="rIdY">` — two different rIds inside the same `<p:pic>`.
- **Rule** — Media-to-shape binding is resolved **only** by parsing `slideN.xml.rels`
  into an `{Id → target}` dict and looking up the `r:link` (video) and `r:embed`
  (poster) on each `<p:pic>`. Never bind media by on-slide position or by document order
  of the media files. *Assertion:* every media-bearing shape must carry a resolved rId
  that exists in the slide's rels; reject any media bound positionally.
- **Proven by** — Global ImAIge (slides 4/6/7/8), CEEVUE (9 video slides), P&G.

---

## 2. Parse XML with a real parser + explicit namespaces — never regex

- **Symptom** — Regex extractors silently returned `None` for `r:embed` / `r:link`,
  producing slides with missing media and missing fills.
- **Root cause** — PPTX attributes are namespace-prefixed (`r:embed`, `r:link`,
  `a:off`). Regex against the raw XML string fails to match these reliably, and the
  failure is silent — it looks like "no media on this slide" rather than an error.
- **Rule** — All PPTX XML is parsed with `xml.etree.ElementTree` (or `lxml`) using an
  **explicit namespace dict**. Relationship attributes are read by their fully-qualified
  name, e.g. `{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link`.
  Regex against raw XML strings is banned in the parse layer. *Assertion:* the parse
  layer imports no `re` for structural attribute extraction; namespace map is the single
  source of prefixes.
- **Proven by** — Global ImAIge, FrameTag, P&G (all parse modules).

---

## 3. Enumerate shapes by topology, never by name

- **Symptom** — A finished slide silently dropped a shape (e.g. slide 21's footnote
  TextBox 7): the builder only looked for "TextBox 1, 4, 8, Picture 10" and ignored
  everything it wasn't told to expect.
- **Root cause** — Name-based lookup (`sh.name == "TextBox 8"`) only renders shapes you
  remembered to name. Any shape you forget is invisibly skipped — the most insidious bug
  class because the output looks plausible.
- **Rule** — Walk the `spTree` in document order and emit **every** shape (`sp`, `pic`,
  `grpSp`, `cxnSp`, `AlternateContent`). Classify shapes by role afterward (position,
  font size, fill), never by name. Recurse into `grpSp` composing group transforms;
  resolve `AlternateContent` by preferring `mc:Choice` then `mc:Fallback`. *Assertion:*
  emit a **coverage map** of every shape in the spTree marked rendered vs. skipped; any
  skipped shape that is not a known designElem locker raises a warning the user can review.
- **Proven by** — P&G (slide 21 footnote), Global ImAIge (topology extractor), FrameTag.

---

## 4. Never flatten layers — keep the layer tree intact

- **Symptom** — Two related failures. (a) On P&G slide 14, a center mockup with an
  intentionally transparent left edge revealed a dieline behind it; flattening the image
  onto white destroyed the intended reveal. (b) On Global ImAIge, video-over-photo tiles
  require the poster `<img>` underlay and the autoplaying `<video>` overlay to coexist as
  separate stacked layers.
- **Root cause** — Treating each shape as an opaque, independently-composited rectangle
  discards the source z-order. PowerPoint compositions deliberately rely on a shape being
  *visible through* the transparency of the shape above it.
- **Rule** — Preserve the full layer tree and z-order from the spTree. Do **not** flatten
  a shape onto an opaque background when it overlaps another shape behind it in z-order
  (the overlap-detection rule). Video tiles keep poster-underlay + video-overlay as
  distinct layers. *Assertion:* for any image with an alpha channel that overlaps a shape
  beneath it in z-order, flattening is forbidden; the renderer must emit both layers with
  correct stacking.
- **Proven by** — P&G (slide 14 dieline; slide 11 flagged 2% overlap sliver),
  Global ImAIge (video-over-photo tiles).

---

## 5. Background text layered under photos must z-stack behind, not render as siblings

- **Symptom** — Fragments of headline text bled out around the edges of foreground
  photos: "ves"/"tyle" on slide 9, "UNNING"/"JNNING" (from "STUNNING") on slides 11–12,
  editorial fragments on slide 13.
- **Root cause** — The source deck layered decorative headline text *beneath* the
  foreground photo composites. The renderer placed those background elements as visible
  siblings instead of z-stacked behind the photos, so they leaked wherever the covering
  photo had a gap or transparency.
- **Rule** — Respect source z-order on render: a text shape that sits below image shapes
  in the spTree renders behind them via stacking, clipped to the covering bounds where
  needed (`overflow: hidden` on a wrapper sized to the photo). Do not promote
  background-layer text to a visible sibling. *Caution:* distinguish a true bleed-through
  (decorative background that was meant to be covered) from intentional brand accent
  (e.g. the green "AI" treatment in "ImAIge") — never strip the accent. *Assertion:*
  no rendered text element may have a higher effective stacking position than an image
  that sits above it in source z-order.
- **Proven by** — Global ImAIge / home-furnishings deck (slides 9, 11, 12, 13).

---

## 6. Extract embedded images as assets — never recreate them

- **Symptom** — Risk of redrawing or approximating logos and graphics (including
  SVG-only pictures like the P&G logo, which had `asvg:svgBlip` with no raster fallback).
- **Root cause** — The fidelity wedge of On-deck is "pixel-faithful." Any recreated
  asset is by definition not faithful, and SVG-only pictures have no raster to fall back
  to if you don't pull the vector.
- **Rule** — Every image is **extracted** from `ppt/media/` via its resolved rId and
  emitted as an asset. SVG-only pictures embed the actual vector (inline or as a
  recognized `data:`/asset `<img>` src). Nothing is recreated, traced, or approximated.
  *Assertion:* every rendered `<img>` resolves to bytes extracted from the source PPTX;
  no synthetic image bytes are introduced by the pipeline.
- **Proven by** — P&G (SVG-only logo on slide 1), FrameTag, Global ImAIge.

---

## 7. Content-hash media for dedup and cache safety

- **Symptom** — A naive per-slide embed duplicated assets massively (a logo on 23 slides
  embedded 23×; ~40–50% of one deck's 67 images were duplicates), bloating output and
  memory.
- **Root cause** — Re-embedding identical bytes per slide with no identity key. The
  browser can only dedup at runtime if the same asset resolves to the same URL.
- **Rule** — Compute a content hash (SHA) of each asset's bytes. Identical bytes map to a
  single asset / single stable URL referenced everywhere. Output asset filenames are
  content-addressed so they can be cached immutably (long TTL on artifacts; cache-busting
  is by versioned path, never query string). Editor compatibility is preserved: refs must
  still resolve to a `data:` / `http` / asset URL the Deck Editor recognizes.
  *Assertion:* no two distinct asset URLs share a content hash; every emitted asset URL is
  derived from its content hash.
- **Proven by** — P&G (logo + duplicate portfolio images), Global ImAIge.

---

## 8. ffmpeg: sequential encode + atomic move

- **Symptom** — Parallel `ffmpeg &` jobs in one shell call timed out waiting on the
  slowest job, leaving partial `.mp4` files that then corrupted downstream moves.
  Detached/`nohup setsid` background jobs did not survive process boundaries reliably.
- **Root cause** — The execution environment waits for the slowest backgrounded job and
  has a per-call time budget; partial outputs from killed jobs look like real files to the
  next step.
- **Rule** — Encode videos **sequentially**, one file at a time, writing to a
  `*.__partial.mp4` temp name and only `mv`-ing to the final name on success
  (`ffmpeg ... out.__partial.mp4 && mv out.__partial.mp4 out.mp4`). Batch in groups of
  2–3 at most. Encoding settings that fit budget: long portrait clips (100s+, 1080×1920)
  → scale to 720px wide, `-preset ultrafast -crf 32`; landscape (1920×1440) → 1280px wide,
  `-preset ultrafast -crf 30`; codec H.264. *Assertion:* the encode step is idempotent and
  never leaves a non-atomic partial file in the output set; a `.__partial.*` file in
  outputs is a hard failure.
- **Proven by** — Global ImAIge (15 videos), CEEVUE (9 videos).

---

## 9. Typography uses container-query units (`cqh`), not viewport units

- **Symptom** — Fonts overflowed the 16:9 letterbox on narrow mobile viewports; text set
  in `vh` did not stay proportional inside the slide canvas.
- **Root cause** — `vh`/`vw` are relative to the viewport, not to the slide container.
  Inside a letterboxed 16:9 canvas the viewport and the container diverge, so viewport
  units overflow.
- **Rule** — The slide inner container is `container-type: size`, and all typography is
  expressed in container-query units (`cqh` for height-proportional type, `cqw` for the
  pixel-faithful desktop canvas). Type scales to the slide, not the screen. *Assertion:*
  no font-size in generated CSS uses `vh`/`vw`; type units inside a slide are `cq*` and the
  slide container declares `container-type: size`.
- **Proven by** — Global ImAIge (vh→cqh refactor), P&G (cqw desktop canvas).

---

## 10. Font substitution scaling is conditional — classify, don't hardcode 1.36×

- **Symptom** — An early assumption baked in a universal `~1.36×` Univers→Barlow scale.
  It was then found to **not** match the P&G bundle, which renders declared sizes 1:1.
  Treating 1.36× as a constant would have made the whole deck ~36% too large.
- **Root cause** — There are two substitution regimes. *Matched-metric*: the substitute
  has near-identical metrics (Univers Condensed → **Barlow Condensed**), so no scaling.
  *Cross-metric*: the substitute has different proportions (e.g. Univers → Arial), so
  PowerPoint scales up to compensate — this is the origin of ~1.36×. The factor is a
  property of the *font pair*, not a global constant, and can even differ slide-to-slide.
- **Rule** — Classify every run's font into one of four paths and act accordingly:
  **matched** (known same-metric pair → render 1:1, no scale), **web** (font is
  web-available, e.g. Barlow → render directly), **cross** (unknown/different-metric
  substitute → apply the legacy ~1.36× compensation), **inherited** (no font specified →
  use the default chain: ~16pt non-bold / ~18pt bold body). The 1.36× constant stays in
  code, documented, gated behind the cross-metric path only. *Assertion:* no scale factor
  is applied unless a run is classified `cross`; matched/web runs render at declared size.
- **Proven by** — P&G (matched: Univers→Barlow, 1:1, bundle-verified), with cross/inherited
  paths reserved for FrameTag/Wheeber fonts.

---

## 11. Bold is not a weight — read the typeface name

- **Symptom** — A heavy weight rendered one step too light because the extractor treated
  `<a:rPr b="1">` as the whole weight story.
- **Root cause** — Some weights are distinct *faces*, not the bold property. "Arial Black"
  is its own typeface, stored in the `typeface` attribute, not expressed as `b="1"`. Mapping
  `b="1"` → 700 and ignoring the face name loses real weight.
- **Rule** — Resolve weight from **both** the `b` flag **and** the `typeface` name; map
  named-weight faces (Black, Heavy, Light, Thin, etc.) to their actual weight rather than
  assuming bold is the only axis. *Assertion:* weight resolution reads `typeface` and maps
  known weight-bearing face names before falling back to the `b` flag.
- **Proven by** — Wheeber (Arial Black headline).

---

## 12. Don't compensate CSS for cross-renderer rendering differences

- **Symptom** — Text set as 12pt Arial bold rendered slightly less heavy in Chrome than in
  PowerPoint (seen on Wheeber "Wheeber" header and the earlier "SEED · 2026" case). The
  temptation was to thicken the CSS to match the PowerPoint screenshot.
- **Root cause** — Browser and PowerPoint rasterize fonts differently; a small weight/edge
  difference is an inherent cross-renderer artifact, not a spec error.
- **Rule** — The PPTX XML is ground truth. Render faithfully to the spec and accept minor
  cross-renderer rasterization differences; do **not** tune CSS to chase a PowerPoint
  screenshot. Compensating inserts a "visual lie" that drifts further from spec when the
  user edits and re-exports. (Screenshot/pixel comparison is a sanity check, not a source
  of truth — it has caused wrong "fixes" before.) *Assertion:* CSS values are derived from
  XML-extracted properties; no styling rule exists solely to match a rendered screenshot.
- **Proven by** — Wheeber (header weight), SEED (prior, reverted).

---

## 13. Color tint/shade uses RGB blend (documented ECMA-376 deviation)

- **Symptom** — Theme colors with tint/shade modifiers needed a defined, testable
  resolution; ECMA-376's wording (HSL Luminance) did not match observed PowerPoint output.
- **Root cause** — ECMA-376 specifies tint/shade in terms of HSL Luminance, but empirical
  output (synthetic_03 fixture) matches an RGB-blend computation instead.
- **Rule** — Color transforms are space-specific: `lumMod`/`lumOff`/`satMod`/`hueMod`
  operate in **HSL** per ECMA-376, but `tint`/`shade` are computed as a per-channel
  **RGB blend** (tint → toward white, shade → toward black) — a deliberate, documented
  deviation from ECMA-376's HSL Luminance wording, justified by `synthetic_03`. Children
  are applied in document order (order matters; the resolver walks them sequentially).
  The `ColorResolver` returns a structured object (`hex`/`rgb`/`alpha`/`css`/`audit_chain`)
  so every resolved color is auditable. *Assertion:* color resolution matches the
  `.expected.json` fixtures (four real P&G theme fixtures + three synthetic edge cases); the
  RGB-blend deviation is the pinned behavior.
- **Proven by** — P&G (theme_fillstyle fixtures), synthetic edge cases (synthetic_01–03).

---

## 14. Preserve source content faithfully — including its mistakes

- **Symptom** — Slide 11 of Global ImAIge labeled two consecutive steps both as "5". The
  instinct is to "fix" the numbering.
- **Root cause** — On-deck's job is faithful conversion, not editorial correction. Silently
  fixing source content makes output diverge from what the customer authored and expects to
  edit.
- **Rule** — Reproduce source text content exactly as authored, including typos and
  duplicate labels. Corrections are the user's call in the editor, not the pipeline's.
  *Assertion:* extracted text content is emitted verbatim; the pipeline performs no
  silent content normalization.
- **Proven by** — Global ImAIge (slide 11 duplicate "5").

---

## 15. Dual-build: pixel-faithful desktop canvas + separate mobile reflow

- **Symptom** — A single responsive DOM could not be both pixel-faithful on desktop and
  sensibly reflowed on mobile.
- **Root cause** — Desktop fidelity needs absolute positioning on a fixed canvas at the
  deck's own aspect; mobile needs a reflowed, scroll-friendly document. One DOM cannot
  serve both cleanly.
- **Rule** — Emit two sections from the same source: `#deck-desktop`, an absolutely-
  positioned canvas **at the deck's own aspect** using `cqw` units (pixel-faithful), and
  a completely separate `#deck-mobile` scroll-snap DOM. Per-slide CSS is scoped
  (`.slide-N`). Editor vocabulary classes are preserved (`.L > .t`, `.ci`, `.tlt`,
  `.tlb`, `.uct`, `.ucb`, etc.). Scroll behaviour: snap on desktop (`mandatory` or
  `proximity`) with `scroll-snap-stop: always`; **below the mobile breakpoint release
  the snap container** — `scroll-snap-type: none` and `scroll-snap-stop: normal`.
  *Assertion:* every slide emits both a `#deck-desktop` and a `#deck-mobile`
  representation; desktop canvas uses `cqw`, neither uses `vh`/`vw` for type; **no
  emitted CSS contains a hardcoded aspect ratio** — every canvas aspect traces to
  `p:sldSz`; and **no rule below the mobile breakpoint sets `scroll-snap-stop: always`**.
- **Proven by** — P&G (dual-build pattern established), Global ImAIge (continuous scroll).
- **Amended 2026-08-26, on two counts. Both were places where this rule did not merely
  fail to prevent a defect — it prescribed one.**
  1. **The aspect is not 16:9; it is whatever `p:sldSz` says.** This rule said "16:9
     canvas" twice, and three builders duly hardcoded it — `aspect-ratio:16/9` plus a
     `max-width:calc(177.78vh - 8vh)` in which `177.78` is `16/9 × 100` wearing a
     disguise. That is correct for the four 960×540 decks and silently wrong for deck 9
     (Venus/Hestia), which is **1224 × 792pt — 17 × 11in tabloid landscape, aspect
     1.5455**. Read the dimensions and publish them as `--ratio`; size everything off
     that. Pillar-boxing a 1.55:1 deck on a 16:9 monitor is correct behaviour, not a bug
     to pad away. The positioning and type maths were never aspect-dependent — only
     these literals were.
  2. **`scroll-snap-stop: always` is wrong on an inertial surface.** Per CSS Scroll Snap
     `always` forbids the container passing over a snap position during a scrolling
     operation, so every fling is forced to the nearest snap point. That is a
     **discrete-paging** affordance: right for a wheel or an arrow key, wrong for a
     thumb. This rule mandated it unconditioned, so it shipped on every deck and was
     found only in live review — HenHouse after four mobile rounds, Olay after five,
     because every round reviewed appearance and none reviewed **scroll behaviour as its
     own dimension**. Snap re-targeting is also what overrides the browser's own
     deceleration curve, so releasing `scroll-snap-type` is what actually returns
     momentum; the accepted cost is that a flick can rest mid-slide.
  **Both now live in `phase_1c/deckkit/css.py`** (`ratio_root`, `CANVAS_WIDTH_FIT`,
  `canvas_max_width`, `mobile_scroll_release`, `MOBILE_BP`) so the next builder inherits
  them instead of re-deriving them. That module exists because nothing was shared: the
  scroll defect had to be diagnosed on HenHouse, ported by hand to Olay, and **was
  missed entirely on Old Spice**, which still ships `y mandatory` + `always` at every
  width — the strictest of the three — on a live deck. Three builders, three chances,
  two takers.
  - **Corollary — a rule is a defect source, not just a defence.** When the same mistake
    turns up in two or three builders, check the spec before blaming the builders. Three
    independent authors do not converge on the same wrong value by accident; they were
    told to.

---

## 16. Validate against LibreOffice ground truth, not against guesswork

- **Symptom** — Iterating against screenshots / eyeballing led to incorrect fixes.
- **Root cause** — Without a deterministic reference render, visual iteration chases
  artifacts and rasterization quirks rather than the actual source layout.
- **Rule** — Generate a ground-truth render per slide via **LibreOffice headless +
  pdftoppm** and verify output via headless Playwright from the staged output location.
  Ground-truth PNGs are a *positional/layout* sanity check; the **PPTX XML remains the
  authority for values** (sizes, colors, bindings). *Assertion:* the pipeline produces a
  ground-truth render per slide and a Playwright capture of the staged build for diffing;
  numeric values trace to XML, not to pixels.
- **Proven by** — P&G, Global ImAIge (LO + pdftoppm + Playwright workflow).

---

## 17. `<a:spAutoFit/>` boxes are a font-metric oracle — use them to pick substitutes

- **Symptom** — Olay declares two unlicensed faces (Franklin Gothic Book, Boston
  SemiBold) with no bundled binary. Picking a substitute by name/lineage looked
  like the only option, and rule 10 forbids guessing a scale factor.
- **Root cause** — A text box carrying `<a:spAutoFit/>` was auto-sized by
  PowerPoint to exactly fit its wrapped text *in the original font*. That means
  the stored `<a:ext cy>` is a measurement of the real face, sitting in the file.
- **Rule** — When a deck has autofit text boxes, solve
  `box_h = tIns + bIns + line_count × (ratio × font_size)` across boxes with
  different line counts. This over-determines the source face's **line-height
  ratio**, and dividing back out gives the true **line count per box**. A
  substitute is metric-matched iff it wraps the same authored strings to the
  same line counts at the same authored widths — a measurement, not a judgement.
  Set `line-height` explicitly from the recovered ratio rather than inheriting
  the substitute's own. *Assertion:* for any deck with `spAutoFit` boxes, the
  chosen substitute reproduces the recovered line count on every such box.
- **Proven by** — Olay. 22 autofit boxes gave ratio 1.2121 (Franklin Gothic Book
  @14pt, boxes stepping in exact 16.97pt increments) and 1.2140 (Boston
  SemiBold @20pt). Archivo at `wdth=94` matched 20/20 boxes; **Libre Franklin —
  the obvious lineage match, being a Franklin Gothic revival — was 8.7% too wide
  and failed**, which is rule 10 restated: the fit belongs to the font pair, not
  the name. Archivo's own line-height ratio is 1.088, so inheriting it would
  have set the body copy 11% too tight.
- **Amended by rule 34** — the *ratio* half of this oracle does not identify a
  face. Only the line-COUNT test does. Olay's 1.2121 was read as evidence for
  Archivo; it was not evidence of anything about the face.
- **AMENDED 2026-08-28 — THE RECOVERY HAS TWO TERMS AND THIS FITS ONE.**
  The equation above (`box_h = tIns + bIns + lines x ratio x size`) is missing a
  constant. Fitted across 25 `spAutoFit` boxes in four decks, six sizes
  (12-40pt) and six faces:

      height = 0.07034 pt + 1.211720 x (lines x size x spcPct) + insets

  to a max residual of **0.00051 pt**. There is a **per-BOX constant of
  0.0703pt** alongside the per-line factor. Dividing total height by
  `lines x size` charges that constant to every line, so what comes back is

      recovered = 1.21172 + 0.07034 / (lines x size)

  which **falls as boxes get bigger**. That one expression reproduces every
  "per-deck constant" in the corpus and every entry in
  `SOURCE_LINE_HEIGHT_RATIOS` — including the two the table's own comment
  noticed without explaining, Aptos at 1.2161 (16pt) and 1.2132 (24pt x2),
  *the same face at two sizes*:

  | entry | recorded | lines x size | 1.21172 + 0.07034/(lines x size) |
  |---|---|---|---|
  | aptos @16pt x1 | 1.2161 | 16 | 1.21612 |
  | aptos @24pt x2 | 1.2132 | 48 | 1.21319 |
  | gotham black @60pt x1 | 1.2129 | 60 | 1.21289 |
  | din condensed @28pt x1 | 1.2143 | 28 | 1.21423 |
  | franklin gothic book @14pt x12 | 1.2121 | 168 | 1.21214 |
  | univers condensed @40pt x1 (deck 10) | 1.2135 | 40 | 1.21347 |

  Olay is the internally decisive case: **one face at one size (14pt) across
  eight distinct line counts (1,2,3,4,5,6,8,12)**, whose one-term factor falls
  monotonically 1.21671 -> 1.21214 exactly as `a + b*n` predicts.
- **RULE — recovery needs at least TWO DISTINCT values of `lines x size`.**
  With one value the terms are not separable and the constant silently absorbs
  the box term. Deck 10 has exactly one: its four `spAutoFit` boxes are the same
  shape copied onto four slides. **A sample of four identical shapes is a sample
  of one**, and the deck could not have caught this from its own file.
  *Assertion:* any recorded line-height ratio must carry the `lines x size` it
  was recovered at; a bare number is not reproducible.
- **The per-face table has no per-face component to model.**
  `SOURCE_LINE_HEIGHT_RATIOS` keys on face, and its own comment already says
  "five unrelated faces, one number... PowerPoint's autofit line spacing, NOT a
  font metric". The variation it records is SIZE. Unfixed — olay, oldspice and
  henhouse still read it — but nothing should be added to it without the
  `lines x size` written beside the value.
- **NOT settled: venus_hestia.** Its 353 `spAutoFit` boxes use AUTHORED insets
  (tIns 1.0pt, bIns 0) rather than the 3.6/3.6 default, and its wrapped boxes
  have unknown line counts, so the two terms cannot be separated there. Its
  single-paragraph median one-term factor is **1.21247**, matching the 1.2124
  already recorded for that deck. **The model is demonstrated on four decks, not
  five**; venus_hestia's constant is deliberately left alone.
- **A method trap inside the method.** The first pass at venus_hestia subtracted
  `spcBef` from the autofit height and produced 1.19065 at 47pt, which read as a
  deck refuting the model. PowerPoint does not charge `spcBef` on a first
  paragraph. **A single measurement that refutes a model fitted to 0.0005pt on
  25 boxes is more likely a bug in the measurement than a finding.**

---

## 18. A `p16:designElem` marker is not sufficient grounds to skip a shape

- **Symptom** — 18 Olay shapes were being dropped silently, including three
  white drop-shadowed cards behind slide 9's video tiles and a full-slide
  translucent wash. The slides rendered with the background showing through
  where panels should be.
- **Root cause** — `_is_design_locker()` treated the `<p16:designElem val="1"/>`
  marker as decisive. PowerPoint Designer also stamps that marker on shapes the
  author subsequently gave real styling to; 8 of the 18 carried a `solidFill`.
- **Rule** — The marker *gates* the check; visual emptiness *decides* it. A
  marked shape is an inert locker only when it paints nothing: no fill (or an
  explicit `<a:noFill/>`), no visible line, no blip, no non-empty run. Genuine
  `noFill noLine` lockers still test true, so decks relying on the old behaviour
  are unaffected. *Assertion:* a skipped shape must have no fill, no line, no
  image and no text; anything else is a coverage-map warning, per rule 3.
- **Proven by** — Olay (slides 9, 10 filled cards vs slides 1, 3, 25–32 true
  no-ops). LibreOffice ground truth agrees on both halves of the split.

---

## 19. `<p:style>` fillRef/fontRef paint shapes that have no explicit fill at all

- **Symptom** — Six client review stickers ("Move forward if feedback is able to
  be incorporated", "Wrong package") rendered as black text floating on the
  slide background. Ground truth shows dark-teal boxes with white text.
- **Root cause** — The shapes carry no `spPr` fill and no run colour. Their
  appearance comes entirely from `<p:style>`: `<a:fillRef idx="1">` points into
  the theme's `fillStyleLst`, substituting its own colour for the template's
  `phClr`, and `<a:fontRef>` supplies the text colour.
- **Rule** — Resolve `p:style` for any shape lacking an explicit fill:
  `fillRef idx` indexes `fmtScheme/fillStyleLst` (1-based) and composes via
  `ColorResolver.resolve_with_theme(fillRef, template)`; `fontRef` supplies the
  default run colour for runs with no declared colour. An explicit `<a:noFill/>`
  beats the reference. *Assertion:* no shape with a `fillRef` and no explicit
  fill renders transparent. **Corollary for deck triage:** a
  `explicit_color_override_pct` of 0.0 measured at *run* level does not mean the
  theme is inert — it can mean the opposite. Check `p:bg` and `p:style` before
  concluding anything about how much colour work a deck needs.
- **Proven by** — Olay (33 `p:style` blocks across 18 slides; all
  `fillRef idx=1` → accent1 `#156082`, `fontRef minor` → lt1 white).

---

## 20. Slide-background alpha composites over the master background, not the page

- **Symptom** — Slide 15's caption column rendered white instead of salmon.
- **Root cause** — `<p:bg>` with `<a:alpha>` was emitted as `rgba()`. Wherever
  no shape covered the slide, the page behind showed through instead of the
  master background. Painting a white underlay *inside* the canvas made it
  worse — it covered the tint rather than backing it.
- **Rule** — A translucent slide background is composited against the resolved
  master background (`p:bg/p:bgRef` → scheme colour) into an **opaque** value at
  build time. Shape-level fills keep their alpha: those composite over whatever
  art sits beneath them, which is genuine transparency. *Assertion:* no emitted
  slide-background colour carries an alpha channel.
- **Proven by** — Olay (s15 `#DD6467` @80.1% → `#E48385`; s28, s31 likewise).
- **Amended by rule 35** — computing the opaque value is only half of this. It
  must also be the value every breakpoint paints with; HenHouse emitted it
  correctly and desktop read the rgba anyway.

---

## 21. `container-type` creates a stacking context — never z-index inside the canvas

- **Symptom** — On slide 21 two review stickers vanished behind full-bleed
  videos that sit *below* them in source z-order — a direct rule 5 violation.
- **Root cause** — `container-type: size` implies `contain: layout`, which makes
  the slide canvas a stacking context. A `z-index: 1` on the `<video>` inside a
  `z-index: auto` wrapper promoted every video above all sibling shapes.
- **Rule** — Inside the slide canvas, paint order is DOM order and nothing
  carries a `z-index`. Poster-under-video stacking (rule 4) is achieved by
  emitting the poster first and the video second, both absolutely positioned in
  the same wrapper. *Assertion:* generated per-slide CSS declares no `z-index`
  inside the canvas.
- **Proven by** — Olay (slide 21 stickers; slides 9/10 unaffected only because
  their stickers happened not to overlap a video).

---

## 22. Editor compatibility forces a single-DOM dual-build (amends rule 15)

- **Symptom** — Rule 15's two DOMs put every live string in the document twice.
  Deck Editor v14 parses with `DOMParser`, never runs JS, and keys on
  `class="slide"` — so it harvested 68 slides instead of 34, and an edit would
  update one view while the other silently went stale.
- **Root cause** — Rule 15's root cause ("one DOM cannot serve both cleanly")
  predates using `container-type` + a `position: absolute → static` switch,
  which preserves absolute desktop fidelity while allowing a real mobile reflow.
- **Rule** — When a deck must stay editable, emit **one** set of
  `<section class="slide">`, keep the desktop path exactly as rule 15 specifies
  (absolute `%` on a 16:9 `container-type: size` canvas, type in `cqw`), and do
  the mobile switch in CSS with per-shape `order`. Two mechanical requirements:
  (a) **crop wrappers must stay positioned** — their `<img>`/`<video>` children
  are absolutely positioned by the `srcRect` maths and will otherwise resolve
  against the canvas and blow up to full size; (b) **`inset: auto !important`
  on every shape** — a `position: relative` wrapper still applies the inline
  `left`/`top` as flow offsets, sliding tiles sideways and tearing holes in the
  stack. Note percentage *heights* self-neutralise (the mobile canvas has no
  definite height, so they resolve to `auto`, letting `aspect-ratio` drive tile
  height) while percentage *widths* do not — size any `flex: 0 0 auto` shape by
  flex-basis, not `width` alone. *Assertion:* exactly one `class="slide"` per
  source slide; total live characters in the output equal the source exactly.
- **Proven by** — Olay (34 sections, 4,874 characters, editor-harvestable).

---

## 23. Source decks carry internal review comments — detect by treatment, suppress by opt-in

- **Symptom** — The Olay deliverable shipped six teal boxes reading "Wrong
  package", "This looks too fake but like suds & they do well", "Move forward
  with #5 as is". They are P&G's internal review notes, left in the working file
  and faithfully rendered by rule 14. Fine for fidelity; not fine for a client.
- **Root cause** — Rule 14 ("reproduce source content exactly, including its
  mistakes") is about not *editorially correcting* the author. It says nothing
  about content the author never intended to publish. A working deck and a
  deliverable are different artifacts cut from the same file.
- **Rule** — Detect annotation shapes by **treatment, never by string match** —
  string lists do not survive the next deck. The signature that worked, and the
  reason it is trustworthy, is that whoever makes a comment box *chooses
  nothing*: they take PowerPoint's default shape and type. So look for a text
  shape where **every** one of these holds:
    1. fill resolves to a theme **accent**, and via `<p:style>/fillRef` rather
       than direct formatting (rule 19)
    2. text colour comes from `<a:fontRef>`, not a declared run colour
    3. no declared typeface on any run (falls back to the theme minor font)
    4. no declared size on any run (falls back to the master default)
    5. no `<a:spAutoFit/>` — the box was hand-dragged, not auto-sized
  Authored copy fails this immediately: it picks a typeface and a size. On Olay
  the split was 6 vs 22 with **no overlap on any of the five properties**.
  **Detection must never remove anything.** Flag the shape in the model
  (`review_sticker: true`), leave it in place, and gate suppression behind an
  explicit per-deck opt-in — the same advisory/authoritative split
  `PHASE_1C_ARCHITECTURE.md` mandates for the deck classifier. A signature that
  silently deletes content on an unseen deck is that doc's failure mode wearing
  a different hat; a legitimately theme-styled callout must not vanish because
  it matched a heuristic.
  *Assertion:* pin the expected match set (count + slide/shape identity), assert
  none of the matched text reaches the output, and assert the unflagged count.
  A deck revision that changes the set then **fails the build** instead of
  silently re-leaking a comment or silently dropping a real caption.
- **Also sweep the non-slide parts.** `ppt/comments/*`, `commentAuthors`, and
  `ppt/notesSlides/*` carry the same exposure and are invisible on the canvas.
  (Olay: no comment parts at all; four notes parts containing only page numbers.)
- **Proven by** — Olay (6 stickers on slides 9, 10, 21, 22; 240 of 4,874
  characters).

---

## 24. Flattening z-order for mobile resurrects buried content and destroys backgrounds

- **Symptom** — Two failures from one cause. (a) Slide 33 showed a second
  "Creative Brief" heading plus 583 characters of body copy that appear nowhere
  on desktop. (b) Section-divider backgrounds reflowed into boxed images sitting
  on white, when the background *is* the slide.
- **Root cause** — Desktop paints an absolutely-positioned canvas in z-order, so
  two things are free: a shape can be **hidden by being painted over**, and a
  shape can be **the ground everything else sits on**. A mobile reflow that
  turns the same nodes into a flow stack has neither concept — every shape
  becomes an equal sibling in document order. Olay slide 33 is slide 2
  duplicated with an opaque full-canvas image laid over it; PowerPoint hides the
  old slide purely by z-order, and the reflow put it all back.
- **Rule** — Before reflowing, classify the z-stack:
  * **Occluded** — anything below an opaque shape that covers the whole canvas
    is not part of the deck. Drop it (behind a per-deck opt-in, per rule 23).
    Test opacity from **pixels**, not from the image mode: the Olay cover is
    RGBA with alpha 128..255, but only 0.023% of pixels are non-opaque and the
    regions over the buried content are solid. Mode alone would have missed the
    occlusion; min-alpha alone would have rejected it. Use a coverage threshold
    (>=99.9% alpha-255).
  * **Backdrop** — the run at the bottom of the *visible* stack that forms the
    ground: full-canvas images (plus any tint/wash rect over them) and
    full-height panel rects of a split background. Stop the run at the first
    non-full-canvas image, which is where content begins. On mobile these leave
    the flow and paint as a full-bleed layer behind the content, sized to the
    reflowed canvas.
  *Assertion:* pin the occluded set; assert no occluded string reaches the
  output; assert each backdrop slide is tagged and its backdrop is behind
  content.
- **Gotcha that will cost an hour** — a backdrop stretched with
  `top:0;bottom:0;height:auto` still collapses to its aspect box if the element
  carries an `aspect-ratio` (tiles need one, backdrops must not). Clear it
  explicitly: `aspect-ratio: auto !important`.
- **Proven by** — Olay (occlusion: slide 33; backdrops: slides 2, 3, 4-7, 8, 9,
  10, 17, 24, 33).

---

## 25. Size a crop tile by its constrained axis, not by width

- **Symptom** — The "Renders" contact sheets were unreadable on a phone: one
  magnified sliver of a bottle cropped at the screen edge, the rest white. A
  reader would scroll past assuming the slide was empty.
- **Root cause** — Tiles were given a width-based flex basis (46%). These tiles
  are tall narrow `srcRect` crops (aspect ~0.25), so 46% of a 362px column
  resolved to **167 x 660px** — taller than the viewport. Width felt like the
  natural axis to constrain because that is what the flex row distributes; the
  binding constraint was height all along.
- **Rule** — For a tile whose aspect ratio is far from 1, size it on the axis
  that actually binds and let the other follow from `aspect-ratio`. In a
  horizontal scroller of tall crops that means `height: min(58svh, 520px);
  width: auto; flex: 0 0 auto` — a whole tile fits on screen and several sit
  side by side. Use `svh`, not `vh`: mobile URL-bar collapse makes `vh` unstable
  (same root cause as the `100vh` finding in NOTES). Keep the scroll inside the
  element's own `overflow-x: auto`; the page body must never scroll sideways.
  Lift any section heading out of the scroll row — inside it, it consumes the
  first screenful and pushes the content off-screen.
  *Assertion:* `document.scrollWidth` equals the viewport width; no shape in a
  vertical-flow slide exceeds the viewport width.
- **Proven by** — Olay (slides 4-7, 7 strips each cropped from 2048x2048 plates).

---

## 26. A slide shorter than the viewport reads as two slides colliding

- **Symptom** — Reported as "the Global Image Factory logo is colliding with the
  Creative Brief heading". Nothing overlapped, and the two elements are not even
  on the same slide: the logo is the cover's footer, the heading is slide 2.
- **Root cause** — The cover reflowed to 507px on a 844px viewport. In a
  continuous mobile scroll a short section lets the *next* section scroll into
  the same screen, so a reader sees the tail of one slide and the head of the
  next together and reads them as one broken layout. The bug is in neither
  element.
- **Rule** — In a scroll-snap deck every slide occupies at least a screen:
  `min-height: 100svh` on the slide canvas, with `align-content: center` so
  short slides sit centred rather than jammed to the top. Tall slides overflow
  and ignore both. Use `svh` not `vh` (rule 25). *Assertion:* no section's
  height is below the viewport height; and separately, no two non-backdrop
  shapes on a slide overlap in both axes — run both in the capture step, where
  a browser already exists.
- **Diagnostic worth keeping** — when a collision is reported, measure both
  elements before assuming they interact. Box geometry said the gap was
  116px *and* that a slide boundary sat between them, which pointed straight at
  section height instead of at either element.
- **Proven by** — Olay (cover 507px, slide 18 342px, "Thank You" 474px; the
  strip slides also surfaced a genuine 11px banner/tile overlap the same audit
  caught).

---

## 27. Percentage geometry inside a scroll container measures the viewport, not the content

- **Symptom** — The two-tone ground on the "Renders" contact sheets covered only
  the first screen of a horizontally-scrolling strip and then slid away, leaving
  the later renders on bare white. It read as a stray coloured rectangle.
- **Root cause** — A percentage width on an absolutely-positioned child resolves
  against its containing block's **padding box**, which for a scroll container is
  the visible box (390px), not `scrollWidth` (956px). The panels faithfully
  reproduced 55%/45% — of the wrong width. And because absolutely-positioned
  children of a scroll container scroll *with* the content, they also travelled
  off-screen, so the failure looked positional rather than dimensional.
- **Rule** — Any ground/backdrop inside a horizontal scroller must be sized from
  the **content extent**, never a percentage. When the scroller's items have known
  aspect ratios and a shared height, that extent is computable in CSS: publish the
  height once as a custom property (`--th: min(58svh, 520px)`), emit each panel's
  aspect-sum and offset from the source geometry, and size with
  `calc(var(--th) * var(--ar) + var(--px))`. *Assertion:* on every scrolling slide
  the ground spans `0 .. scrollWidth` with no seam and no shortfall — check it in
  the capture step, where a browser already exists.
- **Decide split-vs-flatten from the source, not from taste.** Before collapsing a
  two-tone ground to one colour, check whether any item straddles the boundary. On
  Olay slides 4-7 none does — the split sits exactly in the gap between render 4
  and render 5, grouping 4 renders against 3. That makes it structural content, so
  it is preserved and re-expressed against the tile spans it owns. Had a tile
  straddled it, it would have been decoration and safe to flatten.
- **Proven by** — Olay slides 4-7 (ground 0..390 of a 956px strip; after the fix
  0..956 with the boundary at 553, between render 4 ending at 549 and render 5
  starting at 557).

---

## 28. Resolve every colour through `ColorResolver` — never read the scheme name directly

- **Symptom** — Old Spice's variant table rendered as an empty grid: borders and
  header present, every data cell blank. The characters were all in the DOM.
  The cell text was `bg1 + lumMod 50%` (mid grey) and had resolved to plain
  `bg1` — white text on white cells.
- **Root cause** — Both deck builders had a local `_solid()` helper that found
  the `<a:srgbClr>` / `<a:schemeClr>` child, looked its name up in the theme,
  and returned. That is correct right up until a deck applies a transform, at
  which point it is silently wrong — it returns the *untransformed* colour, and
  nothing errors. Rule 13 exists to implement exactly these transforms, and the
  builders bypassed it.
- **Rule** — Every colour reaching output resolves through `ColorResolver`
  (`resolve()`, or `resolve_with_theme()` for the `fillRef`/`phClr` two-phase
  case). A builder must never read `schemeClr/@val` and stop. Two practical
  notes: `ColorResolver` takes a plain dict and does **not** know the
  `bg1/tx1/bg2/tx2 -> lt1/dk1/lt2/dk2` aliases that `Theme.resolve()` handles,
  so expand the dict with `SCHEME_ALIASES` before constructing it; and
  `final_hex` does not carry alpha, so read `<a:alpha>` separately and combine.
  *Assertion:* re-resolve every emitted fill and run colour through
  `ColorResolver` and diff against what the builder produced — any mismatch is
  a bug. That audit is cheap and catches the whole class at once.
- **Why this class is dangerous** — the failure is invisible in code review and
  in most decks. A builder that reads the scheme name is correct until the
  first deck that uses a transform on a rendered surface, and then it produces
  a plausible wrong colour rather than an error. Olay used only one such fill
  and shipped with it (see the Olay known-defect note in NOTES.md); Old Spice
  used 63 and the failure was obvious. The difference was luck, not diligence.
- **Proven by** — Old Spice (table body text, 63 lumMod uses), Olay (2 fills on
  slides 9/10, `bg1 + lumMod 85% + alpha 90%` shipped as `#FFFFFF` instead of
  `#D9D9D9`, confirmed against LibreOffice ground truth to the digit).

---

## 29. Don't reproduce a 16:9 canvas's whitespace on a phone

- **Symptom** — Old Spice product plates filled 21.8-43.5% of a 390px section,
  with 238-330px of dead space above *and* below. The deck read as small images
  floating in white.
- **Root cause** — The mobile reflow sized each image from its authored box
  aspect. That box is a composition device for a 16:9 canvas: the surrounding
  space is part of a desktop layout, not part of the image. Carried to a
  portrait viewport it becomes letterboxing on both axes.
- **Rule** — On mobile, size media to the SECTION, not to the authored box.
  Whitespace authored for the desktop canvas is layout, not content, and does
  not survive the reflow. Where the media is a photograph with background
  padding, measure the content extent and frame that instead (a CSS crop, so no
  bytes are created — rule 6). *Assertion:* no mobile media element fills less
  of its section than its own aspect ratio permits; if it does, the box aspect
  is leaking through.
- **Two traps, both silent.** (a) `height: 100%` + `aspect-ratio` does NOT
  aspect-fit: an explicit height wins, `max-width` then clamps the width, and
  the media is stretched rather than scaled. Compute the fit exactly instead —
  `width: min(100cqw, calc(100cqh * var(--ar)))` with the matching height —
  which needs `container-type: size` on the page element. The distortion
  inflates any "fill %" metric, so it reads as success. (b) A crop scales its
  image far beyond the frame (~5.5x here); without `overflow: hidden` on the
  crop frame, each cell renders its neighbours.
- **Proven by** — Old Spice (24 plates; fill 21.8-43.5% -> 28.6-64.6% with
  aspect preserved on every cell).

---

## 30. Merge slides on mobile by collapsing, never by removing

- **Symptom** — Three destination dividers each wanted to merge into the key
  visual that follows, taking mobile from 34 screens to 31 while the editor
  still had to address 34 slides.
- **Root cause** — Under the single-DOM build (rule 22) the sections ARE the
  editor's slide list. Deleting three of them would change desktop and drop the
  editor's rail and counter to 31, breaking the mapping between what an editor
  addresses and what exists.
- **Rule** — A mobile merge collapses the section to zero height and overlays
  its content on the neighbour; **the section is never removed**. The DOM keeps
  one `<section class="slide">` per source slide, so rail, counter, `data-slide`
  ordinals, `.L > .t` and every body hook keep their places, and the live-text
  total is unchanged (nothing removed, nothing duplicated). The screen count and
  the slide count are then allowed to differ, and that difference is purely
  visual. *Assertion:* `section.slide` count always equals the source slide
  count, whatever the viewport; a capture step must skip zero-height sections
  rather than fail on them, and must not report them as "short sections".
- **Carry the merged slide's ground with its text.** The Old Spice destination
  names are `bg1 + lumMod 50%` grey — correct on the divider's own white slide,
  invisible over a photograph. Recolouring the text would be inventing; giving
  the title its own slide's background preserves both the authored colour and
  the contrast relationship it was chosen for.
- **Proven by** — Old Spice (slides 4/14/24 merged into 5/15/25: 31 visible
  screens, 34 sections, 34 rail entries, 34 headline hooks, 2,058 chars).

---

## 31. Split a multi-unit photograph with crop windows, never by cutting new files

- **Symptom** — Every product plate is a single image shape, so a mobile swipe
  carousel could only come from splitting a photograph.
- **Root cause** — The obvious implementation writes N new image files, which
  rule 6 forbids: no synthetic image bytes may enter the pipeline.
- **Rule** — Emit N `<img>` elements pointing at the SAME asset, each with its
  own CSS crop window — the technique the Olay badge sprite already used. Bytes
  are untouched (rule 6), the asset is still one file and one URL (rule 7), and
  every element still carries a literal `src` for the editor. Derive the windows
  by measuring the source, never by hand-tagging slides.
- **Measure the gutters against the right signal, and verify the probe before
  trusting a negative.** A first pass tested transparency (`alpha > 8`) and
  reported zero splittable slides deck-wide — which looked like a clean negative
  and was a broken probe. Two backgrounds were in play: RGBA product shots whose
  units are separated by a SOFT GROUND SHADOW (alpha spans the full width, so
  threshold high — `alpha > 200` isolates product from shadow), and RGB label
  artworks with no alpha at all (measure distance from the corner background
  colour). *Assertion:* a detector that returns "no units anywhere" on a deck
  that visibly has them is a broken probe, not a finding — check it against a
  handful of images by eye before acting on it.
- **Refusing to split is a valid result.** Units that overlap or share a shadow
  produce no gutter and correctly return one unit; a cut there would run through
  product. Old Spice: 15 slides split (2-3 units), 9 refused — an unfolded box
  dieline (one connected object) and two overlapping arrangements.
- **Proven by** — Old Spice (24 plates, 48 cells, one asset per slide).

---

## 32. A merged title keeps its own ground — don't recolour it, don't rely on a shadow

- **Symptom** — Old Spice's destination names, merged onto the key visual that
  follows, were clipped at the section edge and barely readable: mid-grey text
  sitting on a bright photograph.
- **Root cause, part one (the clipping)** — a shape carries an inline
  *percentage* height from the desktop canvas. Rule 30 collapses the merged
  section to zero, so that percentage resolves to **0**: the box becomes padding
  only, the glyphs render outside their content box, and they are clipped. The
  generic `.sh { height: auto }` does not reach it, because the more specific
  merged-title rule overrides position and width without restating height.
  *Whenever a rule collapses a container, restate `height: auto` on anything
  inside it that was sized in percent.*
- **Root cause, part two (the contrast)** — the title's colour was chosen
  against the slide it came FROM. Old Spice's names are `bg1 + lumMod 50%` grey,
  correct on the divider's white slide and invisible over a photo. Moving the
  text without its ground breaks a figure/ground pair the author set.
- **Rule** — When a merge relocates text onto imagery, carry the SOURCE SLIDE'S
  OWN RESOLVED BACKGROUND with it as a scrim behind the text. Ranked against the
  alternatives:
  * **scrim from the source slide's ground** — chosen. Preserves the authored
    colour exactly, and the scrim is not invented: it is the ground the author
    already paired with that text, relocated alongside it. Derivable on any deck
    (every slide has a background), so no per-deck taste is involved.
  * **drop shadow** — rejected. It adds edge separation, not contrast, and fails
    precisely for MID-TONE text: `#808080` over a mid-bright photo stays
    illegible however deep the shadow.
  * **recolour** — rejected. The only option that changes authored content,
    which rules 12 and 14 forbid; it also breaks desktop/mobile equivalence for
    the same string.
  *Assertion:* a merged title's rendered text height is non-zero and its text
  box sits inside its own background box; the scrim colour equals the source
  slide's resolved background.
- **Scope note** — this covers text the pipeline MOVED. Text the author placed
  over a photo in the first place keeps whatever contrast they gave it: it reads
  the same on both builds and in ground truth, and "fixing" it would be an
  editorial change, not a conversion. Old Spice's "KEY VISUAL" label is that
  case and was deliberately left alone.
- **Proven by** — Old Spice (slides 4/14/24 merged into 5/15/25).

---

## 33. Drop the shape, carry the ground — a canvas composition device is not a mobile one

- **Symptom** — Old Spice slide 3's title is a red ELLIPSE holding white text. On
  the 16:9 canvas it reads as deliberate design, balancing the variant table
  beside it. At 390px, with the table transposed into stacked cards, the same
  shape reads as a stray red blob floating below the content.
- **Root cause** — The shape is a composition device for a layout that no longer
  exists after the reflow. Its geometry was chosen against a canvas; its
  position was chosen against a table that mobile does not draw. On mobile the
  thing that matters is the *title*, not the shape carrying it.
- **Rule** — When a reflow transposes the content a shape was composed against,
  render the shape's TEXT in the mobile idiom — for a label, a plain full-bleed
  header at the top of the section, matching how other labels in the deck sit —
  and drop the geometry (`border-radius`, rotation, decorative sizing). Desktop
  keeps the shape exactly as authored.
- **Dropping the geometry is NOT dropping the fill.** This is rule 32 restated
  from the other direction: a shape's fill is the GROUND its text colour was
  chosen against. Slide 3's title text is `#FFFFFF` — 7.42:1 on the red ellipse,
  and **1.00:1 (invisible) on the white ground it would land on** if the fill
  were stripped while the authored colour was kept. *Assertion:* before removing
  a shape's fill on mobile, compute the contrast of its text against whatever
  would then be behind it; if it fails, the fill is load-bearing and only the
  geometry may go.
- **The same distinction decides what stays.** A backdrop rect spanning the
  canvas IS the slide's ground and must survive the transpose; a narrower one is
  a rail framing desktop content and should not. Key it off measured width, not
  a slide number. Hiding both on Old Spice slide 3 removed the white ground and
  exposed the authored green beneath it.
- **Watch flex-basis again** — `flex: 0 0 100%` from a generic rule overrides a
  more specific `width`, so a full-bleed header stops at the content box. Size
  it with `flex-basis`, not `width` alone (same trap as rule 22's badges).
- **Proven by** — Old Spice slide 3 (ellipse -> flat header, ground preserved,
  section still one screen).

---

## 34. The autofit line-height ratio is PowerPoint's, not the font's (amends rule 17)

- **Symptom** — Rule 17 recovers a line-height ratio from `<a:spAutoFit/>` box
  heights and treats it as a property of the source face, corroborating a
  substitute choice. Deck 6 (Olay) cited Franklin Gothic Book's recovered
  1.2121 as evidence that Archivo was the right match.
- **Root cause** — The ratio does not vary with the face. Five unrelated faces
  across three decks measure the same number to within 0.18%:

  | Face | Deck | Recovered ratio |
  |---|---|---|
  | Franklin Gothic Book | Olay | 1.2121 |
  | Gotham Black | HenHouse | 1.2129 |
  | Aptos | HenHouse | 1.2132 |
  | Boston SemiBold | Olay | 1.2140 |
  | DIN Condensed | Old Spice | 1.2143 |

  A humanist sans, a geometric sans, a neo-grotesque and a condensed grotesque
  have materially different `hhea`/`OS/2` metrics; they cannot all share a
  line-height ratio. What the solve actually recovers is **PowerPoint's autofit
  line spacing**, a constant of the layout engine that the box height happens to
  encode. It is invariant *because* it is not a font metric.
- **Rule** — Split rule 17's oracle in two and keep only one half as evidence:
  - The **line-count test discriminates.** Whether a substitute wraps the
    authored strings to the same line counts at the same authored widths is a
    measurement of advance widths, which *are* face-specific. This is the part
    of rule 17 that picks a substitute, and it stands unchanged.
  - The **ratio test does not discriminate.** A candidate reproducing the
    recovered ratio has demonstrated nothing — every candidate will. Never cite
    it as corroboration for a face.

  The ratio remains worth recovering, for a different purpose: it is the value
  to set `line-height` to explicitly, so the substitute's own (Archivo's 1.088,
  11% too tight) is not inherited. Recover it to *render* with; never to
  *choose* with. *Assertion:* any deck note justifying a substitution must cite
  line counts; a note citing only a ratio is unsupported and must be re-derived.
- **Proven by** — HenHouse (deck 8). Gotham Black @60pt -> 1.2129 and the
  inherited Aptos runs -> 1.2161 @16pt / 1.2132 @24pt, agreeing with two faces
  from two earlier decks that share no lineage with either. Recorded in
  `ondeck/parse/font_calibration.SOURCE_LINE_HEIGHT_RATIOS`. HenHouse's own
  Montserrat choice is unaffected: it rests on the one-line width fit of the
  "MAKES" box (228.7pt rendered into 228.8pt available, wght=900 needing
  231.3pt and wrapping), which is a line-count argument.

---

## 35. A composited slide background must be consumed on every breakpoint (amends rule 20)

- **Symptom** — HenHouse slides 1 and 52 rendered a near-black ground on desktop
  where the PPTX has cream. Text and logo were correct; only the ground was
  wrong. Mobile was correct on the same slides, from the same build.
- **Root cause** — Rule 20 was implemented as a *value* and not as a *contract*.
  `composite()` correctly resolved `<a:srgbClr val="8F993E"><a:alpha val="7721"/>`
  against the master background into an opaque `--bg-solid:#F6F7F0`, and emitted
  it on every canvas. But only the mobile `.canvas` rule read it; desktop still
  read the raw `--bg:rgba(143,153,62,0.0772)`, so `section.slide{background:#111}`
  became the ground and the tint composited against the page after all — the
  exact failure rule 20 names. Producing the right value proves nothing if a
  consumer still reads the wrong one.
- **Rule** — Key it off the measured signature **`bg_alpha < 1.0`**: any slide
  whose background carries alpha is composited against the resolved master
  background at build time, and **every** breakpoint consumes the composited
  value. A translucent slide-background value may exist in the document for
  provenance, but nothing may paint with it. *Assertion:* for each breakpoint,
  the declaration that paints the slide ground resolves to the opaque property,
  and no emitted slide-background colour carries an alpha channel. Assert this
  per breakpoint, not once — a single-breakpoint check passes while the other
  half of the build is wrong.
- **This is NOT rule 28.** No transform was dropped: the source carries `alpha`
  and nothing else — no `lumMod`, no `lumOff`, no tint or shade — and
  `deckkit.Ctx.solid()` already routes through `ColorResolver`. Rule 28 is a
  *producer* defect (a builder reading `schemeClr/@val` and skipping the
  transform); this is a *consumer* defect (a correctly-resolved value that one
  consumer ignores). Fixing this retires nothing about the Olay slide 9/10 wash
  defect, which was retired separately when deckkit adopted `ColorResolver`.
- **The visible symptom under-reports the blast radius.** Slides 1 and 52 were
  reported because 73.7% of their canvas is bare ground. **All 13 slides with
  `bg_alpha < 1.0` were wrong** — 12-15 and 37-40 rendered `#565656`/`#4F4F4F`
  greys for `#F8F8F8`, 47 `#636C61` for `#F2FBF1`, 48 `#212112` for `#EBEBDC`,
  49 `#A2A2A2` for pure white. Slide 49 is the proof of mechanism: `#FFFFFF` at
  61% over a white master is arithmetically a no-op, so the only way it can
  render mid-grey is if the page, not the master, is the ground.
- **Proven by** — HenHouse (13 slides; 11 of 13 match a LibreOffice render of
  the source to <=1/255 after the fix, across alphas 0.077-0.608).
- **Sibling instance, same family, different shape** — a rule can also be dead
  because its TARGET is not live at the breakpoint it is gated to. The Global
  Image builder's Patchology output unlocks `#deck` scrolling at
  `max-width:768px` while hiding `.deck` at `max-width:767px`, so the unlock
  applies only in a 1px sliver. Checking that a declaration exists is not
  checking that anything consumes it; resolve the selector against the DOM at
  that width. Recorded in NOTES (2026-08-24).

---

## 36. Deck Editor v14 externalises `img`/`video` srcs and nothing else — a CSS-painted asset ships inline

- **Symptom** — Published Old Spice
  (`oldspicepackaging.globalimaige.com`) is 3.51 MB, of which **3.45 MB —
  98.3% — is still `url(data:...)` inside a `:root` block.** Its 39
  `<img>`/`poster` srcs were rewritten to R2 correctly. The deck renders fine,
  which is why it went unnoticed for months.
- **Root cause** — The editor's media enumeration walks **elements**: it
  rewrites `src` and `poster` on `img` and `video`. It does not walk CSS, so
  `url(data:...)` inside a `<style>` block is invisible to it and survives the
  round-trip untouched. Deck 7's embed step had introduced a genuine
  optimisation — a crop half painted from `background-image: var(--aN)` with
  the asset inlined once into `:root`, saving real bytes because an
  `<img src="data:">` cannot share bytes with another element. That trade is
  correct for a self-contained file and exactly wrong for a file that is about
  to be externalised: the deduped assets are the ones that never reach the CDN.
- **Rule** — **Any asset that must reach the CDN has to be referenced by an
  `img` or `video` element with a literal `src` (or `poster`).** An asset
  painted from CSS will publish inline. Where a deck's embed step dedupes
  assets into custom properties, that dedupe must be **opted out per deck**
  before import — it trades input-file size against CDN delivery, and the
  published deck is smaller without it even though the input file is larger.
  `@font-face { src: url(data:font/...) }` is the one legitimate exception:
  fonts are not media assets and have no element to carry them.
  *Assertion:* before import, every `data:` payload in the document is
  reachable through an `img`/`video` `src` or `poster`, with `@font-face` the
  only permitted CSS-resident exception. Count them and make them balance.
- **The workaround is per-deck; the real fix is the editor.** Opting out of
  dedupe costs input size and nothing else. Teaching the editor to rewrite
  `url(data:...)` inside `<style>` fixes it once for every deck and
  retroactively unblocks re-import of anything already published this way.
- **Proven by** — Old Spice (live: 15 properties, 3.45 MB of 3.51 MB never
  externalised, 39 element srcs rewritten correctly). HenHouse would have
  shipped **2.49 MB** the same way — 7 properties, 3.9% of a 63.14 MB input.
  Dedupe disabled for its import: file grew to 65.63 MB, `url(data:)` inside
  `:root` fell to **0**, and all 109 payloads became reachable as 93 `img`
  srcs + 7 `video` srcs + 7 posters + 2 `@font-face`. Rendering is unaffected —
  the crop-half markup is byte-identical to the signed-off folder build and
  slide 38 pixel-diffs at **0/255**.

---

---

## 37. Upload media through the R2 modal, never one-click Publish — a swallowed upload ships a deck of 404s

- **Symptom** — On a deck with external media (relative `src="assets/..."`), the
  editor's one-click **Publish** reports five of six steps green and one amber
  `⚠ skip`, then puts a deck live in which **every image and video 404s**. On a
  deck mixing inline and relative media it additionally leaves objects written
  to the R2 prefix with no corresponding HTML rewrite.
- **Root cause** — Two defects compounding.
  1. `doR2Silent()`, the **publish** flow's uploader, has no `needsFile` branch
     — the one `doR2Upload()`, the **modal's** uploader, does have. Handed a
     relative `src` it calls `dataUriToBlob()`, whose
     `uri.split(',')[0].match(/:(.*?);/)` returns `null` on a plain path, and
     throws `TypeError: Cannot read properties of null (reading '1')`.
  2. `doPublish` wraps that call in `try{...}catch(e){setStep(...,'⚠ skip','err')}`
     **with no rethrow.** Control falls straight through to build, create-repo
     and push. Only `index.html` reaches `gh-pages`, so every relative path
     resolves to nothing.
  The uploader iterates in document order and the rewrite block sits *after*
  the loop, so any `data:` assets ahead of the first relative one are already
  written to the bucket when it throws while `rawHTML` is never updated at all.
- **Rule** — Media reaches R2 through the explicit **`Upload to R2`** modal,
  which handles both `data:` and relative-path media (**Select Media Folder** →
  `showDirectoryPicker()` → uploads the File off disk → rewrites the `src`).
  **The one-click `Publish` button is not used on any deck with external
  media.** After uploading and before exporting, assert `collectMedia()`
  returns zero `needsFile` items and that no `src` in the document is still
  relative. A `⚠ skip` on the R2 step is a **stop, not a warning**: assume the
  prefix is contaminated, inspect it, and move to a fresh one rather than
  overwrite — objects are served `immutable` for a year and cannot be repaired
  in place (see NOTES 2026-08-25 on the Deck Name field).
  *Assertion:* before push, every `img`/`video` `src` and `poster` resolves to
  `https://` on the media host under the **intended** prefix; count them and
  balance against the asset manifest.
- **Why this is worse than the Olay / Old Spice prefix collision** — that
  collision wrote *valid images* to the wrong prefix, so both decks still
  rendered and the damage was one client's packaging appearing on another's
  slides. This ships a deck where **nothing** renders, and it announces itself
  as one amber line in an otherwise green list. Both are invisible at publish
  time; this one is also invisible in the artefact, because the HTML is
  correct — the bytes it points at were simply never uploaded.
- **The workaround is per-deck; the real fix is the editor** — same shape as
  rule 36. `doR2Silent` needs the `needsFile` branch `doR2Upload` already has,
  and that `catch` must rethrow rather than downgrade a failed upload to a
  skipped step.
- **Proven by** — Deck 9 pre-build capability testing, 2026-08-26. Minimal
  2-slide fixture, three relative-path assets, local mock Worker recording what
  it was asked to store. Modal: **3/3 uploaded from disk, 3/3 srcs rewritten**;
  mixed inline+relative also clean. Publish: **threw, 0 uploaded, 0 rewritten**;
  mixed inline+relative left **1 object in the bucket and 0 rewrites**. No real
  deck, bucket or prefix was touched.

## 38. An embedded font is EVIDENCE, never a shipping asset — measure it, don't serve it

- **Symptom** — Deck 10 (Secret) is the first deck in the corpus to embed its
  fonts: 6 `.fntdata` parts and a `<p:embeddedFontLst>` covering Aura AT, Bebas
  Neue, Univers and Univers Condensed. The obvious move is to convert them to
  woff2 and finally stop substituting. That move is wrong on three separate
  counts, any one of which is disqualifying.
- **Root cause** — A PPTX font embed is a *rendering* licence inside PowerPoint,
  not a redistribution licence. Three independent blockers:
  1. **Licence.** Univers is Linotype and Aura AT is proprietary. Serving either
     as woff2 from a public deck is redistribution, and the deck is published on
     a public GitHub Pages origin under a client's hostname. This is the
     blocker that does not care how technically easy the extraction is.
  2. **Subset.** 5 of the 6 parts carry the EOT `SUBSET` flag — they contain
     only the glyphs the deck currently uses. The Deck Editor exists so a client
     can edit text; the first character they type outside the subset renders as
     `.notdef`. A shipped font that breaks on edit is worse than a substitute
     that does not.
  3. **Format.** All 6 are EOT v2.2 with `TTCOMPRESSED` (MicroType Express).
     There is no decompressor to hand, so the glyph data is not readable here
     anyway.
- **Rule** — **Read the embedded font's HEADER for evidence; never extract,
  convert, bundle or serve the font data.** The EOT header is uncompressed and
  carries exactly the facts a substitution decision needs: PANOSE (proportion,
  weight, family class), OS/2 weight, italic flag, and the authored family /
  style / full names. That is a free, licence-clean measurement of *what the
  face is*, which is the question rule 10 and rule 34 actually ask. Getting the
  bytes would answer a question nobody is allowed to act on.
  *Assertion:* no `.fntdata`/EOT payload is ever written to `render/fonts/`,
  referenced by an `@font-face`, or committed; a deck's embedded fonts may be
  cited in its notes as measurement evidence only.
- **What the header settles that the autofit oracle cannot** — rule 17's oracle
  needs `<a:spAutoFit/>` boxes, and rule 34 narrowed it further to the
  line-COUNT test alone. Deck 10 has 4 autofit boxes and **all 4 carry
  `wrap="none"`**, which nullifies the width test (the Old Spice condition), and
  all 4 are Univers *Condensed* — so there is **zero** oracle surface for plain
  Univers, the deck's dominant face at 128 slide references. The PANOSE
  proportion byte answered in one read what the oracle could not answer at all:
  `Univers` is **3 = Modern** (normal width) and `Univers Condensed` is
  **6 = Condensed**. Two different width classes, stated by the file.
- **What it still does not settle** — PANOSE gives a width *class*, not advance
  widths. It can prove a mapping wrong; it cannot prove one right. A substitute
  chosen on class alone is provisional in exactly the sense rule 34 means, and
  must be labelled so.
- **Proven by** — Deck 10 (Secret), 2026-08-27. Header parse across all 6 parts;
  EOT v2.2, magic `0x504C`, flags `SUBSET|TTCOMPRESSED`. Recovered autofit ratio
  **1.2135** (Univers Condensed 40pt), a sixth independent confirmation of rule
  34's PowerPoint constant alongside 1.2121 / 1.2129 / 1.2132 / 1.2140 / 1.2143.

---

## 39. A Google Slides export puts grounds on the LAYOUT — walk slide → layout → master (companion to rule 38)

- **Symptom** — Deck 10's first render came out yellow where the source is
  Secret blue, on 9 of 31 slides. The five chapter dividers lost the blue panel
  that is half their composition, and four section slides lost their background
  outright. Every assertion passed while it happened: 22/22, including "no
  hardcoded aspect", "live text preserved", "no z-index". Only a LibreOffice
  ground-truth render caught it.
- **Root cause** — Three separate links of PowerPoint's inheritance chain were
  never implemented, because four PowerPoint-authored decks never used them.
  This deck was exported from **Google Slides**, which places design on the
  layout rather than on the slide or the master:
  1. **Layout SHAPES were not rendered at all.** `slideLayout3` carries
     `Google Shape;37;p9`, a non-placeholder rect, `#A7C6ED`, exactly
     half-canvas by full-height — the blue panel. The builder walked slide
     shapes only.
  2. **Layout `<p:bg>` was not read.** The chain ran slide → master, skipping
     the middle link. `slideLayout2` declares `<p:bg>` `#A7C6ED`; four slides
     inherited the master's `lt1` (`#F1C232`, yellow) instead.
  3. **Layout placeholder `<a:lstStyle>` sizes were not resolved.** The divider
     titles carry `<a:rPr lang="en-US" dirty="0">` with no `sz`; the size lives
     on the layout's title placeholder as `sz="7300"`. They rendered at the
     deck default of 14pt — a 73pt display title at a fifth of its size.
- **Rule** — Resolve background, shapes and inherited text size through
  **slide → layout → master**, all three. Render every non-placeholder layout
  shape, emitted BEFORE the slide's own so paint order puts them beneath
  (rule 21: DOM order is paint order). Exclude placeholders — the slide
  supplies their content, and drawing the layout's copy doubles every title.
  Treat `<a:noFill/>` as "this level paints nothing", NOT as "this level says
  nothing": it must fall through to the master rather than be read as a colour.
  *Assertion:* pin the count of inherited layout shapes and the set of slides
  that inherit a layout background; a deck revision that changes either fails
  the build.
- **Do not gate layout shapes on z-position.** "Only render layout shapes that
  sit beneath slide content" is a condition the format does not have — the
  layout renders regardless — and it would have bought nothing here, since the
  19 plate slides use a BLANK layout carrying no shapes at all. A rule that is
  inert on the deck that motivated it and silently wrong on the next one is the
  worst of both.
- **The origin is detectable, and worth detecting early.** Shape names like
  `Google Shape;152`, layouts named TITLE / SECTION_HEADER / BLANK / CUSTOM_11,
  and a theme pair of "Simple Light" (slides) + "Default" (notes). Any of the
  three should prompt a layout-inheritance check BEFORE the first render.
- **This is rule 38's companion.** Both are the same lesson from the same deck:
  what a converter has never seen, it has never handled, and four decks of
  agreement is not coverage. Rule 38 is about a font surface never exercised;
  this is about an inheritance surface never exercised.
- **`<a:noFill/>` on a layout means "paint nothing" — a JUDGEMENT, not a spec
  reading.** ECMA-376 does not settle whether a layout background of `noFill`
  is an explicit empty ground or a silence that inherits the master. Recorded
  as a judgement so nobody later reads it as proven, the same way the Univers →
  Archivo call is recorded. The evidence for taking it:
  * **Ground truth across all 31 pages shows no yellow background anywhere.**
    On the slides where the inherit-the-master reading paints yellow, GT is
    `#FFFFFF` — s5 11.78% yellow vs GT 0.00%, s11 16.22% vs 0.17%. The 2-3% on
    s17/s20 is product photography, not ground.
  * **The consistency argument.** Under the inheriting reading the master's
    `lt1` would paint on **24 of 31** slides. It appears on none.
  * A theme whose `lt1` is `#F1C232` while all six accents are `#FFFFFF` is a
    vestigial Google Slides export block. Under this reading it never paints,
    which is exactly what the file renders as.
  If a future deck contradicts this, it is this entry that is wrong, not the
  deck — re-derive rather than special-casing.
- **The chain is EVERY inherited property, not the three you noticed.** The
  first fix walked slide → layout → master for background, shapes and font
  size, and desktop review failed on three further symptoms that were all the
  same omission: `anchor` and the four insets also live on the layout
  placeholder (deck 10's slide-level bodyPr is literally `<a:bodyPr/>`), and
  with 73pt type in a 68.5pt box the anchor decides whether the overflow
  splits above and below or falls entirely into the content beneath it. Fixing
  an inheritance chain three properties at a time costs a review round each
  time. Walk the whole `bodyPr`.
- **Two OOXML→CSS translations where the same word means different things:**
  * `spcPct` is a multiple of SINGLE LINE SPACING; CSS `line-height` is a
    multiple of FONT SIZE. Emitting `line-height:2.06` for `val="206000"`
    advanced 9pt labels 18.5pt against a measured badge pitch of 21.86pt — a
    full row of drift over eight rows. Multiply by the source face's
    single-line spacing; a deck that has autofit boxes has already measured it
    (rule 17/34). **CORRECTED TWICE, 2026-08-28. Read the second correction;
    the first was wrong.**

    *First correction.* The constant was mis-recovered: 1.2135 is
    `1.21172 + 0.07034/40`, the per-box term charged to a single 40pt line
    (rule 17, amended). The corrected value is **1.21172**. It stands, and it
    is not what follows is about.

    *Second correction — a PREDICTION MADE HERE AND FALSIFIED.* The first
    correction went on to claim that the "2.9% loose" residual was authored
    geometry, that the badge column would therefore **drift against its labels
    in PowerPoint too** on slides 4/9/14 and not on slide 21, and it flagged
    that as unverified. **Sean's PowerPoint screenshots of both dividers
    falsify it by direct observation: slide 4 shows all eight badge/label pairs
    aligned identically and slide 21 all five. There is no drift in PowerPoint
    at either size.**

    * **What broke is narrower than the constant.** 1.21172 was fitted only to
      `spAutoFit` boxes at **`spcPct = 100%`**. The step from "per-line autofit
      increment = 1.21172 x size" to "line advance at 206% = 2.06 x 1.21172 x
      size" was an **untested assumption**, and it is that step the screenshots
      break — not the constant, which slide 21 confirms. The corpus contains no
      `spAutoFit` box at non-100% spacing outside venus_hestia's 26 wrapped
      multi-line boxes, whose line counts are unknown, so nothing in four decks
      of PowerPoint-produced files can settle it.
    * **The oval pitches ARE genuine readouts after all.** The first correction
      dismissed them as "a fixed authored placement, not an oracle". Every
      shape on slide 4 is PowerPoint-authored — `Title 3`, `Subtitle 4`,
      `TextBox 5`, `Picture 7`, `Oval 9`-`Oval 17`, zero `Google Shape;NNN`
      names — so the ovals were positioned in PowerPoint against PowerPoint's
      own rendering, and the screenshots confirm the author aligned them. The
      pitch therefore measures PowerPoint's line advance at 206%:

      | slide(s) | size | oval pitch | implied base |
      |---|---|---|---|
      | 4 / 9 / 14 | 9pt | 21.86263 pt | **1.179214** |
      | 21 | 12pt | 29.96260 pt | **1.212079** |

      Same face (Univers), same `spcPct` (206000), **2.79% apart**.
    * **No current model reproduces that.** A per-face constant cannot be
      size-dependent by construction — font metrics scale linearly. Rounding
      cannot either: one base requires a pitch ratio of `12/9 = 1.33333`, and
      the measured ratio is `380525/277655 = 1.370485`, **2.8% out**, orders of
      magnitude beyond EMU rounding, and neither figure is a multiple of any
      plausible quantum. **PowerPoint's line advance at non-100% `spcPct` is
      size-dependent in a way nothing here explains. UNRESOLVED — do not fit a
      mechanism to these two points.**
    * **DO NOT adopt 1.179214.** It would improve slides 4, 9 and 14 and break
      slide 21, which the screenshots confirm is currently correct. The
      standing defect is therefore that **our render still drifts 0.6023pt/row,
      4.21pt over seven rows, on slides 4/9/14 against a PowerPoint that does
      not drift at all** — knowingly carried, because the only known
      alternative breaks a slide that works.
    * **Both discarded figures were computed the same way.** The original "2.9%
      loose" and the 9pt/12pt split were both measured against the authored
      oval pitch. That pitch is a fixed placement — a repeated integer,
      277655 EMU x6 with a 3-EMU blip on the last gap — and it took a
      screenshot, not the file, to establish that it nonetheless tracks
      PowerPoint's line advance. **An implied factor is only evidence once you
      know what the quantity it is implied from is a measurement OF**, and that
      question is often not answerable from the file at all.
    * **Component B is untouched and still unexplained.** The constant
      badge-to-label offsets — **+3.90pt** on slides 4/9/14 and **+1.79pt** on
      slide 21 — are first-line leading placement, not pitch. Nothing in either
      correction addresses them.
  * `wrap="square"` wraps at the BOX EDGE, breaking mid-word when a single
    token does not fit — ground truth renders COLOR+TREATMENT as
    COLOR+ / TREATM / ENT. CSS needs `overflow-wrap:anywhere`; without it the
    token has no break opportunity and runs off the canvas.
- **Proven by** — Deck 10 (Secret), 2026-08-27. 9 of 31 slides affected.
  Ground-truth mean delta on the four layout-background slides fell from
  27.20 / 50.98 / 18.86 / 20.01 to 13.44 / 10.02 / 5.37 / 4.52; the three
  sampled plate slides were byte-unchanged, confirming the fix is scoped to
  slides that actually inherit.

---

## 40. LibreOffice is not a fidelity reference for a deck whose fonts it lacks (limits rule 16)

- **Symptom** — Deck 10's desktop review was argued for two rounds off
  LibreOffice ground truth. "GT confirms the source overflows" was stated for
  the cover and for OBJECTIVE, and a fidelity-vs-legibility decision was put to
  the client on that basis. **All of it was wrong.** Sean's screenshots of the
  deck in actual PowerPoint show nothing overflowing: BEAUTY sits on one line,
  OBJECTIVE clears its body copy, VISUAL HOOKS fits its box.
- **Root cause** — LibreOffice does not have Aura AT, Univers or Bebas Neue and
  substitutes all three. Every comparison was therefore **one substitution
  measured against another**, and the question under test was a substitution
  question. The reference was structurally incapable of answering it.
- **Rule** — Rule 16 makes a LibreOffice render a **positional/layout** sanity
  check, and that check is only valid for text set in fonts LibreOffice
  actually has. **Before citing GT on anything involving type — wrapping,
  overflow, collision, line count, box fit — verify the renderer resolves the
  same face.** If it does not, GT can still corroborate geometry (box
  positions, fills, image placement) but says nothing about the type.
  *Assertion:* a note citing ground truth for a typographic claim must record
  which face the reference renderer used; if it substituted, the claim is
  unsupported and must be re-derived.
- **What to use instead when the reference cannot resolve the face** — the
  deck's own geometry. Every authored string sits in an authored box at an
  authored size, so the box gives a **width budget** in em that any candidate
  face must satisfy. That is measured from the file, needs no reference
  renderer, and it is what finally identified deck 10's real defect: BEAUTY
  budgets 2.947 em and Arial needs 4.001 em, so the face resolution — not the
  box, not the size, not "authored overflow" — was always the bug.
- **The narrower true statement, so "nothing overflows" is not read too
  broadly.** Some strings DO wrap in PowerPoint. PRODUCT SILOS budgets
  **0.289 em/char**, which no cap-height face achieves, so the divider titles
  wrap in PowerPoint too. The distinction that matters is **wrapping inside
  their own column versus colliding with adjacent content**: the dividers do
  the former and always did. What was wrong was the claim that the display
  titles collide.
- **Proven by** — Deck 10 (Secret), 2026-08-27.

---

## 41. OOXML properties that do not survive a naive CSS translation — and the method traps that hide them

Deck 10 (Secret) surfaced six of these in one build (a)-(f), then ten more in a
second (g)-(p). They are grouped because they share a shape: **a property the
source states plainly, that the renderer either never reads or translates into
a CSS construct with different semantics.** Each was invisible in code review
and each produced output that looked deliberate.

(a)-(f) are all text-layout properties, which is what the entry was originally
titled for. (g)-(k) extend that to the inheritance chain those properties
travel down; (l) is a PICTURE FILL property and is here because it fails the
same way; (m)-(p) are the METHOD traps that let the rest survive review. The
heading widened rather than splitting because the lesson is one lesson.

### (a) `wrap="none"` must emit `white-space:nowrap`

- **Symptom** — a lone `0` floating above a divider title. Both characters were
  in the DOM; `01` had broken into `0` / `1`.
- **Root cause** — the shape declares `<a:bodyPr wrap="none">`, which OOXML
  defines as *never wrap, overhang the box instead*. The renderer captured
  `wrap` in the model and emitted nothing for it, so a **0.01pt** overflow (a
  50.39pt box with 14.4pt of default insets = 35.99pt inner, against 36.00pt of
  type) became a mid-token break.
- **Rule** — emit `white-space:nowrap` for any shape whose resolved `bodyPr`
  says `wrap="none"`. Overhang is the correct outcome there and must not be
  suppressed. *Assertion:* count `wrap="none"` shapes in the source and assert
  the same count of `white-space:nowrap` in the output.
- **The symptom is VIEWPORT-DEPENDENT, which is why it hid.** At 0.01pt the
  break sits inside sub-pixel rounding: it broke at 1280x720 and 1680x945 and
  did not at 1440x810, 1456x834, 1512x860 or 1920x1080. Two review rounds at
  1440/1456 never saw it. **A layout defect measured at one viewport width is
  not a defect that has been measured.**

### (b) An authored `<a:br/>` inside a paragraph must be honoured

- **Symptom** — `COLOR+` and `TREATMENT` rendered as the single unbreakable
  token `COLOR+TREATMENT`, which then either broke mid-word or overhung its
  column by 84%.
- **Root cause** — the runs are separated by `<a:br/>`, not by a space. The
  MODEL captured it correctly as `br_after` (added for HenHouse, deck 8, where
  the beef-cut names concatenated into "RibeyeStripChuck Eye..."), and
  `model.json` carried it. Only HenHouse's renderer consumed it; **olay,
  oldspice, venus_hestia and secret never read it.** The break opportunity was
  authored all along and the renderer discarded it.
- **Rule** — emit `<br>` after any run carrying `br_after`. Honour it even when
  the run itself has no text: a break recorded against an empty run is still an
  authored break. Now shared as `phase_1c/deckkit/markup.py::runs_html`,
  behaviourally identical to HenHouse's inline loop so that builder can migrate
  without moving a byte. *Assertion:* `<a:br>` count in source == `<br>` count
  in output.
- **Diagnostic worth keeping** — the give-away was that the DOM text had NO
  space between the runs. A missing space suggests stripped whitespace; check
  for `<a:br/>` before hunting a whitespace bug. Deck 10's `<a:t>` elements
  carry no `xml:space` and no leading or trailing space at all -- there was
  never whitespace to strip.

### (c) CSS percentage padding resolves against WIDTH, never height

- **Symptom** — nine badge shapes per divider reported a +5.55pt vertical
  overhang, and the chapter numbers +8.56pt.
- **Root cause** — vertical insets were emitted as a percentage of canvas
  HEIGHT (`ins.t / H * 100` as `%`). Per CSS, **all four padding percentages
  resolve against the containing block's WIDTH.** Every vertical inset was
  therefore inflated by the deck's aspect ratio -- 720/405 = 1.778, i.e. **78%
  too large**: an authored 7.2pt inset resolved to 12.80pt and a 3.6pt one to
  6.40pt.
- **Rule** — emit vertical insets in a unit that resolves against height.
  `cqh` works and needs nothing new: the canvas already declares
  `container-type: size` for `cqw` type sizing, so `1cqh` is 1% of canvas
  height, which is exactly what the number already was. Horizontal stays `%`,
  which is correct against width. *Assertion:* computed `padding-top` in the
  browser equals the authored `tIns` in points.
- **It manufactured two PHANTOM defects and they were mis-filed twice.** The
  badge overhang was reported as "pre-existing and unrelated" and the chapter
  number's as "the line box exceeding the box height". Neither was real: with
  correct insets the badges hold 9.50pt of text in 9.54pt of inner height and
  fit exactly, and the number's true overflow is +2.97pt, not +8.56.
  **A measurement taken through a broken unit conversion is not evidence, and
  calling it "pre-existing" is how it survives two rounds of review.**

### (d) `lnSpc` can sit on `lvl{i}pPr` itself, not only on `defRPr` or the paragraph

- **Symptom** — divider titles rendered 220pt of text in a 68.45pt box.
- **Root cause** — `build_ph_textstyles` read `lvl{i}pPr/a:defRPr` for `sz` and
  `latin`. Layout3's title placeholder declares **73pt AND `lnSpc spcPct
  75000` on the same `lvl{i}pPr`** -- but `lnSpc` hangs off the `pPr`, not off
  its `defRPr`. The size was read, the spacing was not, `model.json` held
  `line_pct: None`, and `line-height` fell to `normal`.
- **Rule** — when reading a placeholder level, read the `lvl{i}pPr` element
  itself as well as its `defRPr`. A paragraph's own `lnSpc` still wins; the
  placeholder's is the fallback, and is authored just as much.
- **The failure mode is rule 17/34 restated.** `line-height: normal` resolves
  to the SUBSTITUTE's natural metric. Here that was Anton at 1.5054 against an
  authored 0.75 -- the substitute's own ratio at double the source's, which is
  exactly what rule 34 says never to inherit.

### (e) Model vertical overflow from INK EXTENT, not line-box sum

- **Symptom** — honouring the authored 75% was projected to cut a title's
  overflow from +165.7pt to +78.8pt. Measured, it went to **+122.6pt**.
- **Root cause** — the projection summed LINE BOXES (2 x 73 x 0.9101 =
  132.9pt). When a face's content area exceeds its line box -- Anton's 1.5054em
  = 109.9pt inside a 66.44pt line box -- the glyphs spill ~21.7pt above and
  below every line. Measured ink extent was 176.7pt.
- **Rule** — for any question about overlap or collision, measure the ink
  extent (`Range.getBoundingClientRect`). The line-box sum understates it
  whenever `line-height` is tighter than the face's natural content area, which
  is precisely when a deck sets tight authored spacing.

### (f) KNOWN LIMITATION — placeholders are keyed by type, not `(type, idx)`

`build_ph_textstyles` and `build_ph_bodypr` key on placeholder TYPE alone. A
layout declaring several placeholders of the same type with different `idx`
keeps only the last. Deck 10's layouts 1 and 5 each declare multiple `subTitle`
placeholders, so four paragraphs resolve against a sibling's entry. **Not
triggered here only because the competing entries agree** (all 80%). On a deck
where they disagree this silently picks the wrong one. Unfixed; `resolve_ph_geometry`
already matches on `(type, idx)` and is the model to copy.

### (g) OOXML alignment values are `l` / `ctr` / `r` / `just`, NOT CSS keywords

- **Symptom** — four shapes that are centred in PowerPoint rendered flush-left.
  It read as an inheritance failure, and an inheritance failure was indeed
  present underneath (see (h)) -- but it was not the cause of what was on
  screen.
- **Root cause** — `secret/render.py` gated on the CSS spellings:
  `if align in ("center", "right", "justify")`. The model value is always an
  OOXML token, so nothing ever matched and **`text-align` was emitted ZERO
  times in the entire document**. 101 paragraphs carrying `algn="ctr"` --
  including 99 badge letters that should sit centred inside their circles --
  rendered flush-left.
- **Rule** — map tokens to keywords explicitly:
  `{"l": "left", "ctr": "center", "r": "right", "just": "justify"}`.
  Venus/Hestia's form is the one to copy because it ASSERTS on an unmapped
  token rather than silently defaulting to `left`.
  *Assertion:* count `algn` values in the model and assert the same count of
  `text-align` declarations in the output. Zero of anything deck-wide is a
  finding, not a null result.
- **The diagnostic that matters** — a defect visible on four shapes was
  actually firing on 101. **Before diagnosing why a property is wrong on the
  shapes you were shown, count how many times it is emitted deck-wide.** Four
  builders had this right; secret was the newest and the only one that wrote
  its own gate instead of reusing the shared idiom.

### (h) `algn`, `marL` and `indent` are ATTRIBUTES of `lvl{i}pPr`, not children of its `defRPr`

- **Root cause** — exactly the gap that hid `lnSpc` in (d), one element over.
  `build_ph_textstyles` descended into `a:defRPr` for `sz` and `latin` and
  never read the element's own attributes, so levels 3-6 of the chain were
  invisible: slideLayout2/3 declare `algn="ctr"` on their title and subTitle
  placeholders, and the master's body placeholder declares `marL="457200"`
  (36pt) with `indent="-317500"` (-25pt hanging).
- **Rule** — when reading a placeholder level, read the `lvl{i}pPr` element
  ITSELF -- its attributes and its non-`defRPr` children -- as well as its
  `defRPr`. `defTabSz` belongs in the same read; deck 10 declares it nowhere,
  so it is unexercised rather than handled.
- **`indent` had no key in the model schema at all**, so even a correct walk
  would have had nowhere to put a hanging indent. **Check that the model can
  HOLD a property before concluding the reader is the only thing missing.**
- **Emit `marL` as the paragraph's left indent and `indent` as the first-line
  indent** -- `padding-left` plus a negative `text-indent`, which is what CSS
  already means by a hanging indent.

### (i) Merge guards must test `is not None`, not truthiness

`resolve_ph_text` merged with `if k not in out and lv.get(k):`. For `sz` and
`face` that is harmless. For geometry it is not: **`marL="0"` and
`indent="0"` are meaningful RESETS** of an inherited indent, and a truthiness
test drops them and lets the outer level win. Deck 10's slide 1 declares
exactly that pair on its cover title against a master that says 36pt/-25pt.
The same applies to any numeric OOXML property whose zero is a statement --
which is most of them.

### (j) Bullet properties inherit, and reading only the paragraph's own `pPr` can be right for the wrong reason

- **Symptom** — none. That is the point.
- **Root cause** — `_paras_of` read `buChar` off the paragraph's own `pPr` and
  treated its absence as "no bullet". Deck 10 has **54 `buNone` declarations**
  the pipeline never saw -- 42 on layout placeholders, 10 on paragraphs, 2 on
  shape `lstStyle` -- and one `buChar` on the master's body placeholder that
  every one of them overrides. **An unread `buNone` and an unread `buChar` both
  come out as "no bullet", so the output was correct and the reasoning was
  not.**
- **What that cost** — a full round was spent on the premise that four label
  lists were bulleted in PowerPoint, because the master's `buChar` was found
  and `slideLayout3`'s `buNone` was not. The conclusion, the projected
  geometry and the expected measurement were all wrong, and none of it was
  visible in the output either before or after.
- **Rule** — resolve `buNone` / `buChar` / `buAutoNum` through the full chain,
  nearest level wins, and treat the KIND as one atomic choice while the other
  bullet properties (`buFont`, `buSzPct`, **`buSzPts`**, `buClr`) merge
  independently per-key, which is how OOXML defines them. `buNone` at any level
  suppresses. Record the suppression rather than merely producing None: "the
  source says no bullet" and "the source says nothing" are different facts.
- **`buSzPts` is not `buSzPct`.** Every `buSz` in deck 10 is the absolute-points
  form; a reader written for the percentage form alone finds nothing.
- **Render the glyph into the HANG, not with a guessed indent.** An
  inline-block exactly `-indent` wide puts the text on `marL` regardless of the
  substituted face's advance. HenHouse's
  `p.t[data-bullet]{padding-left:1.6em;text-indent:-1.6em}` is the shape to
  avoid: 1.6em is a guess, it tracks font size rather than the authored indent,
  and it silently disagrees with the `marL`/`indent` the same paragraph emits.
  Two mechanisms for one measurement is how they drift apart. That rule had
  been copied into secret as dead code and would have double-drawn the glyph.

### (k) A non-placeholder shape has NO placeholder chain, so its own `lstStyle` is the only source of its text properties

- **Symptom** — slide 30 renders three body paragraphs that should be
  identical as one correct and two wrong, differing in face, size, alignment,
  leading and indent.
- **Root cause** — the two wrong ones are `sp` with `txBox="1"` and an empty
  `<p:nvPr/>`. They are not placeholders, so `build_model` passes `_lv = None`
  and no chain is consulted at all. Everything they need is in their OWN
  shape-level `<a:lstStyle>`, which `_paras_of` was reading only for bullets.
  **Six authored properties dropped per paragraph**: `latin` Darker Grotesque
  Medium, `defRPr sz` 1500, `algn ctr`, `lnSpc` 80%, `marL` 457200,
  `indent` -317500. They rendered Liberation Sans 14pt, flush left, at the
  substitute's natural leading, with no indent -- beside a third paragraph that
  IS a placeholder and resolved all six correctly.
- **Rule** — precedence is paragraph `pPr` -> shape `lstStyle` -> placeholder
  chain. **Shape `lstStyle` belongs in `_paras_of`, not in
  `resolve_ph_text`**, because it is per-SHAPE rather than
  per-placeholder-TYPE -- and because the case that needs it most is precisely
  the one with no placeholder entry to hang off.
- **Factor the level extractor, do not copy it.** Hoisting
  `build_ph_textstyles`'s inner read into `_lvl_ent(lvl)` means the shape level
  is read by literally the same code as the layout and master levels. A copy
  would have drifted the first time one side gained a property.
- **Blast radius is not a proxy for importance.** 124 of this deck's 126 shape
  `<a:lstStyle>` elements are empty; only 2 declare anything. Two paragraphs is
  the entire scope, and it was half the readable content of a slide.

### (l) `<a:alphaModFix>` is picture-FILL opacity, and an occlusion test that ignores it deletes content

- **Symptom** — slide 30's right panel rendered as a full-strength photograph
  where the source has a faint wash over light blue, and the blue panel that is
  half the composition was missing entirely.
- **Root cause, first order** — `<a:alphaModFix amt="12000"/>` inside
  `<a:blip>` is 12% opacity, in thousandths of a percent. Nothing in the
  deckkit path read it, so the picture painted at `opacity: 1`. **`amt` is
  OPTIONAL and its ECMA-376 default is `100000`** -- an absent `amt` means
  fully opaque, not zero, and deck 10 has two of those alongside five real
  washes.
- **Root cause, second order — the part worth the entry.** `_opaque()` tested
  a picture with `ctx.opaque_fraction(poster)`, which measures **the FILE's own
  alpha channel**. An opaque JPEG carrying 12% fill opacity therefore read as
  full cover, `_mark()` flagged everything beneath it occluded, and
  `SUPPRESS_OCCLUDED_SHAPES` dropped the layout's `#A7C6ED` panel. **One unread
  attribute deleted a shape that had nothing to do with it.**
- **Rule** — there are two independent ways a picture fails to hide what is
  under it, transparency in the FILE and transparency in the FILL, and an
  occlusion test has to see both. Fold them into a single effective opacity:
  `opaque_fraction(src) * opacity >= OPAQUE_MIN`. One rule, one threshold.
- **When one omission produces two symptoms, fixing the omission fixes both.**
  The missing panel was diagnosed as a separate defect and was not one.

### (m) Vertical geometry in `cqh`, not percent — THIRD occurrence in one session

(c) recorded this for `padding`. It recurred twice more in the same deck:
`marL`/`indent` (horizontal, where `%` and `cqw` agree, but `cqw` is right
because the containing block is the SHAPE and the intent is the CANVAS), and a
connector's stroke weight (vertical, where a percentage would have been 1.778x
too thick). **A percentage length resolves against WIDTH every time, whichever
side it is applied to.** The canvas already declares `container-type: size`, so
`cqw`/`cqh` cost nothing and say what is meant. Treat any percentage length in
a renderer as suspect until its axis is checked.

### (n) A sub-pixel stroke is quantised to the device-pixel grid, so a CORRECT declaration paints at a different weight per viewport

Deck 10's rules are 0.75pt on a 405pt canvas -- `0.1852cqh`, exactly right.
Measured `border-top-width`: **1.00px (0.563pt) at 1280, 1.50px (0.643pt) at
1680, 2.00px (0.750pt) at 1920.** Only the largest lands on the authored value;
the others are the engine snapping a hairline to a `dpr=2` half-pixel grid.
This is (a)'s viewport-dependence lesson in a second form: **verify a weight at
more than one size before calling it wrong, and do not "correct" a declaration
that is already exact.**

### (o) A TEST CAN ENCODE A BUG — and that is still the test doing its job

`secret/validate.py` pinned `EXPECTED_OCCLUDED = {(30, "Google Shape;37;p9")}`
with a comment explaining that a full-bleed photo buried the panel. The photo
was the 12% wash of (l); it never buried anything. The pin recorded a defect as
correct behaviour and passed for two rounds. **When the underlying cause was
fixed, the pin is what failed and made the correction visible** -- which is
exactly what rule 24 asks a pin to do. The lesson is not "do not pin"; it is
that **a pin records what the pipeline DOES, never what the source SAYS**, so
every pinned value needs a source citation beside it, and a pin that fails is
a question about which side is wrong, not an instruction to update the pin.

### (p) A cached page reports the previous build with complete confidence

Two consecutive rounds began with a browser measurement of a STALE
`index.html`: the served copy and the built copy diverged silently, and the
page reported the pre-change state -- 6 elements instead of 7, `opacity: 1`
instead of `0.12` -- with no error and no visible cue. Both were caught only by
reading the file on disk and disbelieving the browser. **Cache-bust before
measuring a fresh build** (`location.replace('/index.html?v=' + ...)`), and
treat agreement between disk and browser as something to establish rather than
assume. Same family as the polluted-history tab and the non-painting tab
already in NOTES: the browser is a measurement instrument and it needs zeroing.

- **Proven by** — Deck 10 (Secret), 2026-08-27/28.

---

## Open gaps (not yet pinned by fixtures)

- `theme_from_pptx()` has no fixtures; theme *parsing* correctness is not yet locked the
  way the color *math* is. Until fixtures exist, treat extracted theme dicts as unverified.
- The theme1-vs-theme2 disagreement case is **still unverified** after a third deck:
  Olay's two themes are byte-identical in `clrScheme`, as P&G's and SHELFBEAUTY's were.
  The Olay model asserts they agree rather than silently preferring theme1, so a deck
  where they diverge will fail loudly instead of rendering half-wrong.
- **Deck 10's FOUR font decisions split into two kinds — do not flatten them.**
  *Not substitutions:* Bebas Neue and Darker Grotesque are the deck's OWN faces,
  shipping as themselves because both are SIL OFL. They arrive by INHERITANCE
  (the runs declare no face; the master's `title` and `body` placeholders
  declare them in their own `<a:lstStyle>`), which is why they were missed.
  *Substitutions, all three SHAPE-BASED where WIDTH DID NOT DISCRIMINATE:*
  Aura AT -> **Anton** (+16.2% mean slack, 7th of 17 that fit; the tightest,
  Asap Condensed at +11.7%, is a regular-weight text face and Aura AT reads
  near-black); Univers Condensed -> **PT Sans Narrow** (only face top-3 on both
  constraints, exactly on the 0.900em budget); Univers -> **Roboto Condensed**
  (width cannot choose at all here — the long strings budget 0.177-0.239
  em/char, unachievable for mixed case, so they wrap and constrain nothing;
  chosen on x-height 0.528 with a tighter 0.403 lc advance for the 8-9pt plate
  labels). **The width budget is an UPPER BOUND from the box, not a target, and
  on the display titles six faces sat within 12-15% of each other. A tie is not
  a result.** The measurement ruled candidates out; it did not pick a winner.
  Sean chose against his own PowerPoint screenshots.
- **Univers -> Archivo (deck 10) is a JUDGEMENT CALL with no oracle behind it.**
  Recorded here so nobody later reads it as proven. Deck 10 has 4 `<a:spAutoFit/>`
  boxes, all `wrap="none"` (width test nullified, the Old Spice condition) and all
  4 are Univers *Condensed* — so there is zero oracle surface for plain Univers,
  the deck's dominant face at 128 slide refs. What IS measured is only that the
  previous mapping was wrong: PANOSE proportion 3 (Modern) for Univers vs 6
  (Condensed) for Barlow Condensed, read from the deck's own embedded font
  headers per rule 38. Archivo was chosen on closest bundled normal-width
  advance (H 0.732em vs Poppins 0.717, Montserrat 0.806), same class of form
  (grotesque, not geometric — Poppins' circular bowls would read visibly
  different at the 8pt plate labels that dominate the deck), and reuse (it
  already carries deck 9's Helvetica Light). **Re-derive against a real Univers
  metric source if one ever becomes available.** The broken `univers -> barlow
  condensed` entry it replaces never fired: deck 10 is the only deck of 68
  scanned that names plain Univers. **SUPERSEDED 2026-08-27: Archivo was
  replaced by Roboto Condensed on shape, per the entry above. The reasoning
  that Barlow Condensed was WRONG still stands; Archivo was never more than a
  first guess at a replacement.**
- Boston SemiBold -> Poppins is the one substitution in the corpus chosen on **design
  class rather than measurement** (52 characters over three short strings; every
  candidate fits with 20-30% width to spare, so the rule 17 oracle cannot discriminate).
  Treat it as provisional.
- Auto-detection of slide templates is deferred: manifest-driven (the operator tags each
  slide's template) is the reliable path for the first several decks. Auto-detection earns
  its place only after the pipeline has seen enough variety to know what "typical" is.
