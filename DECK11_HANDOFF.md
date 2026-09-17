# Deck 11 (Unilever — Skin, Hair & Personal Care capabilities) — reconnaissance handoff

Written 2026-09-17, **before any building**. Every number here is measured
from the source `.pptx` read in place (zip + lxml, explicit namespaces), from a
dry run of `phase_1c.deckkit.model.build_model` against an XML-only scratch
extract, or from scratch encodes run with `deckkit.assets`' exact ffmpeg
command line. Where a figure is an estimate it says so, and says from what.

**UPDATE 2026-09-17: the first full asset build exists -- see "BUILD 1" at the
end of this file. Still nothing rendered, uploaded or published. The status
paragraph below describes the moment of reconnaissance.**

**Status: nothing built, nothing committed, nothing uploaded, nothing
published.** No `phase_1c/unilever_shpc/` directory exists yet. No file was
written to the T7 or to `out/`. The source deck was opened read-only.

Read alongside: `DECK10_MOBILE_HANDOFF.md` (the spine this deck follows, and
the two places it must NOT follow — see OPEN ITEMS 2), `DECK9_HANDOFF.md`
(the only prior deck of this weight class: 958 MB, 53 videos, 5 Mbps ABR, R2
upload hazards), `PHASE_1C_ARCHITECTURE.md`, `LEARNINGS.md`.

Slug: **`unilever_shpc`** → `phase_1c/unilever_shpc/`, `out/unilever_shpc/`.

---

## 1. Source file — settled

```
/Volumes/T7 Touch/2026_GIF_AI_GlobalCapabiltiesPresentation_SKIN_HAIR_PERSONAL_CARE_UNILEVER_OSR.pptx
sha256   d2539cf1b1ea9439df047a34723dea10cb3a0ddb4d2066616a8a775444201226
size     1,569,045,169 bytes (1.57 GB)
modified 2026-09-16 23:55:01
slides   35      canvas 12192000 x 6858000 EMU = 960 x 540 pt (16:9)
```

Confirmed before reading: the `~$` lock file is gone from the T7 root, `lsof`
shows no process holding the deck, and size + mtime are unchanged from the
first scan (it was closed without a save).

("Capabilties" is the filename's own spelling. Do not correct it in paths.)

**The T7 is the only readable copy.** Both `~/Downloads` copies — this deck's
and OSR1's — are truncated: each is exactly 2,794,192,896 bytes, begins with a
valid `PK\x03\x04` and has **no zip central directory**. Two different decks
truncated at the identical byte count; cause not established (the boot volume
is 98% full, 4.6 GB free — a suspect, not a finding). They were not touched,
moved or deleted during reconnaissance. **Both are since gone from
`~/Downloads` — see the 2026-09-17 update under OPEN ITEMS 4.**

### What the package is

| part | files | MB |
|:--|--:|--:|
| `ppt/media` | 104 | 1,568.85 (99.99% of the file; stored, not deflated) |
| `ppt/slides` (+rels) | 70 | 0.53 |
| `ppt/notesSlides` | 64 | 0.09 |
| `ppt/slideLayouts` (+rels) | 26 | 0.06 |
| everything else | 13 | 0.07 |

One slide master (`slideMaster1.xml`), 13 layouts of which 4 are used, two
themes (`theme1` paints; `theme2` is the notes master's and is correctly
ignored by `build_model`'s audit). **No `ppt/charts`, no `ppt/embeddings`, no
`ppt/diagrams`, no embedded fonts.**

---

## 2. Relationship to OSR1

Compared against
`/Volumes/T7 Touch/2026_GIF_AI_GlobalCapabiltiesPresentation_SKIN_HAIR_PERSONAL_CARE_OSR1.pptx`
(2,791,875,898 bytes, 60 slides, 196 media, 2,791.6 MB, same 960x540 canvas),
read-only. Slide text was compared entity-decoded and whitespace-normalised;
media by SHA-256 of every `ppt/media` payload in both packages.

**UNILEVER_OSR is a 35-slide cut of OSR1 with two new slides, one split slide,
and light copy edits on four more. It is not a pure subset.**

* **Media:** 104 payloads; **100 are byte-identical to an OSR1 payload, 4 are
  absent from OSR1.** Media ordinals differ between the two packages (U
  `media6.mp4` = O `media5.mp4`, U `image10.png` = O `image22.png`, …) — **never
  match the two decks by filename.**
* **27 slides are exact** (text identical AND media set identical):
  U1-3→O1-3, U5→O5, U6→O6, U13→O15, U14→O16, U16-22→O18-24, U23-26→O29-32,
  U27-29→O33-35, U30→O38, U31-35→O56-60.
* **4 slides are the same slide with a copy edit** (media identical or a
  subset):
  * U4→O4 — one line removed ("This is how we partner with clients' internal
    teams"; 28 shapes vs 29).
  * U7→O7, U10→O9 — the "STUNNING" label removed (5 shapes vs 7).
  * U8→O8 — "STUNNING" removed and the headline changed from "Models & Ads" to
    "Ads and / Landing / Pages".
* **O17 was split in two:** U12 carries O17's video + poster (media exact) with
  only the footer text; U15 carries O17's text, exact, with no media.
* **2 slides are NEW — nothing like them exists in OSR1:**
  * **U9** — full-bleed video `media5.mp4` (17.00 MB) + poster `image6.png`.
  * **U11** — "We Produce Global ImAIge Brand Videos To Tell A Story Without A
    Day on Set", `media8.mp4` (93.63 MB) + poster `image9.png`.
  These four files are the 4 payloads absent from OSR1.
* **28 OSR1 slides were dropped:** O10-14, O25-28, O36, O37, O39-55. (32 of
  OSR1's 60 survive, O17 feeding two slides: 27 + 4 + 2 + 2 new = 35.)
* Order is preserved with one exception: O17's video half (U12) now sits
  AHEAD of O15/O16 (U13/U14), while its text half (U15) stays after them.

Consequence: OSR1 is not a fallback source for this deck. Anything rebuilt from
OSR1 would lose U9 and U11 and carry the pre-edit copy on five slides.

---

## 3. Inventory — all 35 slides

268 shapes: 149 text, 33 rect, 37 image, 49 video. **0 charts, 0 tables, 0
SmartArt, 0 OLE, 0 connectors, 1 group (slide 33).** `build_model` emitted
268 of 268 with nothing in any slide's `skipped` list.

`inh/ovr/loc` = placeholder shapes inheriting layout geometry / placeholder
shapes with their own xfrm / non-placeholder shapes. `src MB` is the slide's
related media (the 0.09 MB logo `image1.png` is shared by 27 slides, so the
column over-counts by that much per slide; there are no other shared payloads
and no duplicate payloads). `est MB` is the estimated post-`build_all` weight
(section 6). `OSR1` is the slide it maps to (`=` exact, `~` edited, `NEW`).

| # | layout | master | shapes | text | pic | vid | chart | table | grp | inh/ovr/loc | src MB | est MB | flags | OSR1 |
|--:|:--|:--|--:|--:|--:|--:|--:|--:|--:|:--|--:|--:|:--|:--|
| 1 | `DEFAULT` | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0/0/2 | 0.00 | 0.00 | — | =O1 |
| 2 | `DEFAULT` | 1 | 28 | 22 | 1 | 0 | 0 | 0 | 0 | 0/0/28 | 0.09 | 0.07 | anim | =O2 |
| 3 | `DEFAULT` | 1 | 28 | 20 | 1 | 0 | 0 | 0 | 0 | 0/0/28 | 0.09 | 0.07 | — | =O3 |
| 4 | `DEFAULT` | 1 | 28 | 15 | 1 | 0 | 0 | 0 | 0 | 0/0/28 | 0.09 | 0.07 | — | ~O4 |
| 5 | `DEFAULT` | 1 | 31 | 22 | 1 | 0 | 0 | 0 | 0 | 0/0/31 | 0.09 | 0.07 | — | =O5 |
| 6 | `DEFAULT` | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0/0/2 | 0.00 | 0.00 | — | =O6 |
| 7 | `DEFAULT` | 1 | 5 | 3 | 0 | 2 | 0 | 0 | 0 | 0/0/5 | 29.56 | 7.65 | anim | ~O7 |
| 8 | `DEFAULT` | 1 | 6 | 3 | 1 | 2 | 0 | 0 | 0 | 0/0/6 | 111.62 | 44.63 | anim | ~O8 |
| 9 | `DEFAULT` | 1 | 3 | 1 | 1 | 1 | 0 | 0 | 0 | 0/0/3 | 17.43 | 16.32 | anim | NEW |
| 10 | `DEFAULT` | 1 | 5 | 3 | 0 | 2 | 0 | 0 | 0 | 0/0/5 | 50.24 | 12.44 | anim | ~O9 |
| 11 | `DEFAULT` | 1 | 3 | 2 | 0 | 1 | 0 | 0 | 0 | 0/0/3 | 94.70 | 18.44 | anim | NEW |
| 12 | `DEFAULT` | 1 | 2 | 1 | 0 | 1 | 0 | 0 | 0 | 0/0/2 | 29.38 | 15.22 | anim | O17 (video half) |
| 13 | `DEFAULT` | 1 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | 0/0/5 | 0.09 | 0.07 | — | =O15 |
| 14 | `23_Title Slide` | 1 | 6 | 3 | 2 | 1 | 0 | 0 | 0 | 0/0/6 | 242.43 | 21.32 | anim trans | =O16 |
| 15 | `DEFAULT` | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0/0/2 | 0.00 | 0.00 | — | O17 (text half) |
| 16 | `23_Title Slide` | 1 | 7 | 2 | 1 | 4 | 0 | 0 | 0 | 0/0/7 | 47.14 | 36.58 | anim trans ext-NULL | =O18 |
| 17 | `23_Title Slide` | 1 | 7 | 2 | 1 | 4 | 0 | 0 | 0 | 0/0/7 | 25.21 | 17.47 | anim trans | =O19 |
| 18 | `23_Title Slide` | 1 | 5 | 2 | 1 | 2 | 0 | 0 | 0 | 0/0/5 | 12.63 | 10.20 | anim trans | =O20 |
| 19 | `23_Title Slide` | 1 | 6 | 2 | 1 | 3 | 0 | 0 | 0 | 0/0/6 | 13.79 | 8.49 | anim trans | =O21 |
| 20 | `23_Title Slide` | 1 | 6 | 2 | 1 | 3 | 0 | 0 | 0 | 0/0/6 | 34.62 | 28.01 | anim trans | =O22 |
| 21 | `23_Title Slide` | 1 | 7 | 2 | 1 | 4 | 0 | 0 | 0 | 0/0/7 | 461.32 | 131.66 | anim trans | =O23 |
| 22 | `23_Title Slide` | 1 | 7 | 2 | 1 | 4 | 0 | 0 | 0 | 0/0/7 | 21.71 | 16.07 | anim trans | =O24 |
| 23 | `DEFAULT` | 1 | 6 | 2 | 1 | 3 | 0 | 0 | 0 | 0/0/6 | 22.50 | 15.26 | anim | =O29 |
| 24 | `23_Title Slide` | 1 | 6 | 2 | 1 | 3 | 0 | 0 | 0 | 0/0/6 | 22.24 | 15.30 | anim trans | =O30 |
| 25 | `23_Title Slide` | 1 | 6 | 2 | 1 | 3 | 0 | 0 | 0 | 0/0/6 | 22.82 | 15.33 | anim trans | =O31 |
| 26 | `23_Title Slide` | 1 | 6 | 2 | 3 | 1 | 0 | 0 | 0 | 0/0/6 | 28.06 | 11.12 | anim trans | =O32 |
| 27 | `23_Title Slide` | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 0/0/4 | 15.87 | 13.39 | anim trans | =O33 |
| 28 | `23_Title Slide` | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 0/0/4 | 11.43 | 8.61 | anim trans | =O34 |
| 29 | `23_Title Slide` | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 0/0/4 | 207.33 | 21.05 | anim trans | =O35 |
| 30 | `Title Only` | 1 | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0/0/6 | 17.75 | 0.21 | — | =O38 |
| 31 | `Blank` | 1 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 0/0/4 | 10.86 | 7.25 | anim | =O56 |
| 32 | `23_Title Slide` | 1 | 5 | 2 | 2 | 1 | 0 | 0 | 0 | 0/0/5 | 18.38 | 14.00 | anim trans | =O57 |
| 33 | `Blank` | 1 | 7 | 2 | 4 | 0 | 0 | 0 | 1 | 0/0/7 | 1.57 | 0.24 | — | =O58 |
| 34 | `DEFAULT` | 1 | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 0/0/7 | 0.09 | 0.07 | anim | =O59 |
| 35 | `DEFAULT` | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0/0/2 | 0.00 | 0.00 | — | =O60 |

Layouts used: `DEFAULT` (slideLayout12) x17, `23_Title Slide` (slideLayout13)
x15, `Blank` x2, `Title Only` x1. All under `slideMaster1.xml`. **No layout
contributes a single non-placeholder shape**, and every slide's background
resolves to the master (`#FFFFFF`); all visible ground is authored rects
(`#F8F9F2` x10, `#0B0B0C` x4, …) and full-bleed video.

`anim` = a `<p:timing>` tree (25 slides). On the 23 video slides it is only PowerPoint's media
playback nodes (`mediacall`, a mix of `withEffect` = autoplay and
`clickEffect` = click-to-play). **Slides 2 and 34 carry real entrance
animations** (8 and 4 `animEffect`s). `trans` = `<p:fade>` on 15 slides.
deckkit reads none of this — see section 7.

### Geometry groups (measured from the dry-run model, % of canvas)

Proposed per-slide routing for `roles.py`. Advisory only — see section 5.

| group | slides | what is there |
|:--|:--|:--|
| statement | 1, 6, 15, 35 · 13, 34 | text only (2 shapes) · text + logo |
| diagram | 2, 3, 4, 5 | 28-31 shapes: numbered rect cards + text, no media beyond the logo |
| full-bleed video | 9, 12, 14, 27, 28, 29, 31, 32 · 11 | one video at 100x100 (12 is 104x104, overscanned) · 11 at 72x72 |
| portrait video wall | 16, 17, 19, 21-25 · 7, 10 | 3-4 portrait clips at ~23-26% x 74-83% · 2 clips at 28x88 |
| mixed video | 8, 18, 20 | landscape + portrait clips side by side |
| image board | 26, 30, 33 | 26: 73x74 animated GIF + portrait clip · 30: one 1920x9419 image shown as three cropped windows · 33: four billboards, one group, two off-canvas |

57 of 268 shapes extend past the canvas edge.

---

## 4. Fonts

Measured from RUNS (the dry-run model's 335 non-empty runs), not from
`typeface=` references — the package names ~60 faces, almost all of them the
theme's script-fallback table, which render nothing (same trap as Secret's
Darker Grotesque).

| face | runs | sizes | installed on this Mac | web status |
|:--|--:|:--|:--|:--|
| SF Pro Semibold | 260 | 35pt display (206 runs), 15/20 | yes — `/Library/Fonts/SF-Pro.ttf` + the Display/Text cuts | **cannot ship.** Apple licenses SF Pro for UI mock-ups on Apple platforms only; it may not be served as a web font. **SUBSTITUTION REQUIRED.** |
| SF Pro Medium | 66 | 12/15/16 | yes (same family) | same |
| Helvetica | 6 | — | yes (system) | system stack; Liberation Sans is the metric fallback already in `ondeck/render/fonts/` |
| Arial | 1 | — | yes (system + Office) | Liberation Sans, already bundled |
| League Gothic | 1 | — | yes — `~/Library/Fonts/LeagueGothic-*.otf` | SIL OFL, **can ship as itself**; no binary in `ondeck/render/fonts/` yet |
| Calibri (inherited) | 1 | 18 | **NOT installed system-wide** — only inside the PowerPoint app bundle (`DFonts/`) | one run inherits the theme minor font; Carlito is the metric-compatible substitute; not bundled |

**Font gaps, in order of weight:**

1. **SF Pro → a substitute, for 326 of 335 runs (97%).** This is the deck's
   whole typographic voice and the largest fidelity decision in the build. The
   repo holds no candidate chosen for it (`ondeck/render/fonts/` has Anton,
   Archivo, Barlow Condensed, Bebas Neue, Big Shoulders, Darker Grotesque,
   Liberation Sans, Montserrat 800, Poppins 600, PT Sans Narrow, Roboto
   Condensed). Inter is the obvious first candidate on shape, but per Secret's
   `roles.py` the choice must be made the same way: width budgets from the
   authored boxes rule candidates OUT, and the pick among survivors is a
   recorded judgement call against Sean's PowerPoint screenshots. Because SF
   Pro IS installed here, a local render will look right and the shipped deck
   will not — **never judge text fit on this Mac without disabling the local
   face** (`local()` must not appear in the `@font-face` src).
2. League Gothic — add the OFL woff2 (1 run).
3. Calibri — 1 inherited run; identify it before bundling anything.

`SOURCE_LINE_HEIGHT = 1.21172` carries over unchanged (it is face- and
size-independent per Secret's four-deck fit).

---

## 5. Classification — CREATIVE (QA routing only)

**This routes QA effort and must never change rendering.** Every slide is
built from its own XML regardless.

| signal | value |
|:--|:--|
| shapes inheriting geometry from a layout placeholder | **0 of 268 (0.0%)** |
| placeholder shapes overriding locally | 0 of 268 — the deck contains **no placeholders at all** |
| non-placeholder, locally authored shapes | **268 of 268 (100%)** |
| non-placeholder shapes contributed by layouts | 0 across all 13 layouts |
| runs declaring their own typeface (`<a:latin>` on the run) | 345 of 346 |
| shapes past the canvas edge | 57 of 268 (21%) |
| slides whose layout name says what the slide is | 0 of 35 |

Nothing is inherited; every position, face, size and colour is stated on the
slide. That is the creative archetype at its limit → **full manual QA pass on
all 35 slides, desktop and mobile.** No slide earns a lighter pass.

### Can `deckkit.model.build_layout_index` route it the way Secret was routed?

**Mechanically yes, usefully no.** `build_layout_index` ran clean and every
model slide carries `layout_name`/`layout_type`. But Secret's routing was only
safe because a Google Slides author named the layouts by role. This deck is
PowerPoint-authored and its names are defaults: `DEFAULT` covers the cover, the
statements, the four diagram slides AND seven video slides; `23_Title Slide`
covers every showcase slide from a single full-bleed TVC to a four-clip
portrait wall. A `LAYOUT_ARCHETYPE` table can honestly say only:

```python
LAYOUT_ARCHETYPE = {"DEFAULT": None, "23_Title Slide": "showcase",
                    "Blank": None, "Title Only": None}
```

So routing here is a **per-slide table in `roles.py` keyed on measured
geometry** (section 3's groups), in the manner of Secret's `PLATE_SLIDES` /
`GROUP_B` / `HEADER_SLIDES` tuples and its slide-30 lesson: key on geometry,
never on `layout_name`. `archetype_of` still returns the default for an
undeclared layout, which is the visible-gap behaviour we want.

---

## 6. Size — where 1.57 GB comes from, and what it becomes

| kind | files | MB |
|:--|--:|--:|
| `.mp4` | 47 | 1,455.22 |
| `.png` | 54 | 78.63 |
| `.gif` (animated, 1,187 frames) | 1 | 25.54 |
| `.mov` | 2 | 9.45 |

**Four files are 791 MB — half the deck — and three slides (14, 21, 29) carry
911 MB.** Every media file is referenced; none is orphaned; none is duplicated.

### Single files over 100 MB

| file | MB | slide | what it is |
|:--|--:|--:|:--|
| `media10.mp4` | 242.07 | 14 | 1920x1080, 58.0 s, **33.4 Mbps** |
| `media29.mp4` | 224.87 | 21 | 1080x1920, 113.3 s, 15.9 Mbps |
| `media47.mp4` | 206.80 | 29 | 1920x1080, 48.6 s, **34.1 Mbps** |
| `media28.mp4` | 117.59 | 21 | 1080x1920, 48.1 s, 19.6 Mbps |

### Top 20 media files

| MB | file | slide |
|--:|:--|--:|
| 242.07 | `media10.mp4` | 14 |
| 224.87 | `media29.mp4` | 21 |
| 206.80 | `media47.mp4` | 29 |
| 117.59 | `media28.mp4` | 21 |
| 93.63 | `media8.mp4` | 11 |
| 83.31 | `media3.mp4` | 8 |
| 69.77 | `media27.mp4` | 21 |
| 42.98 | `media30.mp4` | 21 |
| 28.63 | `media9.mp4` | 12 |
| 27.10 | `media4.mp4` | 8 |
| 26.36 | `media1.mp4` | 7 |
| 25.54 | `image45.gif` | 26 |
| 24.75 | `media7.mp4` | 10 |
| 21.94 | `media6.mp4` | 10 |
| 17.73 | `media49.mp4` | 32 |
| 17.66 | `image50.png` | 30 |
| 17.00 | `media5.mp4` | 9 |
| 14.28 | `media45.mp4` | 27 |
| 12.70 | `media12.mp4` | 16 |
| 11.56 | `media14.mp4` | 16 |

### Every video

All 49 are H.264 / yuv420p in an MP4/MOV container, so nothing needs a codec
change to play; the re-encode question is purely rate. **48 of 49 carry an AAC
audio track.** 23.6 minutes of footage in total.

| file | slide | MB | WxH | s | codec / profile | fps | Mbps | audio | action |
|:--|--:|--:|:--|--:|:--|--:|--:|:--|:--|
| `media1.mp4` | 7 | 26.36 | 1080x1920 | 13.8 | h264 Main | 24.00 | 15.29 | aac | **re-encode** |
| `media2.mp4` | 7 | 0.82 | 720x1280 | 8.0 | h264 High | 24.00 | 0.82 | aac | copy |
| `media3.mp4` | 8 | 83.31 | 1920x1440 | 14.8 | h264 Main | 30.00 | 45.13 | aac | **re-encode** |
| `media34.mov` | 22 | 7.07 | 540x960 | 10.4 | h264 High | 30.00 | 5.45 | aac | **re-encode** |
| `media4.mp4` | 8 | 27.10 | 1080x1920 | 101.5 | h264 High | 25.00 | 2.14 | aac | copy |
| `media44.mov` | 26 | 2.38 | 300x600 | 14.9 | h264 Main | 24.00 | 1.28 | aac | copy |
| `media5.mp4` | 9 | 17.00 | 1920x1080 | 48.6 | h264 Main | 30.00 | 2.80 | aac | copy |
| `media6.mp4` | 10 | 21.94 | 1080x1920 | 11.8 | h264 Main | 24.00 | 14.94 | aac | **re-encode** |
| `media7.mp4` | 10 | 24.75 | 1080x1920 | 13.0 | h264 Main | 24.00 | 15.23 | aac | **re-encode** |
| `media8.mp4` | 11 | 93.63 | 1920x1080 | 40.8 | h264 Main | 29.97 | 18.36 | aac | **re-encode** |
| `media9.mp4` | 12 | 28.63 | 1280x720 | 30.4 | h264 High | 29.97 | 7.54 | aac | **re-encode** |
| `media10.mp4` | 14 | 242.07 | 1920x1080 | 58.0 | h264 Main | 30.00 | 33.37 | aac | **re-encode** |
| `media11.mp4` | 16 | 9.99 | 1080x1920 | 20.0 | h264 High | 30.00 | 3.99 | aac | **re-encode** |
| `media12.mp4` | 16 | 12.70 | 1080x1920 | 68.9 | h264 High | 25.00 | 1.47 | aac | copy |
| `media13.mp4` | 16 | 4.21 | 1080x1920 | 24.8 | h264 High | 29.97 | 1.36 | aac | copy |
| `media14.mp4` | 16 | 11.56 | 1080x1920 | 47.3 | h264 High | 29.97 | 1.96 | aac | copy |
| `media15.mp4` | 17 | 6.81 | 1080x1920 | 10.0 | h264 Main | 23.98 | 5.44 | aac | **re-encode** |
| `media16.mp4` | 17 | 8.78 | 1080x1920 | 24.9 | h264 High | 25.00 | 2.82 | aac | copy |
| `media17.mp4` | 17 | 2.79 | 1080x1920 | 20.6 | h264 High | 30.00 | 1.08 | aac | copy |
| `media18.mp4` | 17 | 1.57 | 828x1792 | 14.0 | h264 High | 23.98 | 0.90 | aac | copy |
| `media19.mp4` | 18 | 8.33 | 1920x1080 | 15.0 | h264 High | 30.00 | 4.44 | aac | **re-encode** |
| `media20.mp4` | 18 | 2.80 | 600x900 | 15.0 | h264 Main | 23.98 | 1.49 | aac | copy |
| `media21.mp4` | 19 | 2.97 | 1080x1920 | 12.1 | h264 High | 23.98 | 1.97 | aac | copy |
| `media22.mp4` | 19 | 2.92 | 1080x1920 | 12.1 | h264 High | 23.98 | 1.94 | aac | copy |
| `media23.mp4` | 19 | 2.96 | 1080x1920 | 12.1 | h264 High | 23.98 | 1.96 | aac | copy |
| `media24.mp4` | 20 | 11.41 | 1080x1920 | 39.4 | h264 High | 30.00 | 2.32 | aac | copy |
| `media25.mp4` | 20 | 10.78 | 1080x1080 | 60.1 | h264 High | 23.98 | 1.44 | aac | copy |
| `media26.mp4` | 20 | 7.57 | 1080x1920 | 27.2 | h264 High | 29.97 | 2.23 | aac | copy |
| `media27.mp4` | 21 | 69.77 | 1080x1920 | 53.7 | h264 High | 30.00 | 10.39 | aac | **re-encode** |
| `media28.mp4` | 21 | 117.59 | 1080x1920 | 48.1 | h264 Main | 30.00 | 19.57 | aac | **re-encode** |
| `media29.mp4` | 21 | 224.87 | 1080x1920 | 113.3 | h264 Main | 30.00 | 15.87 | aac | **re-encode** |
| `media30.mp4` | 21 | 42.98 | 1080x1920 | 18.9 | h264 Main | 24.00 | 18.18 | aac | **re-encode** |
| `media31.mp4` | 22 | 8.39 | 480x854 | 25.8 | h264 CBP | 50.00 | 2.60 | aac | copy |
| `media32.mp4` | 22 | 2.01 | 720x1280 | 10.0 | h264 High | 29.97 | 1.61 | none | copy |
| `media33.mp4` | 22 | 0.88 | 720x1280 | 5.5 | h264 High | 30.00 | 1.27 | aac | copy |
| `media35.mp4` | 23 | 6.38 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.11 | aac | **re-encode** |
| `media36.mp4` | 23 | 6.73 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.38 | aac | **re-encode** |
| `media37.mp4` | 23 | 6.51 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.21 | aac | **re-encode** |
| `media38.mp4` | 24 | 6.29 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.03 | aac | **re-encode** |
| `media39.mp4` | 24 | 6.41 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.13 | aac | **re-encode** |
| `media40.mp4` | 24 | 6.42 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.13 | aac | **re-encode** |
| `media41.mp4` | 25 | 6.47 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.17 | aac | **re-encode** |
| `media42.mp4` | 25 | 6.31 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.05 | aac | **re-encode** |
| `media43.mp4` | 25 | 6.36 | 1080x1920 | 10.0 | h264 Main | 25.00 | 5.09 | aac | **re-encode** |
| `media45.mp4` | 27 | 14.28 | 1920x1080 | 62.1 | h264 High | 29.97 | 1.84 | aac | copy |
| `media46.mp4` | 28 | 10.23 | 1920x1080 | 107.6 | h264 High | 60.00 | 0.76 | aac | copy |
| `media47.mp4` | 29 | 206.80 | 1920x1080 | 48.6 | h264 Main | 30.00 | 34.07 | aac | **re-encode** |
| `media48.mp4` | 31 | 8.05 | 1920x1080 | 14.1 | h264 High | 23.98 | 4.55 | aac | **re-encode** |
| `media49.mp4` | 32 | 17.73 | 1920x1080 | 27.8 | h264 High | 25.00 | 5.10 | aac | **re-encode** |
| `image45.gif` | 26 | 25.54 | 1000x571 | 47.5 | gif, 1,187 frames | 25.00 | 4.30 | none | **GIF→video (no deckkit path)** |

**Needing an ffmpeg re-encode: 27 of 49** (everything over 3 Mbps — 1,298.6 MB
of the 1,464.7). The other 22 (166.1 MB, 0.76-2.82 Mbps) are already web-rate
and should stream-copy, exactly Secret's case. **This deck is deck 9 and deck
10 at once**, and `build_videos` takes ONE mode per call — see section 7.

### Estimated output after `deckkit.assets.build_all`

Images are **measured**: every image run through `build_images`' exact
transform (RGB/RGBA, LANCZOS to `MAX_DIM` 2000, WebP q80 method 6) in memory.
The seven heaviest videos are **measured**: encoded in scratch with
`build_videos`' exact command line (`libx264 -crf 23 -preset medium -pix_fmt
yuv420p -movflags +faststart -an`), outputs deleted after sizing. The rest are
modelled.

| set | n | source MB | output MB | basis |
|:--|--:|--:|--:|:--|
| images → WebP | 55 | 104.18 | **3.10** | measured |
| 7 heaviest videos, CRF 23 | 7 | 1,038.1 | **201.5** | measured (5.2x) |
| other videos > 3 Mbps, CRF 23 | 20 | 260.5 | ~137.6 | modelled at 4 Mbps x duration, capped at source |
| videos ≤ 3 Mbps, stream-copied `-an` | 22 | 166.1 | ~153.9 | source minus ~128 kbps audio |
| animated GIF → mp4 (not a deckkit path today) | 1 | 25.5 | ~8.9 | modelled at 1.5 Mbps |
| **assets/ total** | | **1,568.9** | **≈ 505 MB** | |

Measured per-clip (source → CRF 23 → 5 Mbps ABR, MB): `media10` 242.1 → 21.2 →
34.2 · `media29` 224.9 → **71.6** → 70.0 · `media47` 206.8 → 20.9 → 29.3 ·
`media28` 117.6 → 20.7 → 29.3 · `media8` 93.6 → 18.4 → 24.2 · `media3` 83.3 →
19.0 → 9.1 · `media27` 69.8 → 29.6 → 32.6. CRF 23 beats deck 9's 5 Mbps cap on
five of seven and is the better default here; `media3` (1920x1440, 10.3 Mbps
at CRF 23) is the one clip a cap helps. All-5M-ABR total would be ≈ 550 MB.
Encode time for the seven: 191 s at CRF 23 on this machine; expect ~6-8 minutes
for the full set, sequential per rule 8.

Heaviest slides after encoding: **slide 21 ≈ 131 MB (four clips, one of them
71.6 MB)**, slide 8 ≈ 45, slide 16 ≈ 36, slide 20 ≈ 28, slide 14 ≈ 21.

### Against Secret

| | Secret (deck 10) | this deck | ratio |
|:--|--:|--:|--:|
| source `.pptx` | 77.7 MB | 1,569.0 MB | 20x |
| slides / shapes / videos | 31 / 211 / 7 | 35 / 268 / 49 | |
| `assets/` | 19.3 MB (72 files) | **≈ 505 MB** (104 files) | 26x |
| added to git | 18.66 MB | would be ≈ 505 MB | 27x |
| `index.html` | 813,433 B | **est. 1.5-2.0 MB** | ~2x |
| `index.standalone.html` | 26.9 MB | **est. ≈ 675 MB** | 25x |

`index.html` estimate: Secret's 813 KB scaled by shape count (268/211) gives
~1.0 MB for the desktop DOM; the locked rules require a SEPARATE mobile DOM,
which roughly doubles markup (not media — `data-media` threads the same
payload), hence 1.5-2.0 MB. Standalone = 505 MB x 4/3 base64 + HTML.

**A standalone build of this deck is not a deliverable of any kind.** Secret's
26.9 MB standalone already cost ~16 s of blank screen at 10 Mbps; 675 MB is a
file no phone will open and no `DOMParser` in the Deck Editor should be handed.
Deck 9 reached the same conclusion at 235 MB. That matters because Secret's
standalone was ALSO the workaround for the editor's image-predicate defect
(relative `src` harvests 0 images) — that workaround is unavailable here, so
this deck needs **absolute R2 URLs** (GAP's shape) for the editor to see its
media at all.

### What cannot live in git — stated plainly

* **The source `.pptx` (1.57 GB) — never.** Nor any of its four source videos
  over 100 MB (`media10`, `media29`, `media47`, `media28`): GitHub rejects any
  blob over 100 MB outright.
* **The encoded video set (≈ 493 MB, 49 files) — must go to Cloudflare R2, not
  the git object store.** No single encoded file crosses 100 MB (largest ≈
  71.6 MB, already past GitHub's 50 MB warning), so git would *accept* them —
  and that is the trap. `.git` is 35 MB today. One commit takes it to ~540 MB;
  assets are content-addressed by SOURCE hash, so any change of CRF, preset or
  ffmpeg version rewrites all 27 re-encoded blobs under the same names and adds
  another ~340 MB of unreachable-but-permanent history. **The second rebuild
  crosses 1 GB.** Secret's force-add pattern does not scale to this deck.
* **Can live in git** (force-added past `.gitignore`, as `9237592` did for
  Secret): `model.json`, `used_assets.json`, `asset_manifest.json`, and the 55
  WebP images (3.1 MB). Total well under 5 MB.
* **The published `gh-pages` repo has the same ceiling** (Pages: 100 MB/file,
  ~1 GB/site). `index.html` + `.nojekyll` + `CNAME` only; every `<video>` and
  `poster` absolute on `media.globalimaige.com`.

### What the repo does today for large media

* `out/` is gitignored. **Secret is the only deck with build outputs in git**
  (75 files, +18.66 MB, force-added so the byte-for-byte regeneration gate has
  something to compare against). Olay, Old Spice, HenHouse and Venus/Hestia
  outputs are untracked files on one disk.
* No LFS, no wrangler, no CI, no `r2 object put`. **Nothing in this pipeline
  writes to R2.** Media reaches R2 (`media.globalimaige.com`,
  `/shared/<deck>/<group>/<file>`) only through Deck Editor v14's explicit
  **`Upload to R2` modal** — never one-click Publish, which swallows upload
  failures and ships a deck of 404s (LEARNINGS rule 37; DECK9_HANDOFF §R2).
* HTML ships from a per-deck `<slug>-deck` GitHub repo on `gh-pages`. Two
  shapes exist: Patchology (one 26.87 MB self-contained file) and GAP (127 KB
  `index.html`, all media absolute on R2, since May 2026). **This deck is the
  GAP shape; there is no other option.**
* `R2_PREFIX` is a separate value typed into the editor and must not collide
  with `olay`, `olay-v2`, `oldspicepackaging`, `hh-creativestrategy`,
  `pgdigital`, `venus-hestia`. Not chosen yet.

---

## 7. Media plan, and what deckkit lacks for this deck

`build_model` parses this deck today — 35 slides, 268/268 shapes, themes
audited clean. **What follows are the gaps between "parses" and "correct".**
Each was found by measurement, not anticipated.

1. **Slide 16's second video resolves to the string `NULL`.** The clip
   `bioelements-sizzlereel-tradeshow-…` has
   `<a:videoFile r:link="rId3"/>` where rId3 is
   `Target="NULL" TargetMode="External"`; the real payload is on
   `<p14:media r:embed="rId4"/>` → `media12.mp4`. `model.py` reads only
   `a:videoFile`, takes `basename("NULL")`, adds `"NULL"` to `used_videos`,
   and reports `media12.mp4` as an unbound rel. `build_videos` would then print
   `MISSING NULL` and carry on — **a silently missing video, not an error.**
   Fix in the parser (through the parsed tree): prefer `p14:media/@r:embed`,
   and treat an External or unresolvable `a:videoFile` target as absent. This
   is a deckkit change shared by every deck; re-run Secret's byte-for-byte
   regeneration after it.

   **FIXED 2026-09-17, in the commit that adds this file.**
   `deckkit.model._video_target` reads `p14:media` first, then `a:videoFile`;
   `_rels` now records `TargetMode="External"`, and an External or missing rel
   reads as absent (the target STRING is never inspected — "NULL" is not
   special, External is). External rels are also excluded from
   `unbound_rels`, since they name no part of the package. Proven three ways:
   `tests/test_deckkit_video_target.py` (synthetic one-slide package through
   the real `build_model`; 3 of its 4 tests fail on the old parser with
   `['NULL']`, all pass now; suite 22/22); Secret regenerated from the T7
   source — `model.json`, `used_assets.json`, `asset_manifest.json` and 72/72
   assets byte-identical to what is committed, `index.html` identical to the
   recorded `b3933c4cf6b5ed86…` (813,433 B); and a model-only dry run of this
   deck — slide 16 now lists `media11`, `media12`, `media13`, `media14`, 49
   used videos all resolving to real files, "NULL" nowhere in `model.json` or
   `used_assets.json`, no skipped shapes and no unbound rels on any slide.
2. **`build_videos` takes one mode per deck; this deck needs two.** 22 clips
   should `copy`, 27 should re-encode. Either a per-file mode map in
   `roles.py` passed through `video_kw`, or a measured bitrate threshold
   (3 Mbps separates the two populations cleanly here: nothing sits between
   2.82 and 3.99). A per-deck measured call either way, per the docstring.

   **FIXED 2026-09-17.** `build_videos(..., modes={name: "copy" | "encode" |
   {copy, crf, preset, bitrate}}, audio="strip" | "keep")`. A file the map does
   not name takes the call's own mode, so a map of the exceptions is enough; a
   name the deck does not use is an error, not a no-op. `audio="keep"`
   preserves the track on both paths -- copied as-is when the video is
   stream-copied and the track is already AAC, otherwise encoded to AAC 160k
   (so a PCM `.mov` still lands in an mp4) -- and a silent source stays silent
   without failing. A keep/mapped build records `"mode"` and `"audio"` (does
   the OUTPUT carry a track) per file. **The default call is unchanged to the
   byte and writes no new key**: pinned by a test that builds the old call and
   the spelled-out defaults side by side, and by Secret's 7 videos.
   One hazard NOT fixed, because it predates this and no deck has hit it:
   outputs are named by SOURCE hash and an existing file is reused, so
   re-running with a different mode or `audio` into a populated `out/` keeps
   the old bytes. Deck 11 must be built into an empty `out/unilever_shpc/`;
   `out_sha256` will show it if that is ever forgotten.
3. **`-an` strips audio from all 49 outputs.** Correct for Secret's silent
   loops. Here 48 clips have audio and the content is TV commercials, UGC
   testimonials and a slide whose own copy says "Voiceover". The editor's
   attribute set is `autoplay muted loop playsinline`, so stripped audio is
   consistent with how the decks play today — but it is irreversible in the
   asset. **Decision for Sean, before the first encode**, because it changes
   every re-encoded byte.
4. **The animated GIF becomes a still.** `image45.gif` (slide 26, 1000x571,
   1,187 frames, 47.5 s, shown at 73x74% of the canvas — the slide's main
   content) goes through `build_images` → `Image.open().convert()` → a
   single-frame WebP of frame 0. Needs a GIF→mp4 path rendered as a muted
   looping `<video>`, or animated WebP. Note it is a `<p:pic>` image, so the
   editor will see it as an image either way.

   **FIXED 2026-09-17.** A GIF with more than one frame keeps its ordinary
   manifest entry -- the frame-0 WebP this stage always made, now its poster
   -- and gains an `"animated"` block: a silent H.264 clip of every frame
   (`vid_<source sha>.mp4`), with `frames`, `loop` (from the GIF's own loop
   count), `matte`, probed size, `out_bytes` and `out_sha256`. A renderer that
   has never heard of the block still gets a correct still. yuv420p needs even
   edges, so the odd row is CROPPED (1000x571 -> 1000x570), never resampled;
   frame delays come through untouched. `model.json` marks the shape
   `"animated_gif": true` and leaves it `type: "image"`, so the editor still
   sees a picture. No renderer reads either yet. Single-frame GIFs take the
   WebP path exactly as before.

   Measured on this deck (model + `build_images` only, scratch, deleted):
   poster `img_cbfe6e8e1f0e.webp` 1000x571, 0.009 MB; clip
   `vid_cbfe6e8e1f0e.mp4` 1000x570, **3,708,587 B**, 1,187 frames, loops --
   from a 25.54 MB GIF.

   **Transparency, settled from XML and file structure, not from pixels.**
   The colour behind `image45.gif` is **#FFFFFF**: slide 26 has no `<p:bg>`,
   `slideLayout13` has none, the master's is `<p:bgRef idx="1001">` ->
   `schemeClr bg1` -> clrMap `bg1=lt1` -> theme `lt1` = `FFFFFF`, and the GIF
   is the bottom-most shape in the spTree with nothing under it. ffmpeg, left
   alone, flattens GIF transparency onto **white** -- measured on a synthetic
   half-transparent GIF and pinned by a test (the test was first written
   expecting black, and failed; so was the first docstring). The two colours
   agree, so nothing needed re-emitting: built with and without the explicit
   matte, the clip is **byte-identical** (sha256 `e60be9a502dc30ce…`). It is
   moot twice over, because although the GIF DECLARES a transparency index
   (55), not one of its 1,187 composited frames has a non-opaque pixel -- the
   index is only inter-frame delta coding. White is nonetheless right by luck
   and wrong for any other ground (Secret's is `#A7C6ED`), so the colour is now
   explicit: `deckkit.assets.image_mattes(deck)` reads the opaque colour
   directly behind each animated GIF from the model (nearest covering solid
   fill, else slide bg, else master bg; NO entry over a photo, gradient,
   translucent fill or a layout that paints nothing), and the clip is
   composited over a painted copy of its own frames so nothing is retimed.
5. **`MAX_DIM` crushes slide 30.** `image50.png` is 1920x9419 (a full-length
   page capture) shown three times as three cropped windows (`srcRect` top
   0-27%, 40-70%, 70-100%), each ~364-401 pt wide. `MAX_DIM = 2000` applies to
   the LONG edge, so it ships as **408x2000** — 408 px across a box that is
   ~700 px wide on a 1680 canvas. Crops stay in CSS by design (reversible in
   the editor), so the fix is a per-asset `max_dim` override or a
   short-edge-aware cap, not baking the crop.

   **FIXED 2026-09-17 -- with one deliberate departure from the brief, and one
   re-baselined Secret asset.** `build_all(..., deck=deck)` computes, per
   image, the full-image size its largest displayed `srcRect` window needs
   (`image_needs`: box / window-fraction, over every use incl. video posters
   and `<p:bg>`). Crops stay in CSS; the whole file always ships.

   The brief said: size from the window at 2x a 1920-px canvas, capped at
   source, and leave images that are fine today byte-identical. Measured
   BEFORE coding, those two collide: at the 3840 standard **7 of Secret's 65
   images** fall short today (MAX_DIM trims several large photos), so applying
   it across the board re-sizes shipped decks as a side effect. The rule
   therefore uses TWO canvases (`_window_scale`): the FLOOR asks whether
   MAX_DIM is failing the image against MAX_DIM's own standard -- one 1920-px
   canvas -- and if not, the image takes the old code path and the old bytes;
   only an image that fails the floor is lifted, to the TARGET of 2x that
   canvas, never past its source. `"lifted_from"` records what MAX_DIM alone
   would have shipped. Re-sizing the other six to the 3840 standard is a
   legitimate future re-baseline; it is not smuggled into this one.

   On this deck: **`image50.png` 408x2000 -> 1605x7872** (0.95 MB), the only
   one of 55 images lifted. Image output total 3.10 MB -> 3.91 MB of WebP, plus
   the 3.71 MB GIF clip = 7.62 MB.

   **Secret re-baseline -- `image65.png`, 2026-09-17, on Sean's decision.**
   The floor caught one Secret image that really is short today: slide 30
   `Picture 12`, a 2400x1920 source shown through a 36.3% x 65.6% window in a
   box 747x1080 px on a 1920-px canvas; MAX_DIM's 2000x1600 gave that window
   726x1050 -- 2.8% under 1:1. It now ships whole:

       out/secret/assets/img_037499090073.webp
       old  2000x1600   87,660 B  sha256 7b8f4025f9edb842d73fde9578c562a77f3bbc4e84ce6c7fa814098f37cbfc2a
       new  2400x1920  115,988 B  sha256 d1e1f685912e110ea69127bb12f68544429770f542d50ae93d7eb80f1c693569

   Same filename (assets are named by source hash), so `index.html` is
   byte-identical (`b3933c4cf6b5ed86…`), as are `model.json`,
   `used_assets.json`, the other 71 assets and every other manifest entry.
   **The live Secret site was NOT republished and still serves the old file.**
   Full record in `DECK10_MOBILE_HANDOFF.md`. Gate:
   `tools/strip_compare.py <regen> --allow --rev <pre-rebaseline commit>
   --allow-assets image65.png` -> "71 of 72 identical + 1 allowed"; against
   the re-baseline commit itself, 72 of 72 with no allowance.
6. **Playback intent is not read.** All 23 video slides carry `mediacall` timing that
   distinguishes autoplay (`withEffect`) from click-to-play (`clickEffect`);
   e.g. slide 14's TVC is click-to-play, slide 16's four clips autoplay.
   deckkit ignores `<p:timing>` entirely; the renderer autoplays everything.
   With 49 clips that is also a load problem, not just fidelity: Secret's 7
   autoplaying videos already opened 6 concurrent connections and stalled a
   single-threaded server. **49 must not all fetch at load** — `preload="none"`
   plus an IntersectionObserver play/pause gate is required in the new
   `render.py`, and `+faststart` (already applied) is what makes that stream.

   **FIXED 2026-09-17 (the parser half).** `deckkit.model._playback_index`
   reads each slide's `<p:timing>` through the parsed tree and joins timing
   nodes to shapes by `<p:spTgt spid>` == `<p:cNvPr id>` only. Every video in
   `model.json` now carries `"playback"`: `auto` (a `playFrom` mediacall in a
   main-sequence step that starts on slide entry), `click` (a clickEffect in
   the main sequence, or only PowerPoint's interactive toggle-pause sequence)
   or `none`. `nodeType` alone is NOT the test: a step that waits for a click
   always contains a clickEffect, so a withEffect riding in that step is
   `click`; and auto outranks click because every auto clip also carries the
   toggle-pause sequence. `"loop"` / `"muted"` are written only when the
   shape's `<p:cMediaNode>` states them (`repeatCount`, `mute`) — absent
   attribute, absent key. **No renderer reads any of this yet**; Secret's
   `index.html` is byte-identical with the fields present. The load half of
   this item (49 clips must not all fetch at load) is still open and belongs
   to the new `render.py`.

   Measured on this deck: **43 auto, 6 click, 0 none.** The six click-to-play
   clips are exactly the long, heavy, spoken ones — `media10` (slide 14, 58 s
   TVC), `media27`-`media30` (slide 21, the four UGC testimonials, 19-113 s),
   `media47` (slide 29, 49 s) — 904 MB of source between them, and none states
   `mute`. Stated muted: 27 clips; stated looping: 18; two state a finite
   repeat (`media20`, `media46`); 21 state neither. That bears directly on the
   audio decision in item 3: the author muted the ambient loops and left the
   click-to-play films audible. Secret, for comparison: 7 of 7
   `auto` / `loop` / `muted`, which is what it shipped as.
7. **Entrance animations (slides 2, 34) and fade transitions (15 slides) are
   dropped.** Recorded, not proposed: no deck in the corpus renders them.
8. **`asset_manifest.json` records the SOURCE sha and `out_bytes`, not an
   output hash.** With the videos on R2 rather than in git, the byte-for-byte
   gate needs `out_sha256` per asset so a regeneration can be verified against
   the committed manifest instead of against committed blobs.

   **FIXED 2026-09-17.** `deckkit.assets` writes `out_sha256` beside
   `out_bytes` for every WebP, SVG and video, hashed from the finished file on
   disk after the atomic rename. `sha` is unchanged and still names the asset
   by its SOURCE. Secret's committed `asset_manifest.json` now carries all 72,
   and each equals the sha256 of the committed blob it names — so the manifest
   alone can now stand in for the blobs, which is what this deck needs.
9. **CRF re-encode determinism is unproven.** Secret's byte-for-byte proof
   covered stream-copy only ("deterministic under ffmpeg 8.1"). libx264 output
   is normally reproducible for a fixed build, preset and thread count, but
   that has not been shown on this machine. Prove it on one clip (encode twice,
   compare hashes) before the gate is relied on; pin `-threads` if it fails.

   **RESOLVED 2026-09-17.** Two complete builds into two empty directories,
   from two separate extractions: all 27 CRF 23 re-encodes -- and their AAC
   audio encodes -- came out byte-identical, with no `-threads` pin (ffmpeg
   8.1, 8 cores). See BUILD 1. Proven for THIS machine and THIS ffmpeg; a
   different x264 build is a different claim, and `out_sha256` will say so.
10. **Local disk.** 4.6 GB free on the boot volume. A build needs the raw
    extract (1.57 GB) + `out/` (~0.5 GB) + scratch partials; a standalone
    (0.67 GB, not wanted anyway) would not fit alongside. Pass `--raw` to a
    roomier volume or free space first. Do NOT point `--raw` at a directory
    beside the source on the T7 without care — `build()` does
    `shutil.rmtree(raw)`.

Not gaps for this deck (verified, so nobody re-checks): charts, tables,
SmartArt, OLE (none); multiple slide masters (one); theme disagreement
(`theme2` is notes-only); layout-inherited shapes and backgrounds (none);
gradients (none); rotation (none); review stickers (none flagged); connectors
(none); SVG pictures (none); `hdphoto`/`.wdp` (none).

### The build, when it starts

`phase_1c/unilever_shpc/` with `build.py` (Secret's driver pattern:
unzip → `DeckPaths(...)` directly, not `for_deck` → `dkmodel.write_model` →
`dkassets.build_all`), `roles.py` (slug, per-slide geometry groups, SF Pro
substitution with its evidence, video mode map), a **new** `render.py`
(OPEN ITEMS 2), `validate.py`. **No `model.py`** — `deckkit/model.py` is the
parser. Items 1, 2, 4, 5 and 8 above are deckkit changes and land there, not
in a deck-local fork. (1, 2, 4, 5, 6 and 8 are all done as of 2026-09-17 — see
their FIXED notes. Open in this list: 3 is now a settled decision (section 9
item 5), 6's LOAD half and 7 belong to the new `render.py`, 9 and 10 stand.
deckkit changes are gated with `tools/strip_compare.py`.)

---

## 8. Locked rules

- Desktop: pixel-faithful, every shape at its authored PPTX position, 16:9 canvas in cqw units, one scroll-snap point per slide.
- Mobile: a separate DOM, never a reflow of desktop (Wheeber pattern), 100svh per screen, full-bleed photos, cqh typography with container-type: size, scroll feel matching patchology.globalimaige.com.
- PPTX XML is ground truth. Never take values from screenshots.
- Geometry and chart edits go through the parsed XML tree. Chart <c:v> values must match their exact stored form.
- Deck Editor v14 classes .t .ci .tlt .tlb. Never apply .ci to whitespace-only runs or runs with meaningful edge whitespace.
- Images use data-media on desktop <img>, threaded to the mobile --photo variable. No duplicated payloads.
- Delivery gate: editor_roundtrip.py passes, and pptx to html regenerates byte for byte, as Secret does.
- The text checker must decode XML entities before comparing.

On the last rule: `&amp;` is stored on **32 of this deck's 35 slides**
("Skin, Hair & Personal Care" is the running footer). An undecoded checker would fail almost every slide by a
constant 4 characters per occurrence — Secret's tell, at ten times the scale.

---

## 9. OPEN ITEMS

The locked rules stand. These are the places the repo does not yet meet them.

### 1. `editor_roundtrip.py` does not exist

Not in the working tree, not in any commit on any branch
(`git log --all -- '*roundtrip*'` is empty), not found by Spotlight anywhere on
this Mac. The delivery gate names a script that has never been written. The
closest existing evidence is prose: `FRAGMENT_NAV_HANDOFF.md` §2 and `NOTES.md`
"Editor round-trip — ids survive", plus Secret's one-off verification against
Deck_Editor_v14's own parse (slide count, image/video harvest counts, live
character count per slide). **It must be written before delivery**, and
Secret's checks are its starting spec: parse with the editor's predicates
(`editableImgs()`), assert slides = 35 (not 70 — rule 22, and a separate mobile
DOM makes that failure mode MORE likely here, not less), harvest counts equal
document counts, per-slide live characters equal the model's, and a save with
no edits is byte-identical.

### 2. Secret's `render.py` is not the template

Secret shipped a **mobile reflow of the single desktop DOM** ("One
`<section class="slide">` per source slide; no second DOM") and **no
scroll-snap anywhere** (implemented, shipped and pulled: any snap position
re-targets a fling passing it). Both are the opposite of this deck's locked
rules. This deck needs a **new `render.py`** with a separate mobile DOM
(Wheeber pattern) and one desktop snap point per slide — **not a copy of
`phase_1c/secret/render.py`**. Reusable from Secret: `run_css`, `para_html`,
`box_style`, `crop_img`, `rgba`, the `deckkit.css`/`markup` helpers, and the
`p.t` strut lesson (emit a `font-size` on `p.t` from the paragraph's own runs —
LEARNINGS 41(s) — from day one rather than inheriting the open defect). Not
reusable: `plate_css` / `divider_css` / `header_css` and the
`@media (max-width:820px)` block — those ARE the reflow. Two things to settle
on evidence before coding: Secret's reason for pulling snap was measured on
mobile fling, so confirm desktop-only snap does not reproduce it; and the
standing test ("strip the mobile block → character-identical to desktop")
needs restating for a two-DOM document.

### 3. deckkit drops charts and reads only the first slide master

Both gaps stand in `phase_1c/deckkit/model.py`: any `graphicFrame` that is not
an `<a:tbl>` is skipped as "graphicFrame, not a table", and master defaults
come from `masters[0]` only. **Slides affected in this deck: none.** Charts by
slide: **zero chart graphicFrames on all 35 slides** — no `ppt/charts` part, no
`ppt/embeddings` workbook, and no `graphicFrame` of any kind (0 charts, 0
tables, 0 SmartArt, 0 OLE), so there is no chart type or embedded-data status
to record. One slide master, so `masters[0]` is the only master. The
chart rule in section 8 is locked but has nothing to act on here. The gaps this
deck DOES hit are section 7's: **slide 16** (the `NULL` video link), **slide
26** (animated GIF flattened), **slide 30** (`MAX_DIM` on a 1920x9419 image),
**all 49 video shapes on 23 slides** (audio strip, playback intent, single
video mode), **slides 2 and 34** (entrance animations).

### 4. The source decks have one copy each

`~/Downloads/2026_GIF_AI_…_UNILEVER_OSR.pptx` and `…_OSR1.pptx` are both
truncated at exactly 2,794,192,896 bytes with no central directory and cannot
be opened. They were left exactly as found. The T7 Touch copies are the only
readable ones, Time Machine has no destination configured (per
`DECK10_MOBILE_HANDOFF.md`, unchanged), and the boot volume has 4.6 GB free —
too little to hold a copy of OSR1 (2.79 GB) alongside a build. **Make a
hash-verified second copy of this deck on another volume before any build
work** (expected sha256 at the top of this file). Nothing in this session
copied, moved or modified either deck.

#### UPDATE 2026-09-17 — truncated `~/Downloads` copies cleared

The paragraph above describes the state at reconnaissance. Later the same day,
on Sean's instruction, in this order:

* **Verified truncated:** `~/Downloads/…_UNILEVER_OSR.pptx` was exactly
  2,794,192,896 bytes (mtime 2026-09-16 00:20:02) and `unzip -l` failed with
  "End-of-central-directory signature not found".
* **Verified intact first:** the T7 `…_UNILEVER_OSR.pptx` re-hashed to
  `d2539cf1…201226` — identical to section 1 — at 1,569,045,169 bytes, mtime
  unchanged. The T7 `…_OSR1.pptx` passed `unzip -l` (exit 0, 428 entries,
  2,791,875,898 bytes) with **60** `ppt/slides/slideN.xml`.
* **Moved to the macOS Trash** via Finder (`osascript … delete POSIX file`, not
  `rm`): the truncated `~/Downloads/…_UNILEVER_OSR.pptx`. Confirmed gone from
  `~/Downloads` and present in `~/.Trash` at the same byte count. Recoverable
  until the Trash is emptied; it was never a usable file.
* **The `~/Downloads/…_OSR1.pptx` copy disappeared OUTSIDE any session.** It
  was present and truncated at reconnaissance; by the first attempt at this
  step it no longer existed (`stat`: no such file), Spotlight found it nowhere,
  and `~/.Trash` was empty (directory mtime 2026-09-17 01:15 — consistent with
  it having been trashed and the Trash emptied by hand, which is an inference,
  not an observation). No session command removed it.
* **Boot volume:** 4.6 GB free at reconnaissance → 29 GiB free (86% used)
  before this step, freed outside the session. Moving a file to the Trash frees
  nothing until the Trash is emptied (+2.79 GB then). Section 7 item 10's disk
  constraint no longer binds a build; it would bind again below ~3 GB.

What has NOT changed: **each source deck still has exactly one copy, on the
T7, with no backup.** Clearing the broken copies removed clutter, not risk.
The hash-verified second copy is still owed, and there is now room for it.
*(Superseded the same day — see the next update.)*

#### UPDATE 2026-09-17 — hash-verified second copy made

```
/Users/gif025/DeckSources/unilever_shpc/        (outside the repo, outside ~/Downloads)
  2026_GIF_AI_GlobalCapabiltiesPresentation_SKIN_HAIR_PERSONAL_CARE_UNILEVER_OSR.pptx
      1,569,045,169 bytes   35 slides
      sha256 d2539cf1b1ea9439df047a34723dea10cb3a0ddb4d2066616a8a775444201226
  2026_GIF_AI_GlobalCapabiltiesPresentation_SKIN_HAIR_PERSONAL_CARE_OSR1.pptx
      2,791,875,898 bytes   60 slides
      sha256 dd7a88f037e84a0d2d83abe1b906a723a8ff6fe095fb7bb781f14dfe96d192cb
  SHA256SUMS                                     (`shasum -a 256 -c SHA256SUMS` → both OK)
```

Copied from the T7 with `cp -p`, one at a time (27 GiB free before, 23 GiB
after). For each file: byte size equals the T7 original; sha256 of the T7
original and of the copy were computed independently and are identical
(UNILEVER_OSR also equals section 1's recorded hash; OSR1's hash is recorded
here for the first time); `unzip -l` on the copy exits 0 with 35 / 60 slides.
mtimes are preserved. The copies were then made read-only (`chmod a-w`) — they
are reference copies, and `phase_1c/<slug>/build.py` only ever reads its
source.

**Either location is now a valid build source**; the T7 path stays the source
of record. Verify with `SHA256SUMS` before building from the local copy.

**STILL OPEN — an off-site third copy.** Both copies are in one room: one USB
SSD and one laptop whose Time Machine has no destination. Theft, fire or a
spill takes both. A third copy somewhere else (R2 is already in this
workflow; any cloud drive would do) verified against the same two hashes
closes this item. Not done, not started.

**Correction to the update above — the vanished OSR1 copy was MOVED, not
deleted.** Two files now sit on the T7 root that were not there at
reconnaissance: `…_OSR1 2.pptx` and `…_OSR1 copy.pptx`. Both are exactly
2,794,192,896 bytes with mtime 2026-09-16 23:23:12 — the byte count and the
mtime of the truncated `~/Downloads/…_OSR1.pptx` — and both fail `unzip -l`
with "End-of-central-directory signature not found". So the earlier inference
(trashed by hand, Trash emptied) was wrong. They were checked read-only and
left exactly as found. **They are a hazard where they are:** two unopenable
files (5.6 GB together) named almost identically to the real OSR1, beside it. Do not
build from, hash against, or "recover" either one; the real file is
`…_OSR1.pptx` with the sha256 above. Removing them is Sean's call.

#### UPDATE 2026-09-17 — hazard RESOLVED: truncated OSR1 files off the T7 root

On Sean's instruction, in this order:

* **Re-verified both** — `…_OSR1 2.pptx` and `…_OSR1 copy.pptx`: each exactly
  2,794,192,896 bytes (mtime 2026-09-16 23:23:12), each failing `unzip -l`
  with "End-of-central-directory signature not found".
* **Hashed the real `…_OSR1.pptx` first:** `dd7a88f0…d192cb`, matching
  `SHA256SUMS`, before anything was touched.
* **Moved ONLY those two to the Trash** via Finder (`osascript … delete POSIX
  file`, not `rm`), one at a time. Both are gone from the T7 root and present
  in the T7's own Trash (`/Volumes/T7 Touch/.Trashes/501/`) at the same byte
  count. The T7 root now holds exactly two files of this family: the real
  `…_OSR1.pptx` and the real `…_UNILEVER_OSR.pptx`.
* **Re-hashed both real decks on the T7 afterwards:**
  `shasum -a 256 -c ~/DeckSources/unilever_shpc/SHA256SUMS` run from the T7
  root → both `OK`; sizes and mtimes unchanged.

Files trashed from an external drive stay ON that drive (in its `.Trashes`
folder) until the Trash is emptied **with the T7 mounted**; unplugging it first
just hides them. Until then they remain recoverable and they are no longer
beside the real deck, which was the hazard.

Open under this item now: **only the off-site third copy.**

### 5. Decisions needed from Sean before the first encode

~~Strip audio or keep it (7.3)~~ · the SF Pro substitute (section 4) · the R2
prefix · ~~whether click-to-play clips stay click-to-play (7.6)~~.

**SETTLED 2026-09-17 — audio and playback come from the deck's own XML, not
from a preference.**

* **Audio is kept in every file.** Build with `audio="keep"` on both the copy
  and the re-encode path (7.2). Nothing is stripped at the asset stage, because
  what is stripped there cannot be given back on the page.
* **Muting follows `model.json`.** A clip whose `<p:cMediaNode>` states
  `mute="1"` (27 of 49) plays muted; the page mutes it, the file does not. A
  clip that states nothing is not muted by assumption -- and browsers refuse
  unmuted autoplay, so an `auto` clip with no stated mute is a case the new
  `render.py` must handle explicitly (muted autoplay with an unmute control,
  or wait for a gesture) rather than discover on a phone. There are 16 such
  clips: the 43 auto less the 27 stated muted.
* **Click-to-play follows `playback`.** The six `click` clips -- `media10`,
  `media27`-`media30`, `media47`, the long spoken films, none of them muted by
  the author -- wait for the viewer; the 43 `auto` clips start on entry,
  subject to the load gate in 7.6.

Still open here: the SF Pro substitute and the R2 prefix.

---

# BUILD 1 -- first full asset build, 2026-09-17

**Model + 55 images + 49 videos + the GIF clip. Nothing rendered, nothing
uploaded, nothing published. No media is in git.**

(Correction made with this build: section 3's geometry table listed slide 20
under both "portrait video wall" (as part of "19-25") and "mixed video". Its
three clips are 24x75, 42x75, 24x75 -- it is mixed, and `roles.py` lists it
once. The table row now reads "16, 17, 19, 21-25".)

## What exists

    phase_1c/unilever_shpc/
      build.py     unzip -> DeckPaths -> write_model -> build_images -> videos, one file per call
      roles.py     slug, GEOMETRY_GROUPS (section 3), VIDEO_MODES written out per file
                   (27 encode / 22 copy), AUDIO = "keep", fonts an explicit TODO
                   (FONTS_DECIDED = False -> section 4), R2_PREFIX = None
      (no model.py by design; no render.py and no validate.py yet)

    out/unilever_shpc/                 499 MB on disk, gitignored
      model.json            401,562 B  sha256 24040d93ce780804…   COMMITTED (force-added)
      used_assets.json        1,784 B  sha256 32aa5daebd0e2dcc…   COMMITTED
      asset_manifest.json    33,537 B  sha256 401bf69eac4d73c1…   COMMITTED
      assets/               105 files, 498.15 MB                  NOT in git, by decision

    python3 -m phase_1c.unilever_shpc.build --raw ~/DeckBuild/unilever_shpc/raw

`build.py` differs from Secret's driver in three deliberate ways: it REFUSES a
non-empty `--out` (the source-hash reuse hazard, section 7 item 2); it asserts
`roles.VIDEO_MODES` names exactly the deck's used videos, so a revision that
adds or drops a clip reopens the decision instead of falling to a default; and
it builds videos one file per call in `build_videos`' own sorted order, timing
each and surviving a failed encode (recorded, reported, non-zero exit, never
written into the manifest). The manifest is identical to a single
`build_all` call's.

The raw extract lived at `~/DeckBuild/unilever_shpc/raw` -- boot volume,
outside the repo, off the T7 -- and was deleted afterwards; the two build logs
are kept there. Source: the local copy in `~/DeckSources/unilever_shpc/`,
verified `OK` against `SHA256SUMS` immediately before.

## Result

309 s wall clock (extract 4 s, model 0.3 s, images incl. the GIF clip 18 s,
videos 287 s). **49 of 49 videos, 0 failures.**

| set | n | source MB | output MB |
|:--|--:|--:|--:|
| images -> WebP | 55 | 104.18 | 3.91 |
| animated GIF -> H.264 | 1 | 25.54 | 3.71 |
| videos re-encoded, CRF 23 + AAC 160k | 27 | 1,298.6 | 324.5 |
| videos stream-copied, audio copied | 22 | 166.1 | 166.0 |
| **assets/** | **105 files** | **1,568.9** | **498.15** |

Reconnaissance estimated ~505 MB (section 6); measured 498.15, with audio
kept, which the estimate had assumed stripped. Largest single file:
`media29.mp4` -> `vid_8b5b8a8ec320.mp4`, **73.99 MB** -- under GitHub's 100 MB
wall, over its 50 MB warning, and beside the point: none of it goes to git.

Verified against the files on disk, not the log:

* `model.json`: 35 slides, 268 shapes, 49 videos; "NULL" nowhere in it or in
  `used_assets.json`. Slide 26's picture carries `animated_gif`.
* `asset_manifest.json`: `out_sha256` + `out_bytes` on all 105 entries (55
  images, 49 videos, 1 `animated` block), every one matching its file;
  `assets/` holds exactly the files the manifest names, no strays.
* ffprobe on all 50 clips: H.264, yuv420p, `moov` before `mdat` (faststart).
  **AAC audio on 48 of 49 videos**; `media32.mp4` has no track at source and
  none out (`"audio": false`); the GIF clip is silent.
* Slide 26: poster `img_cbfe6e8e1f0e.webp` (8,714 B) + clip
  `vid_cbfe6e8e1f0e.mp4` (3,708,587 B, 1000x570, matte `#FFFFFF`).
* Slide 30: `image50.png` at **1605x7872**, `lifted_from [408, 2000]`.

## The regeneration gate -- PASSED

A second complete build, from a second extraction, into a second empty
directory, hash-compared file by file against the first: **108 of 108 files
IDENTICAL** -- `model.json`, `used_assets.json`, `asset_manifest.json`, 55 of
55 WebP, 50 of 50 MP4. None missing, none extra. This is this deck's
byte-for-byte gate, and because the media is not in git it is re-runnable
against the COMMITTED `asset_manifest.json` alone: rebuild anywhere, compare
`out_sha256`.

## Found by this build -- three re-encodes came out LARGER than their source

| file | slide | source | output | source Mbps |
|:--|--:|--:|--:|--:|
| `media19.mp4` | 18 | 8.33 MB | **11.72 MB** | 4.44 |
| `media49.mp4` | 32 | 17.73 MB | **18.79 MB** | 5.10 |
| `media42.mp4` | 25 | 6.31 MB | **6.45 MB** | 5.05 |

For these the 3 Mbps rule buys a second lossy generation AND a bigger file --
the exact trade Secret's `copy` switch exists to refuse. `media11` (9.99 ->
8.64) and `media36` (6.73 -> 5.90) are marginal wins of the same kind. The rule
was applied as written and the build is committed as built; flipping these
three to `"copy"` in `roles.VIDEO_MODES` is a one-line-each change that would
save 4.6 MB and one generation of loss, and moves three `out_sha256` values.
**Sean's call** -- it is a change to a per-file decision he specified.

## Not done / still open

* **No push was possible from this session** -- the harness's permission
  classifier blocked `git push`. Commits are local until Sean pushes.
* No `render.py`, no `validate.py`, no `index.html`. Fonts undecided (section
  4), R2 prefix unchosen, `editor_roundtrip.py` unwritten, off-site third copy
  of the sources not made (OPEN ITEMS 1, 2, 4, 5).
* Nothing has been uploaded to R2; the 498 MB in `out/unilever_shpc/assets/`
  exists on this one disk only. It is fully regenerable from the source deck
  in ~5 minutes, which is the reason that is acceptable.
