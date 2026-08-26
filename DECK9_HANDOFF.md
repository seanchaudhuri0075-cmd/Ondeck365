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
  **Two corrections to that estimate, 2026-08-26 — see section 8.**
  (a) **~235 MB is the VIDEO ONLY** (176 MB × 4/3). Deck 9 also has 172 distinct
  images at 112.8 MB of source bytes; even optimised the way HenHouse's were,
  they add tens of MB of base64 on top. The realistic embed is **~275–315 MB**,
  not 235.
  (b) **The comparison baseline is 65.6 MB, not 24 MB.** HenHouse's imported
  embedded file is **65,633,415 bytes**. 24.49 MB was its *transcoded video
  total before base64 inflation* — the payload, not the artefact. Deck 9's embed
  is roughly **4–5×** the largest file the editor has ingested, not 7×.
- **This is the fourth per-deck `render.py`.** The scroll defect had to be fixed
  independently in two of them because nothing is shared. Lifting the common
  mobile CSS into `deckkit` is cheaper before deck 9 is written than after.
- **Old Spice still carries rule 36's problem** — 3.45 MB of its 3.51 MB
  published file is inline `url(data:)` the editor won't externalise. Flagged in
  NOTES for re-import once the editor is fixed. Unrelated to deck 9.

---

## 7. TEST 1 — Deck Editor v14 script tolerance: **PASS** (2026-08-26)

**Answer: yes. An inert `<script>` survives a real editor import, unchanged,
in every position tested. Section 5a is closed and the IntersectionObserver
approach is not blocked by the editor.**

Tested by import, not by reasoning about `DOMParser`. The editor is a local
single-file app, `~/Downloads/Deck_Editor_v14.html` (119,451 B, md5
`7d2f9bc2ca58cfde9f3e7d4583ecb191`), served over `http://127.0.0.1` and driven
in Chrome. Fixtures were built from the real HenHouse folder build
(`out/henhouse/index.html`). Import went through the editor's own
`<input id="fileIn">` → `loadFile()` → `FileReader.readAsText` → `fullParse()`
path; only the OS file picker was bypassed.

### Fixture A — one HenHouse slide, four scripts, four positions

`<head>`, top of `<body>`, **inside** the `<section class="slide">`, and end of
`<body>` (the last carrying a real `IntersectionObserver` bootstrap of the shape
deck 9 would ship).

| check | result |
|---|---|
| all four `<script>` present after load | ✅ |
| all four present after `commitAll()` | ✅ |
| all four present in `buildOutput()` — what Export writes | ✅ |
| `probe-end` script **byte-identical** source → export | ✅ |
| all four **execute** in the editor's preview iframe | ✅ (`sandbox="allow-same-origin allow-scripts"`) |
| `IntersectionObserver` constructs inside the preview | ✅ |
| slide harvest unaffected | 1 section in, 1 slide parsed |

Full diff of source → export, **complete list**, all benign HTML
re-serialisation and none of it inside a `<script>`:

1. `<!doctype html>` → `<!DOCTYPE html>`
2. newline between `<html>` and `<head>` dropped
3. `hidden` → `hidden=""` (boolean attribute normalisation on the rail `<nav>`)
4. `&#x27;` → `'` **inside `style` attribute values** (font-family quotes) —
   semantically identical CSS
5. trailing newlines around `</body></html>`

### Fixture B — full 52-slide HenHouse deck + one end-of-body script

Three successive real `commitAll()` cycles.

| check | result |
|---|---|
| slides parsed | **52 / 52** |
| script surviving cycles 1, 2, 3 | ✅ ✅ ✅ |
| `window.__IO_OK=true;` intact each cycle | ✅ |
| output length after cycles 1/2/3 | 192,952 / 192,952 / 192,952 — **idempotent after the first pass** |
| live text characters | **7,152 in, 7,152 out, identical** |
| `<img>` / `<video>` / `.rail-item` / `.sh` | 93 / 7 / 52 / 178 — all unchanged |

Length went 196,336 → 192,952 (−3,384). Fully accounted for: 688 `&#x27;` → `'`
substitutions = −3,440, offset by +56 of `hidden=""`-class normalisations.
Nothing was lost.

### Corroborating code fact

The editor itself creates and injects `<script>` elements (`__me_script`, the
media-editor overlay, lines ~1819–1990) into the preview document. It has no
sanitiser and no script-stripping path anywhere.

**Consequence for deck 9:** ship the IntersectionObserver bootstrap as a single
end-of-body `<script>`. Section 5b's fallback (fewer simultaneous videos per
slide on mobile) is **not** forced by the editor. It may still be wanted on its
own merits for slides 49–64, which carry three videos each — that is a layout
call, decide it separately.

---

## 8. TEST 2 — Deck Editor v14 embed size ceiling: **ceiling found between 180 and 240 MB**

### 8a. The largest embed the editor has actually ingested

Measured off the artefacts on disk, not from memory:

| deck | embedded file | bytes |
|---|---|---|
| Old Spice | `out/oldspice/oldspice_deck_embedded.html` | 12,529,794 |
| Olay | `out/olay/olay_deck_embedded.html` | 50,098,894 |
| **HenHouse** | `out/henhouse/henhouse_deck_embedded.html` | **65,633,415** |

**The record is HenHouse at 65,633,415 B (65.6 MB)** — the dedupe-disabled build
from rule 36, which was imported and published. NOTES' "63.14 MB" is the earlier
dedupe-*enabled* build and is correct in its own context; the imported artefact
is the 65.6 MB one.

**Correcting the working figure:** 24.49 MB is HenHouse's *transcoded video
total* (5 unique mp4s, from the scroll-test variant's `assets/`), i.e. the
payload before base64 inflation. It is not what the editor ingested. Against the
right baseline, deck 9's embed is **~4–5× the record**, not ~7×.

### 8b. Is there a size ceiling — measured

**There is no explicit size check anywhere in the editor's code.** The ceiling is
a memory ceiling, and it is real. Escalating imports of padded HenHouse decks
(base64 `<video src="data:...">` padding, structure otherwise unchanged), each in
a freshly reloaded tab:

| file | loaded? | slides parsed | read+parse | JS heap after load | `buildOutput()` | `commitAll()` | preview |
|---|---|---|---|---|---|---|---|
| **65.6 MB** (real HenHouse) | ✅ | 52 | 3.9 s | 118 MB | 493 ms | 1,293 ms | 52 sections |
| **120 MB** | ✅ | 52 | 3.7 s | 302 MB | 817 ms | 2,561 ms | 52 sections |
| **180 MB** | ✅ | 52 | 2.9 s | 468 MB | 1,226 ms | 3,503 ms | 52 sections |
| **240 MB** | ✅ import returned | 52 | 3.7 s | **645 MB** | **never ran** | **never ran** | **renderer died** |
| **320 MB** | **NOT TESTED** | — | — | — | — | — | — |

**What happened at 240 MB.** The import itself completed and reported honestly:
52 slides parsed, 645 MB JS heap. Then the tab went unresponsive **before the
first post-load operation executed**. The editor's renderer process vanished
from the process table (largest surviving Chrome renderer: 172 MB). It did not
recover — a reload did not bring the tab back and it had to be closed.

**Two limits of this result, stated plainly:**

- **I did not isolate the cause.** The death sits between "import returned" and
  "first operation ran". The two candidates are the preview iframe rendering a
  240 MB `srcdoc` (a second full copy of the string, re-parsed into an iframe
  document, with 24 giant `data:video` URIs to decode) and the first
  `buildOutput()`. Not separated.
- **320 MB was generated but never run.** The file exists; the test does not.
  Nothing below should be read as evidence about 320 MB.

**Peak memory caveat:** the per-size numbers are `performance.memory` JS heap,
which under-reports — it excludes the DOM, the iframe document, and external
string storage. Clean per-stage renderer RSS peaks were not captured. **This
machine has 8 GB of RAM**, which is very likely the binding constraint, and is
Sean's actual publishing machine.

### 8c. Two amplifiers in the editor's design, read from the source

Both make the ceiling lower than file size alone suggests:

1. **`rawHTML` is re-parsed from scratch on essentially every operation.** There
   are **~20 separate `DOMParser.parseFromString(rawHTML, 'text/html')` call
   sites**. Every edit, commit, media enumeration and export builds a complete
   new DOM of the entire document.
2. **The undo stack keeps up to 30 full copies of the document.**
   `pushUndo()` stores `{html: rawHTML}` and `UNDO_MAX = 30`. At 240 MB that is
   **7.2 GB after 30 edits on an 8 GB machine.** At HenHouse's 65.6 MB it is
   already ~2 GB. This alone rules out an embedded deck-9 workflow that involves
   any real editing.

Add `iframe.srcdoc = rawHTML` (a full second copy, re-parsed) after nearly every
one of those operations. A hard upper bound also exists regardless of RAM: V8's
maximum string length is ~512 MB, so a file above that cannot be read as text at
all.

### 8d. THE FINDING THAT CHANGES THE PLAN — the editor already handles external media

**`collectMedia()` handles relative-path media, and the R2 dialog uploads it
from disk.** This is the question NOTES recorded as unknown ("Deck Editor v14's
handling of relative asset URLs is undocumented", "recorded nowhere, and was not
guessed at"). It is answered by the source:

- `collectMedia()` classifies an `img`/`video` `src` that is not `data:`, not
  `http`, and not `blob:` as `needsFile: true`, keeping its `relPath`.
- The R2 modal then shows **"📁 Local media files detected — Select Media
  Folder"** and calls `showDirectoryPicker()` (with a `webkitdirectory` fallback),
  walking the folder into a `{path → File}` map.
- `doR2Upload()` uploads the **File off disk** for those items and rewrites the
  element's `src` to the returned R2 URL, exactly as it does for `data:` items.

**So the publish path for deck 9 does exist.** A multi-file build — small
`index.html` with relative `src="assets/…"` plus an `assets/` directory — goes
through the editor without ever inlining 235+ MB of base64. That is also the
shape GAP has published since May 2026 (`media.globalimaige.com`, absolute
HTTPS URLs after rewrite). The editor's working set drops to the size of the
markup, a few hundred KB, and every amplifier in 8c stops mattering.

**Three things to verify before relying on it** (none tested here):

1. **The one-click `Publish` flow does NOT support this path.** `doR2Silent()`
   — the publish flow's uploader — does `it.isLocal ? it.localFile :
   dataUriToBlob(it.src)` with **no `needsFile` branch**. On a relative `src`,
   `dataUriToBlob` runs `uri.split(',')[0].match(/:(.*?);/)` on a plain path,
   gets `null`, and throws. **Use the explicit `Upload to R2` modal, not
   `Publish`.** Untested, read from source.
2. Rule 36 still applies unchanged: only `img`/`video` `src`/`poster` are
   rewritten. Keep `DEDUPE_CROP_HALVES` off (already decided; deck 9 has no crop
   halves anyway).
3. 53 videos + 172 images = ~225 sequential uploads in one `for` loop with no
   retry — a single failure marks that item `✗` and continues. Budget for a
   verification pass over the R2 prefix afterwards.

### 8e. What this means for deck 9

- **The self-contained embedded artefact is out.** ~275–315 MB is past a ceiling
  that sits between 180 and 240 MB on this machine, and the undo-stack
  multiplier makes editing an embedded build impossible well before that.
- **The multi-file build is in, and it is not novel** — it is GAP's shape, and
  the editor supports it through the folder picker.
- **The R2 prefix hazard is unchanged and gets worse here.** Section 4 /
  NOTES stand: read the Deck Name field, clear it, type `venus-hestia`. With
  ~225 objects the blast radius of inheriting `olay-v2` is far larger than the
  24 ordinals Old Spice clobbered.
- **Still open, deliberately:** the 320 MB run, and isolating whether the
  240 MB death was the `srcdoc` preview or `buildOutput()`. Neither blocks the
  decision above — both point the same way.

**Method note.** Reproduce with the harness in
`<scratchpad>/editortest/` (POST-capable static server `srv.py`, fixture
generators, padded decks). The padded decks are ~860 MB on disk and were not
committed. Disk was at 7.4 GB free after generating them; regenerate rather than
keep them.
