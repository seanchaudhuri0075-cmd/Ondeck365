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
- **Root cause** — Desktop fidelity needs absolute positioning on a fixed 16:9 canvas;
  mobile needs a reflowed, scroll-friendly document. One DOM cannot serve both cleanly.
- **Rule** — Emit two sections from the same source: `#deck-desktop`, an absolutely-
  positioned 16:9 canvas using `cqw` units (pixel-faithful), and a completely separate
  `#deck-mobile` scroll-snap DOM. Per-slide CSS is scoped (`.slide-N`). Editor vocabulary
  classes are preserved (`.L > .t`, `.ci`, `.tlt`, `.tlb`, `.uct`, `.ucb`, etc.). Scroll
  behavior: `scroll-snap` mandatory on desktop, proximity on mobile, `scroll-snap-stop:
  always`. *Assertion:* every slide emits both a `#deck-desktop` and a `#deck-mobile`
  representation; desktop canvas uses `cqw`, neither uses `vh`/`vw` for type.
- **Proven by** — P&G (dual-build pattern established), Global ImAIge (continuous scroll).

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

## Open gaps (not yet pinned by fixtures)

- `theme_from_pptx()` has no fixtures; theme *parsing* correctness is not yet locked the
  way the color *math* is. Until fixtures exist, treat extracted theme dicts as unverified.
- The theme1-vs-theme2 disagreement case is **still unverified** after a third deck:
  Olay's two themes are byte-identical in `clrScheme`, as P&G's and SHELFBEAUTY's were.
  The Olay model asserts they agree rather than silently preferring theme1, so a deck
  where they diverge will fail loudly instead of rendering half-wrong.
- Boston SemiBold -> Poppins is the one substitution in the corpus chosen on **design
  class rather than measurement** (52 characters over three short strings; every
  candidate fits with 20-30% width to spare, so the rule 17 oracle cannot discriminate).
  Treat it as provisional.
- Auto-detection of slide templates is deferred: manifest-driven (the operator tags each
  slide's template) is the reliable path for the first several decks. Auto-detection earns
  its place only after the pipeline has seen enough variety to know what "typical" is.
