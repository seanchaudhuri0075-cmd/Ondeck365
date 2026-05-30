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

## Open gaps (not yet pinned by fixtures)

- `theme_from_pptx()` has no fixtures; theme *parsing* correctness is not yet locked the
  way the color *math* is. Until fixtures exist, treat extracted theme dicts as unverified.
- Auto-detection of slide templates is deferred: manifest-driven (the operator tags each
  slide's template) is the reliable path for the first several decks. Auto-detection earns
  its place only after the pipeline has seen enough variety to know what "typical" is.
