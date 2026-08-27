# OnDeck Pipeline — Notes

Short, factual corrections and clarifications to the conversion spec. The full pattern reference lives in Claude's memory (`project_pipeline_patterns.md`); this file captures things specific to this project that don't fit elsewhere.

---

## Color resolution has TWO sources, not one

The spec says "extract brand colors per deck, never assume." That's correct, but it's not the whole picture: a deck's color universe is the **union** of two sources, with PowerPoint's modifiers stacked on top of either:

```
  Final color = (theme palette  OR  inline shape fill)
              + lumMod / lumOff (optional, applied to either)
              + alpha           (optional, applied to either)
```

**Source 1 — Theme palette** (`ppt/theme/theme1.xml`)
The 12 named scheme colors: dk1, lt1, dk2, lt2, accent1–6, hlink, folHlink. Shapes reference these via `<a:schemeClr val="accent1"/>`.

**Source 2 — Inline shape fills** (in slide XML)
A specific shape can override the theme entirely with `<a:srgbClr val="00B0F0"/>`. These are NOT in the theme palette and never will be.

**How we found this:** the original handoff doc said P&G's accent was `#00B0F0`. When `parse/theme.py` ran, the theme palette had `accent1 = #156082` and `accent4 = #0F9ED5` — neither matched. The cyan `#00B0F0` is a direct inline fill on individual shapes, not a theme reference.

**Implication for the auto-detect phase:**
A "what color is this shape?" question must check inline fill first, fall back to scheme reference second, then apply lumMod/lumOff/alpha. Asking only the theme palette will miss most brand-specific colors used in section dividers and accent moments.

---

## Videos are `<p:pic>` shapes, not `graphicFrame`

The handoff implied videos use `<p:graphicFrame>` shapes. They don't. In PPTX, a video is a `<p:pic>` shape carrying media-extension metadata:

```
<p:pic>
  <p:nvPicPr>
    <p:nvPr>
      <p:extLst>
        <p:ext><p14:media r:embed="..."/></p:ext>   ← the video binary
      </p:extLst>
    </p:nvPr>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="..."/>                         ← the poster image
  </p:blipFill>
  ...
</p:pic>
```

**Detection rule:** look INSIDE `<p:pic>` shapes for `<p14:media>` in the nvPr extLst, NOT by filtering for `graphicFrame`. A `<p:pic>` with media metadata is a video; without, it's an image. Without this rule the pipeline silently drops every video.

**How we found this:** when `parse/slide.py` ran across all 23 P&G slides, the aggregate shape counts showed `graphicFrame=0`. Slide 16 (which has a working video in the bundle) had exactly one shape — a `pic`. Same pattern on slide 7. The video metadata lives inside the `<p:pic>`, not in a separate shape kind.

**Implication for `parse/media.py`:** the module looks at every `<p:pic>` shape and checks for `<p14:media>` to decide "image" vs "video." It also resolves THREE relationship IDs from inside that pic: `<p14:media r:embed>` (binary), `<a:videoFile r:link>` (legacy duplicate), `<a:blip r:embed>` (poster).

---

## Font substitution: P&G is matched-metric, no 1.36× scaling

The handoff specified a 1.36× visual scale-up when substituting Univers → Barlow, plus empirical inherited-size defaults of 28pt bold / 22pt regular. Cross-checking against the bundle's actual CSS, those rules don't fire for P&G:

```
slide   text                              declared  HANDOFF says   BUNDLE renders
──────────────────────────────────────────────────────────────────────────────────
  1     "CREATIVE DECK"                   44pt      60pt (×1.36)   44pt
  1     "Q1-Q3 2025"                      66pt      90pt (×1.36)   66pt
  8     "RETAIL/SHELF/UNITS"              88pt      88pt           88pt
 22     stakeholder name list             None      22pt           16pt
 23     "FOR BUSINESS QUERIES" (bold)     None      28pt           18pt
```

Bundle uses Barlow Condensed via Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@..."/>
--font-cond: "Barlow Condensed", "Univers Condensed", "Arial Narrow", sans-serif;
```

**Why the difference: matched-metric vs cross-metric substitution.**

- **Matched-metric** — source and target share metrics (x-height, advance width). Example: Univers Condensed → Barlow Condensed. Substituted text occupies the same visual footprint; declared size renders 1:1.
- **Cross-metric** — source and target differ. Example: Univers Condensed → Arial (condensed → regular width). Substituted text reads visually smaller; PowerPoint compensates with an undocumented ~1.36× scale-up.

P&G is matched-metric. The handoff's 1.36× rule was correct *in concept* (PowerPoint does this) but mis-applied to P&G *in practice*.

**Implication for the rebuild:**
- The bundle's actual rules (declared 1:1, inherited 16/18pt) live in `parse/font_calibration.py` as the active path for any typeface in the matched-metric table.
- The 1.36× rule is preserved as `CROSS_METRIC_SCALE`, gated behind `classify_substitution()`. It only fires for typefaces NOT in the matched-metric table — i.e. when a future deck uses a substitution we haven't validated yet. Acts as a documented fallback, not active code for P&G.
- Add new matched-metric pairs to `MATCHED_METRIC_SUBS` as new decks are validated.

---

## Deck-level brand color is design metadata, not derivable from PPTX

The P&G brand cyan `#00B0F0` appears in the rendered bundle as a deck-level CSS variable (`--bg-cyan`) used as the **canvas background** on every slide. Tracing back to the source:

- It is NOT in the theme palette (theme accent1 is `#156082`, accent4 is `#0F9ED5`)
- It is NOT in any slide layout's background fill
- It is NOT in the master's background fill (master uses `<p:bgRef><a:schemeClr val="bg1"/></p:bgRef>` = white)
- It only appears as **inline `<a:srgbClr val="00B0F0"/>`** on the cover slide's full-bleed bg shape, AND on isolated decorative shapes throughout the deck

So the deck's brand color is a **design intent that the deck-author chose**, encoded as inline shape fills but not as a deck-wide property. The bundle's prior session captured it manually as a CSS var.

**Implication for the rebuild:** auto-detection is unreliable (which inline fill is "the brand color"?). The manifest needs an explicit `deck_brand_color` field that templates use as the canvas background when shapes don't cover 100% of the canvas.

**Where it shows up visually:** any template where the photo / content shapes don't cover the full canvas. P&G section dividers leave a ~1.6% / 2.5% border around the inset photo — that border shows the canvas color. Without an explicit brand color, my first slide-4 render had a black border there; the bundle had cyan.

---

## (Future entries below — keep this short and chronological)

---

## Mobile video: container aspect ratio matches source video (16:9)

**Policy: mobile videos use the *source video's* aspect ratio on the container, not a fixed portrait box.** For a 16:9 source video, that's `aspect-ratio: 16/9; object-fit: cover` (cover and contain produce identical output when aspects match — cover is the safer default if the encoded video drifts slightly off-spec). The 16:9 video then renders full-width with no cropping and no letterbox bars.

```css
#deck-mobile .video-mobile video {
  width: 100%;
  aspect-ratio: 16/9;       /* match the source — see ffprobe */
  background: #000;
  display: block;
  object-fit: cover;
}
```

**Bundle parity note: bundle uses `aspect-ratio: 4/5; object-fit: cover`,** which crops ~27% off each side of a 16:9 source — destroying the wordmark/branding at the frame edges (e.g. slide 7's Wicked 2 promo). We diverge to preserve the wordmark content, in the same class as the canvas_bg, font-face, and section_divider gradient-direction divergences.

**Vertical space below the video.** A 16:9 box is ~44% as tall as the bundle's 4:5 box on a phone — the freed space is template-allocated. For each video slide, decide what fills it:
- **Other content from desktop** (caption, secondary headline, brand mark) — render in the freed space.
- **Brand background** (canvas_bg per the manifest hint, or `var(--bg-cyan)` for cyan slides) — leave the space clean.
- **Never** dead black letterbox bars or empty white voids.

**Slide 7 specifically:** mobile flow is `top-bar` (cyan w/ logo) → `circle-row` (white w/ cyan circle holding "Wicked 2 / Promo / Cobranded Theme design") → `video-mobile` (16:9). All desktop content elements already appear above the video in the mobile flow — nothing else needs to render below. The freed space below the video shows the panel's `canvas_bg` (white per the slide-7 manifest hint), which is the brand-correct fallback.

**Iteration history (preserved for future-deck context).** Earlier policy was `aspect-ratio: 4/5; object-fit: contain` — keep the bundle's portrait box but switch the fit mode to letterbox the 16:9 source instead of cropping. That eliminated the wordmark loss but introduced ~14% black bars top + bottom. On real iPhone the letterbox was visually heavy and didn't scale well to the 9 other video slides this template will eventually render. The 16:9 container is the third option that solves both — no crop, no letterbox, freed space goes to brand-background or template-allocated content.

**Manifest opt-in for non-16:9 sources.** If a future deck has a video that isn't 16:9, or one where a portrait crop *is* the design intent (centered subject filling the frame, no edge content), use a manifest hint:

```json
"slides": {
  "<N>": { "hints": { "mobile_video_aspect": "4/5", "mobile_video_fit": "cover" } }
}
```

The hint isn't wired into `media_showcase.py` yet — add when the first slide needs it. Slide 16 (the only other video in P&G) is centered-subject TikTok-style 4:5 framing and will likely opt in.

**Always run `ffprobe` on the source video** before deciding the mobile container aspect — the encoded aspect can differ from what the design doc claims, and a mismatched container reintroduces the crop-or-letterbox tradeoff.

---

## Video aspect ratio policy — auto-detected, manifest-driven

**Locked-in policy (productized form of the slide-7 decision):** the pipeline auto-detects every source video's aspect ratio at build time and writes it into the manifest. The template reads from the manifest. Per-slide aspect-ratio decisions are eliminated for all future decks.

**The chain:**

1. **Build-time probe.** The transform stage already re-encodes videos via `ffmpeg`. While each video is open, run `ffprobe` to extract `width`, `height`, and a derived aspect string (`"16/9"`, `"9/16"`, `"1/1"`, `"4/5"`, etc.).
2. **Manifest write.** Store under the slide's entry: `media.video.aspect`. Example:

   ```json
   "slides": {
     "7": {
       "template": "media_showcase",
       "media": {
         "video": { "aspect": "16/9", "width": 1920, "height": 1080 }
       },
       "hints": { "headline_class": "t-bold", "canvas_bg": "#FFFFFF" }
     }
   }
   ```
3. **Template read.** `media_showcase.py` `_render_video_variant` reads `slide_class.media["video"]["aspect"]` and emits it as the `aspect-ratio` CSS value on `.video-mobile video`. `object-fit: cover` stays baked in — matching aspect + cover = no crop, no letterbox, regardless of source shape (16:9, 9:16, 1:1, 4:5, anything).
4. **Manifest override hint** for design-intent divergences. If a future deck has a 16:9 source that should be cropped to 9:16 portrait (TikTok-style framing) on mobile — i.e., the design intent differs from the source aspect — set `hints.mobile_video_aspect_override: "9/16"` on that slide. The override takes precedence over auto-detected `media.video.aspect`. **Default is auto-detect; override is explicit opt-in.**

**Why the CSS aspect-ratio property accepts any ratio.** `aspect-ratio: 1920/1080` works identically to `aspect-ratio: 16/9` — the browser computes the ratio at use. No need to reduce to lowest terms unless you want the manifest to be human-readable, in which case use `math.gcd` to simplify before writing. Recommended: simplify, since manifests are committed and humans read them.

**Implementation lands in `transform/video.py`** (next module on the plan, not implemented yet). Stub design:

```python
import subprocess, json, math

def probe_aspect(video_path) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", video_path,
    ])
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    g = math.gcd(w, h)
    return {"aspect": f"{w//g}/{h//g}", "width": w, "height": h}
```

The transform stage calls `probe_aspect()` per video, merges the result into the slide's manifest entry under `media.video`, and writes the manifest back. The render stage then reads directly — no per-slide CSS decisions in code.

**Bundle parity note.** Bundle hardcodes `aspect-ratio: 4/5; object-fit: cover` on every mobile video, which crops 16:9 sources by ~27%. We diverge per the slide-7 entry above. **Auto-detection is the productized version of that divergence** — instead of every new deck re-living the slide-7 wordmark-crop debate, the manifest carries the per-video aspect and the template just emits it.

**What this resolves for future decks:**
- The slide-16 opt-in (centered-subject 4:5 video) becomes one manifest line, not a code change.
- A future 9:16 vertical phone-shot video Just Works — manifest says `"9/16"`, template emits `aspect-ratio: 9/16`, container matches source.
- The 1:1 square Instagram-format video Just Works.
- The deck author never has to think about mobile video CSS.

**Don't pre-implement.** This entry locks the design; the implementation lands when `transform/video.py` is built. Until then, slide 7 is the only video in the deck and `aspect-ratio: 16/9` can stay hardcoded in `media_showcase.py`. When `transform/video.py` ships: replace the hardcode with manifest read, populate manifest from auto-probe, regression-test slide 7.

---

## Pipeline state — paused 2026-04-27

**Shipped to bundle parity (Phase 1B complete — full state at 2026-04-30 entry below):**
- `cover` — slide 1
- `section_divider` standard variant — slides 4, 8 — **LOCKED 2026-04-28**, refined 2026-04-30 (logo_invert + inline photo bg)
- `section_divider` badge variant — slide 5 — **LOCKED 2026-04-28**, refined 2026-04-30 (logo_invert + inline grid photos)
- `media_showcase` photo-grid badge-overlay — slide 6 — **SHIPPED 2026-04-28**, refined 2026-04-30 (logo_invert)
- `media_showcase` video — slide 7 — **SHIPPED 2026-04-28**, refined 2026-04-30 (logo_invert); Phase 2 backlog entry below for full-bleed mobile work
- `title_stats` continuation variant — slide 3 — **SHIPPED 2026-04-28**, refined 2026-04-30 (logo_invert)
- `title_stats` paired variant — slide 21 — **SHIPPED 2026-04-28** (logo_invert was already set; unchanged 2026-04-30)

Authoritative MD5 baseline lives in the 2026-04-30 entry near the bottom of this file. The 2026-04-28 baseline is now historical.

**Not yet started (templates not built):**
- `title_stats` (slides 3, 19, 20, 21)
- `card_grid` (slide 2)
- `two_column` (slides 22, 23)
- `media_showcase` other variants:
  - small-corner-label sub-variant (slides 11, 12, 14) — `t-bold` 14pt + `t-sub` 11pt per the bundle CSS survey
  - large-headline sub-variant (slides 15, 17) — 88pt headline (6.875cqw)
  - centered-subject video sub-variant (slide 16) — 4:5 cover allowed; needs `mobile_video_aspect`/`mobile_video_fit` hints (see entry above)
  - mixed photo-grid sub-variants (slide 9 = 1×3 strip, slide 13/18 = ?)

**Manifest hints established this phase (pattern: deck-author design intent that OOXML can't carry):**
- `headline_class` — `"t-wnba"` (slide 5, 22pt) or `"t-bold"` (slides 6, 7, 9, 24pt). Maps to inherited-bold pt via `INHERITED_BOLD_PT_BY_HINT` in `media_showcase.py`.
- `canvas_bg` — `"#FFFFFF"` (slides 5, 6, 7); default `deck_brand_color` (cyan) for everything else.
- (planned, not yet implemented) `mobile_video_aspect`, `mobile_video_fit` — for the slide-16 opt-in.

**Key invariants tested under each render:**
- Inherited-size runs use the 16/18 fallback in `font_calibration.py` unless a slide-specific hint overrides (see `INHERITED_BOLD_PT_BY_HINT`).
- `--bg` = canvas_bg (per-slide); `--bg-cyan` = deck brand color (constant for the deck). Don't reuse `var(--bg)` for elements that should always be cyan; use `var(--bg-cyan)`.
- Mobile parity is checked separately from desktop. Cross-template invariants (canvas_bg, top-bar bg, mobile video aspect) need explicit verification per slide.

**Driver pattern (no orchestrator yet):** rendering is driven by inline `python3 -c` invocations that import the template, call it, and write `out/pg_slide_NN.html`. `media_showcase` returns `(html, aux_files)`; other templates return `html` directly. When `title_stats` / `two_column` ship, decide whether to formalize into a single driver script.

**Non-trivial open questions (resolved 2026-04-28 / 2026-04-30 — kept here for trace):**

- ~~Slide 7 mobile video undersized vs bundle.~~ Resolved during the `transform/video.py` retrofit and the 2026-04-30 logo_invert round. Active state lives in the Phase 2 backlog entry above (controls policy + iOS Safari `playsinline` chrome).
- ~~Slide 6 was 13MB inline.~~ Resolved by the `transform/image.py` retrofit (slide 6 is now 163KB, photos external `.webp`).
- ~~Helpers duplicated across templates.~~ Resolved when `_shared.py` was created (`image_src`, `inline_data_url`, `is_logo_pic`).

---

## Per-slide `canvas_bg` is design intent OOXML can't carry

Same class of decision as `headline_class` — the deck-author picks per-slide; the manifest records it. The PPTX/master chain says every slide background is white (all `<p:cSld>/<p:bg>` and the master `<p:bgRef>` resolve to `bg1` → `lt1` → `#FFFFFF`), but the bundle uses cyan on most slides and white only on the photo-grid slides (5, 6). That choice doesn't live in the file:

```
slide   <p:bg> in slide.xml                 OOXML resolves to   bundle .canvas
─────────────────────────────────────────────────────────────────────────────
  1     absent (inherits master)            #FFFFFF             cyan
  4     bgPr/solidFill/schemeClr=bg1        #FFFFFF             cyan
  5     bgPr/solidFill/schemeClr=bg1        #FFFFFF             #FFFFFF  ✓
  6     absent (inherits master)            #FFFFFF             #FFFFFF  ✓
  8     bgPr/solidFill/schemeClr=bg1        #FFFFFF             cyan
 22     bgPr/solidFill/schemeClr=bg1        #FFFFFF             cyan
 23     bgPr/solidFill/schemeClr=bg1        #FFFFFF             cyan

clrMap: bg1="lt1"
theme:  <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
master: <p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef>
```

The deck-author picked white only for slides 5 and 6 — both are 4-photo 2×2 grids that cover ~100% of the canvas, with subpixel seams between adjacent photos. White hides the seams; cyan would draw a thin cyan cross through the slide. Reading OOXML strictly would give white everywhere and break the 5 cyan slides; using `deck_brand_color` everywhere breaks 5 and 6.

**Implication for the manifest:** add an optional per-slide `canvas_bg` hint, default = `deck_brand_color`. Slides 5 and 6 get `"canvas_bg": "#FFFFFF"`. Same plumbing pattern as `headline_class`. Templates resolve `slide_class.hints.get("canvas_bg") or deck_brand_color` and feed it to the canvas as `--bg`. Note: `--bg-cyan` is kept as a separate var on slides where elements (mobile top-bar, mobile circle) genuinely need the deck brand color regardless of the canvas choice.

**False-positive caught while fixing this:** the original slide 5 render was approved visually but had the same `var(--bg) = cyan` bug as slide 6 — it was masked because the WNBA photos at the seam happen to be high-contrast and dark, so the 1px cyan seam disappeared into the imagery. Slide 6's lighter Wicked-2 photos exposed it. Lesson: visual diff on a single slide doesn't guarantee the same template-level bug isn't present elsewhere; cross-template invariants (canvas bg, font weights, etc.) need explicit checking.

---

## Inherited-size runs converge on 18pt — slide 5's 22pt is a deck-author override

The deck has 72 inherited-size runs (no `sz` on rPr) across 8 slides: 3, 5, 6, 7, 9, 21, 22, 23. The hypothesis from earlier — "different layouts produce different sizes via the lstStyle/layout-placeholder/master walk" — does not hold for this deck.

**Every inherited-size run lives on a non-placeholder `<p:cNvSpPr txBox="1"/>` shape with empty `<a:lstStyle/>`. The OOXML inheritance chain converges on 18pt for all of them:**

```
shape lstStyle               empty
layout placeholder           N/A — none of these shapes are placeholders
layout <p:txStyles>          absent (layout 7 is type="blank")
master <p:txStyles>/<p:otherStyle>/<a:lvl1pPr>/<a:defRPr sz="1800">    →  18pt
presentation.xml <p:defaultTextStyle>/<a:lvl1pPr>/<a:defRPr sz="1800">  →  18pt
```

A walker would output 18pt for all 72 runs. The bundle does not. Bundle outputs (cqw × 1280pt / 100):

```
slide   run                            bold?   bundle   walker would say
─────────────────────────────────────────────────────────────────────────
  5     "WNBA"                         yes     22pt     18pt   ←  +4pt override
 22     stakeholder names              no      16pt     18pt   ←  −2pt
 23     "FOR BUSINESS QUERIES"         yes     18pt     18pt   ✓
 23     contact lines                  no      16pt     18pt   ←  −2pt
```

Two consequences:

1. **The 16/18 constants in `parse/font_calibration.py` are doing the right thing.** They match 5 of the 6 cases above (the lone bold case at 18pt happens to agree with the walker too). Replacing them with an OOXML walker would regress slides 22 and 23.

2. **Slide 5's 22pt is a deck-author design override**, not derivable from PPTX. The bundle's prior session encoded this as the `.t-wnba` CSS class. The manifest already carries it as `slides.5.hints.headline_class = "t-wnba"`. The badge variant in `render/templates/section_divider.py` reads that hint and bumps inherited-bold runs to 22pt for that one slide; nothing else changes.

**Implication for future decks:** the same pattern likely repeats — most inherited-size runs match a small number of deck-wide defaults (here: regular=16, bold=18), with rare per-shape overrides that the deck author hand-placed in CSS. Capture those as manifest hints, not as walker output. Reach for a real OOXML walk only if a future deck shows runs converging on a *different* default (e.g. master `otherStyle` = 22pt for the whole deck), or has actual placeholder-bearing shapes whose layouts override the master.

---

## Inline @font-face replaces Google Fonts `<link>` — file:// + iOS Safari is the root cause

The bundle (and our scaffold up through last session) loaded Barlow Condensed via `<link href="fonts.googleapis.com/...">` plus two preconnect hints. That works fine over http(s); it silently degrades when the HTML is opened over `file://` — which is the actual delivery mode for AirDrop, Files-app preview, Quick Look, and double-clicking on the desktop. iOS Safari doesn't reliably execute the Google Fonts CSS request for `file://` documents; combined with `font-display: swap`, the page hands off to SF Pro the moment the font hasn't arrived and never swaps back. Every "share to phone for review" path showed system fallback, not the actual typeface.

**Fix:** drop the 3 head links (preconnect ×2, stylesheet ×1) in `render/html.py` and inline 4 weights of Barlow Condensed (300/400/500/700) as base64 woff2 data URLs in the `<style>` block ahead of CSS_RESET. Implementation lives in `render/fonts.py` (`font_face_css()`); the woff2 binaries sit alongside in `render/fonts/`. The font now travels with the file — no network request, no fallback path to fall through.

**Cost:** ~78KB per slide × 23 slides ≈ 1.8MB duplicated deck-wide. Acceptable for the regression-testing phase. Phase 2 publish will switch to a sibling `.woff2` file with proper Cache-Control so the font loads once per origin.

**Why this wasn't caught earlier:** desktop preview (Chrome opening a `file://` URL on macOS) loads the Google Fonts URL fine, so the font appeared correct in dev. The failure mode is specifically iOS Safari + `file://` + the swap fallback path. Real-iPhone preview (AirDrop) surfaced it; emulated mobile in DevTools didn't.

**Implication for future templates:** all `render_page()` callers go through the same shell, so this fix is universal. Don't reintroduce `<link href="fonts.googleapis.com/...">` for any future template; the `font_face_css()` block covers the whole deck. If a future deck needs a different family, extend `render/fonts.py` (woff2 binaries + family/weights), not `html.py`.

---

## Phase 2: Mobile UX Pass — real-iPhone testing as a class-wide bug surface

The font/Google-Fonts issue above is one instance of a broader pattern: **bugs that desktop `file://` preview can't see but real iPhones do.** Examples we've already hit:
- Fonts (above) — `file://` + iOS Safari + swap fallback degrades silently to SF Pro
- Slide 7 mobile video aspect (NOTES.md "Video edge-content" entry) — bundle's 4:5 cover crops edge wordmarks; only visible on real device sizing, not desktop emulation
- Slide 6 `var(--bg)` cyan seam masked by dark photo content (NOTES.md "Per-slide canvas_bg" entry) — emulator made the seam invisible; the iPhone exposed it

**Decision for Phase 2:** instead of patching mobile bugs ad-hoc as they surface, do a dedicated **Mobile UX Pass** on a real iPhone after each template ships. Catalog issues, classify them as template-level (applies to every slide using that template) vs slide-level (one-off design override), then fix at the right layer. The "fix one slide and ship" pattern misses class-wide bugs because the same template propagates the bug to every slide that uses it.

**How to apply:**
- After each template ships, run *every* slide using it through real-iPhone preview (AirDrop or Files-app), not just desktop emulation or DevTools mobile mode.
- Classify each issue: template bug (fix in `render/templates/*.py` or `render/html.py`)? Deck-author override (add a manifest hint)? Bundle bug we accept as our better-than-bundle baseline (document in NOTES.md as a deliberate divergence)?
- Don't ship Phase 2 publish until the catalog is empty for slides 1-23.

This entry is a placeholder for the catalog — populate it as the Mobile UX Pass surfaces specific issues. The first three (fonts, slide 7 video, slide 6 seam) are already filed under their own entries above; future findings can either land here as one-liners or get their own entry if the root cause is non-trivial.

**Phase 2 backlog (parked from Phase 1B):**

- **Slide 7 / `media_showcase` video variant — revisit during Phase 2.** Shipped state: functional but doesn't match the bundle's full-bleed mobile reference. **Updated finding from `transform/video.py`:** both P&G videos (slide 7 and slide 16) are 1920×1080 16:9 — there is *no* mixed-aspect problem in this deck. The earlier "16:9 vs 9:16" framing was wrong. Slide 7 should render as 16:9 full-bleed on mobile (matching source); slide 16's TikTok-style portrait framing is a *design-intent crop*, not a source-aspect difference, and is the canonical use case for the `mobile_video_aspect_override` manifest hint (set per-slide; the `transform/video.py` auto-detection writes the source aspect to `media.video.aspect`, the override hint takes precedence at render time). **Update post template-retrofit (2026-04-28):** the inline-base64 → external `.webp`/`.mp4` retrofit did NOT fix slide 7 mobile; the `<video>` element's attributes are unchanged (`autoplay loop muted playsinline controls preload="auto"`), and `controls` is the attribute that surfaces iOS Safari's player chrome. Removing `controls` hides the chrome but disables user interaction (no pause/seek) — that's a Phase 2 design call (do we want users to be able to pause? per-slide override?), not something the retrofit can resolve as a side effect. Phase 2 fix is now scoped to: (a) decide the controls policy (always off / always on / per-slide hint), (b) figure out why iOS Safari ignores `playsinline` on this build (already set; chrome shouldn't render with it), (c) verify the 16:9 CSS rule actually takes effect once chrome is settled.

---

## section_divider standard variant — mobile gradient + viewport-height fixes

Real-iPhone testing on slides 4 (2-line) and 8 (3-line) surfaced two class-wide bugs in the standard section_divider mobile layout. Both inherited from the bundle; both fixed once at the template level.

**Failure mode 1 — gradient rotated 90° on mobile but headline stayed at flex-bottom.** Desktop runs the cyan readability gradient *cyan-left → transparent-right* with the headline absolutely positioned on the cyan-left band. Mobile rotates the gradient to *cyan-top → transparent-bottom* but keeps the headline at `margin-top: auto` (flex-pushed to the bottom of the panel). The headline lands on the *transparent* (photo-only) half — the gradient and the headline got rotated independently and stopped overlapping.

```
desktop:  ┌─────────────────┐         mobile (broken):  ┌─────────────────┐
          │ cyan │ photo→   │                            │ cyan band       │
          │ band │ →        │                            │ ↓               │
          │ TEXT │ (faded)  │                            │ photo (full)    │
          │ here │          │                            │ TEXT here ←inv. │
          └─────────────────┘                            └─────────────────┘
```

**Why slide 4 hides the bug, slide 8 reveals it.** The bug is white text on photo (no gradient backdrop) — readability depends entirely on the photo's tone where the headline sits. Slide 4's photo at the bottom is dark (retail/display scene), so white text contrasts adequately and the bug looks like "fine, just no cyan band." Slide 8's photo at the bottom is bright (retail wall displays), so white text on bright photo is invisible and the headline disappears entirely. Same template, same CSS, same headline-on-photo pattern; only the photo brightness changes whether the bug is visible.

This is the second instance of "one slide visually masks a class-wide bug, another reveals it" in this template (canvas_bg seam on slide 5 vs slide 6 was the first — see the canvas_bg entry above). Worth checking new templates against multiple slides before declaring them done.

**Failure mode 2 — `min-height: 100vh` panel taller than visible viewport on iOS.** iOS Safari defines `100vh` as the viewport with the URL bar fully retracted (largest possible). When the URL bar is showing — default state on first paint — the panel extends below the visible area. With `margin-top: auto` pushing the headline to the bottom of the panel, the headline lands below the fold. User has to scroll up. Same root cause for slide 4 (small viewport overhang, headline mostly visible but cropped at top) and slide 8 (3-line headline + URL-bar overhang = headline mostly off-screen).

**Fix (both, applied to standard `_build_css` only):**
```css
/* panel and ancestor chain */
@media (max-width: 768px) {
  html, body          { height: 100%; }     /* required for 100dvh to clip */
  #deck-mobile        { display: block; height: 100%; }
  #deck-mobile .panel {
-   min-height: 100vh;
+   height: 100vh;       /* fallback */
+   height: 100dvh;      /* iOS Safari 15.4+, Chrome 108+, Firefox 101+ */
    overflow: hidden;
  }
}

/* overlay-mobile */
- background: linear-gradient(to bottom, var(--overlay) 0%, var(--overlay-0) 60%);
+ background: linear-gradient(to top,    var(--overlay) 0%, var(--overlay-0) 60%);
```

**Note on the panel-height story:** earlier versions of this entry recommended `min-height: 100dvh`, then `height: 100dvh` alone, then `height: 100dvh` + `min-height: 0` on a flex child. None of those alone fix the iOS Safari scroll-overflow on slide 8. The actual root cause is the *ancestor chain* — see the "iOS Safari `100dvh` requires explicit height on every ancestor" entry below for the canonical lesson. The diff shown above is the post-correction form.

After fix: cyan band sits at the bottom of the panel where the headline is, photo shows in the upper ~60% (~40% if the gradient stop changes; we kept 60% to match desktop's ~56%), white text always sits on cyan = readable on every photo regardless of brightness. Panel fits the visible viewport, no scroll-to-see-headline.

**Bundle parity note: bundle has the identical bugs.** Both `pg_unzipped/pg_slide_04.html` and `pg_slide_08.html` use `min-height: 100vh` + `to bottom` gradient + `margin-top: auto` headline. The bundle's prior conversion shipped this; the issue only surfaces on real devices because desktop emulation gives a viewport without a URL bar, and the dark slide-4 photo masks the contrast bug in eye-tests. Our render diverges from the bundle here, in the same class as the slide-7 video-fit fix, the canvas_bg fix, and the inline @font-face fix.

**Scope of the fix:** standard `_build_css` in `render/templates/section_divider.py` (line ~333) — covers slides 4, 8, 10, 13, 18 (every standard-variant slide). The badge variant `_build_css` (line ~605) was left untouched: slide 5 (the only badge slide so far) renders correctly on iPhone and uses a different layout (4-photo grid + circle, no full-bleed photo+gradient+headline-at-bottom pattern). Re-rendered slides 4, 5, 8 to verify; slide 5 byte-equivalent to pre-fix.

**Implication for other templates:** when `media_showcase`, `title_stats`, `card_grid`, `two_column` ship, audit each for the same two patterns:
- Any panel intended to fill exactly one viewport → use `height: 100dvh` AND ensure every ancestor (`html`, `body`, the `#deck-mobile` section) has an explicit height (`height: 100%` is the simplest). See "iOS Safari `100dvh` requires explicit height on every ancestor" entry below.
- Any mobile gradient rotated from a desktop horizontal gradient → check that the headline (or other content) lands on the opaque side, not the transparent side.

---

## section_divider standard variant — final mobile architecture (revert of Day-2 flex restructuring)

**Final architecture: section_divider mobile uses absolute photo background + gradient overlay + absolute headline at bottom.** The Day-2 round of flex restructuring (flex:1 photo + auto-height headline + `<img>` child) was incorrect — the original overlay architecture was right; only the gradient direction on mobile needed flipping (`to top`, not `to bottom`) so cyan lands at the bottom of the panel where the headline sits.

**The Day-2 hypothesis and why it was wrong.** Real-iPhone testing surfaced what looked like a new "photo overflow" symptom: the user observed the photo subject hidden behind the cyan area. The hypothesis was that absolute layers had no explicit vertical relationship between photo and headline, so the photo subject (centered via `background-size: cover`) was landing behind the cyan band. The proposed fix restructured the layout into flex siblings: photo `flex: 1` + headline auto-height + replace `background-image` with an `<img>` child. This *changed the architecture* rather than fixing the actual bug, and introduced new failure modes (panel overflow, then headline block bloat, then ever-shrinking photo strip), each requiring another round of corrections that didn't fully converge.

**What was actually wrong.** The cyan band was visually too tall because the gradient stop was at 60% (covering 60% of the panel with cyan-tinted fade). The headline sat in that cyan zone; the photo subject was visible *underneath* the cyan-tint of the gradient (not "hidden behind a layer," just visually muted by the overlay). The right fix was a tighter gradient — solid cyan from 0% to 25% (covers headline area cleanly), fading to transparent by 60%. The architecture — photo absolute, overlay absolute, headline absolute over the cyan portion — was correct from the start.

**Final CSS (matches the original bundle architecture with four targeted divergences):**

```css
@media (max-width: 768px) {
  html, body          { height: 100%; }                       /* ancestor chain — see entry below */
  #deck-mobile        { display: block; height: 100%; }
  #deck-mobile .panel { height: 100vh; height: 100dvh;        /* fixed, not min */
                        position: relative; overflow: hidden;
                        background: var(--bg); }
  #deck-mobile .photo-mobile   { position: absolute; inset: 0;
                                 background-size: cover; background-position: center;
                                 z-index: 0; }
  #deck-mobile .overlay-mobile { position: absolute; inset: 0;
                                 background: linear-gradient(to top,
                                   var(--overlay) 0%, var(--overlay) 25%,    /* solid plateau */
                                   var(--overlay-0) 60%);                    /* fade to transparent */
                                 z-index: 1; pointer-events: none; }
  #deck-mobile .top-bar        { position: absolute; top: 0; right: 0;       /* slide 4 only */
                                 z-index: 3; padding: 5vw; }
  #deck-mobile .headline-mobile    { position: absolute; left: 0; right: 0; bottom: 0;
                                     padding: 1.5rem; z-index: 2; }
  #deck-mobile .headline-mobile .t { font-size: clamp(3rem, 13vw, 4rem);
                                     font-weight: 700; line-height: 0.95;
                                     text-transform: uppercase;
                                     text-shadow: 2px 2px 6px rgba(0,0,0,0.3); }
}
```

Body markup: photo uses inline `background-image: url(...)`, no `<img>` child. Order: `.photo-mobile` → `.overlay-mobile` → `.top-bar` (slide 4) → `.headline-mobile`.

**Four divergences from the bundle's original mobile architecture:**

1. **Gradient direction `to top` (not `to bottom`).** Bundle had `to bottom` so cyan was at the top, headline at the bottom on transparent photo — the contrast bug from the round-2 entry. Flipping to `to top` puts cyan at the bottom where the headline sits.
2. **3-stop gradient with a solid plateau (0%→25% solid, 25%→60% fade).** Bundle had a 2-stop simple fade. The plateau gives the headline a sturdy readable backdrop without the cyan-tint bleeding too high up the photo.
3. **Panel `height: 100dvh` and full ancestor chain `height: 100%`.** Bundle's `min-height: 100vh` with no ancestor heights lets the panel grow past one viewport on iOS Safari. The fix is `height: 100dvh` on the panel *plus* `height: 100%` on `html`, `body`, and `#deck-mobile` — the percentage chain has to resolve all the way down or `100dvh` doesn't actually clip. See the "iOS Safari `100dvh` requires explicit height on every ancestor" entry below.
4. **rem-based headline typography** — see paragraph below.

**Headline typography is also rem-based (not vw-based).** Bundle used `padding: 8vw 6vw 12vw; font-size: 18vw;` — those values produce a reasonable headline on most phones but bloat awkwardly on larger viewports. `padding: 1.5rem` + `font-size: clamp(3rem, 13vw, 4rem)` gives stable padding and fluid type that holds within a sensible range across phone sizes. This is independent of the architecture revert.

**Why slide 5 is unaffected by all of this.** Badge variant uses a different layout entirely (4-photo grid + circle badge, no full-bleed photo + gradient + absolute-bottom headline). Different `_build_css`, different DOM. Slide 5 MD5 unchanged across all rounds: `40dc325b997eb8758692808d7b961c16`.

**Lesson — when you see a new symptom, first check whether the architecture is right.** The Day-2 path took a real symptom (photo subject muted by cyan tint) and treated the symptom as evidence that the architecture itself was wrong. It wasn't. The architecture was right; one parameter (the gradient stop) was the actual problem. Restructuring the architecture to "fix" what was actually a single-value tuning issue introduced a cascade of new problems that took three more rounds to undo. Before refactoring an architecture, see if a single-value fix (gradient stop, font-size, padding, viewport unit) explains all the observed symptoms.

---

## iOS Safari `100dvh` requires explicit height on every ancestor

**Root cause of the panel-overflow saga.** `height: 100dvh` on a deeply-nested element doesn't actually clip to the visible viewport on iOS Safari unless every ancestor in the chain (`html`, `body`, the wrapping `<section>`) has an explicit height. If any link in that chain is height-auto (the default), the parent grows to fit its child's content height — which means the panel can compute its `100dvh` correctly but the *body* extends past the viewport because nothing told the body to stop. The user reads this as "the panel scrolls" but the panel is the right size; the body around it isn't.

**The chain that has to resolve.** From outermost to innermost:

```
html                                      → height: 100%      (resolves against viewport)
  body                                    → height: 100%      (resolves against html)
    <section id="deck-mobile">            → height: 100%      (resolves against body)
      <div class="panel">                 → height: 100dvh    (the actual viewport-sized box)
```

If any link is missing `height`, percentages collapse to `auto` and that element becomes content-sized. Since `auto` heights below `body` mean `body` grows with content, the panel's `100dvh` becomes "the only height anchor in the chain" — and on iOS Safari that doesn't reliably clip.

**Fix — explicit `height` on every ancestor inside the mobile media query:**

```css
@media (max-width: 768px) {
  html, body          { height: 100%; }
  #deck-mobile        { display: block; height: 100%; }
  #deck-mobile .panel { height: 100vh; height: 100dvh;
                        overflow: hidden; }
}
```

The CSS_RESET in `render/html.py` defines `html, body { width: 100%; … }` with no height, on purpose — at desktop, slides are content-sized and don't need viewport-bound bodies. The mobile chain needs heights but desktop doesn't, so the rule is scoped inside the `@media (max-width: 768px)` block. Keeping it scoped also means `#deck-mobile` (which is `display: none` outside the media query) doesn't acquire a layout-affecting height when it's not rendering anything.

**Why earlier rounds didn't catch this.** The iteration tried `min-height: 100vh`, then `min-height: 100dvh`, then `height: 100dvh`, then a flex restructure, then `height: 100dvh` again — all on the panel itself. None of those changes touched the ancestor chain. Each round produced a build where `.panel` was correctly sized, but the body around it wasn't, so the viewport overflow persisted no matter what the panel did. Only when the diagnostic explicitly checked `html`, `body`, and the section's CSS did it become clear that the chain was the missing piece. **Lesson:** when a child element has the right CSS but the parent is misbehaving, look up the chain, not at the child.

**`height` vs `min-height` (subordinate lesson).** `height: 100dvh` is still preferred over `min-height: 100dvh` on the panel — `min-height` lets the panel grow if content somehow exceeds the viewport, which can mask a future bug. But once the ancestor chain is correct, either should clip in practice. Earlier versions of this NOTES file treated the height-vs-min-height distinction as the canonical fix; it isn't, the ancestor chain is. Round-2's diff has been updated to reflect this.

**Bundle parity:** bundle uses `min-height: 100vh` on `.panel` and has no ancestor-chain heights. We diverge by adding both. Same class as canvas_bg, font-face, slide-7 video-fit, gradient-direction fix.

**Iteration retrospective.** The section_divider mobile bug took five rounds to fully fix. What survived from each:
- Round 2: gradient direction (`to top`, not `to bottom`) — kept
- Round 3 (Day-2 flex restructuring) — reverted; was an architecture change made in response to a single-value-tuning symptom (gradient stop)
- Round 3.5: rem-based headline typography (`padding: 1.5rem`, `font-size: clamp(3rem, 13vw, 4rem)`) — kept
- Round 4: gradient stop (3-stop with solid plateau, 25%/60%) — kept
- Round 5 (this entry): ancestor-chain `height: 100%` — kept; the actual root cause

**Two general lessons** worth carrying to other templates:

1. **Tune before restructuring.** When a real-iPhone bug appears, exhaust single-value fixes (gradient stop, viewport unit, font-size, padding) before reaching for an architecture change. Architecture changes layer new failure modes on top of the original; if the architecture was sound, the new failures are net-new problems. The Day-2 detour is the cautionary tale.
2. **When a child has the right CSS but layout misbehaves, look up the chain.** Percentage heights, `flex` sizing, `position: sticky`, and viewport-relative units all have prerequisites on ancestor properties. The fix is rarely on the child you're looking at. This applies to any layout engine, not just iOS Safari `100dvh`.

Real-iPhone iteration is still the only way to surface these bugs (desktop emulation hides URL-bar timing, percentage cascades, and dvh quirks), but the iteration should default to ancestor-chain checks and single-value tuning, not restructuring the element under test.

---

## Templates match by `src_id` and role, not by image count

Discovered while retrofitting `media_showcase` to read images from the manifest: **slide 6 has 5 image shapes, not 4** (4 photo-grid panels + 1 GIF logo top-right). The original manifest notes for slide 6 say "4 photos arranged 2×2," which describes the photo-grid pattern but undercounts the slide's `<p:pic>` total because the logo is also a `<p:pic>`. Any template that branches on image count (`if len(images) == 4`) would mis-classify the logo as a fifth photo and break the grid layout.

**Rule for all template builders:** match images to roles by **src_id + geometric role** (e.g., logo = small + top-right; photo-grid = larger + tiled), never by total image count. The `_classify()` helpers in each template already work this way for shape kinds (sp vs pic) and geometry; the same discipline applies to image roles.

**transform/image.py** writes one manifest entry per `<p:pic>` regardless of role — `slides.<N>.media.images: [{src_id, filename, width, height, format}, ...]` is the full list ordered by document position. Templates iterate the list, classify each entry by role (using shape geometry from `parse/shapes.py` `flatten_slide`), and skip entries that don't match the role they're filling. A logo that ends up at index 4 in the array doesn't break a 2×2 grid because the grid template only consumes the four photo entries it identifies as grid-role.

Same shape as the canvas_bg discovery (slide 5 vs slide 6 seam): one slide makes a class-wide assumption visible because it sits on the boundary of the assumption. New templates should be tested against multiple slides whose composition differs (e.g., `media_showcase` against slide 6 with a logo *and* slide 9 without one) before declaring the role-classifier done.

---

## Phase 1B template retrofit — base64 → external `.webp`

After `transform/image.py` shipped, the four templates that handled images inline (`cover.py`, `section_divider.py` standard + badge, `media_showcase.py` photo-grid + video) were retrofitted to read filenames from `slide_class.media["images"]` by `src_id`. Helper lives in `render/templates/_shared.py` (`image_src(shape, slide_class, slide)`) and falls back to inline data URLs for shapes the manifest doesn't cover (SVG-only shapes, e.g., the cover slide-1 hero, since `transform/image.py` skips SVGs by design).

Deck-wide HTML size impact (Phase 1B slides 1, 4, 5, 6, 7, 8 only; the manifest carries entries for all 23 slides for when remaining templates ship):

```
slide   before retrofit   after retrofit   Δ
─────────────────────────────────────────────────
  1       121 KB           98 KB          −19%   (SVG hero stays inline)
  4       324 KB           84 KB          −74%
  5       357 KB           85 KB          −76%
  6      13.9 MB           85 KB          −99.4%
  7       235 KB          154 KB          −34%   (video poster still inline)
  8       266 KB           84 KB          −68%
```

Slide 6's drop is the headline number — the four 1600×900 photo-grid images that were inlined as base64 are now sibling `.webp` files. Total deck-wide image weight: 73 `.webp` files at 3.7 MB combined.

**Inline base64 retained intentionally** for: SVG heroes (cover slide 1; transform skips SVG), video posters (`<video poster="...">` on slide 7; small, auxiliary, not worth a separate file). Both are caller-side decisions, not failures of the retrofit.

`image_src` helper has SVG-first preference in its fallback path (`extract_svg_ref` before `extract_image_ref`) so cover heroes that have BOTH an SVG extension and a PNG raster fallback use the SVG — matching the prior `_hero_data_url` behavior.

---

## OOXML structural assumptions need verification before template design

Discovered while building `title_stats` for slides 3 and 21. The initial design proposal assumed "title + one list shape" — a clean conceptual model that *did not match the source XML*. Both slides actually use **two body shapes**, but for structurally different reasons:

- **Slide 21** ("BRAND ASSETS TURNAROUND TIMES"): two body shapes with **equal paragraph count** — `sp[2]` holds 8 labels (each ending in a Unicode dot run), `sp[3]` holds 8 corresponding values. Paragraph N in shape A pairs with paragraph N in shape B to form one displayed entry.
- **Slide 3** ("TYPE OF BRAND ASSETS CREATED"): two body shapes with **unequal paragraph count** — `sp[2]` has 14 paragraphs, `sp[3]` has 11. They're a single conceptual list that the deck-author split across two columns to fit the slide. Order matters; pairing doesn't.

Same template (`title_stats` per the manifest), same outer structure (title + 2 body shapes), but the inter-shape semantics differ. A "title + single list" extractor would mis-render both. A "title + 2 columns of independent lists" extractor would mis-render slide 21. The right answer was three variants distinguished by a paragraph-count parity check (see the `title_stats` module docstring).

**Lesson for every new template:** before designing the role classifier or extractor, **grep the actual slide XML for every slide that uses the template**. The manifest's `notes` field describes deck-author *intent* but undercounts shapes (logos, footnotes, decorative blanks) that the renderer still has to handle. The visual interpretation is also lossy — slide 3's "list of asset types" *looks* like one list but is two text shapes; slide 21's "title + entries with timing" *looks* like one block but is four shapes (title, labels, values, footnote).

This is the same shape as the slide-6 image-count discovery (5 picture shapes despite "4 photos" notes), the canvas_bg seam (slide 5 vs slide 6 visibility), the section_divider mobile iteration (each round revealed an unverified assumption). Spending five minutes greping the source XML before writing the role classifier saves hours of iteration on the failure modes the assumption hides.

---

## Dotted leaders in this deck are inline Unicode dots, not OOXML `<a:tab leader>`

Discovered while building `title_stats` for slide 21. The proposed variant detector scanned `<a:pPr><a:tabLst><a:tab leader='dot'/>` — the canonical OOXML mechanism for leader-filled tab stops. **Slide 21 has none of those attributes.** Instead, the deck author typed long runs of Unicode horizontal-ellipsis characters (`……………………………………………………`) directly into the label text, as inline content runs.

The OOXML for slide 21 paragraph 1 looks like:

```xml
<a:p>
  <a:pPr><a:lnSpc><a:spcPct val="200000"/></a:lnSpc></a:pPr>
  <a:r>...bold properties...<a:t>Retail WOW Displays</a:t></a:r>
  <a:r>...light properties...<a:t>……………………………………………………..</a:t></a:r>
</a:p>
```

No `<a:tab>`, no `<a:tabLst>`, no `leader=` attribute. The "leader" is a styled run of literal characters.

**Detection in `title_stats` is therefore content-based:** a paragraph's run is treated as a leader if its text (stripped of whitespace) is ≥3 consecutive characters drawn from a Unicode dot set — `…`, `.`, `·`, `‧`, `⋯`, `∙`, `•`, `‥`, `․`. Common variants chosen empirically; extend the set if a future deck uses different characters. The detector strips trailing dot-runs from labels before rendering and replaces them with a CSS pseudo-element span (`<span class="leader">`) that draws the visual dotted line via `border-bottom: dotted`. Result: clean text in the HTML, leader scales to whatever space remains between label and value, no fragility when labels are long.

**Why the bundle author did this:** unclear. Possibly the OOXML tab-leader didn't render the way they wanted in the original PowerPoint, possibly muscle memory from typewriter-era typesetting, possibly the deck was edited in a tool that didn't expose the `leader=` attribute. Doesn't matter — we render what's actually in the file.

**Lesson, generalized:** OOXML offers multiple ways to encode the same visual outcome. When designing a template extractor, scan the actual XML for the visual feature you're targeting; don't assume the canonical encoding. (`<a:tab leader>` would have been the canonical answer; inline Unicode dots are the actual answer for this deck.) Keep detection content-aware where the canonical attribute might not be present.

---

## Phase 1B — COMPLETE — 23/23 verified — 2026-05-03

**23 / 23 slides shipped + iPhone-verified.** Phase 1B opened 2026-04-30 with 8/23 verified; closed 2026-05-03 with 23/23 verified. Final cohort sequence: 2026-05-02 Cohort B5 (slides 19, 20 — `titled-grid` sub-variant of `media_showcase`) + slide 14 (photo-grid badge with transparent-edge mockup), then Cohort B6 (slide 22 — new `two_column` template + shared `resolve_inherited_size` helper for OOXML font-size inheritance walk + sizing-fix sub-round adding 4 typography hints), then Cohort B7 (slide 23 — `two_column` contact variant via `two_column_layout: "contact"` dispatch hint, adds SVG hero + wordmark-as-content + right-column text stack + plain-text mailto: links), then Cohort B8 over 2026-05-02 / 2026-05-03 (slide 2 — NEW `card_grid` template + transform-stage `<a:duotone>` / `<a:alphaModFix>` pre-baking + alpha-aware canvas-skip heuristic + background-photo / tint-overlay z-stack + mobile cluster grouping by world-coord proximity + title size override).

**6 templates shipped, 12 sub-variants exercised:** `cover` (1) · `title_stats` (paired + continuation = 2) · `section_divider` (standard + badge = 2) · `media_showcase` (photo-grid + large-headline + titled-grid + video full-bleed = 4) · `two_column` (stakeholders + contact = 2) · `card_grid` (1). All 6 manifest-declared templates now shipped and verified.

**Authoritative MD5 baseline (supersedes 2026-04-28 baseline):**

```
slide   template + variant                 md5                                size
─────────────────────────────────────────────────────────────────────────────────────
  01    cover                               f2ce39c7cfaae403a46d89edb78f3895   119KB  ✓ verified 2026-05-01
  02    card_grid                           a95fe1208df080861a42cd5441921317   364KB  ✓ verified 2026-05-03 (Cohort B8 — card_grid + duotone bg + alpha overlay + mobile cluster grouping + title 32pt/12vw)
  03    title_stats / continuation          54e285d2f7e74c28fcaf96941cfb17dc   108KB
  04    section_divider / standard          acc8e7ae5ae7aa22042996a4374d35e4   316KB
  05    section_divider / badge             8d9f04424f78844eef3ed21d8e2299c5   348KB
  06    media_showcase / photo-grid         7d41c39be518b867624fc92cabe63af3  2.27MB  ✓ verified 2026-05-01 (inline-WebP)
  07    media_showcase / video              2a7ff473282e5f6885ffa7102be3f6df   230KB
  08    section_divider / standard          feb87e17160f5872287ca1e0e3b726f0   259KB
  09    media_showcase / photo-grid         a72ad5f60580079579f6131be8045904   451KB  ✓ verified 2026-05-01 (inline-WebP)
  11    media_showcase / photo-grid         67a897111c5d515147dd0d153f7a0ea4   324KB  ✓ verified 2026-05-01 (inline-WebP)
  12    media_showcase / photo-grid         abff1803fd9061774903c2b288c8c58e   343KB  ✓ verified 2026-05-01 (inline-WebP)
  14    media_showcase / photo-grid         f17afa15584bfd483fb56d590001a0aa   311KB  ✓ verified 2026-05-02 (inline-WebP, hard-edge alpha)
  15    media_showcase / large-headline     1bc4b47755e980cfdec1b9183af8b65c   362KB  ✓ verified 2026-05-01 (inline-WebP)
  17    media_showcase / large-headline     1cb16c93df920a09e4cccd64064acc78  1.14MB  ✓ verified 2026-05-01 (inline-WebP)
  19    media_showcase / titled-grid        99bf9d562191bfa4aebbafc78e9ff821  2.25MB  ✓ verified 2026-05-02 (titled-grid + inline-WebP)
  20    media_showcase / titled-grid        b9a32693b3a0babe74ffe6bb037c00ca  1.28MB  ✓ verified 2026-05-02 (titled-grid + inline-WebP)
  21    title_stats / paired                da0ec642b60c43222432ef4d6ec8738d   ~110KB
  22    two_column                          c0bc3048e688821fd469a8518666ad39   111KB  ✓ verified 2026-05-02 (Cohort B6 sizing fix — title 60pt/400, body 22pt/700, mobile title 9vw/500)
  23    two_column / contact                1d357d140726201ce837f485dd9adb4c   181KB  ✓ verified 2026-05-02 (Cohort B7 — SVG hero + wordmark-as-content + right-column stack)
```

**Round history within this baseline:**
- 2026-04-28: initial baseline (8 slides shipped — see prior NOTES entries above for context).
- 2026-04-30: slides 4-8 changed (logo_invert hint + inline-photo backdrops + asset-validator architecture). Slide 21 unchanged.
- 2026-05-01 round 1: slide 01 rebaselined post role-taxonomy + inline-logo retrofit, then iPhone-verified.
- 2026-05-01 round 2: slides 06, 09, 11, 12, 15, 17 rebaselined post photo_grid-showcase inline-WebP carve-out (see Operating principles below); all 7 newly-baselined slides solo-file AirDrop iPhone-verified under the new self-contained-HTML rule (smoke test: slide 11 first; heaviest payload: slide 06 at 2.27 MB rendered without issue). Slide 06's known line-height 1.05 vs 1.0 divergence remains parked per Phase 2 backlog — new MD5 locks the existing divergence, not addressing it in this round.
- 2026-05-02 (Cohort B5): slides 19, 20 added under new `titled-grid` sub-variant of `media_showcase` (title text above grid, no circle, no logo). Required new dispatcher hint `media_showcase_layout: "titled-grid"` + new `_render_titled_grid_variant` function (~225 new lines in `media_showcase.py`). All 17 prior siblings (11 truly-locked + 6 inline-WebP) regression-verified byte-identical. Both new slides solo-file iPhone AirDrop verified same day.
- 2026-05-02 (slide 14): added under existing photo-grid badge variant — same archetype as slides 9, 11, 12 (3 photos + cyan circle + 3-paragraph white label). No code change. Manifest hint `flatten_on_canvas: false` made explicit on img_02 (Picture 4, 770x770 RGBA hard-edge alpha — the transparent-edge antiperspirant box mockup that overlays Picture 9's WNBA design through corner cutouts). On-disk webp confirmed RGBA with 4/4 corners alpha=0; data URL extracted from rendered HTML decoded back to RGBA with alpha intact — alpha survived the transform → inline pipeline end-to-end. All 19 prior siblings byte-identical. Solo-file iPhone AirDrop verified same day; hard-edge alpha at box corners rendered cleanly on iPhone Safari, no gray fringing.
- 2026-05-02 (Cohort B6): built new `two_column` template + shared `resolve_inherited_size(shape, slide, paragraph_lvl)` helper in `_shared.py` for OOXML font-size inheritance walk. Slide 22 shipped (title + 2 name columns, 30 names total). New template count: 7 (was 6). Hardcoded text-handling rules: multi-run paragraphs concatenate to a single string, trailing whitespace-only runs stripped, U+00A0 (NBSP) preserved verbatim. All 20 prior siblings byte-identical post-implementation. Slide 22 pending iPhone solo-file AirDrop verification (44pt title + 18pt body via `<p:otherStyle>` inheritance, multi-run names, NBSP preservation).
- 2026-05-02 (Cohort B6 CSS-fix round): post-render audit against PPT visual reference surfaced 4 renderer bugs in two_column.py — title didn't wrap (flex container with unconstrained inner div), title centered (overrode OOXML algn=l), body line-height 1.4 hardcoded (OOXML otherStyle has no lnSpc → tight default), body margin 0.4cqw invented (OOXML spcBef/spcAft absent → 0), bodyPr default insets ignored (lIns=9.6 codebase-pt / tIns=4.8 codebase-pt per OOXML default were not honored). Plus 1 size-resolution bug — `calibrate_size_pt`'s 16pt fallback for inherited non-bold runs shadowed the OOXML 18pt resolution from `<p:otherStyle>/<a:lvl1pPr>` AND shadowed the manifest `body_size_pt: 18` hint (since hint check used `if size_pt is None` but calibrate always returns a value). Fixes applied: (a) `_extract_paragraphs` now passes `inherited_size` to `calibrate_size_pt` as the `declared` value when run's declared is None, so master-resolved 18pt wins over the helper's 16pt default; (b) `body_size_pt` hint now applies unconditionally (matches title_stats:122-130 precedent); (c) title-frame uses block layout instead of flex (allows wrap); (d) text-align: left on title; (e) line-height: 1.0 + margin: 0 on body and title; (f) bodyPr insets emitted as padding via new `_read_bodypr_insets` helper (OOXML defaults: lIns=91440 EMU = 9.6 codebase-pt, tIns=45720 EMU = 4.8 codebase-pt). All 20 prior siblings still byte-identical. Slide 22 re-baselined to `deb760889cdabbccff98fc63219ca1a9`. Body weight gap (Univers Condensed Medium → Barlow Condensed Medium visual difference) deferred to Phase 1C deck-token work — flagged below as known limitation.
- 2026-05-02 (Cohort B6 sizing fix): post-CSS-fix-round visual diff against slide-3 reference surfaced 5 typography divergences on slide 22 — desktop title size 44pt (OOXML sz=4400) vs slide-3 60pt section-title baseline; desktop title weight 500 (typeface→Medium) vs slide-3 weight 400; desktop body weight 500 vs visually-correct 700 (Barlow Condensed Medium reads too light vs source PPT visual reference at 22pt); desktop body line-height 1.0 vs visually-correct 1.15 (matches slide-3 heading-item density); mobile title 6vw/700/1.0 vs slide-3 mobile baseline 9vw/500/1.05. Fixes applied: (a) new manifest hint `title_weight` consumed in `render_two_column` mirrors the existing `title_size_pt` override pattern — both now overwrite `run["weight"]` / `run["size_pt"]` on title-frame runs unconditionally (deck-author intent wins over OOXML); (b) body weight 700 + line-height 1.15 hardcoded in `_build_css` body-emission block with inline comment referencing the slide-3 visual-density target and the Barlow-Condensed-vs-Univers-Condensed font-substitution gap; (c) three new manifest hints `mobile_title_size_vw` / `mobile_title_weight` / `mobile_title_line_height` with current-value defaults (6.0 / 700 / 1.0) preserve template-default behavior for slide 23 (Cohort B7), slide 22 opts in to slide-3 parity (9.0 / 500 / 1.05). Slide 22 manifest now carries 5 typography hints: `title_size_pt: 60`, `title_weight: 400`, `body_size_pt: 22`, `mobile_title_size_vw: 9.0`, `mobile_title_weight: 500`, `mobile_title_line_height: 1.05`. All 20 prior siblings byte-identical post-implementation. Slide 22 re-baselined to `c0bc3048e688821fd469a8518666ad39` (111KB) and iPhone + desktop verified 2026-05-02. Mobile-title margin axis still structurally diverges from slide 3 (slide 22 wraps title in `.title-mobile` with container padding; slide 3 puts margin on the headline directly) — accepted as visually equivalent, not changed. Cosmetic byte-divergence: emitter writes `9.0vw` while slide 3 writes `9vw` — int-coerce-when-whole deferred (functionally identical).
- 2026-05-02 (Cohort B7): slide 23 shipped via new `two_column_layout: "contact"` dispatch hint added to `render_two_column`. Default `"stakeholders"` (slide 22) preserves prior code path byte-identically — verified by re-rendering slide 22 in-memory post-implementation. Contact variant adds 4 new functions in `two_column.py`: `_render_contact_variant` (orchestrator), `_classify_contact` (returns `(hero_pic, wordmark_pic, text_frames)` — hero detected via `has_svg_blip`, wordmark = first non-SVG non-logo pic, no title/body split on text), `_build_css_contact` + `_build_body_contact` (desktop = absolute positioning at native OOXML coords; mobile = vertical flex stack). New CSS class taxonomy: `.hero` (asset-validator role=hero), `.photo-0` (role=photo_grid), `.text-block-N` (per-frame absolute container), `.t` with inline `style="font-weight: N"` (per-paragraph weight; bold headers get 700 from `b=1`, plain detail lines get 500 from typeface→Medium default). Mobile: `.hero-mobile`, `.photo-m`, `.contact-stack-mobile > .contact-block-mobile`. SVG hero (Graphic 4 / image1.svg, 720×720 viewBox multi-gradient Identity logo) inlined via existing `inline_data_url` (SVG-first → raster fallback path; reused from cover.py precedent without refactor). Wordmark (Picture 10 / image21.png, 278×102 RGBA, multi-color non-invertible) also inlined via `inline_data_url` (raw PPTX PNG blob, ~few KB — `inline_optimized_data_url` carve-out path skipped to avoid threading `media_dir` through render signature; revisit if size becomes an issue). Mailto: hyperlinks (rId4 sean, rId5 rajit) NOT extracted — `parse_text_frame` doesn't read `<a:hlinkClick>` so emails render as plain text per Cohort B7 scope (clickability deferred to Phase 2 alongside hlinkClick extraction). All 21 prior siblings byte-identical post-implementation. Slide 23 baselined to `1d357d140726201ce837f485dd9adb4c` (181KB) and iPhone + desktop verified 2026-05-02. The `two_column_layout` hint is currently 1 known value (`"contact"`); future contact-style slides in other decks would set it the same way.
- 2026-05-02 (Cohort B8): slide 2 shipped via new `card_grid` template (`render/templates/card_grid.py`, ~360 lines — 7th template, completes Phase 1B template matrix). First-pass shipped without bg-photo/overlay handling; visual diff vs PPT surfaced two issues (background photo missing, brand logos pixelated). Issue 1 fixed in this round; Issue 2 accepted as source-asset limitation (see "Brand-logo source resolution limitation" entry below). Issue-1 fix landed across 3 modules: (a) **transform/image.py** gained `_extract_blip_transforms(pic_elem)` + `_apply_blip_transforms(img, transforms)` — detects blip-level `<a:duotone>` (two-color tint walk; `prstClr` resolved via small preset map, `srgbClr` raw) and `<a:alphaModFix amt="N"/>` (alpha = N/100000, bounded [0,1]); applies via PIL `ImageOps.colorize` for duotone (grayscale → black-to-white-mapped) and per-channel alpha-scale for alphaModFix. Color modifiers `<a:tint>` + `<a:satMod>` on duotone endpoints NOT yet resolved (raw srgbClr used); slide 2 visual diff acceptable with raw — extend if a future deck needs the modifier resolution. Order: duotone first, alpha second, then existing `flatten_on_canvas` if hint set. Slide 2 Picture 62 (image3.jpeg) re-transformed: `blip[duotone 000000↔53C1EA, alpha=0.82]` baked into `pg_creative_deck_slide_02_img_01.webp`; verified RGBA mode + avg alpha 209/255 = 82%, color buckets dropped from 80 (natural photo) to 18 (limited duotone palette). (b) **`_is_canvas_skip_rect` in two_column.py + card_grid.py** updated to refuse-skip when `<a:alpha>` is present in srgbClr — prevents future regressions of the slide-2-Rectangle-1 class (cyan rect with alpha=55% sitting on a duotoned bg photo). Verified slides 22/23 still render byte-identically (Rectangle 5 on those slides has no alpha). (c) **card_grid.py** `_classify` returns 5-tuple `(bg_photo, tint_overlay, chrome_logo, brand_logos, title_frame)`: bg_photo identified by `s.z == 0 AND _is_full_canvas` (z-order + geometry, more precise than the previous "≥90% canvas size" heuristic which false-positives on intentionally large foreground pics); tint_overlay returned via new `_read_tint_overlay` helper that parses full-canvas alpha-bearing rect color matching `canvas_bg` into `{r,g,b,alpha}` dict. Z-stack emit order in DOM (back→front): `.photo` (full-canvas bg) → `.tint-overlay` (rgba background) → `.gif-logo` → `.t-title` → `.photo-N` brand logos. Browser z-order follows source order for absolute siblings, no `z-index` needed. Slide 2 manifest: added `expected_assets.photo_bg: 1`. Slide 2 baselined to `6c58a1b07a833db6af684787bf36dd1e` (324KB; up from 287KB pre-bg-fix due to inlined duotoned bg photo). All 22 prior siblings byte-identical post-implementation (verified by full md5 sweep + in-memory slide 22/23 re-render check). Slide 2 pending iPhone solo-file AirDrop verification (cyan-tint duotone bg photo + cyan overlay + 9 brand logo grid). Class-name correction during round: initially emitted bg as `class="photo-bg"` which `_class_to_role` doesn't recognize (validator failed `photo_bg: expected 1, found 0`); changed to `class="photo"` matching the existing convention from `section_divider.py`. Going forward, the new "alpha-aware canvas-skip + bg-photo + tint-overlay z-stack" pattern is templated for any future deck slide with a duotone-bg + cyan-tint design — see "Background-photo + tint-overlay z-stack" topical entry below for the reusable framing.

- 2026-05-03 (Cohort B8 closure): slide 2 verified, completing Phase 1B at 23/23. Three additional sub-rounds landed after the 2026-05-02 first pass: (i) **bg-photo + tint-overlay fix** — visual diff vs PPT surfaced that Picture 62 was a duotoned bg photo (not occluded) and Rectangle 1 was a 55%-alpha cyan overlay (not solid). `transform/image.py` gained `_extract_blip_transforms` + `_apply_blip_transforms` to pre-bake `<a:duotone>` (PIL `ImageOps.colorize` after grayscale) and `<a:alphaModFix>` (per-channel alpha scale) into the on-disk WebP — verified post-bake: RGBA mode, color buckets dropped 80→18, alpha avg 209/255=82%. `_is_canvas_skip_rect` (in both `card_grid.py` AND `two_column.py`) now refuses-skip when `<a:alpha>` present in srgbClr — slides 22/23 byte-identical (their cyan rects have no alpha). `_classify` 5-tuple now distinguishes `(bg_photo, tint_overlay, chrome_logo, brand_logos, title_frame)`: bg_photo by `s.z == 0 AND _is_full_canvas`; tint_overlay by `_read_tint_overlay` returning `{r,g,b,alpha}`. DOM z-stack: `.photo` (bg) → `.tint-overlay` (rgba) → `.gif-logo` → `.t-title` → 9× `.photo-N`. Class-name correction: bg div emits `class="photo"` (NOT `photo-bg`) per `_class_to_role` taxonomy + `section_divider` precedent. (ii) **mobile fixes** — visual diff of mobile surfaced 3 issues: bg photo missing on mobile, title too small, 3×3 grid broke logo-lockup grouping. Fixes: mobile path now emits `.photo-mobile` + `.tint-overlay-mobile` under `.panel { position: relative; overflow: hidden }` (natural-flow content uses `position: relative` to layer above via source-order stacking; same data URL reused desktop+mobile so validator unique-source count stays at 1); slide 2 manifest gained `mobile_title_size_vw: 9.0` + `mobile_title_weight: 500` + `mobile_title_line_height: 1.05` (slide-22 precedent now reused on `card_grid` — establishes the 4-hint mobile-typography pattern as cross-template); new `_cluster_logos_by_row(logos)` helper does 2-stage clustering (stage 1 sorts by y-center and splits rows when consecutive gap > `_ROW_GAP_THRESHOLD_PT` = 80pt; stage 2 sorts by x-left and clusters consecutive logos whose x-ranges overlap). Slide 2 produces row 0 = 3 clusters {P43} | {P39, P44} | {P45, P47} matching the 3 Secret variants; row 1 = 4 single-logo clusters (Always / Gillette / Olay / Ivory). Cluster cells use `position: relative` + per-img `position: absolute` percent-positioned within `_cluster_bbox` so desktop overlap geometry survives the desktop→mobile reflow (Secret Clinical lockup with P39+P44 reproduces at 12.4%/0% offsets within its cluster cell). (iii) **title size bump** — visual diff post-mobile-fix showed title still reading too small. `card_grid.py` extended to consume `title_size_pt` hint (mirrors title_stats / two_column override pattern); slide 2 manifest set `title_size_pt: 32` (1.333× of OOXML's 24pt) and `mobile_title_size_vw` bumped 9.0→12.0 proportionally. Final desktop title CSS: `font-size: 2.500cqw; font-weight: 500`; mobile: `font-size: 12.0vw; font-weight: 500; line-height: 1.05`. Slide 2 final baseline `a95fe1208df080861a42cd5441921317` (364KB) supersedes prior round md5s (`289d09…` first pass → `6c58a1…` post bg-fix → `17cbd9…` post mobile-fix → `a95fe1…` post title-bump). All 22 prior siblings byte-identical post-implementation across all 3 closure sub-rounds (verified by full md5 sweep + in-memory slide 22/23 re-render check). **Phase 1B closes 23/23 verified 2026-05-03.**

Slides 10, 13, 16, 18 are also shipped + iPhone-verified but tracked in MEMORY.md / running-list rather than the formal table (template-already-built render+verify rounds, no rebaselining since their initial ship).

**Not yet started — 2 slides, 2 template surfaces:**

- `card_grid` — slide 2 (NEW template; 9 logos in 4-level nested group + full-bleed bg). Cohort B8.
- `two_column` (already built in B6) — slide 23 only (Identity SVG hero + asymmetric contact info + email mailto: hyperlinks; structurally distinct from slide 22 — may need additional handling). Cohort B7.

**Manifest hints established by deck (deck-author design intent that OOXML can't carry):**

- `headline_class` — `"t-wnba"` (slide 5, 22pt) or `"t-bold"` (slides 6, 7, 24pt). Maps to inherited-bold pt via `INHERITED_BOLD_PT_BY_HINT` in `media_showcase.py` / `section_divider.py`.
- `canvas_bg` — `"#FFFFFF"` (slides 5, 6, 7); default `deck_brand_color` (cyan) elsewhere.
- `logo_invert` — `true` (slides 3, 4, 5, 6, 7, 21). All 4 logo-bearing templates (cover, section_divider, media_showcase, title_stats) read it.
- `title_size_pt` / `heading_size_pt` / `body_size_pt` — title_stats per-slide font-size overrides.
- `hide_footnote` — title_stats slide 21 (suppress footnote body, keep title's "*").
- `expected_assets` — validator hint, see "expected_assets validator architecture" entry below.
- (planned, not yet wired) `mobile_video_aspect_override` / `mobile_video_fit` — slide-16 opt-in.

---

## logo_invert manifest hint — required deck-author override bundle missed

`logo_invert: true` on a slide → all logo-bearing templates emit `filter: brightness(0) invert(1)` on `.gif-logo` (desktop) and `.gif-logo-mobile` (mobile), regardless of template. Implemented uniformly across `cover.py`, `section_divider.py` (standard + badge), `media_showcase.py` (photo-grid + video), and `title_stats.py`. Default is `false`.

**When to apply:** the GIF brand mark is full-color (PNG with transparency), and is unreadable on cyan or any saturated brand color in the same family. It also clashes against the white circle badges on photo-grid slides. The bundle's prior renders applied an invert filter to the mobile top-bar logo on most slides (but not desktop), and missed it entirely on slide 4. We track per-slide as a hint because:

- Mobile top-bar is *always* cyan (var(--bg-cyan)) — so logo_invert for mobile is ON for every slide that has a logo.
- Desktop sometimes is cyan (canvas_bg = cyan), sometimes is white (slides 5, 6, 7 with photo grid covering canvas). On white desktop we still want invert, because the logo on white reads OK *but* the mobile-top-bar inversion is jarring without matching desktop. Keep desktop + mobile in lockstep per slide; the hint controls both.

**Current usage in this deck:** on for slides 3, 4, 5, 6, 7, 21. Off (default) for slides 1, 2, 8, 9–20, 22, 23 — note that slides 8, 10, 13, 18 don't have logos at all (1-image-only section_divider where the photo *is* the only image), and slide 1 deliberately keeps the logo full-color (it is the deck's identity beat on the cover, not chrome).

**Bundle-author error class — required overrides bundle missed:** the bundle render of slide 4 has the logo unfiltered → invisible against cyan in the mobile top-bar. The bundle author *forgot* the override they'd applied to slides 5/6/7. Same shape as the bundle's slide-21 missing `title_size_pt: 60` (we override the bundle's incorrect 44pt) and the bundle's slide-3 `heading_size_pt: 22` (we override the implicit 18pt). The "bundle is truth" parity rule has an exception class: **the bundle is truth for design intent that's *expressed* in the bundle, but it's NOT a complete record of the deck author's intent.** Some required overrides got dropped during their hand-conversion to HTML and only surface when we systematically apply them across slides. Catalog these in the manifest as we find them; the manifest is the corrected superset. As more decks get converted, expect a similar pattern: per-slide design intent that's correctly applied on most slides but missing on a few, and our render must over-correct.

---

## inline_data_url scope rule — what's inline, what's external

After the 2026-04-30 round, the rule is concrete:

```
asset role            transport      reason
──────────────────────────────────────────────────────────────────────────────────
logo                  inline         Tiny (~5KB), brand-critical, must travel with HTML
                                     for AirDrop / file:// delivery (already locked)
hero (SVG)            inline         transform/image.py skips SVGs by design;
                                     inline_data_url's SVG-first preference handles
photo_bg              inline         section_divider full-bleed photo backdrop —
                                     decoration baked into the slide's identity;
                                     inline keeps the slide self-contained; size
                                     impact is one photo per slide (~75-100KB JPEG)
photo_grid (badge)    inline         section_divider badge variant 4-photo grid
                                     (slide 5) — same rationale as photo_bg
photo_grid (showcase) external       media_showcase grid photos (slides 6, 9, 11,
                                     12, 14, 15, 17, 19, 20) — content assets,
                                     not decoration; user can swap them per deck;
                                     external `.webp` from transform/image.py
video                 external       media_showcase video (slides 7, 16) — multi-MB
                                     binary; transform/video.py owns the .mp4
video_poster          inline         small JPEG, lives on the <video poster=...>
                                     attribute; external would defeat the purpose
                                     of having a poster
```

**Distinction that matters: `photo_bg` vs `photo_grid` is not just count.** A 1-photo `section_divider` standard treats its photo as a *backdrop* (decoration). A 4-photo `section_divider` badge treats them as a *grid* (also decoration, baked into the slide design). A 4-photo `media_showcase` photo-grid treats them as *content* (the photos are what the slide is *about*). The shape archetype determines the role; the role determines the transport. Templates that build new variants should classify into one of the 6 roles (logo, hero, photo_bg, photo_grid, video, video_poster) and use the matching helper:

- `inline_data_url(shape, slide)` — for inline transport
- `image_src(shape, slide_class, slide)` — for external transport (manifest filename + inline fallback)

`image_src`'s fallback is intentional: SVG-only shapes (transform skips them) get inlined automatically because the manifest has no entry for them. Don't switch to `inline_data_url` for showcase photo-grids — that re-inflates the HTML to 13MB (slide 6's pre-retrofit state) and defeats the whole external-asset retrofit.

---

## expected_assets validator architecture + 6-role taxonomy

**Architecture (lives in `ondeck/layout/detect.py`):**

- `SlideClass.expected_assets: dict[str, int] | None` — manifest-declared counts per role; None disables validation for that slide.
- `Manifest.validate(slide_index, html) -> list[str]` — returns `[]` clean, list of mismatches otherwise.
- `_scan_html_for_assets(html) -> dict[str, set[str]]` — regex scan of rendered HTML; counts unique source URLs per role.

**6-role taxonomy:**

```
role              detected via                                              inline?
──────────────────────────────────────────────────────────────────────────────────
logo              <div class="gif-logo|gif-logo-mobile|logo|logo-mobile">   yes
hero              <div class="hero|hero-mobile">                             yes
photo_bg          <div class="photo|photo-mobile"> (no digit suffix)         yes
photo_grid        <div class="photo-N"|"photo-m"> (digit or 'm' suffix)      mixed (see scope rule)
video             <source src="..."> inside <video>                          no
video_poster      <video poster="...">                                       yes
```

The scanner is *anchored* to `<div class="...">` wrappers around `<img>` elements (or `<div>` with a `style="background-image:..."`). This naturally excludes the inline `@font-face { src: url(data:font/woff2;...) }` block in the page's `<style>` — that CSS isn't preceded by a div wrapper, so the regex doesn't match. Other `url(...)` calls inside CSS are similarly ignored. The two regex flavors `_DIV_BG_DOUBLE_RE` and `_DIV_BG_SINGLE_RE` handle both `style="..."` and `style='...'` quoting (the latter is what `section_divider.py` emits so it can carry `url("data:...")` with double-quotes inside).

**Dedup by source URL:** each slide is rendered with both `<section id="deck-desktop">` and `<section id="deck-mobile">` in one HTML document. A photo referenced in both desktop and mobile (the common case) collapses to a single count. So `expected_assets: {photo_bg: 1, logo: 1}` means "one unique photo, one unique logo across the whole HTML" — not "one in desktop and one in mobile separately." That keeps the expected counts stable as templates emit the same asset to multiple selectors.

**Why this matters — the slide 8 lesson.** Slide 8 is `section_divider / standard` with NO logo (just a photo backdrop). Mobile uses `<div class="photo-mobile" style='background-image: url(...)'>` for the photo. If the URL fails (typo, missing file, wrong content type), the gradient overlay covers the empty area — the slide *looks* fine but with a blank photo backdrop. The eye doesn't catch it because the gradient masks the absence. `expected_assets: {photo_bg: 1}` validates that exactly one photo source URL exists in the rendered HTML; if the bg-image string didn't materialize, validate() returns `["role 'photo_bg': expected 1, found 0"]`. This was the canonical "asset silently missing under decorative overlay" failure class — gradient overlays *especially* on `section_divider` slides hide it, so we need explicit validation, not visual inspection.

**Generalized lesson:** any template where a content asset sits beneath a decorative layer (gradient, frosted glass, color tint, blur) is at risk for silent-asset-failure. Eye-test passes because the overlay dominates the visual reading; only an asset count check catches it. Add `expected_assets` for all such slides as a regression net.

---

## section_divider gradient masks silently-failed background-image refs

Specific instance of the validator-architecture lesson above, kept as its own entry for searchability when the bug recurs.

**The failure mode:** `section_divider` standard variant emits the photo backdrop on mobile as a `style='background-image: url(...)'` on a `<div class="photo-mobile">`. Above it sits a `linear-gradient(to top, var(--overlay) 0%, var(--overlay) 25%, var(--overlay-0) 60%)` — opaque cyan covering the bottom 60% of the panel where the headline sits. If the URL string has any defect (path typo, missing transform output, byte-level corruption in the data URL), the photo doesn't render — but the gradient is unchanged, so the slide presents as "all-cyan headline area with a faint cyan tint above." It *looks* like a stylistic choice rather than a bug. Real-iPhone eye-test does not catch this; the gradient is doing its job whether the photo is there or not.

**Detection going forward:**

1. `expected_assets` validation (above) — primary mechanism. Any `section_divider` slide gets `photo_bg: 1`; the renderer's HTML output is checked before shipping.
2. Diff against pre-block MD5 — secondary mechanism. If a photo's binary changed (e.g., transform/image.py output drift), MD5 catches it. If the URL goes missing entirely, MD5 still catches it but the diff doesn't tell you *why* without the validator's role-level message.
3. Real-iPhone test — tertiary, unreliable for this specific failure. Useful for visual regressions but not for "is the photo actually loaded."

**Why this entry exists separately:** the `expected_assets` entry is the architectural how. This entry is the *specific* "section_divider + gradient" pairing that motivated building it. When future templates add their own decorative-overlay-over-content-asset patterns, repeat the validator hookup — don't trust eye-tests on overlay slides.

---

## Operating principles

### AirDrop verification: only fully-inlined HTML can be trusted on iPhone

**The wall is iOS Quick Look's file:// sandbox, not the transfer method.** When iPhone Safari or Quick Look opens an `.html` from Files, sibling-file fetches (`<img src="sibling.webp">`) are blocked at the sandbox layer regardless of how the files arrived together. Confirmed 2026-05-01:

1. Zip-then-AirDrop landed all 4 files in a single folder (verified via iOS Files inspection). Photos still rendered as broken-image icons.
2. Desktop Safari opened the same HTML from `file://` and rendered all photos correctly — proving the HTML, paths, and webp files are valid.
3. Quick Look on individual webp files in iOS Files previewed each photo cleanly — proving WebP decode works and the asset format is fine.

The conclusion: iOS Quick Look refuses to fetch any sibling resource, even from the same directory. Only fully-inlined `data:` URLs survive iOS file:// rendering.

**Implication: the `inline_data_url` scope rule (above) needs revising for `photo_grid` showcase slides.** Showcase photos must inline by default if iPhone single-file AirDrop is the verification path. Tracked as a separate scope-rule entry below.

**Prior verifications of slides 6, 11, 12, 15, 17 are technically invalid.** Those verifications appeared to pass under multi-file AirDrop or directory drop, but per the 2026-05-01 finding, iOS Quick Look would have blocked the sibling fetches in those cases too. The fact that they were marked "AirDrop-verified" earlier likely means one of:
- The verification used desktop Safari rather than iOS (different sandbox)
- The user opened the HTML in mobile Safari directly (not Quick Look) where some `file://` fetches are permitted depending on the launch path
- The visual inspection was done on a slide where the broken-image pattern wasn't obvious (e.g., dark photos on dark canvas hide the iOS broken-image icon)

These slides require **re-verification** under the inline rule once the showcase transport is flipped. Do not assume past "verified" status carries forward.

**Reliable workflow once the inline rule lands:**

1. AirDrop the standalone `.html` — all assets self-contained, no sibling files needed. This is what works for slide 1 today and for `cover` / `section_divider` slides generally.
2. Zip-then-AirDrop and directory-drop are still useful for bulk transfer (move the whole `out/` once), but they do NOT fix the sandbox issue — they only help if the HTML is inline-self-contained anyway.

**Slide-by-slide AirDrop verification matrix** (post-rule-revision target state):

- Solo-AirDrop-safe (fully inlined): 1 (cover), 3 (title_stats), 4, 5, 8, 10, 13, 18 (section_divider — both standard and badge variants), 21 (title_stats), 6, 9, 11, 12, 14, 15, 17 (media_showcase photo-grid + large-headline, all post-2026-05-01 inline-WebP rule; slide 14 added 2026-05-02 with hard-edge-alpha PNG mockup), 19, 20 (media_showcase titled-grid, post-2026-05-02 sub-variant landing). Note on slide 14: per 2026-04 audit it was speculatively classified as small-corner-label sub-variant; 2026-05-02 OOXML audit corrected this to photo-grid badge variant (same archetype as slides 9, 11, 12). No new code needed — manifest hint pass only.
- Still external (must travel with HTML, but iOS Quick Look will fail to fetch them anyway — only desktop Safari or non-Quick-Look mobile browsers will render): 7, 16 (media_showcase video — `.mp4` is external; inlining a multi-MB video as base64 is impractical, so video slides remain a known limitation for iOS solo-file verification).

### Photo_grid showcase carve-out from the inline-vs-external transport rule

**Rule (landed 2026-05-01):** `media_showcase` photo_grid showcase slides inline WebP via `inline_optimized_data_url`; previous external-asset rule retained for hero/video only.

**What changed:** the helper `inline_optimized_data_url(shape, slide_class, slide, media_dir)` in `_shared.py` reads the optimized WebP that `transform/image.py` already produced in `out/<filename>` and inlines it as `data:image/webp;base64,...`. Both `_render_photo_grid_variant` and `_render_large_headline_variant` in `media_showcase.py` route their content photos through this helper. Logos still inline via `inline_data_url` (raw PPTX blob, since logos are tiny and the PPTX-side PNG is fine).

**Strict contract on the helper:** `media_dir` is required. The helper raises `ValueError` when it's None — the silent raw-PPTX-blob fallback was deliberately removed because it would produce 4× larger HTML when a driver forgot to thread the param. Callers that want the raw-blob path can call `inline_data_url` directly.

**Why a carve-out, not a full rule revision:**

- Rule still holds for hero (cover slide 1) — single SVG, inlines naturally.
- Rule still holds for video (slides 7, 16) — inlining multi-MB `.mp4` as base64 is impractical (1.4× expansion, slow parse, browser memory pressure). Video slides remain external; iOS Quick Look verification of video slides is a known limitation we'll address separately when we revisit the video pipeline.
- Rule changes only for photo_grid showcase (slides 6, 9, 11, 12, 14, 15, 17, 19, 20) where the WebP is already optimized to ~50-300 KB per photo and inlining is iOS-Quick-Look-compatible.

**Why we're not rewriting the global "inline_data_url scope rule" entry yet:** the global rule was written to balance HTML size against transport-self-containment, treating "showcase content = external" as a unitary principle. The 2026-05-01 finding splits that principle cleanly along the photo_grid / video boundary — but until we decide on the video-side answer (Phase 2), the global rule still has internal tension. Documenting as a carve-out keeps the global rule's prior reasoning legible while making the new photo_grid behavior unambiguous.

**Cost realized:** 6 slides re-baselined 2026-05-01. Total HTML inflation across the 6 slides: ~4.0 MB. Largest single slide: 06 at 2.27 MB; smallest deltas: 09/11/12 at +200-340 KB each. Inflation came in ~2× the pre-implementation estimate because each photo's data URL is emitted twice (desktop section + mobile section). Phase 2 optimization candidate: de-duplicate via a single CSS `background-image: url(data:...)` rule referenced from both sections.

### Titled-grid sub-variant of media_showcase (2026-05-02)

**Rule (landed 2026-05-02):** slides whose layout is "title-text above photo grid, no circle badge, no logo" route through `_render_titled_grid_variant` via the manifest hint `media_showcase_layout: "titled-grid"`. Slides 19 (4×2 product grid), 20 (1×5 vertical poster row) ship under this variant.

**Why this is a new sub-variant rather than an extension of photo-grid badge:**

- Badge variant (slides 6, 9, 11, 12) classifies the text shape as a circle-overlay label and positions it at the circle's coords. Slides 19/20 have no circle and a title shape with its own positioning — same shape topology (text + photos) but visually + structurally distinct.
- Auto-detecting "circle absent + text present → titled-grid" is unsafe because future photo-grid slides could legitimately have text without a circle (e.g., a photo grid with a corner caption). Explicit hint dispatch makes the deck author's intent unambiguous.
- The variant has its own CSS class (`.title` / `.title-mobile`) instead of the badge variant's `.L` / `.circle-mobile`. This keeps the two patterns visually + semantically distinct in the rendered DOM and avoids accidental cross-contamination of CSS rules.

**Dispatcher behavior:** The hint check sits between the gradient auto-detect (large-headline) and the photo-grid fallback in `render_media_showcase`. Order: video → gradient → titled-grid (hint) → photo-grid (fallback). Auto-detected variants (video, gradient) win over the hint; the hint wins over the photo-grid default. Slides without the hint are unaffected.

**Inherits the inline-WebP rule:** `_render_titled_grid_variant` calls `inline_optimized_data_url(p, slide_class, slide, media_dir)` for content photos — same transport as the other media_showcase variants. The strict-mode contract on the helper (raises `ValueError` if `media_dir is None`) ensures new variants can't accidentally fall back to external URLs.

**Cost realized:** 2 slides shipped 2026-05-02. Slide 19 = 2.25 MB (8 photos), slide 20 = 1.28 MB (5 photos). Both within the same range as the inline-WebP siblings. ~225 new lines in `media_showcase.py` (`_classify_titled_grid` + `_render_titled_grid_variant` + `_build_css_titled` + `_build_body_titled`); ~5 lines touched in the dispatcher. All 17 existing siblings (11 truly-locked + 6 inline-WebP) regression-verified byte-identical.

### Alpha-aware canvas-skip-rect heuristic (2026-05-02 Cohort B8)

**Rule:** `_is_canvas_skip_rect` (in both `two_column.py` and `card_grid.py`) skips a full-canvas solid rect ONLY when its `<a:srgbClr>` matches `canvas_bg` AND has NO `<a:alpha>` child. A rect with alpha is a deck-author tint overlay and must be emitted as a CSS `rgba()` background, not silently dropped.

**Why this matters:** the original implementation matched on color alone, which mistook slide 2 Rectangle 1 (cyan #00B0F0 with alpha=55%) for a redundant fill and skipped it. Combined with the now-deleted `_is_occluded_background_pic` heuristic skipping the duotoned bg photo underneath, the slide rendered as a flat cyan canvas — both the photo AND the tint overlay erased.

**Generalizes to:** any future deck slide where a full-canvas color rect is the deck-author's intentional tint pass over an underlying photo or pattern. The check is alpha-aware — solid full-canvas overlays still get the skip optimization (slides 22, 23 Rectangle 5).

### Background-photo + tint-overlay z-stack (2026-05-02 Cohort B8)

**Pattern:** when a slide layers `(background photo) + (full-canvas alpha-bearing color rect) + (foreground content)`, the renderer emits three layers in DOM source order:

1. `<div class="photo"><img src="data:image/webp;base64,..."></div>` — full-canvas bg
2. `<div class="tint-overlay"></div>` with CSS `background-color: rgba(...)` — the alpha overlay
3. Foreground (chrome logo, title, brand logos, etc.)

Browser z-order follows source order for absolute-positioned siblings — no `z-index` declarations needed.

**Classification (in `card_grid.py`):**
- bg photo: pic with `s.z == 0 AND _is_full_canvas` (z-order + ≥90% canvas geometry). The z=0 check is what distinguishes intentional full-bleed bg from a large foreground pic that happens to be near canvas size.
- tint overlay: full-canvas rect via `_read_tint_overlay` (returns `{r,g,b,alpha}` dict) when color matches canvas_bg AND has `<a:alpha>` set.

**Class taxonomy:** bg photo emits `class="photo"` (NOT `class="photo-bg"`) so `_class_to_role` resolves it to role `photo_bg` for asset-validator counting. The convention matches `section_divider.py` precedent. Don't invent new class names without updating the validator's role-mapping table.

**Generalization:** the `_classify` 5-tuple `(bg_photo, tint_overlay, chrome_logo, brand_logos, title_frame)` is a reusable signature for any "full-bleed-photo with overlay tint" template. Slide 2 is the first; future deck slides with similar design (tinted hero shot under foreground content) can use the same pattern.

### Blip-level transform pre-baking in transform/image.py (2026-05-02 Cohort B8)

**Rule:** `transform/image.py` detects `<a:duotone>` and `<a:alphaModFix>` on a `<p:pic>`'s blip and bakes the resulting pixel data into the on-disk WebP before the renderer sees it. This means the renderer always reads "ready-to-display" images — no runtime CSS filter chains, no per-template duotone math.

**Implementation:**
- `_extract_blip_transforms(pic_elem)` returns `{"duotone": {dark_hex, light_hex}, "alpha": float}` or None.
- `_apply_blip_transforms(img, transforms)` applies via PIL: `ImageOps.colorize(grayscale(img), dark, light)` for duotone; per-channel alpha-scale for alphaModFix.
- Order: duotone before alpha (matches PowerPoint's blip-child document-order rendering per ECMA-376 §20.1.8).

**Color-modifier resolution NOT yet implemented:** `<a:tint>`, `<a:satMod>`, `<a:lumMod>`, `<a:lumOff>` on duotone color endpoints are dropped — raw `srgbClr val` is used. Slide 2 Picture 62 has `tint=45000 + satMod=400000` on the cyan endpoint; visual diff with raw 53C1EA was acceptable. Extend with proper modifier resolution if a future deck shows visible drift.

**Other unhandled blip transforms (extend when needed):** `<a:lum>`, `<a:biLevel>`, `<a:grayscl>`, `<a:tile>`, srcRect crops within `<a:blipFill>`. Add per-need; slide 2 only required duotone + alphaModFix.

**Idempotency:** existing `--overwrite` flag toggles re-encode. Without it, an existing webp is kept; renderer reads stale pixels. Always pass `--overwrite` when changing blip-transform behavior on an already-transformed image.

### Brand-logo source resolution limitation (2026-05-02 Cohort B8)

**Known limitation, not a bug.** Slide 2's 9 brand logos (image4-image11.png) are embedded in the .pptx at 175-257px source dimensions — designed for 1280px-canvas display at 1× resolution. PowerPoint's authoring tools never anticipated retina/4K displays.

**Visible effect:** at any viewport wider than 1280px the canvas scales up proportionally (CSS: `width: min(100vw, 177.78vh)`), and the brand-logo `<img>` elements scale 1:1 with the canvas. On a 1920×1080 display: 1.5× upscale. On 4K: 3× upscale. On retina iPhone (devicePixelRatio 3) effective: ~7× → visibly pixelated.

**Renderer is faithful:** OOXML cx/cy for each pic equals the embedded image's pixel dimensions; the renderer reproduces 1:1. There is no upscaling we introduce — the apparent pixelation is purely the source-asset → display-size ratio on real screens.

**Matches the original PPT bundle behavior** (the deck export the bundle was built from has the same source-resolution constraint).

**Phase 2 fix paths if higher fidelity is needed:**
- A: Procure higher-DPI brand assets from official brand asset libraries (Pampers, Pantene, Always, Olay, etc. publish 2-3× resolution logos).
- B: AI super-resolution at transform time (Real-ESRGAN, waifu2x). Risky — sharp brand-mark geometry artifacts.
- C: Use SVG sources where available — vector resolution-independent.
- D: Accept (current state, matches PPT, no extra work).

Currently shipped: Fix D. Re-evaluate when client supplies high-res brand assets or a Phase 2 brand-asset procurement round is opened.

**Re-verification queue:** slides 19, 20 solo-file AirDrop iPhone-verified 2026-05-02 (same day as landing). No re-verification needed for prior baselines — they don't carry the new hint, take the unchanged dispatch path.

### Inherited size resolution: txBox vs placeholder distinction (2026-05-02, Cohort B6)

Freestanding text boxes (`<p:cNvSpPr txBox="1"/>` with no `<p:ph>`) inherit from the master's `<p:otherStyle>`, NOT `<p:bodyStyle>`. Renderer encodes this as a hard rule in `resolve_inherited_size(shape, slide, paragraph_lvl)` in `_shared.py`. Verified empirically on slide 22 — 30 names resolve to 18pt via `<p:otherStyle>/<a:lvl1pPr>/<a:defRPr sz="1800"/>`. Without this rule, txBox frames would default to bodyStyle's lvl1=28pt and overflow narrow text frames.

**Helper API:**

```python
resolve_inherited_size(shape, slide, paragraph_lvl=0) -> Optional[float]
```

**Walk order** (returns at first hit):
1. Shape-level `<p:txBody>/<a:lstStyle>/<a:lvl{N}pPr>/<a:defRPr sz="...">` where N = paragraph_lvl + 1.
2. Layout-level `<p:txStyles>` (deferred — no slide currently in scope uses layout overrides; placeholder for future expansion).
3. Master-level `<p:txStyles>`:
   - Shape has `<p:ph type="title"|"ctrTitle">` → `<p:titleStyle>`
   - Shape has `<p:ph>` (other types) → `<p:bodyStyle>`
   - Shape has no `<p:ph>` (txBox or freestanding) → **`<p:otherStyle>`**

**Why this matters beyond slide 22:** any future template that emits text from non-placeholder shapes must call `resolve_inherited_size` rather than assuming bodyStyle. The bug class to avoid: "I read the master's bodyStyle/lvl1 and got 28pt, but the slide visibly renders at 18pt because PowerPoint resolved via otherStyle." Surface as a defensive rule: when in doubt, check whether the shape carries `<p:ph>` and route accordingly.

**Manifest hint precedent (slide 21 + slide 22):** even with clean OOXML resolution, set `body_size_pt` and `title_size_pt` EXPLICITLY in the manifest as insurance. Slide 21 needed `title_size_pt: 60` because the bundle's prior render diverged from OOXML inheritance — the deck author's design intent didn't survive their own hand-conversion. Same defensive pattern applied to slide 22 (`title_size_pt: 44` matches OOXML, `body_size_pt: 18` matches `<p:otherStyle>` resolution; both are "insurance, not correction"). When OOXML resolution and explicit hint agree, the hint is no-op. When they diverge, the hint wins (matches `title_stats.py:122-130` precedent).

**Two related bug classes also surfaced 2026-05-02 during the slide-22 CSS-fix round:**

1. **`calibrate_size_pt` shadowed master inheritance.** The helper has hardcoded `INHERITED_SIZE_REG_PT=16` / `INHERITED_SIZE_BOLD_PT=18` defaults that fire when a run's declared `size_pt` is None — bypassing any value `resolve_inherited_size` would have computed from the master. **Fix pattern (now used in `two_column.py`):** when a run's declared size is None, pass the resolved-inherited value (from `resolve_inherited_size`) to `calibrate_size_pt` as the `declared` argument, rather than letting the helper fall back to its hardcoded defaults. New templates that consume `calibrate_size_pt` should mirror this.

2. **Manifest hint check used `if size_pt is None`.** Since `calibrate_size_pt` always returns a non-None value, the `is None` guard never fired and the hint was effectively dead. **Fix pattern:** apply `body_size_pt` / `title_size_pt` hints UNCONDITIONALLY (matches `title_stats.py:129-130` — that template applied `if title_run is not None and title_size_pt_hint is not None` without checking the existing size).

### Known font-substitution gap: Univers Condensed → Barlow Condensed visual weight (2026-05-02)

Body text on slide 22 (and other Univers-Condensed-targeted slides) renders slightly lighter visually than the PPT reference, even though the OOXML weight is correctly resolved (`b=None` → 500 / Medium per `TYPEFACE_WEIGHT["univers condensed"]` map). Cause: matched-metric substitution (`MATCHED_METRIC_SUBS["univers condensed"] = "barlow condensed"`) preserves metrics 1:1 but the visual "weight" of Barlow Condensed Medium reads thinner than Univers Condensed Regular at the same nominal weight value.

**Deferred to Phase 1C deck-token work.** Two paths considered, both rejected for this round:
- Bump `TYPEFACE_WEIGHT["univers condensed"]` from 500 → 600 globally → regression risk on the 21 verified slides that already passed iPhone verification at 500.
- Add per-slide `body_weight: 600` manifest hint → premature; Phase 1C will do per-deck token tables that supersede individual hints.

For now, accept the slight visual-weight gap on slide 22 and any future Univers-Condensed slide. Re-evaluate when Phase 1C lands.

### Transport rule by asset role — current state + Phase 2+ trajectory

**Current behavior (as of 2026-05-01):**

| role | transport | helper | applies to |
|---|---|---|---|
| `logo` | inline data URL (raw PPTX blob) | `inline_data_url` | every slide with a logo (1, 3, 4, 5, 6, 7, 9, 11, 21 + others as added) |
| `hero` | inline data URL (SVG-first, raster fallback) | `inline_data_url` via `image_src` SVG-fallback path | cover slide 1 |
| `photo_bg` | inline data URL (raw PPTX blob) | `inline_data_url` | section_divider standard variant — slides 4, 8, 10, 13, 18 |
| `photo_grid` (badge) | inline data URL (raw PPTX blob) | `inline_data_url` | section_divider badge variant — slide 5 |
| `photo_grid` (showcase) | **inline WebP** (optimized, from `out/`) | **`inline_optimized_data_url`** | media_showcase photo-grid + large-headline variants — slides 6, 9, 11, 12, 14, 15, 17, 19, 20 |
| `video` | external URL (relative `.mp4` filename) | `image_src` for the poster-still; `extract_video` writes the `.mp4` aux file | media_showcase video — slides 7, 16 (Phase 2 decision pending) |
| `video_poster` | inline data URL (raw PPTX blob, JPEG) | `inline_data_url` | media_showcase video — slides 7, 16 |

**The rule, said plainly:** everything role-detected by the validator's 6-role taxonomy travels inline EXCEPT video. Video is the lone external asset in the current production state. iOS Quick Look's `file://` sandbox dictates that "inline = iPhone-AirDrop-verifiable, external = not."

**Phase 2 video decision is the open question.** Inlining a multi-MB `.mp4` as base64 is impractical for HTML parse/memory reasons (would push slide 7 to ~30+ MB HTML). Three plausible paths when we get there:

1. Keep `.mp4` external; accept that video slides aren't iPhone-AirDrop-verifiable solo. Verification done via desktop Safari or device-specific Cloudflare URL preview.
2. Inline a low-bitrate "preview" `.mp4` as data URL + load the full video lazily over network when bandwidth is available. Two-tier asset: inline preview, external full.
3. Move all video to the Cloudflare CDN path (see below) and treat AirDrop verification as a Cloudflare-URL preview. iOS Quick Look still won't fetch external HTTPS resources from a `file://` HTML page (same sandbox rule), but a hosted-HTML preview URL doesn't need AirDrop at all.

The decision waits until Phase 2 because it interlocks with the CDN migration plan below.

### Cloudflare CDN migration path (Phase 2+)

**Architectural design intent — not yet implemented.** When the deck moves to hosted delivery (production state for shareable links rather than AirDrop preview), assets transition from local `out/` to Cloudflare. The helper-as-abstraction shape we landed on 2026-05-01 makes this a non-rewrite migration:

**The pivot:** `inline_optimized_data_url` is a *transport-layer abstraction*. Today its body reads `out/<filename>` and base64-encodes; under Cloudflare it reads `<filename>` and returns `https://<cdn-host>/<deck-slug>/<filename>`. Same call sites in `media_showcase.py`, same arguments, same return type (a string the renderer drops into `<img src="...">`). No template touch needed; no validator change needed (it classifies by the wrapping `<div>`'s class string, not the URL); no manifest schema change needed (filenames already deterministic per `transform/image.py`'s output convention).

**What gets renamed at migration time:** `inline_optimized_data_url` becomes a misnomer once it's returning HTTPS URLs. Plan to rename to `optimized_asset_url` (transport-agnostic) when the Cloudflare body lands. Or keep the name and add a sibling. Decide at implementation time.

**What does NOT change:**

- Layout / CSS / DOM shape
- Validator's 6-role taxonomy and `_class_to_role` classifier
- MD5 baseline architecture (well, MD5s themselves change because the URLs in HTML change, but the *baseline tracking mechanism* — locked-siblings table, expected_assets — is unaffected)
- The 4-template render API (cover, section_divider, media_showcase, title_stats) and their public function signatures
- Manifest format (deck_name, source_pptx, deck_brand_color, slides[].template, slides[].hints, slides[].expected_assets, slides[].media)
- `transform/image.py` output (it already produces deterministic deck-prefixed slide-indexed role-indexed filenames; CDN cache stability is built-in)

**What changes at migration time:**

- Helper body: `read+b64+f-string` → CDN URL construction
- Verify-vs-ship asymmetry dissolves: today AirDrop verification uses inline data URLs and Cloudflare-hosted production would use external HTTPS URLs — different bytes, different MD5s. Post-migration, both use the same external HTTPS URLs and verify on the same artifact production ships.
- Logo transport stays inline regardless. Logos are < 10 KB, inlining beats a CDN round-trip for first-paint, and they're brand-critical (offline display still works for the cover image and chrome). Don't migrate logos to CDN.
- Asset naming: `pg_creative_deck_slide_NN_img_KK.webp` (and `_video.mp4`) is the deterministic convention. Must stay stable across runs so Cloudflare cache keys don't churn. `transform/image.py` already enforces this; document so future-self doesn't break it during a refactor.

**Acceptance criteria for the CDN migration when it lands** (do not start; this is the spec for future-self):

1. Cloudflare bucket structure: `<bucket>/<deck-slug>/<filename>`. Deck-slug from manifest's `deck_name` (lowercase, `[a-z0-9-]+`); filename verbatim from `media.images[].filename` / `media.video.filename`.
2. Pure-helper-body change in `_shared.py`. No template-level edits to `media_showcase.py`, `cover.py`, `section_divider.py`, or `title_stats.py`.
3. New manifest field `cdn_base_url` (or env var override) — not per-slide; deck-level. Helper reads it. Empty/None falls back to local-inline behavior (preserves AirDrop verification path).
4. Re-baseline all 23 slides at migration time. MD5s shift because URLs change; locked-siblings table gets a "post-CDN-migration baseline" round.
5. Validator: no change. The `_class_to_role` classifier already accepts any `src` value, including HTTPS URLs.
6. Slide 1 / 21 (logo-only slides) keep their pre-migration MD5s — logos stay inline, and those slides have no other role-typed content. Locked across the migration.

This is a documented intent, not a queued task. Update or override at Phase 2+ planning.


## Color resolver — known gaps

- `theme_from_pptx()` in `ondeck/parse/color.py` does not yet have its own
  fixtures. Phase 1c locks the resolution math given a theme dict, but the
  pptx → theme dict extraction is unverified. Add theme-parsing fixtures
  (a known .pptx + expected dict) before relying on `theme_from_pptx()`
  in production.
- `theme_fillstyle_*` fixtures in `phase_1c/fixtures/` describe gradient
  fill definitions, which are a separate surface from `ColorResolver` and
  not exercised by `tests/test_color_resolver.py`. They belong to a future
  fill-style resolver.

## Color resolver — phase 1d update (2026-05-15)

- `parse_theme_xml()` is now locked by `theme_demert_default_office.xml`
  (Office default scheme, 12 entries, sysClr handling for dk1/lt1).
- Custom-theme decks (non-Office scheme colors) are not yet covered.
  Empirical finding from DEMERT (2026-04-15, current GIF deck): the theme
  layer is left at Office defaults; brand colors live elsewhere (slide
  masters, per-shape fills, fillStyleLst). Worth checking other GIF decks
  before assuming custom themes are common.
- Multi-theme decks: DEMERT has theme1 + theme2 with identical color
  schemes (diff is in fonts/fillStyleLst only). Behavior on decks where
  theme1 and theme2 disagree on colors is unverified.

## Color resolver — theme_from_pptx() end-to-end closed (2026-07-30)

- `theme_from_pptx()` is now verified end-to-end against a real deck:
  `SHELFBEAUTY_RETAIL_INVESTOR_PRESENTATION_OSRX.pptx` (theme1 != theme2
  colors, real 121-entry zip namelist). Fixture is a trimmed re-zip of the
  deck's real `theme1.xml`/`theme2.xml` alone (source deck is 51MB; fixture
  is ~4KB) at `phase_1c/fixtures/theme_shelfbeauty.pptx`, exercised by
  `test_theme_from_pptx_real_shelfbeauty_deck` in `test_color_resolver.py`.
  Result matches `_SHELF_THEME1_EXPECTED` exactly.
- The prior synthetic multi-theme test only proved the sort()+[0] selection
  rule against clean minimal XML; this proves the real zipfile-open +
  real-namelist + ET.parse path on an actual authored deck.
- Confirmed this specific deck has no `themeOverride` or other
  `*theme*`-named entries that could confuse the theme1/theme2 filter.
- Remaining open item: a deck where theme1 and theme2 disagree on colors
  (SHELFBEAUTY's two themes match; DEMERT's two themes also match) is still
  unverified — all real multi-theme decks seen so far happen to have
  identical color schemes across themes.

---

# Deck 6 — Olay (P&G) "Premium BW and HBL / CGI Assets Visual Boards" (2026-08-21)

Source: `OlayPremiumBWandHBL_CGI_VisualBoards_CreativeDeck.pptx`, 746.7MB,
34 slides. Produced by **Global Image Factory** (their logo is `image3.png` on
slides 1 and 34) — same agency as the Global ImAIge deck.

Output: `out/olay/index.html` + `out/olay/assets/`. **746.7MB -> 36.5MB**
(html 0.14 + images 5.9 + video 30.5). Build is four scripts in
`phase_1c/olay/`: `model.py` -> `assets.py` -> `render.py` -> `validate.py`,
with `roles.py` as the operator-tagged manifest and `capture.py` for QA.

## What the intake numbers missed

The deck was handed over as "34 slides, 194 shapes, 58 runs, 11 offcanvas,
4,874 chars live text, 17 slides with text, 17 flattened images, zero
animation, explicit_color_override_pct 0.0". Verified against the file:

- **31 embedded videos, ~470MB, across 14 slides** — absent from the intake
  entirely, and 63% of the file. Easy to miss: `videoFile` is in the `a:`
  namespace, not `p:`, so a `p:videoFile` lookup silently finds nothing.
- **18 slides carry live text, not 17** (s34 is "Thank You", 9 chars).
- **"17 flattened images" is wrong in kind.** No slide is a flattened render.
  16 slides have no live text but are compositions of individually croppable
  tiles; s12 carries three videos. The genuinely rasterised text is **9 banner
  assets** in an italic display serif (a third typeface, raster-only) — kept as
  images by decision.
- **`explicit_color_override_pct = 0.0` is true but misleading.** It is
  measured at run level, and no run overrides colour. The deck's colour still
  comes almost entirely from the theme — via 24 per-slide `<p:bg>` fills and 33
  `<p:style>` fillRef/fontRef blocks. See LEARNINGS rule 19.
- **Zero animation confirmed**, with the reason: 14 slides have `<p:timing>`,
  but every node is media playback (31 `cMediaNode`), no `animEffect`.
- **194 vs 184 shapes** is the design-locker split (LEARNINGS rule 18).

## Deck-level classification — the spec'd heuristic misfires here

`PHASE_1C_ARCHITECTURE.md` open question 1 asks whether the classifier sorts
the known decks cleanly. **It does not sort this one.** The spec'd heuristic
keys on explicit size overrides + animation count; Olay reads 0.0 and 0, so it
returns **corporate** -> "spot-check only". The deck is structurally
**creative**: *zero placeholders in all 34 slides* (every text shape is a plain
TextBox/Rectangle, `ph=None`), a per-slide background on 24 slides, 56 shapes
crossing the canvas edge as intentional bleed, and a stock untouched Office
theme. Routing it to spot-check is exactly the "trusted instead of checked"
failure the safeguard section warns about.

**Recommendation: add placeholder-usage ratio as a classifier signal.** It is a
far stronger discriminator than either current input — a corporate deck uses
the master's placeholders, a hand-built canvas deck does not — and it is one
cheap count per slide. Still advisory, still never authoritative.

## Category badge system (decoded)

`image9.png` (11724x885) is a sprite of 7 numbered chips, referenced from 15
slides via 7 distinct `srcRect` crops. Decoded from slide 3's legend by pairing
chip geometry against text geometry, then cross-checked against slides 9 and 10
whose captions name the numbers in prose. Mapping lives in `roles.py`:
1 Abstract elements / 2 Lifestyle / 3 Ambient / 4 Cinematic /
5 Application-in-situ / 6 Sensorial / 7 Group shots.

## Fonts — measured, not guessed

Both source faces are unlicensed here. Every text box carries `<a:spAutoFit/>`,
which turns the file into a metric oracle (LEARNINGS rule 17):

| source | substitute | basis |
|---|---|---|
| Franklin Gothic Book 14pt | **Archivo** `wdth=94`, line-height **1.2121** | measured, 20/20 autofit boxes exact (valid window 93.5-95.0) |
| Boston SemiBold 20pt | **Poppins 600**, line-height **1.2140** | design class only — 52 chars, oracle cannot discriminate. Provisional. |
| Aptos (inherited, 18pt) | **Archivo** `wdth=100` | theme minor-latin; 6 review-sticker runs |

Libre Franklin, the obvious lineage match, is **8.7% too wide** and fails the
oracle. All three classify `matched` -> declared sizes render 1:1, no 1.36x.
Registered in `parse/font_calibration.py` (`MATCHED_METRIC_SUBS`,
`SOURCE_LINE_HEIGHT_RATIOS`, `MATCHED_METRIC_AXES`). Binaries are subset woff2
(Archivo variable 45KB + Poppins 5KB) in `render/fonts/`, exposed through a new
**opt-in** `font_face_css(families=...)` path — the no-argument default still
emits byte-identical CSS, so the P&G baselines are untouched (asserted).

## Shared-layer changes (affect other decks — re-baseline before trusting)

1. `parse/slide.py::_is_design_locker` now requires visual emptiness, not just
   the marker (rule 18). **Verified across all 52 .pptx files in ~/Downloads**
   (`scratchpad/locker_regress.py`, old vs new predicate over every sp/pic):
   only 24 `designElem`-marked shapes exist in the whole corpus, and exactly
   two decks change — Olay (8 recovered) and OldSpice_Destination (2). Both
   recovered sets are solid-filled rectangles, i.e. real content that was being
   dropped. **FrameTag, Global Image Factory and the P&G decks are unaffected
   (0 shapes recovered)**, so existing baselines cannot move. The 18 unit tests
   also pass.
2. `render/fonts.py::font_face_css()` gained an optional `families` argument.
   Default path proven byte-identical.

## Rule 15 deviation (single-DOM dual-build)

Deck Editor v14 compatibility forced it; see LEARNINGS rule 22 for the full
reasoning and the three CSS mechanics it requires. Desktop fidelity is
unchanged from rule 15's spec.

## Verification

`phase_1c/olay/validate.py` — 18 assertions, all passing (editor contract,
rules 1/3/4/5/6/7/8/9/14). LibreOffice + pdftoppm ground truth vs Playwright
capture across all 34 slides: **still slides mean diff 3.79, video slides 9.78**.
Four defects were found by that diff and fixed: missing `p:style` fills,
slide-background alpha compositing, the `z-index`/stacking-context bug, and
three separate mobile-reflow faults.

**CORRECTED 2026-08-21.** An earlier version of this note attributed the
video-slide gap wholly to "LO decoding a first video frame where we correctly
show the authored poster." That was one contributor of three, and stating it as
the explanation was misleading. Decomposed properly, the gap on slides 9 and 10
(15.0 and 14.2, the two worst non-s15 slides) is:
  1. poster-vs-first-frame decode — real, and the only one that is not a divergence;
  2. **deliberate** review-sticker suppression — LibreOffice still draws the teal
     box, which is 2.6% of ground-truth pixels in a high-contrast colour;
  3. the wash-colour defect below — ~22% of each of those two slides rendered
     35/255 too light.
Do not read a ground-truth delta as a single cause without decomposing it; on
these two slides the "obvious" cause accounted for the smallest share.

## Internal review comments suppressed (2026-08-21, after client-deliverable review)

P&G left six internal review notes in the working file — teal boxes, white text,
on slides 9, 10 (x2), 21 (x2) and 22: "Wrong package", "This looks too fake but
like suds & they do well", "Move forward with #5 as is", and "Move forward if
feedback is able to be incorporated" (x3). 240 of the deck's 4,874 characters.
**Authored in the source; the conversion introduced nothing** (verified by
reading the shapes straight out of the .pptx zip).

Found by treatment, not by matching strings — see LEARNINGS rule 23 for the
five-property signature and why it is trustworthy. Split was 6 vs 22 with no
overlap on any property. No sticker "furniture" (leader lines, pointers) exists,
and nothing else in the deck is teal, so removal leaves nothing orphaned.

Implementation is deliberately two-stage:
- `model.py::_is_review_sticker` **flags** (`review_sticker: true`); the shape
  stays in `model.json`, auditable and reversible.
- `roles.py::SUPPRESS_REVIEW_STICKERS = True` is the per-deck **opt-in** that
  makes `render.py` skip them, and it logs each one it drops.

That split follows the advisory/authoritative rule this repo already applies to
the deck classifier. Flip the flag to `False` to get the fidelity-complete
render back — useful when handing something to the deck's author rather than
their client.

`validate.py` pins the outcome: exact match set (6, by slide + shape name), no
sticker text anywhere in the output, 22 authored blocks still unflagged, and a
deliverable total of exactly **4,634** characters. A deck revision that changes
the set fails the build rather than silently re-leaking a comment.

Also swept: **no `ppt/comments/` or `commentAuthors` parts exist**, and the four
`notesSlides` parts contain only page numbers ("9", "12", "23", "3"). These six
shapes were the entire exposure.

Post-suppression ground-truth diff: slides 9/10/21/22 now diverge *more* from
the LibreOffice render (LO still draws the stickers, by design), while the other
30 slides are unchanged — median 3.92.

## Mobile review round (2026-08-21) — three fixes, desktop untouched

Desktop was signed off before this round. Every change lives inside the
`@media (max-width:820px)` block or drops shapes that are invisible on desktop,
and that was **verified by pixel diff**: all 20 non-video slides render
byte-for-byte identically to the pre-change build (the 5 that differ are all
video slides, differing only by decode frame timing).

**1. Backgrounds boxed instead of full-bleed** — slides 2 (a `<p:bg>` blipFill),
and 3, 8, 17, 24, 33 (a full-canvas `<p:pic>` at the bottom of the stack), plus
the split panel rects on 4-7 and the full-slide tints on 9-10. New `backdrop`
classification in `model.py`; on mobile these leave the flow and paint as a
full-bleed layer. See LEARNINGS rule 24.

**2. "Creative Brief" appearing twice** — slide 33 only, and the cause was not a
stray banner: **slide 33 is slide 2 duplicated with an opaque full-canvas image
(`image4.png`) painted over it at z=4**, with the real slide-33 content on top.
Desktop hides the old slide by z-order alone; the mobile reflow resurrected the
banner, both text columns and the product shot. Fixed by the occlusion rule
(rule 24), gated by `roles.py::SUPPRESS_OCCLUDED_SHAPES`.

*This supersedes the earlier "reproduce slides 2 and 33 verbatim" decision*, which
was taken before the duplication was known to be occluded. Slide 2 still shows
the brief in full; slide 33 now shows what it actually renders. Cost: 583 buried
characters. Deliverable text is now **4,051** (4,874 authored - 240 review
stickers - 583 occluded). Flip the flag to `False` to restore them.

**3. Renders slides unreadable** — slides 4-7. Tiles had a width-based flex basis
that resolved to 167x660px, taller than the viewport, so only a magnified sliver
showed. Now sized by height (`min(58svh,520px)`, width from `aspect-ratio`), with
the section banner lifted out of the scroll row and the split background restored.
Three whole renders per screen, scrolling right. See LEARNINGS rule 25.

`validate.py` grew 9 assertions covering both rules (occluded set pinned by slide
+ shape, "Creative Brief" appears exactly once deck-wide, backdrop slide list,
the `aspect-ratio: auto` guard, and the height-based strip sizing).

## GIF logo report + mobile spacing round (2026-08-21)

Reported as the Global Image Factory logo colliding with the "Creative Brief"
heading. **Only two GIF logo placements exist in the deck** — slides 1 and 34,
identical geometry (`image3.png`, 9.89% x 6.45%, top-right on the desktop
canvas, no crop, aspect 2.725 matching the asset exactly). Neither is on slide 2,
and at 390px both render complete and undistorted at 123x45px. Nothing was
overlapping.

The real cause was **section height**: the cover reflowed to 507px on an 844px
viewport, so slide 2 scrolled into the same screen and the cover's footer logo
appeared next to slide 2's heading. Seven sections were shorter than the
viewport (1, 4-7, 18, 34). Fixed with `min-height:100svh` + `align-content:center`
on the mobile canvas — see LEARNINGS rule 26.

Two further defects the same audit caught:
- **Strip banner overlapped its tiles by 11px** on slides 4-7 — a regression from
  the previous round. The lifted banner was sized by width (62%), so its height
  floated to 73px while the canvas `padding-top` clearing it was a fixed 78px.
  Now sized by height (46px) so its footprint is predictable.
- **Logo butted against the title** on slides 1 and 34 (14px, the text box's own
  padding). Added `margin-top:12px` on `.sh.im.logo`.

`capture.py` now runs a **mobile layout audit** on every capture and hard-fails
on: any section shorter than the viewport, any two non-backdrop shapes
overlapping in both axes, or `document.scrollWidth` exceeding the viewport.
That is the check that would have caught all three of these before review.

Desktop re-verified pixel-identical (0.00000 across all non-video slides).

## Renders ground fix (2026-08-21) — slides 4-7

The two-tone ground covered only the first 390px of a 956px horizontal strip.
Cause was dimensional, not positional: percentage widths on the absolutely-
positioned panels resolve against the canvas **padding box** (the 390px
viewport), not `scrollWidth`. Renders 5-7 had no ground at all, and because
abspos children of a scroll container scroll with the content, the panels also
slid off-screen. See LEARNINGS rule 27.

Kept the split rather than flattening to one colour, on evidence: no tile
straddles the boundary on desktop (tiles end at 53.3% and resume at 55.0%, the
split at 55%), so it is a deliberate 4-renders-vs-3 grouping, and the tint is
the only thing distinguishing s4 `#C7B7C5` / s5 `#B1BFDB` / s6 `#F6D3D9` /
s7 `#D99088`.

`render.py::strip_ground_metrics` maps each ground panel to the span of tiles it
covers on the DESKTOP canvas and emits that span as `--bl-ar/--bl-px/--bw-ar/
--bw-px`. Tile height is published once as `--th: min(58svh,520px)` and the
panels size off the same variable, so ground and tiles cannot drift apart.
Group assignment is derived from source geometry, not hard-coded, so it works
for any split-ground contact sheet.

Measured after: ground spans 0..956 of 956 with a 0px seam, full 844px height,
boundary at 553 — between render 4 (ends 549) and render 5 (starts 557).
`capture.py` now also asserts the ground is continuous across every strip slide.
Desktop re-verified at 0.00000.

## KNOWN DEFECT (open) — two fills resolve to the wrong shade on slides 9 and 10

Found 2026-08-21 while fixing the same bug in deck 7, by auditing backwards.
**Not fixed: deliberate decision not to re-ship Olay for a shade error on 2 of
34 slides. Fix it with the next Olay change.**

`Rectangle 9` (slide 9) and `Rectangle 10` (slide 10) — the full-canvas wash —
are `<a:schemeClr val="bg1"><a:lumMod val="85000"/><a:alpha val="90000"/>`.
`phase_1c/olay/model.py::_solid()` reads the scheme name and ignores the
transform, so it resolves `#FFFFFF` where the correct value is `#D9D9D9`.
Composited over the `#7030A0` slide ground that ships `rgb(241,234,246)` instead
of `rgb(206,200,211)` — **35/255 too light**, across **~22% of each slide's
surface** (21.6% of pixels in our build, 23.4% in ground truth).

Confirmed independently: LibreOffice renders those slides at exactly
`(206,200,211)`, the correct composite, to the digit.

**Scope is exactly 2 fills.** All 43 colours the Olay builder consumed were
re-resolved through `ColorResolver`; 41 match. **No text run is affected** — no
Olay run declares a colour, and the six review stickers took the `p:style` path
which already went through `ColorResolver`. The deck's other `shade`/`satMod`
values sit in `lnRef`/`effectLst`, which that build never rendered.

The fix is the one deck 7 now carries: route `_solid()` through `ColorResolver`
with a `SCHEME_ALIASES`-expanded theme dict. Generalised as LEARNINGS rule 28.
Re-shipping also means re-render, re-capture, desktop + mobile re-verify, and
regenerating the 50 MB embedded file.

## Single self-contained embedded file (2026-08-21)

`out/olay/olay_deck_embedded.html` — **50.10 MB** (50,097,918 bytes), built by
`phase_1c/olay/embed.py` from the folder build. All 34 slides are static markup;
nothing is constructed at runtime.

Payload floor is the assets: 36.37 MB raw -> 48.49 MB base64, of which **video is
40.6 MB** and images 7.9 MB. There is no compressing that away inside a single
file — if a lighter artifact is ever needed, dropping video for poster stills is
the only lever that moves the number materially.

**Duplication.** "Literal `src` on every element" and "each asset inlined once"
cannot both hold for an asset referenced from more than one DOM site. Measured
cost was 3.15 MB raw. 31 of the 38 repeats were avoidable: the folder build
inlines each video poster twice, as the `<img class="poster">` underlay AND as
the `<video poster>` attribute. The underlay is the layer rule 4 requires, so
the attribute is dropped in the embedded build — saves ~3 MB, is still
`src`-compliant, and pixel parity proves it changes nothing on screen. The
remaining 8 shared assets (badge sprite at 36 sites, section art on two slides
each) are genuinely the same bytes at different DOM sites; deduping them would
need `<picture>`/CSS indirection, which the brief rules out.

**Verified with scripts disabled** (`verify_embed.py`, JS-disabled context —
the editor's actual view): 34 `section.slide`, ids sequential `s1..s34`, rail
labels sequential, **138/138 `<img>` and 31/31 `<video>` carry a literal
`data:` src**, zero `srcset`/`<picture>`/`<source>`, live text exactly **4,051**
characters, review stickers and the occluded slide-2 copy both absent, "Creative
Brief" present exactly once.

**Pixel parity vs the folder build** (`parity.py`, videos pinned to t=0 in both
so decode timing does not dominate): **1440px 34/34 identical**; **390px 33/34
identical**, the one exception being slide 22 at 0.0172 mean delta — a single
row (y=994, the bottom edge of the second video) covering 0.08% of pixels. Box
geometry is identical to the fraction of a pixel in both builds, so that row is
a raster blend on the video's last line, not a layout difference.

## Mobile round 2 (2026-08-22) — fill, merge, carousels

Desktop signed off before this round and **re-verified pixel-identical across
all 34 slides (max diff 0.00000)**. Everything below is inside the mobile media
query or is markup that desktop hides.

**Stretch decision — REVISED 2026-08-22 after phone review.**
`roles.KEEP_AUTHORED_STRETCH = False`. Desktop keeps the authored stretch as
signed off; **mobile uses the true source aspect.** Reviewed on a real phone the
1.56x horizontal stretch is worse at full-screen scale than the desktop/mobile
divergence — a product blown up to fill the screen is the wrong place to
reproduce it. Fill by scaling, never by distorting (rule 29).

**1. Fill (rule 29).** Plates were 21.8-43.5% of the section with 238-330px dead
above and below, because the reflow sized images from the authored 16:9 box.
Now sized to the section at true source aspect: **39.3-82.9%, aspect exact on
every cell** (s7 went 22.2% -> 82.9%). The intermediate stretched build measured
28.6-64.6%; unstretching bought the rest. Two traps recorded in the rule:
`height:100% + aspect-ratio` silently stretches rather than fits (it inflated an
early measurement to a fake 76.3%), and a crop frame without `overflow:hidden`
shows its neighbours.

**2. Divider merge (rule 30).** Slides 4/14/24 collapse to zero height and
overlay their destination name on 5/15/25. **The sections are not removed.**
Measured after: 31 visible screens, **34 sections / 34 rail entries / 34
`data-slide` / 34 `.L > .t`**, live text unchanged at 2,058. The merged title
carries its own slide's white ground — the destination names are
`bg1+lumMod50%` grey, right on the divider's white slide and invisible over a
photo; recolouring would be inventing, reproducing its ground is not.

**3. Carousels (rule 31).** All 24 plates are ONE image shape, so a carousel can
only come from splitting a photograph — done with CSS crop windows over the same
asset (the Olay badge-sprite technique), so no image bytes are created and each
slide still has one asset and one URL. `units.py` derives the windows by
measurement, not tagging: **15 slides split into 2-3 units, 9 correctly refuse**
(an unfolded box dieline is one connected object; STICK+BOX and GROUP SHOT
overlap and a cut would run through product).

**The probe that lied.** The first detector tested transparency (`alpha > 8`)
and reported *zero* splittable slides deck-wide. That looked like a clean
negative and was a broken probe: RGBA product shots are separated by a soft
ground shadow (alpha spans the full width — threshold `> 200` to isolate product
from shadow), and the label artworks are RGB with no alpha at all (measure
distance from the corner background instead). Recorded in rule 31: a detector
returning "none anywhere" on a deck that visibly has them is a broken probe, not
a finding.

`validate.py` grew 9 assertions covering all three, including that no unit cell
references an asset outside the manifest (i.e. nothing was sliced into new
files) and that the merge left the section count untouched.

## Mobile round 3 (2026-08-22) — unstretch + merged-header fix

Desktop re-verified **pixel-identical, max diff 0.00000 across all 34**.

**Unstretch.** `KEEP_AUTHORED_STRETCH = False` for mobile only. Fill went
39.3-82.9% (from 28.6-64.6% stretched), aspect exact on every cell.

**Merged headers were clipped, and the cause was not the padding.** The title
shape carries an inline PERCENTAGE height from the desktop canvas; rule 30
collapses the divider section to zero, so that percentage resolved to 0. The box
became padding-only (44px + 18px, 0px content), the glyphs rendered outside it
and were clipped. `.sh { height:auto }` did not reach it because the specific
merged-title rule overrode position/width without restating height. Fixed by
restating `height:auto` — recorded in rule 32 as a general consequence of
collapsing any container.

**Legibility resolved by carrying the ground, not by recolouring.** Options
weighed were scrim / drop shadow / recolour. Chose the scrim, sourced from the
merged slide's OWN resolved background: it preserves the authored `#808080`
exactly, and the scrim is not invented — it is the ground the author already
paired with that text. Drop shadow was rejected because it adds edge separation
rather than contrast and fails precisely for mid-tone text; recolour was
rejected as an editorial change (rules 12/14).

**REVERSED BY SEAN, 2026-08-22.** Originally closed as "leave as authored" on
the reasoning that the pipeline had not moved that text. Sean reviewed it on a
phone and reversed the call: a deck that cannot be read on the device it ships
to has not been converted successfully, regardless of who placed the text. The
concept blocks on 5/15/25 now carry a mobile-only scrim. Desktop keeps the
authored presentation, verified pixel-identical. Rule 32's scope note was
rewritten to match — it now covers author-placed text that the reflow scales
down, not only text the pipeline relocates.

## Mobile round 4 (2026-08-22) — slide 3 (variant matrix)

Desktop re-verified **pixel-identical, max diff 0.00000**.

- **Cards rendered in Times.** `build_cards()` emits markup the pipeline
  generates rather than reads from a run, and `body` declared no family, so it
  fell through to the browser default in an otherwise Aptos deck. Fixed as
  INHERITANCE, not a per-slide font: the deck stack is declared once as
  `--deck-font` on `:root` and applied to `body`; authored runs still override
  inline. Mobile type scale likewise shared (`--ms-*`) so the cards are not
  their own scale — card body now measures 15.2px / lh 19.76px, identical to
  `#s2 .cbi`.
- **Grey block down the left edge** was the authored 16.5% desktop rail. Only
  partial-width backdrop rects are dropped on a transposed slide; the
  full-canvas rect IS the ground and stays. A first attempt hid both and exposed
  slide 3's authored green `#4EA72E` underneath — corrected, and the width test
  is measured (`w < 97%`), not a slide number.
- **Overflowed the viewport by 67px.** Closed by spacing alone, type untouched
  at deck body size. Fits one screen at >=390px (iPhone 12 through 15 Pro Max);
  **scrolls 8px at 375, 40px at 360, 252px on an SE**, because narrower
  viewports wrap the copy onto more lines. Options put to Sean: accept, or make
  the cards a horizontal swipe (robust at any width, reuses the deck's carousel
  idiom). Not resolved yet.
- **Title ellipse became a plain header** at the top of the section (rule 33).
  The ellipse geometry is dropped; the red fill is NOT, because the title text
  is `#FFFFFF` — 7.42:1 on red, 1.00:1 (invisible) on the white ground it would
  otherwise land on. Same reasoning as rule 32: drop the shape, carry the ground.

## Embedded single file — Old Spice (2026-08-22)

`out/oldspice/oldspice_deck_embedded.html` — **12.53 MB**, built by
`phase_1c/oldspice/embed.py`.

**Dedupe was necessary and partial.** The document holds 78 image references
over 29 unique assets, because the carousel renders each product unit as its own
crop of the same photo. Inlining naively: **18.29 MB** of base64 against
**6.78 MB** of distinct bytes — 2.70x.

An `<img src="data:...">` cannot share bytes with anything: each attribute
carries its own copy. A CSS custom property can be referenced by any number of
rules while appearing once. So carousel cells were converted from an oversized
`<img>` to `background-image: var(--aN)`. The conversion is exact, not
approximate — for a crop with visible fraction vw:

    img         width = 100/vw %        left = -l/vw * 100 %
    background  background-size = 100/vw %   background-position = l/(l+r) %

since a percentage background-position places the image's p% point at the
container's p% point, giving p = -left% / (width% - 100).

**Solo cells were deliberately NOT converted.** A solo cell plus the desktop
`<img>` is two copies either way, so converting buys no bytes and costs
pixel-parity — an `<img>` and a `background-image` resample differently. Leaving
them as images restored parity on 9 slides at zero size cost.

**Every asset inlines once or twice; 25 of 29 appear twice.** The floor while
`<img>` elements are required:
  - 15 carousel assets: 1 desktop `<img>` + 1 shared CSS property
  - 9 solo assets: 1 desktop `<img>` + 1 cell `<img>`
  - the SVG wordmark: 2 imgs (slides 1 and 34)

Reaching **exactly once** means dropping the desktop `<img>` for the 24 plate
assets and painting them from the shared property too — measured at
**~6.95 MB**, but those assets would then have no `img` element at all. That is
not a violation of "literal src on every img" (the imgs that remain all have
one), and a `<style>` block survives a DOMParser round-trip intact — but it
would remove them from any editor media enumeration. **Raised with Sean, not
decided unilaterally.**

**Verified with scripts disabled:** 34 `section.slide`, ids `s1..s34`, rail
labels sequential, 39/39 imgs carry a literal `data:` src, zero
`srcset`/`<picture>`/`<source>`, occluded duplicate still suppressed, table +
3 cards + 48 crop cells present.

**Pixel parity vs the folder build:** desktop **34/34 identical**; mobile
**16/31 identical**, the 15 carousel slides differing by mean 1.2-4.0. Diagnosed
rather than assumed: uncropped cells show no shift at all and cropped cells at
most 1px, with 27-40% of differing pixels sitting on image edges against an 11%
edge density — i.e. `<img>` vs `background-image` resampling, not geometry.

## Known limitations

- `hdphoto1/2.wdp` (JPEG XR effect caches on s1/s34) are not rendered. They are
  alternates of rasters already emitted; logged as known-unbound in the
  coverage map rather than dropped silently.
- Slides 2 and 33 duplicate two text boxes verbatim. Reproduced as authored per
  rule 14; flagged to the client as an authoring issue, not fixed in the build.
- Boston SemiBold pairing is provisional (see above).
- On mobile, slide 3's seven legend badges reflow to a chip row at the end of
  the slide rather than pairing with their legend lines — the source positions
  them absolutely against two text columns, so pairing needs per-badge tagging.
- Mobile backdrops use `object-fit: cover`, which discards the authored
  `srcRect` framing on those few full-canvas images in exchange for a true
  full-bleed. Deliberate, and mobile-only; desktop keeps the authored crop.


---

# Deck 7 — Old Spice "Destination Theme Product Series Concepts" (2026-08-21)

Source: `OldSpice_Destination_ProductSeries_Variants_CreativeDeck_R1.pptx`,
331.4 MB, 34 slides, 960x540pt. Output `out/oldspice/`, built by
`phase_1c/oldspice/` (model -> assets -> render -> validate, + capture, roles).
**331.4 MB -> 5.23 MB** (html 0.14 + assets 5.09). No video.

## Shape of the deck

The sparsest in the set at 2.35 shapes/slide, and the most templated: three
identical 9-slide destination series (Maldives / Sao Paulo-Rio / Sedona) with
the same eight product labels each. Six archetypes, one of which is 24 slides:

| archetype | slides | existing `archetype.py` label |
|---|---|---|
| product plate | 24 | `photo_with_caption` |
| key visual | 5, 15, 25 | `generic` |
| destination divider | 4, 14, 24 | `title_or_cover` |
| cover / close | 1, 34 | `generic` |
| brief | 2 | `generic` |
| variant matrix | 3 | `title_or_cover` (wrong — the table yields no items) |

**Placeholder-usage ratio 53.3%** (24/45 text-capable shapes; 20/34 slides use
at least one). Olay was 0.0%. Recorded only — the deck-level classifier signal
set stays frozen through deck 9 as instructed.

## Signal reconciliation (operator tooling vs this pass)

Everything matched exactly — n_slides, total_runs 92, tab_positioned_runs 0,
explicit_size_override 71.74% (66/92), explicit_color_override **100.0%
(92/92)**, 2 typefaces, 0 animated. Two needed comment:

- `total_shapes` 80 = **76 rendered + 4 designElem lockers**. Not a conflict.
- `offcanvas_shapes` 3 is the known left-only bug. True figure: **16 distinct
  shapes** crossing an edge (28 edge-crossings; a shape crossing two edges
  counts twice — an earlier draft of this note said 28 shapes, which was wrong).
  Left 3 / right 7 / top 9 / bottom 9. **13 shapes invisible to the tooling.**
  All 16 are pictures; no text crosses an edge, so nothing risks being clipped
  unreadable. Overhangs are systematic per series: 10/20/30 top 90pt (16.6%),
  13/23/33 top 71pt + right 45pt, 27 right 80pt, 7/17 left 27pt + right 36pt.

`explicit_color_override_pct` of 100.0 is the mirror of Olay's 0.0: text colour
here never touches the theme, so the resolver is not load-bearing for type —
but it IS load-bearing for fills, see the lumMod bug below.

## Fonts — DIN Pro Condensed

Fixed as **key normalization**, not a new table entry:
`font_calibration.normalize_typeface()` strips foundry/release tokens
(Pro/Std/LT/MT/...) as whole tokens before any lookup, so "DIN Pro Condensed"
reaches the existing `din condensed` entry. Generalises for free — "Helvetica
LT Std" now resolves to `helvetica` (web) — while "Proxima Nova" correctly
keeps its "Pro". Without it the face fell to `cross` and **1.36x would have
fired**: 36pt->48.96, 28pt->38.1, 24pt->32.6. Rule 10's exact failure.

**Barlow Condensed vs Big Shoulders: the oracle cannot discriminate them, and
that is the honest answer.** The only width evidence was slide 1's 0.421 em
advance, and **all three `<a:spAutoFit/>` frames carry `wrap="none"`** — text
overflows freely, so box width constrains nothing. What survives is the
line-height ratio **1.2143** (two 28pt frames at h=41.2pt, corroborated by a
third at the inherited size: 21.9/1.2143 = 18.03pt, independently confirming
the master's 18pt default). Both candidates have an identical natural ratio of
1.2000, so both need the same override.

They are not interchangeable though: Big Shoulders' caps are **14% taller**
(cap 0.800 / x-ht 0.600 vs Barlow 700's 0.700 / 0.514), and this deck is 41
bold ALL-CAPS runs where cap height sets apparent size. Chose **Barlow
Condensed 700** because `BUNDLED_FALLBACKS` already maps `din condensed` to it
and published DIN cap heights sit near 0.72 — a reference value, not a
measurement of this face. `fonts.py` records the opposite argument (Big
Shoulders was picked for SHELFBEAUTY because it matches DIN's flat-topped "A").
One-line swap; marked provisional in `MATCHED_METRIC_SUBS`.

## Four bugs the build surfaced (all found by measurement, not by eye)

1. **Table body text was invisible, not missing.** Cells use
   `bg1 + lumMod 50%`; the Olay-derived `_solid()` read the scheme name and
   ignored the transform, resolving mid-grey to white — white text on white
   cells. The deck has **63 lumMod uses**, so this was pervasive, not local.
   Fixed by routing fills through `ColorResolver`, which implements rule 13.
   Note ColorResolver needs an alias-expanded theme dict (it does not know
   bg1/tx1 -> lt1/dk1 the way `Theme.resolve` does); expanded locally rather
   than changing the shared resolver.
2. **Slide 3's title lost its red fill and its geometry.** Text shapes never
   emitted a background, and `prstGeom` was assumed rect — Olay was 100% rect,
   this deck has one `ellipse`. Both now honoured.
3. **Bullets were dropped.** 12 bulleted paragraphs, all in the table
   (`<a:buChar char="•">`). Olay had none so the model never read them; a list
   was flattening into run-on lines.
4. **Mobile slide 3 looked empty.** Two causes, neither the cards: the 16.5%
   grey band was being stretched full-width (the full-bleed override must apply
   to IMAGE backdrops only), and `.card` is static so it painted *beneath* the
   positioned backdrop despite every value being in the DOM.

## Carried-forward rules

- **P&G review stickers: 0 matches**, and cleanly — **no shape in this deck
  carries `<p:style>` at all**, so the signature has no surface to fire on. No
  false positives across 43 text frames.
- **Occlusion: 2 slides, 542 chars.** Slides 15 and 25 are the Maldives key
  visual duplicated, covered by an opaque full-canvas image (both measured
  100.000% opaque) with the new destination's copy on top — the Olay slide-33
  pattern exactly. Buried Maldives text sat under the Sao Paulo and Sedona
  slides. **Verified after build: neither slide reveals it** (desktop matches
  ground truth; the string appears once, on slide 5, where it belongs).
- Deliverable text **2,058** chars (2,600 authored - 542 occluded).

## Editor hooks, matched to the text distribution

28 of 34 slides are single-line labels, so this deck does NOT get Olay-style
body copy. `.L > .t` on **all 34** (every slide has exactly one label/title);
`.sl` on 1 (slide 1's "CONCEPTS"); body hooks on **five** slides only — 2
(311), 3 (458, per table cell), 5 (271), 15 (403), 25 (219). Note the intake
summary named three prose slides; 15 and 25 were obscured by the buried
duplicate sitting in their character counts.

## Verification

`validate.py` — 30 assertions, all passing. Desktop vs LibreOffice ground truth
across all 34: **median 4.16, mean 4.40** (Olay still-slides were 3.79). The
worst, s3 at 12.3, is dominated by a deliberate divergence: the source says
`prstGeom prst="ellipse"` and we render an ellipse; LibreOffice draws a
rectangle. Per rule 16 the XML is the authority, so this is LO being wrong, not
us — do not "fix" it toward the screenshot.

Mobile: layout audit clean (no short sections, no overlaps, no horizontal page
scroll). Mobile treatment is deliberately lighter than Olay's because the deck
is sparse — plates overlay their label on the plate (what `archetype.py` says
`photo_with_caption` needs), key visuals use the image as a backdrop, and only
the table is transposed (3 stacked cards; desktop keeps the true table).

## Shared-layer changes

- `parse/font_calibration.py`: `normalize_typeface()` + `din condensed` entries
  in `MATCHED_METRIC_SUBS` / `SOURCE_LINE_HEIGHT_RATIOS`.
- `render/fonts.py`: "Barlow Condensed" added to `_OPTIONAL_FONTS`, reusing the
  binaries already bundled by default rather than shipping a second copy.
- Default `font_face_css()` output unchanged (md5 `e68750697422`), 18/18 tests
  pass, so P&G baselines are untouched.

## Mobile round 2 (2026-08-22) — fill, merge, carousels

Desktop signed off before this round and **re-verified pixel-identical across
all 34 slides (max diff 0.00000)**. Everything below is inside the mobile media
query or is markup that desktop hides.

**Stretch decision — REVISED 2026-08-22 after phone review.**
`roles.KEEP_AUTHORED_STRETCH = False`. Desktop keeps the authored stretch as
signed off; **mobile uses the true source aspect.** Reviewed on a real phone the
1.56x horizontal stretch is worse at full-screen scale than the desktop/mobile
divergence — a product blown up to fill the screen is the wrong place to
reproduce it. Fill by scaling, never by distorting (rule 29).

**1. Fill (rule 29).** Plates were 21.8-43.5% of the section with 238-330px dead
above and below, because the reflow sized images from the authored 16:9 box.
Now sized to the section at true source aspect: **39.3-82.9%, aspect exact on
every cell** (s7 went 22.2% -> 82.9%). The intermediate stretched build measured
28.6-64.6%; unstretching bought the rest. Two traps recorded in the rule:
`height:100% + aspect-ratio` silently stretches rather than fits (it inflated an
early measurement to a fake 76.3%), and a crop frame without `overflow:hidden`
shows its neighbours.

**2. Divider merge (rule 30).** Slides 4/14/24 collapse to zero height and
overlay their destination name on 5/15/25. **The sections are not removed.**
Measured after: 31 visible screens, **34 sections / 34 rail entries / 34
`data-slide` / 34 `.L > .t`**, live text unchanged at 2,058. The merged title
carries its own slide's white ground — the destination names are
`bg1+lumMod50%` grey, right on the divider's white slide and invisible over a
photo; recolouring would be inventing, reproducing its ground is not.

**3. Carousels (rule 31).** All 24 plates are ONE image shape, so a carousel can
only come from splitting a photograph — done with CSS crop windows over the same
asset (the Olay badge-sprite technique), so no image bytes are created and each
slide still has one asset and one URL. `units.py` derives the windows by
measurement, not tagging: **15 slides split into 2-3 units, 9 correctly refuse**
(an unfolded box dieline is one connected object; STICK+BOX and GROUP SHOT
overlap and a cut would run through product).

**The probe that lied.** The first detector tested transparency (`alpha > 8`)
and reported *zero* splittable slides deck-wide. That looked like a clean
negative and was a broken probe: RGBA product shots are separated by a soft
ground shadow (alpha spans the full width — threshold `> 200` to isolate product
from shadow), and the label artworks are RGB with no alpha at all (measure
distance from the corner background instead). Recorded in rule 31: a detector
returning "none anywhere" on a deck that visibly has them is a broken probe, not
a finding.

`validate.py` grew 9 assertions covering all three, including that no unit cell
references an asset outside the manifest (i.e. nothing was sliced into new
files) and that the merge left the section count untouched.

## Mobile round 3 (2026-08-22) — unstretch + merged-header fix

Desktop re-verified **pixel-identical, max diff 0.00000 across all 34**.

**Unstretch.** `KEEP_AUTHORED_STRETCH = False` for mobile only. Fill went
39.3-82.9% (from 28.6-64.6% stretched), aspect exact on every cell.

**Merged headers were clipped, and the cause was not the padding.** The title
shape carries an inline PERCENTAGE height from the desktop canvas; rule 30
collapses the divider section to zero, so that percentage resolved to 0. The box
became padding-only (44px + 18px, 0px content), the glyphs rendered outside it
and were clipped. `.sh { height:auto }` did not reach it because the specific
merged-title rule overrode position/width without restating height. Fixed by
restating `height:auto` — recorded in rule 32 as a general consequence of
collapsing any container.

**Legibility resolved by carrying the ground, not by recolouring.** Options
weighed were scrim / drop shadow / recolour. Chose the scrim, sourced from the
merged slide's OWN resolved background: it preserves the authored `#808080`
exactly, and the scrim is not invented — it is the ground the author already
paired with that text. Drop shadow was rejected because it adds edge separation
rather than contrast and fails precisely for mid-tone text; recolour was
rejected as an editorial change (rules 12/14).

**REVERSED BY SEAN, 2026-08-22.** Originally closed as "leave as authored" on
the reasoning that the pipeline had not moved that text. Sean reviewed it on a
phone and reversed the call: a deck that cannot be read on the device it ships
to has not been converted successfully, regardless of who placed the text. The
concept blocks on 5/15/25 now carry a mobile-only scrim. Desktop keeps the
authored presentation, verified pixel-identical. Rule 32's scope note was
rewritten to match — it now covers author-placed text that the reflow scales
down, not only text the pipeline relocates.

## Mobile round 4 (2026-08-22) — slide 3 (variant matrix)

Desktop re-verified **pixel-identical, max diff 0.00000**.

- **Cards rendered in Times.** `build_cards()` emits markup the pipeline
  generates rather than reads from a run, and `body` declared no family, so it
  fell through to the browser default in an otherwise Aptos deck. Fixed as
  INHERITANCE, not a per-slide font: the deck stack is declared once as
  `--deck-font` on `:root` and applied to `body`; authored runs still override
  inline. Mobile type scale likewise shared (`--ms-*`) so the cards are not
  their own scale — card body now measures 15.2px / lh 19.76px, identical to
  `#s2 .cbi`.
- **Grey block down the left edge** was the authored 16.5% desktop rail. Only
  partial-width backdrop rects are dropped on a transposed slide; the
  full-canvas rect IS the ground and stays. A first attempt hid both and exposed
  slide 3's authored green `#4EA72E` underneath — corrected, and the width test
  is measured (`w < 97%`), not a slide number.
- **Overflowed the viewport by 67px.** Closed by spacing alone, type untouched
  at deck body size. Fits one screen at >=390px (iPhone 12 through 15 Pro Max);
  **scrolls 8px at 375, 40px at 360, 252px on an SE**, because narrower
  viewports wrap the copy onto more lines. Options put to Sean: accept, or make
  the cards a horizontal swipe (robust at any width, reuses the deck's carousel
  idiom). Not resolved yet.
- **Title ellipse became a plain header** at the top of the section (rule 33).
  The ellipse geometry is dropped; the red fill is NOT, because the title text
  is `#FFFFFF` — 7.42:1 on red, 1.00:1 (invisible) on the white ground it would
  otherwise land on. Same reasoning as rule 32: drop the shape, carry the ground.

## Embedded single file — Old Spice (2026-08-22)

`out/oldspice/oldspice_deck_embedded.html` — **12.53 MB**, built by
`phase_1c/oldspice/embed.py`.

**Dedupe was necessary and partial.** The document holds 78 image references
over 29 unique assets, because the carousel renders each product unit as its own
crop of the same photo. Inlining naively: **18.29 MB** of base64 against
**6.78 MB** of distinct bytes — 2.70x.

An `<img src="data:...">` cannot share bytes with anything: each attribute
carries its own copy. A CSS custom property can be referenced by any number of
rules while appearing once. So carousel cells were converted from an oversized
`<img>` to `background-image: var(--aN)`. The conversion is exact, not
approximate — for a crop with visible fraction vw:

    img         width = 100/vw %        left = -l/vw * 100 %
    background  background-size = 100/vw %   background-position = l/(l+r) %

since a percentage background-position places the image's p% point at the
container's p% point, giving p = -left% / (width% - 100).

**Solo cells were deliberately NOT converted.** A solo cell plus the desktop
`<img>` is two copies either way, so converting buys no bytes and costs
pixel-parity — an `<img>` and a `background-image` resample differently. Leaving
them as images restored parity on 9 slides at zero size cost.

**Every asset inlines once or twice; 25 of 29 appear twice.** The floor while
`<img>` elements are required:
  - 15 carousel assets: 1 desktop `<img>` + 1 shared CSS property
  - 9 solo assets: 1 desktop `<img>` + 1 cell `<img>`
  - the SVG wordmark: 2 imgs (slides 1 and 34)

Reaching **exactly once** means dropping the desktop `<img>` for the 24 plate
assets and painting them from the shared property too — measured at
**~6.95 MB**, but those assets would then have no `img` element at all. That is
not a violation of "literal src on every img" (the imgs that remain all have
one), and a `<style>` block survives a DOMParser round-trip intact — but it
would remove them from any editor media enumeration. **Raised with Sean, not
decided unilaterally.**

**Verified with scripts disabled:** 34 `section.slide`, ids `s1..s34`, rail
labels sequential, 39/39 imgs carry a literal `data:` src, zero
`srcset`/`<picture>`/`<source>`, occluded duplicate still suppressed, table +
3 cards + 48 crop cells present.

**Pixel parity vs the folder build:** desktop **34/34 identical**; mobile
**16/31 identical**, the 15 carousel slides differing by mean 1.2-4.0. Diagnosed
rather than assumed: uncropped cells show no shift at all and cropped cells at
most 1px, with 27-40% of differing pixels sitting on image edges against an 11%
edge density — i.e. `<img>` vs `background-image` resampling, not geometry.

## Known limitations

- The two deck builders (`phase_1c/olay/`, `phase_1c/oldspice/`) now share
  roughly 80% of their code. Factoring them is the obvious next move, but it
  should wait for deck 8 so the shared shape is chosen from three examples
  rather than two — same principle as the deferred template auto-detection.
- ~~OPEN: the "KEY VISUAL" label does not read on the mobile scrim.~~
  **RESOLVED 2026-08-22** with a second, light ground behind the label alone
  (Sean approved departing from the single-scrim brief). Both authored colours
  now clear their thresholds on mobile: red `#AF000F` **7.42:1** on a white chip
  (36pt bold needs 3:1), white body **9.8-10.7:1** on the dark scrim (needs
  4.5:1). Neither colour was touched. The light ground shrink-wraps the label
  into a chip rather than splitting the card into two full-width tones — a hard
  horizontal seam reads as a rendering fault, a chip reads as an eyebrow tag.
- Mobile carousels duplicate the asset reference per unit. Harmless for the
  folder build (one URL, browser-cached) but an embedded single-file build would
  inline those bytes per cell — dedupe there before shipping one for this deck.
- No embedded single-file build produced for this deck (not requested). It
  would be ~7 MB, since there is no video.

---

# HenHouse Market (deck 8)

## Desktop verification — what was and was not checked (2026-08-23)

**Correcting a claim made repeatedly during the mobile passes.** Every mobile
round reported desktop as "pixel-identical", and that phrasing was wrong in a
way worth recording rather than quietly dropping.

What was actually verified: the rebuilt desktop HTML against **the previous
desktop HTML** — flattened `.sh` sequence, class, geometry and span text
compared build-to-build across 52 sections / 164 shapes. That is a genuine and
useful regression check: it proves a mobile change did not disturb desktop.

What was **never** verified until now: desktop against **the source deck**.
Nothing in those passes compared a rendered slide to the PPTX. So a defect
already present in the desktop baseline before mobile work began would survive
every "pixel-identical" check, because both sides of the comparison carried it.

That is exactly what happened. The slide-background alpha defect (LEARNINGS
rule 35) was in the desktop build from the first render, was found during
mobile pass 3, was fixed for mobile only on instruction, and then passed every
subsequent desktop check — because the check was build-to-build. It surfaced
only when the embedded file was opened against the source by eye.

**Rule of thumb going forward:** "pixel-identical" without a named reference is
not a claim. State the reference — `identical to the previous build` is a
regression check; `matches the source` is a fidelity check. They catch
different things and neither substitutes for the other.

## Slide-background alpha (fixed 2026-08-23)

13 slides carry `bg_alpha < 1.0`. `composite()` resolved each against the
master background correctly and emitted `--bg-solid`, but only the mobile
`.canvas` rule consumed it; desktop read the raw `rgba()` and composited
against `section.slide{background:#111}`. Slides 1 and 52 rendered `#1B1C14`
for a `#F6F7F0` cream. Fix: desktop `.canvas` reads `--bg-solid` too. Written
up as LEARNINGS rule 35, with the per-breakpoint assertion added to
`phase_1c/henhouse/validate.py`.

Ground truth: a LibreOffice render of the source (media stripped to 1px
placeholders so a 618 MB deck would convert; backgrounds are solid fills in the
slide XML and survive intact) matches 11 of 13 to <=1/255 across alphas
0.077-0.608. The four slides at alpha 0.32167 (12-15) render `#F2F2F2` in
LibreOffice against our `#F8F8F8`. Unexplained: their `<p:bg>` differs from
slides 37-40 only in the alpha value, both resolve `bg2` -> `lt2` = `#E8E8E8`
over a white master, and the arithmetic is validated exactly at alpha 0.29.
Solving for the ground LibreOffice appears to use gives ~`#F7F7F7` for those
four and ~`#FFFFFF` for the rest, which is not a coherent alternative model —
recorded as a probable LibreOffice quirk, not adopted.

## Mobile scroll feel (2026-08-24)

**Symptom:** one section per drag, no momentum carry.

**Cause:** `section.slide{scroll-snap-stop:always}` was emitted unconditioned.
Per CSS Scroll Snap, `always` forbids the container passing over a snap
position during a scrolling operation, so a fling is forced to target the
nearest snap point. That is a discrete-paging affordance — correct for a wheel
or arrow key, wrong on an inertial surface. Released on mobile only
(`scroll-snap-stop:normal` inside the 820px query); desktop keeps `always`.
`scroll-snap-type`, the `#deck` container, and every height rule are untouched.

**Reference build (Patchology / Global Image Factory) — what it actually does,
after reading the file rather than grepping its CSS.** It does NOT release the
snap container on mobile. At `max-width:767px` it sets `.deck{display:none}`
and shows `#mob-view`, a **separate hand-authored mobile DOM**: `position:fixed;
inset:0; overflow-y:auto`, a flex column of 15 `.mob-section` blocks with
`.mob-img{width:100%;height:auto}` and 3px gaps. There is no snap on mobile
because there is no deck on mobile. Zero `scroll-snap-stop` in the whole file.
Two `<script>` tags, so it is not the zero-script pattern either.

**A dead-consumer defect in that file, worth logging as its own instance.**
The deck element is `<div class="deck" id="deck">` — one element, both
selectors. The queries are:

| query | effect |
|---|---|
| `max-width:767px` | shows `#mob-view`, **hides `.deck`** |
| `max-width:768px` | "Unlock page scroll" — `#deck{scroll-snap-type:none;height:auto;overflow:visible}` |
| `min-width:768px` | hides `#mob-view` |

The unlock block's only live window is **767px < width <= 768px**, where the
deck is still displayed. At every real phone width its target is
`display:none`, so it does nothing. Same family as LEARNINGS rule 20/35: a
correctly-authored rule whose consumer is never live. The tell is identical —
it reads as intentional in review and is inert in the browser. Not fixed here;
it belongs to the Global Image builder, and is recorded so the next person
reading that file for a scroll reference does not take the block at face value
the way this session initially did.

**Method note.** The first pass at this diagnosis extracted the CSS rules and
diffed them without checking which DOM they applied to, and concluded that
Patchology "releases the snap container on mobile". That was wrong. Grepping
declarations answers *what is written*; it does not answer *what is live*. For
any breakpoint question, resolve the selector against the DOM at that width
before drawing a conclusion.


## Diagnostic artefact — `henhouse_DIAGNOSTIC_no-video-bytes_DO-NOT-SHIP.html` (2026-08-24)

**21.03 MB. NOT A DELIVERABLE. Never to the Deck Editor, never to R2, never to
a client.** The name carries the warning because a 21 MB file that opens and
scrolls correctly is otherwise indistinguishable from a shippable one.

**What it is:** the embedded build with the seven `<video>` elements intact —
poster, `autoplay muted loop playsinline preload="none"`, and the shape's
`--ar` — but with the `src` attribute removed entirely, so no media bytes and
no external reference. It exists to separate two symptoms the 63.14 MB file
conflates: scroll-snap behaviour (fixed by `scroll-snap-stop:normal`) and
decode/memory pressure from 63.0 MB of base64. Built with
`python3 -m phase_1c.henhouse.embed --diagnostic`; the deliverable path is
untouched by that flag (md5 verified identical across the run).

**Why the src is stripped rather than pointed at a file.** An external
`src="assets/vid_*.mp4"` was the obvious alternative and is wrong here for
three separate reasons, all pre-existing and already recorded:

1. **iOS `file://` sandbox** — NOTES (P&G, Phase 2 video decision): *"inline =
   iPhone-AirDrop-verifiable, external = not"*. Opened from Files on a phone the
   videos would not load at all, so a smoother scroll would prove nothing: the
   comparison becomes 63 MB-with-video against 21 MB-with-no-video-loading.
2. **The R2 publish path does not exist *in this pipeline*.** NOTES:
   *"Architectural design intent — not yet implemented"*. **AMENDED 2026-08-24:
   true of the pipeline code, false as a statement about how decks are actually
   published — see "How decks are really published" below. Decks ARE live, and
   GAP has served media externally over HTTPS since May 2026.**
3. **Deck Editor v14's handling of relative asset URLs is undocumented.** Rule
   22 pins that it uses `DOMParser`, runs no JS, keys on `class="slide"` and
   finds media through `img` elements. Whether it resolves a sibling `assets/`
   directory is recorded nowhere, and was not guessed at.

**Precedent check (as it stood before 2026-08-24):** every embedded file
*produced by this pipeline* is fully self-contained — Old Spice 0 external
refs, Olay 0 (32 videos, all `data:video/mp4`), HenHouse 0. **AMENDED: right
about the pipeline's own output, wrong as a claim about published decks. GAP
has shipped multi-file with external media since May 2026.**

**AMENDMENT 2026-08-24 — the diagnostic and the published variant are two
different artefacts.** The "never to a publish path" line above still stands
for THIS file (`henhouse_DIAGNOSTIC_no-video-bytes_DO-NOT-SHIP.html`): it has
no video at all and would misrepresent the deck. It was not published. A
SEPARATE multi-file variant was built and published for the phone test — see
"Published scroll-test variant" below. Nothing here was overridden; a different
artefact was made for the job this one could not do.

## How decks are really published (established 2026-08-24)

NOTES previously implied the only publish path was an unimplemented Cloudflare
migration. That was wrong, and wrong in the direction that matters: decks have
been live for months. The actual mechanism, read off DNS and response headers
rather than from memory:

**HTML — GitHub Pages, one public repo per deck.** Repos named `<slug>-deck`
under `seanchaudhuri0075-cmd`, content on a **`gh-pages`** branch at path `/`,
custom domain set by a `CNAME` file in that branch. `globalimaige.com` runs on
Cloudflare nameservers (`violet`/`rory.ns`), and each deck subdomain is CNAME'd
to `seanchaudhuri0075-cmd.github.io` **DNS-only** — it resolves straight to the
GitHub Pages IPs (185.199.108-111.153), so Cloudflare does DNS and nothing else
for those hostnames. No wrangler, no `r2 object put`, no CI.

**Media — Cloudflare-fronted object storage at `media.globalimaige.com`**,
proxied (104.26.x / 172.67.x), `server: cloudflare`, MD5-shaped etags, range
requests supported. Every signal says R2 behind a custom domain. Laid out as
`/shared/<deck>/<group>/<file>`.

**Two publishing shapes coexist; the choice is per deck:**

| deck | repo size | shape |
|---|---|---|
| Patchology | 20 MB | single self-contained `index.html` (26.87 MB) + `CNAME` |
| GAP | 382 MB | small `index.html` (127 KB) + `.nojekyll` + `assets/`, all media on `media.globalimaige.com` as absolute HTTPS URLs |

A multi-file deck is therefore neither new nor risky — GAP has been one since
May 2026. What remains genuinely unknown is whether **Deck Editor v14**
resolves relative asset URLs on import. GAP sidesteps that question entirely by
using absolute URLs to the media host.

## Published scroll-test variant (2026-08-24)

`https://seanchaudhuri0075-cmd.github.io/henhouse-scrolltest-deck/`

Repo `henhouse-scrolltest-deck`, branch `gh-pages`, **deliberately no `CNAME`**
so it takes no `globalimaige.com` hostname and cannot collide with the two
existing HenHouse repos (`henhouse-creative-deck`, `henhousecreative-deck`) —
neither of which was touched.

21.03 MB `index.html` (all images inlined) + `assets/` with the 5 unique
videos, 24.49 MB, referenced by **relative** `src`. 45.52 MB total. Over HTTPS
the relative refs resolve and `preload="none"` genuinely defers each fetch
until the element nears playback; the origin honours range requests (verified
`206` on a 1KB range), so videos stream rather than download whole.

Diagnostic artefact, not a deliverable. It exists to make the scroll test
answerable with real video playing, which neither the 63.14 MB single file
(all bytes up front) nor the no-video diagnostic could do.

## Old Spice — flagged for re-import once the editor is fixed (2026-08-24)

**Not touched. Recorded so it is not forgotten.**

`oldspicepackaging.globalimaige.com` is live and renders correctly, but
**3.45 MB of its 3.51 MB published file is `url(data:...)` inside `:root`** —
15 shared-property crop assets that Deck Editor v14 never externalised (see
LEARNINGS rule 36). Its 39 `img`/`poster` srcs went to R2 as expected; only the
CSS-painted ones stayed inline. 98.3% of what a visitor downloads is bytes that
were supposed to be on the CDN.

**Re-import is worth doing when — and only when — the editor rewrites
`url(data:...)` inside a `<style>` block.** Re-importing before that changes
nothing: the same 15 properties would survive the round-trip again.

The alternative, if the editor fix is far off, is the HenHouse workaround:
rebuild `oldspice_deck_embedded.html` with the crop-half dedupe disabled so all
15 become real `<img>` elements, then re-import. That grows the input file by
roughly 4.6 MB (15 assets × the copy the dedupe was saving) and shrinks the
published deck by ~3.45 MB. `phase_1c/oldspice/embed.py` would need the same
`DEDUPE_CROP_HALVES = False` switch HenHouse now carries.

Deliberately not done now: Old Spice is signed off and live, and this is a
delivery-efficiency fix, not a correctness one.

## Olay — scroll feel was never reviewed (2026-08-25)

Olay's mobile has **five documented rounds** in the Deck 6 section above:
mobile review round (backdrops, occlusion, tile sizing), GIF logo + spacing,
renders ground fix for slides 4-7, and mobile rounds 2-4 (fill/merge/carousels,
unstretch/merged-header, slide 3 variant matrix). Round 2 records *"Reviewed on
a real phone"*. Each round re-verified desktop pixel-identical.

**Scroll feel was in none of them.** Grepping the whole Deck 6 section for
`scroll-snap`, `snap`, `momentum`, `scroll feel`, `inertia`, `fling` returns
nothing. Every round was layout, sizing, occlusion and spacing.

That is the same blind spot HenHouse had: mobile signed off on *appearance*,
with scroll *behaviour* never examined. Both decks shipped
`scroll-snap-stop:always` unconditioned — a discrete-paging affordance that
turns every fling into a single-step advance on an inertial surface — and it
survived five review rounds on Olay and four on HenHouse because nobody was
looking at that axis. Worth treating scroll behaviour as its own review
dimension rather than something that rides along with a layout pass.

**Ported to Olay 2026-08-25**, both declarations together, mobile-gated at the
same 820px breakpoint:

```
#deck  { scroll-snap-type:none }      /* was: y proximity */
.slide { scroll-snap-stop:normal }    /* desktop keeps y mandatory + always */
```

Desktop CSS byte-identical; body markup byte-identical. The strip carousel
keeps its own `scroll-snap-type:x proximity` — verified at runtime: mobile deck
`none`, carousel `x`; desktop deck `y mandatory`, carousel off.

The `.slide` selector is left blanket, so `stop:normal` also lands on the
carousel tiles. Inert there (their snap is on the x axis), and left visible
rather than pre-empted, by instruction.

**Geometry differs from HenHouse and may matter.** At 390x844 HenHouse had 28
of 51 snap points exactly one viewport apart (55%), which made proximity behave
as mandatory. Olay has 11 of 33 (33%), median gap 983px, max 2272 — but **no
gap is shorter than one viewport** (min exactly 844px). So proximity intercepted
fewer flings here, and `stop:always` was likely the dominant cause rather than
snap strictness. The two declarations were applied together at Sean's
instruction, to be judged on the phone rather than split.

Diagnostic build published for review at
`https://seanchaudhuri0075-cmd.github.io/olay-scrolltest-deck/` — separate repo,
no CNAME, no globalimaige.com hostname, no R2, nothing touching the live deck.
It also carries the `_solid_color`/ColorResolver fix (slides 9/10 wash).

## Deck Editor v14 — the "Deck Name" field persists across sessions (2026-08-25)

**Confirmed from the editor, not inferred.** `Upload to R2` opens a dialog with:

| field | |
|---|---|
| Worker URL | *(the deck-media Worker endpoint — read it from the dialog; deliberately not recorded here, this repo is public)* |
| **Deck Name (folder prefix)** | **sets the R2 prefix** |
| Auth Token | |
| | *"Files stored as /deckname/video-1.mp4"* |

**The Deck Name field is pre-filled and does NOT reset per deck.** Loading
Olay's embedded file showed the field still holding `henhouse` from a previous
session — note it was `henhouse`, not `olay` and not the loaded file's name, so
it carries the last *typed* value rather than deriving from the deck.

**That is the whole root cause of the Old Spice / Olay collision.** Olay was
imported 2026-08-21 with the field at `olay`. All three Old Spice imports the
next day inherited it, wrote 29 objects into `olay/`, and clobbered 24 of
Olay's 94 image ordinals — putting Old Spice packaging on Olay's slides 2-6 in
front of a client. Nothing in the tooling flagged it; the deck still rendered.

**Standing risk: the field must be read and set deliberately on EVERY import.**
It is a single text input that silently carries the previous deck's value, and
the failure is invisible at publish time — the deck renders correctly because
the *other* deck's assets are valid images. It only surfaces when someone
compares published bytes against the build, which is how this was found, four
days late.

Mitigations, in order of durability:
1. **Check the field every time.** Process only; this is what failed.
2. **Make it content-derived** (deck title or file name) so nothing can carry.
3. **Namespace per publish** (`<deck>/<build-id>/`) so even a repeated value
   lands in a fresh directory — this also permanently removes the immutable
   cache hazard, since every publish produces new URLs.

Until (2) or (3), treat the field as the highest-risk control in the pipeline.

**Cache consequence.** R2 objects are served `Cache-Control: max-age=31536000,
immutable`. Overwriting a poisoned key corrects the origin but NOT the copies
already held by browsers and the edge, for up to a year. So a collision cannot
be repaired in place — it needs a fresh prefix and an HTML re-point.

---

# Deck 9 — Venus / Hestia "Photoshoot GenAI Creative Ads" (2026-08-26)

## R2 prefix: `venus-hestia` — WRITE THIS INTO THE DIALOG

**Deck Name (folder prefix) = `venus-hestia`**

Recorded here *before* the Deck Editor step, deliberately, because the field
does not reset between sessions and currently reads **`olay-v2`** from the last
publish. Typing it at the dialog from memory is exactly how Old Spice inherited
`olay/` and put another client's packaging on Olay's slides 2-6 for four days.
Read the field, clear it, type `venus-hestia`, then upload.

Prefix must not collide with: `olay`, `olay-v2`, `oldspicepackaging`,
`hh-creativestrategy`, `pgdigital`.

## Source file — canonical is the _OSR

`Venus_Hestia_Photoshoot_GenAI_CreativeAds_OSR.pptx`
sha256 `32689c7c0d8e84793f8c91a44fc41bc6689b25566f5f76c3ae505c90f09d1162`
958,639,589 bytes, modified 2026-08-26 01:37:45, **65 slides**.

`041626_..._R4.pptx` (958,571,645 B, 2026-08-18, 63 slides) is the superseded
revision and is to be ignored entirely.

`_OSR` is this client's standard delivery suffix, not a one-off export — the
same folder holds `FACTORY_EXPANDED_OSR.pptx` and
`GIF2026_3D_CGVFX_AI_Presentation_OSR.pptx`. The OSR mtime is 34 seconds before
the Finder screenshot that delivered it.

**Do not mix the two files.** OSR is a strict superset: 224 of its 226 media
contents also exist in R4, none of R4's are absent from OSR, and it adds
slides 64/65 plus 2 media. But the media are **renumbered by one** —
`OSR image101.jpeg == R4 image100.jpeg`, and 170 of 226 files carry identical
bytes under a different name. Since the Deck Editor derives R2 keys from media
ordinals, building from one file and later switching would move 170 assets to
different keys under `Cache-Control: max-age=31536000, immutable`. The source
choice fixes the key space for the life of the deck.

**Open at desktop review:** slides 64 and 65 are the entire content difference
from R4 and their contents are not yet known. Flag them for Sean.

---

# Fragment navigation, slide identity, chapter anchors (2026-08-27)

Recorded from a session whose transcript was lost. **Everything below was
investigated and measured in a live browser against live files — none of it is
reasoned or inferred.** The one item that is a proposal rather than a
measurement is labelled as such.

## Fragment navigation — root cause found: `scroll-behavior: smooth`

**`pgdigital` sets `scroll-behavior: smooth` on `#deck`. The other three decks
use `auto`.** Fragment navigation and `scrollIntoView()` both inherit it, and a
smooth scroll over ~48,000px inside a snap container gets **cancelled**.

**Being an inner scroller is NOT the problem.** That was the standing
hypothesis and it is wrong — three decks are inner scrollers and their fragment
navigation works fine. The single differing property is the cause.

### Measured

| case | result |
|---|---|
| hh desktop, snap active, `#s40` | lands exactly, `targetTop` 0, 100% of viewport |
| hh mobile 390x844, gate released (`snap:none`, `stop:normal`) | lands exactly, `targetTop` 0 |
| cold load, both of the above | **zero drift**, with 93 images still `incomplete` |
| pgdigital desktop, `#slide-45` | **does not move** — `deckScrollTop` 0, still on slide-0, target 43,290px below |

Cold load is clean because every media box is reserved from `--ar`:
`imgs_without_reserved_box: 0`. Late-loading images cannot shift the landing
position, so image decode is excluded as a contributing cause.

### Mechanism isolated

On pgdigital desktop, same target, same element:

| call | result |
|---|---|
| `deck.scrollTo({top, behavior:'smooth'})` | **FAILS** — stays 0 |
| `deck.scrollTo({top, behavior:'instant'})` | works — 43290 |
| `deck.scrollTop = top` | works — 43290 |

The distance is the variable, not the target and not the container: the same
scroller reaches the same offset by two of three routes.

### Corroboration from this repo

`scroll-behavior` appears **nowhere** in this repository — not in `deckkit`,
not in any generator, and not in any built deck under `out/` (grep across all
files, excluding `.git` and `out.zip`, 0 hits). Our builder never emits the
property, so every deck it produces defaults to `auto`. pgdigital's `smooth`
came from outside this pipeline, which is consistent with it being the only
deck of the four that has the defect.

**Fix direction:** do not set `scroll-behavior: smooth` on a long snap
scroller. Where smooth motion is wanted, drive it per-call with an explicit
`behavior` rather than inheriting it from the container, so long jumps can fall
back to `instant`.

**This blocks chapter anchors.** pgdigital is the only deck with chapters
(below), and it is the one deck where fragment navigation does not work. Fix
the `scroll-behavior` first — anchor work on pgdigital cannot be verified until
fragment navigation lands.

## Editor round-trip — ids survive

Import → `commitAll()` → `buildOutput()`, run on live files:

| deck | ids | attribute counts | scripts |
|---|---|---|---|
| hh | 52 ids identical | `data-slide` 52 → 52 | — |
| pgdigital | 50 ids identical | `data-n` 55 → 55, rail 51 → 51 | both preserved |

Consistent with the earlier finding of **five benign normalisations and no
sanitiser** (`DECK9_HANDOFF.md` §7). Nothing in the editor rewrites, strips, or
renumbers ids on a round-trip.

## Ordinal stability — the editor is safe, the builder is what breaks links

Both editor mutations were measured on live files:

| mutation | result |
|---|---|
| delete slide 3 | ids become `s1`, `s2`, **`s4`**, `s5` — the editor **leaves a gap, it does not renumber** |
| reorder via `moveSlide(0,4)` | ids become `s2`, `s4`, `s5`, `s6`, **`s1`** — **ids travel with their content** |

**The editor is content-bound and is not the hazard. Our builder is.** Ordinals
are assigned by output position, so any change to the source slide set
renumbers everything downstream of it. Deck 9 is the worked example: dropping
source slide 1 at build level (commit `3cf5ae1`) renumbered the remaining
slides 1..64, so **the old `s2` became `s1`** — every previously shared link
silently moved by one slide.

This is the same failure class as the R4 → OSR media renumbering (deck 9,
§"Source file") and the R2 prefix collision (§"Deck Editor v14"): one
identifier silently meaning two different things.

### Proposal — NOT yet implemented

Emit **`id="s{src_n}"` and `data-slide="{n}"`**: the id bound to the **source
PPTX slide number**, the data attribute to **output position**.

- Human-readable and guessable, unlike an opaque id.
- Stable under the mutation that actually breaks links — dropping or inserting
  a source slide no longer moves any other slide's id.
- Output position stays available for anything that needs it, on the data
  attribute where renumbering is harmless.

**No content hash. Sean rejected an opaque id.**

## Chapter anchors

### pgdigital needs no authoring hint

`class="slide k-divider"` already marks **exactly 5 slides**, matching the five
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
`#01-omnichannel` and the full form work.

Also measured: on pgdigital the chapter name appears as a **running kicker on
every content slide**, so chapter membership is recoverable for **every** slide,
not just the five dividers.

### The other decks are not uniform — this needs a per-deck mapping

| deck | divider signal | chapters? |
|---|---|---|
| pgdigital | `class="slide k-divider"` ×5 | yes |
| oldspicepackaging | `data-arch=divider` ×3 | yes |
| hh-creativestrategy | none; closest is `data-arche=route` ×3 | — |
| olay | nothing (only `data-layout=strip`) | **no chapter structure to anchor** |

So the answer is a **per-deck mapping, not a per-slide hint**. Each `phase_1c`
builder already classifies archetypes; it only needs to declare **which
archetype means chapter divider**. Do not add per-slide authoring markup.

## Fragments, not paths — confirmed

Measured against the live host:

| URL | result |
|---|---|
| `/01-omnichannel` | **real 404**, GitHub's own error page |
| `/#01-omnichannel` | **200** |

**There is no SPA fallback.** Anchors must be fragments. A path-shaped share
link cannot be made to work on this host without adding a fallback that does
not currently exist.

## Constraint — pgdigital's existing ids must not be renamed

pgdigital's ids are **`slide-N` and 0-based** (`slide-0` is the first slide;
the measured target above was `#slide-45`). **Do not rename them.** Links may
already have been shared against them, and this host 404s rather than falling
back, so a renamed id fails outright rather than degrading. Any new scheme is
additive on pgdigital — keep `slide-N` resolving.

---

# pgdigital — `scroll-behavior` fixed, and where the file actually lives (2026-08-27)

## FIXED — `scroll-behavior:smooth` removed from `.deck`

**Live repo:** `seanchaudhuri0075-cmd/pgdigital-deck`, branch `gh-pages`.
**Commit:** `4e10fd9`. **Revert target: `fb60694`** (`Deploy deck: pgdigital`).

One declaration deleted, 26 bytes, CSS only:

```diff
 .deck{
   height:100svh;
   overflow-y:auto;
   overflow-x:hidden;
   scroll-snap-type:y proximity;
-  scroll-behavior:smooth;
   -webkit-overflow-scrolling:touch;
 }
```

### Verified before and after, on the real file, locally served

| | `scroll-behavior` | `#slide-45` → `deck.scrollTop` |
|---|---|---|
| before (control) | `smooth` | **0** — still on slide-0, target 43,290px below |
| after | `auto` | **43290** — exact, `viewportTop` 0 |

The control was the unpatched byte-identical file served from the same server
to the same browser in the same session, so the one deleted line is the
established cause, not a coincidence of environment.

Fragment navigation is also exact on **hashchange**, not just cold load:
`#slide-0` → 0, `#slide-4` → 3848, `#slide-26` → 25012, `#slide-45` → 43290,
`#slide-49` → 47138. That includes the full-length 47,138px jump, which is
longer than the one that was failing.

### Three corrections to the 2026-08-27 findings above

1. **The selector is `.deck` (class), not `#deck` (id).** The `#deck` in the
   earlier entry is wrong. `#deck` is what *our* `phase_1c` builders emit;
   pgdigital predates them and uses a class.
2. **A `prefers-reduced-motion` override was already present** and was left in
   place: `@media (prefers-reduced-motion:reduce){ .deck{scroll-behavior:auto} }`.
   It is now a no-op, kept deliberately — it documents intent and still guards
   if `smooth` is ever re-added. **It also means fragment navigation was never
   broken for reduced-motion users**, which is why the bug was not universal.
3. **The rail is not user-facing.** `<nav class="rail" hidden aria-hidden="true">`
   — it is deck-editor metadata, backed by `.rail[hidden]{display:none!important}`.
   There is no rail click to regress, so the "short rail jump" check has no
   subject.

### The one user-visible change: keyboard paging

The deck intercepts `keydown` and calls `deck.scrollTo({top})` **with no
explicit `behavior`**, so paging inherited the container's value. Arrow /
PageUp / PageDown / Space paging **was animated and is now instant.**

This was accepted deliberately, on the grounds that it is already the shipped
experience for every `prefers-reduced-motion` user via the override above.
Paging still lands on exact snap positions — verified 45 → 46 → 47 forward and
ArrowUp back to 46. It was never affected by the cancellation bug, because it
only ever moves one adjacent slide.

The alternative, if the glide is ever wanted back, is an explicit
`behavior` at that single call site **guarded by `matchMedia`** — an
unqualified `behavior:'smooth'` in JS would override the reduced-motion CSS and
regress it.

## pgdigital's live HTML is the master artifact — and it is NOT alone

**No builder in this repo can regenerate pgdigital.** It predates `phase_1c`.
`k-divider` and `data-slide-name` appear in no source file here, and
`scroll-behavior` has never existed anywhere in this repo's git history. Do not
go looking for a builder — the published HTML *is* the source.

Do not confuse it with `out/` ("P&G Digital First Deck"), which is the Phase 1B
output: 23 separate `pg_slide_NN.html` pages, no `.deck`, no rail. Different
artifact, similar name.

**But the reversion surface is real — embedded copies exist in `~/Downloads`:**

| file | size | md5 | carries the bug |
|---|---|---|---|
| `Deck_WIP_2026-08-21_1002.html` | 147,410 | `e8a6fa34…` — **byte-identical to the pre-patch live file** | yes |
| `pg-digital-first-embedded.html` | 79,511,127 | `6358120b…` | yes |
| `PG_Deck_for_client/pg-digital-first-embedded.html` | 79,511,127 | `6358120b…` (same file) | yes |
| `PG_Deck_for_client/pg-deck-view/pg-digital-first-deck/index.html` | 73,516 | — | **no — has no `scroll-behavior` at all** |

**`Deck_WIP_2026-08-21_1002.html` is the hazard.** It was byte-identical to
live, so re-exporting it from the Deck Editor silently reverts this fix. The
patch was applied to the live repo only; **these local copies were deliberately
not touched** — patching stale copies invites publishing the wrong one.

The 73,516-byte variant is the interesting one: it has no `scroll-behavior`
whatsoever and predates the embedded build by three minutes (04:13 vs 04:16 on
2026-08-21). So `smooth` was added late in that session, and the deck shipped
broken from that point.

**Standing rule: pgdigital changes are made in `pgdigital-deck@gh-pages` and
nowhere else.** If a Deck Editor round-trip is ever needed, re-import from the
live file, not from a `~/Downloads` copy.

## The HTML patch technique — recorded, having been used four times undocumented

The decks that predate `phase_1c` have no builder, so the published HTML is the
master. A change to one is a **surgical edit to the shipped file**, not a
re-render. The technique, as actually practised:

1. **Clone the publishing repo and edit there.** The `gh-pages` branch is both
   the live file and the deploy target, so there is no separate publish step
   and no chance of editing a copy that is not the one serving traffic.
2. **Locate by anchored, counted match.** Confirm the string occurs exactly as
   often as expected (`grep -c`) before editing, and delete or replace by line
   with an anchored pattern. Never a bare global substitution.
3. **Diff must be exactly the intended change.** `git diff` before committing;
   if it shows more than the intended hunk, throw it away and start again.
   Editors that reflow, minify, or re-encode are disqualified — this is why the
   edit is done with `sed`/`Edit` and not by opening the file in a tool that
   rewrites it.
4. **Run a before/after control.** Serve the unpatched copy and the patched
   copy from the same server to the same browser in the same session, and show
   the defect reproducing on one and gone on the other. Without the control,
   "it works now" does not distinguish the fix from the environment.
5. **Leave deploy metadata alone.** `CNAME` in particular — it is the live
   hostname, it is not part of the deck, and touching it takes the site down.
6. **Record the parent commit as the revert target** in the same breath as the
   fix, because there is no build to roll back to.
7. **Enumerate the reversion surface.** Find every embedded or WIP copy that
   could be re-exported over the fix, and record which ones carry the old bytes.
   A single-file deck has no dependency graph to protect it — the only defence
   is knowing the copies exist.

---

# pgdigital — counter diagnosis, 1-based aliases, scroll-tracked URL (2026-08-27)

**Commit `8cedd3b`** on `pgdigital-deck@gh-pages`. **Revert target: `4e10fd9`**
(the scroll-behavior fix). Live bytes verified md5-identical to the commit
(`20dbf64a…`), CNAME untouched, `~/Downloads` copies deliberately not patched
and confirmed still at their original md5s.

## Why the counter "did not track scroll" — it was never wired to

The counter is **static text baked into `index.html`**: every `.slide` ships its
own `<div class="num">NN / 50</div>`. A generator exists — `foot(s, total)`,
emitting `String(s.n).padStart(2,"0") + " / " + total` — but the boot function
guards it:

```js
if (!deck.querySelector(".slide")) { /* build */ } else { /* adopt markup */ }
```

The 50 slides ship as static markup, so **`buildSlide()` and `foot()` are dead
code on the live deck.** The counters were baked at authoring time.

**The whole file contained exactly one `addEventListener`, and it was
`keydown`.** No scroll listener, no `hashchange`, no `popstate`, no `history.*`,
no `location.hash` write. The one IntersectionObserver present only played and
paused video. So nothing updated the counter and nothing updated the URL.

Measured before changing anything: on desktop the static counters are in fact
**correct**, and read correctly while scrolling — walking from `#slide-40`
forward, sampling at each snap point and at 50% mid-scroll, there was always
exactly one counter in the viewport, owned by the dominant slide (41→47). All
50 are monotonic: `slide-N` carries `N+1 / 50`. The reported "frozen" reading is
explained by the URL never changing: the address bar stays on whatever fragment
was loaded, and any reload re-applies it and snaps back there.

## What shipped — three additive changes, no id renamed

1. **One-based fragment aliases.** Each slide gains a zero-size
   `<span class="alias" id="slideN">` pinned to its top, N being the slide's
   `data-n` — the number printed on screen. `#slide45` lands on the slide
   reading `45 / 50`. The 0-based `slide-0 … slide-49` are untouched and still
   resolve, so already-shared links keep working. **No script required for
   this half** — it is markup plus one CSS rule.
2. **Address bar follows the slide in view**, via `history.replaceState` and an
   IntersectionObserver over a **zero-height band at the viewport midline**
   (`rootMargin:"-50% 0px -50% 0px"`). ~11 lines.
3. **slide-1's missing footer**, added to match the other 49.

### Why a midline band and not a ratio threshold

The five `.tall` slides (`slide-2, -3, -7, -22, -32`) exceed the viewport, so
their intersection ratio can never reach a high threshold — `threshold:0.6`
would have silently skipped exactly those five. A zero-height band has exactly
one qualifying element at any scroll position regardless of element height.
**This is the same failure the deck 9 player hit** ("a tile taller than the
viewport can never reach ratio 0.5", `DECK9_HANDOFF.md` §12) — second time this
bites. Treat a ratio threshold as wrong by default wherever elements may exceed
the viewport.

### Why `replaceState` and never `location.hash`

Measured over 8 slide changes: `history.replaceState` added **0** history
entries, `location.hash =` added **8**. The latter traps the back button behind
one entry per slide. Verified after shipping: scrolling 11 slides added 0
entries while the URL tracked as `#slide11`, `#slide2`, `#slide23`, each
matching the printed counter.

## slide-1 reads `02 / 50`, NOT `01 / 50`

The request was for `01 / 50`. **That would have been wrong and was not
shipped.** `slide-0` already carries `01 / 50`, and `slide-1` carries
`data-n="2"`. Shipping `01` would have put a duplicate counter in front of the
client and broken the run of 50. Bar set to 4% (2/50), matching the formula the
other 49 use.

slide-1 is `k-hero`, and was the only slide of 50 with **neither `.chrome` nor
`.foot`** — its bare state looked deliberate, not accidental. Screenshotted
after the change: the bar sits below the brand lockup without collision, hero
crop intact. On desktop `.foot` is absolutely positioned and costs the hero no
space; **below 900px it is in flow and takes 34px off the hero image.**

## UNVERIFIED — mobile, below 900px

The window resize bounced back to 1680×962 on every attempt, as it did in the
previous session. **Nothing below the 900px breakpoint is confirmed**: not the
aliases, not the URL tracking, and specifically **not the new hero footer**,
which is the one change that consumes layout space at that breakpoint. Someone
must open the live deck on a phone and look at the hero. Do not report this
round as mobile-verified.

## Method — two traps that each cost a session, and will recur

### 1. A polluted browser tab produces confidently wrong results

The first round of testing had `#slide45` landing on `slide-0` and results
drifting by exactly one per call. **All of it was the test harness, not the
deck.** Two causes, both self-inflicted:

- Mutating `location.hash` in a loop had pushed **50 history entries** into the
  tab, and the browser was restoring scroll positions from them.
- **Assigning `location.hash` the value it already holds is a no-op** — no
  navigation, no scroll. Once the new observer began rewriting the hash, many
  of the test's own jumps silently never fired.

**Rule: verify fragment navigation with a full page load in a fresh tab, not by
assigning `location.hash` in a live page.** A full load is also what a shared
link actually does. Re-run that way, every result was correct first time.

### 2. A dead-looking IntersectionObserver is usually a tab that is not painting

The new observer appeared completely dead — it never fired, and neither did any
observer injected for comparison, **including one with the page's own working
options**. There were no console errors.

**Cause: the automation tab was not rendering.** `requestAnimationFrame` never
fired within 45 seconds. IntersectionObserver callbacks are delivered during the
render step, so with no paint there are no callbacks — ever. Videos will not
autoplay either, for the same reason.

**Diagnostic: race a rAF against a timeout. If rAF never fires, the tab is not
painting and no observer result means anything.** The fix is to force a paint —
taking a screenshot did it, and the URL immediately flipped to `#slide11`
against a counter reading `11 / 50`, proving the observer had been correct all
along.

**This is the same trap as the deck 9 / Venus mobile review**, where per-tile
player state was invisible enough to need a `?debug=1` overlay
(`DECK9_HANDOFF.md` §12). Both times, observer-driven behaviour looked broken
under automation when it was not. Check the paint before debugging the observer.

---

# pgdigital — mobile scroll gate ported from hh (2026-08-27)

**Commit `8c971d9`** on `pgdigital-deck@gh-pages`. **Revert target: `8cedd3b`.**
Live bytes md5-identical to the commit (`040c6432…`), CNAME untouched,
`~/Downloads` copies confirmed still at their original md5s.

**Confirmed on a real phone by Sean**, after desktop was signed off: on hh a
flick carries through several slides; on pgdigital every slide took a
deliberate drag with no momentum. Third deck with this exact symptom, after
HenHouse and Olay, and the same fix signed off on both.

## The fix — two declarations, byte-identical to hh's

```css
@media (max-width:899px){
  .deck{scroll-snap-type:none}
  .slide{scroll-snap-stop:normal}
}
```

Only the selectors differ: pgdigital uses `.deck` / `.slide`, hh uses `#deck` /
`section.slide`. (pgdigital's element carries both `class="deck"` and
`id="deck"`, but the CSS is written against the class.)

## THE RULE — gate at the deck's own mobile boundary, not at hh's 820px

**This is the third deck to take these two lines, and the next one will have its
own boundary too. Do not copy the number.**

hh gates at `max-width:820px` because **820 is hh's mobile breakpoint** — it is
hh's only media query. pgdigital switches layout at `min-width:900px` /
`max-width:899px`, so it gates at **899**.

Copying `820` literally into pgdigital would have left **821–899px** in mobile
layout — `.m-only` visible, all 13 `.artscroll` carousels live — while still
carrying desktop snap: a band with the mobile problem and none of the fix.

**The invariant being ported is "release snap wherever the deck is in mobile
layout", not "release snap below 820px".** Read the target deck's own
breakpoint first and gate there.

## Why it works — geometry, not the keyword

Measured: slide height == viewport == snap gap == 895px on every slide. With
snap points exactly one viewport apart, `proximity` has nowhere to rest outside
its threshold, so it re-targets every fling and animates on its own curve —
**behaving identically to `mandatory`**. `scroll-snap-stop:always` then forbids
travelling past even one point. Turning the snap container off is what returns
the browser's own deceleration, because snap re-targeting is what overrides it.

Accepted cost, same as hh's: slides no longer align on touch, so a flick can
rest mid-slide.

## Desktop untouched — measured, not assumed

Sean had just signed desktop off, so this was verified before pushing. On the
patched file at 1680px: `snap-type: y`, `snap-stop: always`, slide height 895 ==
viewport, and **10 wheel ticks travel exactly 895px, snapped** — the same figure
produced by the pre-patch file, the current file, and hh. The added rules live
inside `max-width:899px` and cannot apply at ≥900px.

## The 13 nested carousels — measured unaffected

`.artscroll` (13 slides, all inside `.m-only`, so below 900px only) carries its
own `scroll-snap-type:x proximity`. Computed values read before and after
applying the gate:

| property | before | after |
|---|---|---|
| `.deck` snap-type | `y` | **`none`** |
| `.slide` snap-stop | `always` | **`normal`** |
| `.artscroll` snap-type | `x` | `x` |
| `.artscroll` overscroll-x | `contain` | `contain` |
| `.artscroll img` snap-align | `start` | `start` |
| `.artscroll` overflow-x | `auto` | `auto` |

`scroll-snap-type` does not inherit, and each `.artscroll` is its own x-axis
scroll container, so releasing the parent's y-axis snap cannot reach it.

## UNVERIFIED — the diagonal-swipe caveat. Do NOT read this as tested.

**Reasoned, not measured. Touch gestures are not testable in this environment.**

Today's `scroll-snap-stop:always` acted as a brake: a vertical fling could not
run past one slide, which incidentally masked the vertical component of a
diagonal gesture on a carousel slide. With the gate released, **a diagonal swipe
starting on one of those 13 slides may now carry vertically through several.**

Chrome usually locks gesture direction on touch, which should contain it, and
`overscroll-behavior-x:contain` handles horizontal end-of-travel — but it does
not constrain vertical. **hh has no nested scrollers, so hh's sign-off does not
cover this case and cannot be cited for it.**

**This is the same shape the Venus/deck 9 mobile build was rejected over** — a
horizontal scroller nested inside a vertical one, flagged in
`DECK9_HANDOFF.md` §12 as "a plausible cause" of a scroll-feel complaint.
Those 13 slides need a deliberate look on a phone. Until someone does that and
records it here, this is an open risk, not a verified outcome.
