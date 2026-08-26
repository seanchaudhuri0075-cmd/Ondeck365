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

---

## 9. TEST 3 — the Publish caveat, now tested instead of read (2026-08-26)

Section 8d flagged, from source only, that the one-click `Publish` flow would
throw on relative-path media. That was the same shape of unverified claim as the
`DOMParser` one, so it was tested the same way.

**Harness:** minimal 2-slide multi-file fixture — a 1.2 KB `index.html` with
three relative-path assets (`media/img_a.png`, `media/img_b.png`,
`media/clip_1.mp4`) — plus a **local mock Worker** on `127.0.0.1` that records
what it was asked to store and returns a `https://mock-worker.invalid/…` URL.
**No real deck, no real bucket, no real prefix, nothing named `venus-hestia`.**
Deck Name was `zz-local-mock-test`; the Worker URL pointed at localhost, so
nothing left the machine. Editor served over `http://127.0.0.1`, a different
origin from `file://`, so the persisted Deck Name field was never read or
written; the test origin's `localStorage` was cleared afterwards.

### Result

| path | relative-path media | outcome |
|---|---|---|
| **`Upload to R2` modal** | 3 of 3 | ✅ **all uploaded from disk, all 3 `src` rewritten to R2 URLs** |
| **`Publish` (one-click)** | 3 of 3 | ❌ **`TypeError: Cannot read properties of null (reading '1')`** — 0 uploaded, 0 rewritten |
| `Upload to R2` modal, mixed inline + relative | 1 `data:` + 2 relative | ✅ all 3 uploaded and rewritten, no `data:` left |
| `Publish`, mixed inline + relative | 1 `data:` + 2 relative | ❌ **1 object written to the bucket, then threw. 0 rewritten.** |

The `Upload to R2` modal shows **"📁 Local media files detected — Select Media
Folder"**, rows go `needs file` → `✓ done`, and srcs land as
`https://…/zz-local-mock-test/<file>`. The multi-file path is confirmed working
end to end.

*(One honesty note on method: `showDirectoryPicker()` is a native dialog and
cannot be driven from here. The test built the exact `{path → File}` map that
`pickR2Folder()` produces and assigned it to `r2LocalFileMap`, then ran the real
`doR2Upload()`. The picker **dialog** is unexercised; everything downstream of it
is real. Note also that `openR2Modal()` **resets `r2LocalFileMap` and re-reads
config from localStorage** — link the folder *after* opening the modal, which is
the order the UI enforces anyway.)*

### The part that is worse than section 8d said

**`doPublish` does not abort on the R2 failure — it swallows it and keeps
publishing.** Verbatim, at `doPublish` step 1:

```js
try{ await doR2Silent(); setStep('r2','☁','Media uploaded to R2','✓ done','ok') }
catch(e){ setStep('r2','☁','R2: '+e.message.substring(0,40),'⚠ skip','err') }
```

No rethrow. Control falls straight through to step 2 (`buildOutput`), step 3
(create repo), step 4 (push `index.html` to `gh-pages`). Verified: after the
throw the step renders **`⚠ skip`**, and the HTML that would be pushed still
carries `src="media/img_a.png"` and friends. Since only `index.html` is pushed
to `gh-pages`, **every image and video on the published deck 404s** — a live,
customer-visible deck of broken media, announced by one amber `⚠ skip` line in a
six-step list that otherwise reads all-green.

The mixed case adds the second hazard: `doR2Silent` uploads items in order and
throws at the first relative one, so **`data:` assets ahead of it are already
written to the bucket while `rawHTML` is never rewritten.** That is a partially
populated prefix under `Cache-Control: max-age=31536000, immutable` — the exact
condition NOTES says cannot be repaired in place.

### Rules for deck 9

1. **Use `Upload to R2`. Never use `Publish`.** For a multi-file deck the
   one-click flow is not slower or riskier, it is simply broken, and it fails
   loudly enough to notice only if you are reading the step list.
2. **After uploading, confirm zero relative `src` remain** before exporting.
   `collectMedia()` returning any `needsFile` item post-upload means the rewrite
   did not happen.
3. **A `⚠ skip` on the R2 step is a stop, not a warning.** If `Publish` is ever
   run by accident, treat the prefix as contaminated: check what landed, and
   move to a fresh prefix rather than overwriting.
4. Worth fixing in the editor eventually — `doR2Silent` needs the `needsFile`
   branch `doR2Upload` already has, and that catch should rethrow. Same class as
   rule 36: the real fix is in the editor, the workaround is per-deck.

---

## 10. Deck 9 is multi-file — AirDrop CANNOT review it

**Every mobile review of deck 9 goes through a staging repo over HTTPS. Not
AirDrop, not Files, not Quick Look.**

Deck 9's media lives in `assets/` (before upload) or on
`media.globalimaige.com` (after). Opened from Files on a phone, the document is
a `file://` URL and **iOS Quick Look's sandbox will not fetch sibling assets** —
relative `assets/…` refs resolve to nothing and absolute HTTPS refs are subject
to whatever the sandbox allows. Nothing loads.

**The trap is that the deck still looks fine.** A `<video>` that never loads
still lays out — the box is reserved from `--ar`, the poster slot is empty, and
the page scrolls beautifully because there is nothing to decode. A reviewer
swipes through 65 slides, sees layout and type, and signs off on scroll feel
that was measured against zero media. **This nearly produced a wrong conclusion
once already**: the HenHouse scroll diagnosis (NOTES 2026-08-24) is explicit
that pointing the diagnostic at external media would have turned the comparison
into "63 MB-with-video vs 21 MB-with-no-video-loading" and proved nothing. That
is exactly why
`henhouse_DIAGNOSTIC_no-video-bytes_DO-NOT-SHIP.html` was built with the `src`
**stripped** rather than pointed at a folder, and why the separate
`henhouse-scrolltest-deck` repo was published to answer the question honestly.

This retires the old operating principle for this deck. NOTES records *"AirDrop
verification: only fully-inlined HTML can be trusted on iPhone"* and *"inline =
iPhone-AirDrop-verifiable, external = not"*. Deck 9 cannot be fully inlined
(section 8), so **the inlined-AirDrop review path does not exist here at all.**

**The procedure:**

- Publish each review round to its own staging repo on `gh-pages`, pattern
  `venus-hestia-scrolltest-deck`, **deliberately no `CNAME`** — no
  `globalimaige.com` hostname, no collision with the live deck. Precedent:
  `henhouse-scrolltest-deck`, `olay-scrolltest-deck`.
- Media over HTTPS with **range requests** (verified `206` on HenHouse), so
  `preload="none"` genuinely defers each fetch and videos stream instead of
  downloading whole. This is the only setup in which the IntersectionObserver
  behaviour from section 7 can be judged.
- **Review scroll behaviour as its own dimension**, with video actually playing.
  NOTES 2026-08-25: scroll feel survived five review rounds on Olay and four on
  HenHouse because every round looked at appearance. Layout sign-off is not
  scroll sign-off.
- Never review deck 9 from a local file. If a build cannot be reached over
  HTTPS, it cannot be reviewed.

---

## 11. Content-derived slug — investigation, NOT yet implemented (2026-08-26)

**Instruction: do not plan to type `venus-hestia` into the Deck Name field.
Typing into that field IS the failure mode.** This section reports what a
content-derived slug would take. Nothing here is built.

### What the editor does today — read from source, all four call sites

The Deck Name field is `<input type="text" id="r2Deck">`. Its entire data flow:

| | |
|---|---|
| **Read** | `doR2Upload()` and `doR2Silent()`, both as `getElementById('r2Deck').value.trim() \|\| 'deck'` |
| **Written by code** | **exactly one place** — `loadR2()`, restoring `s.deck` from `localStorage['deckR2']` |
| **Written by human** | typing |
| **Persisted by** | `saveR2()`, on every upload |

And the decisive finding:

```js
function loadFile(e){const f=e.target.files[0];if(!f)return;const r=new FileReader();
  r.onload=ev=>{rawHTML=ev.target.result;fullParse();toast('Loaded '+slides.length+' slides')};
  r.readAsText(f)}
```

**`loadFile()` keeps nothing about the document it loaded — not the title, not
even the filename.** The editor reads no `<meta>`, no `data-*` on `<html>`, and
no `<title>` for any configuration purpose anywhere. So the answer to "can the
editor take the slug from the deck" is **no, and not narrowly** — the plumbing
does not exist. It is a small amount of new code, not a setting.

### The smallest fix is a DELETION, not an addition

`saveR2()` persists `{url, deck, token}`. Worker URL and auth token are
genuinely **per-operator** and should persist. **The deck name is per-deck and
must not.** Dropping `deck` from the persisted object — one clause removed from
`saveR2()`, one `if(s.deck)` removed from `loadR2()` — means the field starts
**empty on every load**. That alone retires the entire failure mode:

> An empty field is a visible prompt. A pre-filled wrong one is not.

Old Spice inherited `olay/` because the field silently held the previous
session's value and rendered correctly afterwards. It could not have inherited
an empty field.

### Full content-derived version, if the editor is to change

1. **The builder emits the slug it intends** — `<meta name="deck-slug"
   content="venus-hestia">` in `<head>`. Pipeline-controlled, declarative, no
   derivation heuristic to get wrong. Slugifying `<title>` or the filename is
   strictly worse: both are guesses, and a title changes for editorial reasons.
2. **`loadFile()` reads it** after `fullParse()`, and then:
   - declared → set the field, `readOnly = true`, badge it "from document";
   - **not** declared → **clear** the field and disable the upload button until
     something is typed. Never carry a value across documents.
3. `loadR2()` stops restoring `deck` (the deletion above).

Size: roughly **10 lines in one file**, no build step — the editor is a single
static HTML document.

**A caveat that matters more than the diff.** `Deck_Editor_v14.html` lives in
`~/Downloads`, is **not in this repo, not in any repo**, and has no history. The
highest-risk control in the pipeline sits in an unversioned file in a Downloads
folder, and any edit to it is unrecoverable. Vendoring a copy in is worth doing
first — but note its Worker URL placeholder contains the real endpoint, which
NOTES deliberately keeps out of this public repo, so it must be scrubbed before
any copy is committed.

### If the editor is not to change — four places the slug can be derived and verified

Ranked by value against cost. **(d) is the one to do first regardless.**

- **(a) Build side — emit and record.** The builder writes the slug into the
  document *and* a sidecar `out/<deck>/publish.json`. Costs nothing, and is a
  precondition for (b). No protection on its own.
- **(b) Post-upload, pre-push verifier.** Parse the exported HTML; assert every
  `img`/`video` `src`/`poster` matches `https://<media-host>/<expected-slug>/`,
  and that the count balances against the asset manifest. Deterministic, runs
  in seconds, catches a wrong prefix **before the deck goes live**. Worth having
  even with the editor fixed: it is the only check that covers an operator
  overriding a correct auto-filled value. **But it detects after the bytes have
  already landed** — it protects this deck, not the one that got clobbered.
- **(c) Worker side — the only true pre-flight.** Reject a write whose path
  prefix is not on an allowlist, or scope the auth token per deck. This is the
  only mitigation that **prevents** the write rather than reporting it, and so
  the only one that protects *other* decks. Requires touching the Worker, which
  I have not seen.
- **(d) Namespace every publish — `<slug>/<build-id>/`.** NOTES mitigation 3.
  Even a wrong slug then writes into a fresh directory that collides with
  nothing, so **no existing object is ever overwritten**. It converts a data-loss
  bug into a cosmetic naming error, and it permanently retires the
  `Cache-Control: immutable` repair problem, since every publish produces new
  URLs. Cheapest large win; costs only storage.

### RESOLVED 2026-08-26 — both fixes landed, and the Worker confirmed

| | |
|---|---|
| **Fix 1** | `5d87689` — the Deck Name is no longer persisted. Field starts empty every load; both uploaders refuse an empty name; the config panel opens when either field is blank. Worker URL and token still persist. |
| **Fix 2** | `e47ed5a` — every upload writes to `<slug>/<build-id>/`, id = `YYYYMMDD-HHMMSS-xxxx` with four crypto-random base36 chars. |
| **Worker** | **PASS, confirmed against the real Worker 2026-08-26 via `tools/deck_editor/worker_keytest.sh`. Two-segment keys work.** The `<slug>/<build-id>/` layout is verified end to end, not inferred. |

**What this changes for deck 9's publish step.** A wrong slug can no longer
overwrite anything — it lands in a directory that collides with nothing — and
because every publish produces new URLs, the
`Cache-Control: max-age=31536000, immutable` repair problem is retired: there is
nothing to correct at the edge. Setting the Deck Name correctly still matters
(a wrong one is a mislabelled directory and a wrong public URL), but it is now
a **cosmetic** error rather than data loss in another client's deck.

The remaining standing instruction is unchanged and much cheaper to satisfy:
the field is empty, so type `venus-hestia` and read back the destination line
the modal now shows — *"Writing to venus-hestia/&lt;build-id&gt;/"* — before
clicking Upload.

### Recommendation (superseded above, kept for the reasoning)

**(d) plus the `loadR2` deletion.** Together they make a wrong slug harmless
rather than merely unlikely — one removes the silent carry, the other removes
the collision. Add (a)+(b) as the build-side check. (c) is the real fix and
should be raised with whoever owns the Worker.

**Until at least one of these lands, the standing instruction stands and gets
worse with this deck:** read the field, clear it, type `venus-hestia`, verify,
then upload — with ~225 objects at stake instead of Old Spice's 29.
