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
- `theme_from_pptx()` end-to-end is still unverified — the parser is tested,
  but the pptx-unzip-and-pick-theme1 wrapper has no fixture.
- Custom-theme decks (non-Office scheme colors) are not yet covered.
  Empirical finding from DEMERT (2026-04-15, current GIF deck): the theme
  layer is left at Office defaults; brand colors live elsewhere (slide
  masters, per-shape fills, fillStyleLst). Worth checking other GIF decks
  before assuming custom themes are common.
- Multi-theme decks: DEMERT has theme1 + theme2 with identical color
  schemes (diff is in fonts/fillStyleLst only). Behavior on decks where
  theme1 and theme2 disagree on colors is unverified.
