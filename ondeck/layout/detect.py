"""Layout classification — manifest-driven for Phase 1B.

Owns: reading a per-deck manifest JSON file and exposing a typed
accessor that maps slide index → template name (+ optional hints).

Per the user's design call (see feedback memory
`feedback_manifest_driven_layout.md`): Phase 1B is manifest-driven.
The deck author hand-tags each slide once. Auto-detect is a follow-up
phase whose regression target will be the manifest output of this
phase.

The six template names are enumerated in TEMPLATES — must stay in sync
with renderer modules in `render/templates/` (built later). Rendering
code reads `Manifest.classify(n)` to pick which template renderer to
invoke for slide n.

MANIFEST SCHEMA (see pg_manifest.json for an example):

    {
      "deck_name":         "<human-readable name>",
      "source_pptx":       "<file name of the source .pptx>",
      "deck_brand_color":  "<#RRGGBB>",   ← REQUIRED for non-cover templates
      "templates":         [<six names>], ← documents valid names; validated
      "slides": {
        "<N>": {
          "template": "<one of TEMPLATES>",   ← required
          "hints":    {...},                  ← optional, see HINTS below
          "notes":    "...",                  ← optional, human-readable
          "media":    {...}                   ← written by transform/* stages,
                                                read by render templates
        }
      }
    }

`deck_brand_color` is the deck-level design choice the deck-author made
for the canvas/panel background — the color that fills any slide area
not covered by shapes. It is NOT derivable from the PPTX (not in the
theme, not in the layout/master bg) and must be supplied per-deck.
Each new deck (FrameTag, Wheeber, etc.) needs its own brand color set
in its own manifest. See `ondeck-pipeline/NOTES.md` entry #4.

HINTS — per-slide design-intent overrides that OOXML can't carry. Each
template reads only the hints it cares about; unknown keys are ignored.

  canvas_bg                "#RRGGBB"
      Per-slide background color override. Default: deck_brand_color.
      Used by section_divider + media_showcase. See NOTES.md.

  headline_class           "t-bold" | "t-wnba"
      Maps to inherited-bold pt size for media_showcase / section_divider
      headlines. See INHERITED_BOLD_PT_BY_HINT in those modules.

  mobile_video_aspect_override   "9/16" | "4/5" | etc.
      Used by media_showcase video variant when the source-video aspect
      auto-detected by transform/video.py is NOT the design intent (e.g.,
      a 16:9 source meant to be cropped to 9:16 for TikTok-style framing).
      Takes precedence over media.video.aspect at render time.

  mobile_photo_layout            "stack" | "grid-2col"
      Used by media_showcase photo-grid variant. Default: count-driven
      auto-detect (`len(photos) >= 5 → grid-2col`, else `stack`). Set
      explicitly when the auto-detect picks the wrong layout — typically
      a photo-grid slide whose photos are tall/portrait and cramped in
      a 2-col grid (e.g., P&G slide 11 has 8 photos but 3 are portrait
      product shots; grid-2col with object-fit:contain wastes horizontal
      space, stack is the correct mobile layout). Aspect-ratio
      auto-detection was considered and rejected — too easy to misfire
      on a future deck. Hint is the deck-author-intent escape hatch.

  list_style               "plain_list" | "dotted_leader"
      Used by title_stats. Overrides the OOXML-detected list variant
      (dotted-leader detection scans for <a:tab leader='dot'/> on any
      paragraph's <a:pPr>). Rare escape hatch — the auto-detection should
      cover normal cases.

  bullet_char              "•" | "→" | "" (empty for no bullet)
      Used by title_stats plain_list variant. Overrides the template
      default (no bullet — OOXML's omission of <a:buChar> is treated as
      a signal, not an oversight). Set explicitly when a deck wants
      visible bullets.

  title_size_pt            <float>
      title_stats per-slide title font-size override (pt). Default:
      calibrated from the title shape's first run via
      parse/font_calibration. Set when the deck author scales the title
      beyond the source-declared sz (P&G slide 3 = 60pt vs declared
      44pt). Same class as the headline_class override.

  heading_size_pt          <float>
      title_stats per-slide override for the bold-heading lines in the
      continuation variant. Default: inherited-bold = 18pt. Set when
      the bundle renders bold headings at a different size (P&G slide
      3 = 22pt).

  body_size_pt             <float>
      title_stats per-slide override for the body row font-size. In
      the paired variant, applies uniformly to both label and value
      columns; weight differences (bold lead vs regular trail) are
      class-driven, not size-driven. Default: calibrated per-run
      (bold inherited 18pt + regular inherited 16pt). Set when the
      bundle uses one size with weight-only emphasis (P&G slide 21
      = 16pt uniform).

  logo_invert              true | false
      title_stats per-slide hint to render the GIF logo as solid white
      via `filter: brightness(0) invert(1)`. The bundle applies this
      only on slides where the logo's native colors don't read on the
      canvas (P&G slide 21 only — slide 3 desktop sits on the same
      cyan canvas without the filter, a bundle inconsistency we
      replicate per the "bundle is truth" parity rule). Default false.

  hide_footnote            true | false
      title_stats per-slide hint to suppress rendering the footnote
      shape even when one is detected on the slide. The bundle drops
      the asterisk's body text on P&G slide 21 — only the title's "*"
      character remains. Default false (footnote renders if present).

MEDIA — written by transform/video.py and transform/image.py before
render runs. Render templates read these via slide_class.media:

  media.video    {"aspect": "16/9", "width": 1920, "height": 1080,
                  "filename": "<deck_slug>_slide_<NN>_video.mp4"}
                 — singular; if a slide has multiple videos, the first
                 in document order wins (warning printed). Schema would
                 need to grow to media.videos: [...] for true multi-video.

  media.images   [{"src_id": "<cNvPr/@id>", "filename": "...webp",
                   "format": "webp", "width": ..., "height": ...,
                   "flatten_on_canvas": <bool>?}, ...]
                 — list, ordered by document position. Templates match
                 by src_id + role (geometry), never by index or count.
                 See "Templates match by src_id and role" entry in NOTES.md.

EXPECTED_ASSETS — optional per-slide validator hint. The manifest may
declare the expected count of unique asset sources per role; the
renderer's HTML output is then post-validated against that expectation
via Manifest.validate(idx, html). Six roles:
  logo            — class 'gif-logo' / 'gif-logo-mobile' / 'logo' /
                    'logo-mobile'.
  hero            — cover slide hero (class 'hero' / 'hero-mobile').
  photo_bg        — full-bleed photo backdrop (class 'photo' /
                    'photo-mobile' — no digit suffix).
  photo_grid      — tiled photo cells (class 'photo-<digit>' or
                    'photo-m' for the mobile counterpart).
  video           — <source src="..."> inside a <video> element.
  video_poster    — poster="..." attribute on a <video> element.
Counts are by unique source URL — desktop+mobile sections that
reference the same image collapse to one. validate() returns an empty
list when the rendered HTML matches expected_assets exactly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

# The six layout templates exercised by P&G. Each name corresponds to a
# renderer module that will live in render/templates/.
TEMPLATES = (
    "cover",            # solid bg + branded logo + headline
    "title_stats",      # title + stats / numbered list / text-only
    "card_grid",        # multi-card grid (logos / packshots, 3-N cells)
    "section_divider",  # photo bg + gradient overlay + 88pt stacked headline
    "media_showcase",   # title + photos or video + circle annotation
    "two_column",       # title + left col + right col
)


@dataclass
class SlideClass:
    """Classification result for one slide."""

    slide_index: int                              # 1-based
    template: str                                  # one of TEMPLATES
    hints: dict = field(default_factory=dict)     # optional per-slide overrides
    notes: str = ""                                # human-readable, ignored by renderer
    media: dict = field(default_factory=dict)     # transform-stage output, e.g. {"video": {"filename": "...", "aspect": "16/9", ...}}
    expected_assets: Optional[dict] = None        # validator hint: {role: count}; None disables validation


@dataclass
class Manifest:
    """Loaded manifest for one deck. See pg_manifest.json for the format."""

    deck_name: str
    source_pptx: str
    deck_brand_color: str          # canvas bg for non-cover templates; '#RRGGBB' or ''
    classifications: dict          # {slide_index: SlideClass}

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Manifest":
        """Read a manifest JSON file and validate its template names."""
        path = Path(path)
        return cls.from_dict(json.loads(path.read_text()))

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        # Validate any top-level 'templates' declaration if present.
        declared = data.get("templates")
        if declared is not None:
            unknown = [t for t in declared if t not in TEMPLATES]
            if unknown:
                raise ValueError(
                    f"manifest declares templates not in code enum: {unknown}"
                )

        classifications: dict = {}
        for key, body in data.get("slides", {}).items():
            idx = int(key)
            template = body.get("template")
            if template not in TEMPLATES:
                raise ValueError(
                    f"slide {idx}: unknown template {template!r} "
                    f"(allowed: {TEMPLATES})"
                )
            classifications[idx] = SlideClass(
                slide_index=idx,
                template=template,
                hints=body.get("hints", {}),
                notes=body.get("notes", ""),
                media=body.get("media", {}),
                expected_assets=body.get("expected_assets"),
            )

        return cls(
            deck_name=data.get("deck_name", ""),
            source_pptx=data.get("source_pptx", ""),
            deck_brand_color=data.get("deck_brand_color", ""),
            classifications=classifications,
        )

    def classify(self, slide_index: int) -> SlideClass:
        """Look up the template + hints for slide N (1-based). KeyError if missing."""
        if slide_index not in self.classifications:
            raise KeyError(f"manifest has no entry for slide {slide_index}")
        return self.classifications[slide_index]

    def missing(self, total_slides: int) -> list:
        """Return slide indices in [1..total_slides] that the manifest does NOT cover."""
        return [i for i in range(1, total_slides + 1) if i not in self.classifications]

    def validate(self, slide_index: int, html: str) -> list:
        """Compare rendered HTML against the slide's expected_assets.

        Returns an empty list when the asset roles + unique-source counts
        match exactly. Each mismatch is one human-readable string. If the
        slide has no expected_assets entry, returns []. Roles not declared
        in expected_assets but found in the HTML count as mismatches.
        """
        sc = self.classify(slide_index)
        expected = sc.expected_assets
        if expected is None:
            return []
        found = _scan_html_for_assets(html)
        mismatches: list = []
        for role, exp_count in expected.items():
            actual = len(found.get(role, set()))
            if actual != exp_count:
                mismatches.append(
                    f"role {role!r}: expected {exp_count}, found {actual}"
                )
        for role, srcs in found.items():
            if role not in expected and srcs:
                mismatches.append(
                    f"role {role!r}: unexpected (found {len(srcs)})"
                )
        return mismatches


# ────────────────────────────────────────────────────────────────────────────
# HTML asset scanner — used by Manifest.validate
#
# Anchored to <div class="..."> wrappers so the embedded @font-face block in
# the page <style> (which uses `src: url(data:font/woff2;...)` not as a tag
# attribute) is naturally excluded — no <div> precedes those CSS url() calls.

# <div ...class="..." ...> ... <img ...src="..."...>  (img as immediate-ish child)
_DIV_IMG_RE = re.compile(
    r'<div\b[^>]*?\bclass="([^"]+)"[^>]*>\s*<img\b[^>]*?\bsrc="([^"]+)"',
    re.IGNORECASE | re.DOTALL,
)
# <div class="..." style='... background-image: url(...) ...'> for the
# section_divider mobile photo backdrop. Style is single-quoted in our
# emitter so the inner url() can carry double-quoted data: URLs.
_DIV_BG_DOUBLE_RE = re.compile(
    r'<div\b[^>]*?\bclass="([^"]+)"[^>]*?\bstyle="([^"]*?)"',
    re.IGNORECASE | re.DOTALL,
)
_DIV_BG_SINGLE_RE = re.compile(
    r"<div\b[^>]*?\bclass=\"([^\"]+)\"[^>]*?\bstyle='([^']*?)'",
    re.IGNORECASE | re.DOTALL,
)
_BG_URL_RE = re.compile(
    r'background-image\s*:\s*url\(\s*([\'"]?)([^)\'"]+)\1\s*\)',
    re.IGNORECASE,
)
_VIDEO_POSTER_RE = re.compile(r'<video\b[^>]*?\bposter="([^"]+)"', re.IGNORECASE)
_SOURCE_SRC_RE = re.compile(r'<source\b[^>]*?\bsrc="([^"]+)"', re.IGNORECASE)


def _class_to_role(class_attr: str) -> Optional[str]:
    """Map a class= attribute string to one of the 6 asset roles.

    Returns None for unrecognized class soups. Order of checks matters:
    photo_grid wins over photo_bg when both 'photo' and 'photo-N' appear
    on the same element (the badge variant emits class="photo photo-0",
    which is a grid cell, not a backdrop).
    """
    classes = class_attr.split()
    for c in classes:
        if re.match(r"^photo-(\d+|m)$", c):
            return "photo_grid"
    for c in classes:
        if c in ("gif-logo", "gif-logo-mobile", "logo", "logo-mobile"):
            return "logo"
    for c in classes:
        if c in ("hero", "hero-mobile"):
            return "hero"
    for c in classes:
        if c in ("photo", "photo-mobile"):
            return "photo_bg"
    return None


def _scan_html_for_assets(html: str) -> dict:
    """Extract {role: set_of_unique_sources} from rendered HTML.

    Sources are deduped by URL/data: string — desktop and mobile sections
    that reference the same asset count once. <video poster=...> contributes
    to video_poster; <source src=...> contributes to video. <img>/<div>
    with role-class contribute via _class_to_role.
    """
    found: dict = {
        "logo": set(),
        "photo_bg": set(),
        "photo_grid": set(),
        "hero": set(),
        "video_poster": set(),
        "video": set(),
    }
    for class_attr, src in _DIV_IMG_RE.findall(html):
        role = _class_to_role(class_attr)
        if role:
            found[role].add(src)
    for class_attr, style_val in _DIV_BG_DOUBLE_RE.findall(html):
        m = _BG_URL_RE.search(style_val)
        if not m:
            continue
        role = _class_to_role(class_attr)
        if role:
            found[role].add(m.group(2))
    for class_attr, style_val in _DIV_BG_SINGLE_RE.findall(html):
        m = _BG_URL_RE.search(style_val)
        if not m:
            continue
        role = _class_to_role(class_attr)
        if role:
            found[role].add(m.group(2))
    for poster in _VIDEO_POSTER_RE.findall(html):
        found["video_poster"].add(poster)
    for src in _SOURCE_SRC_RE.findall(html):
        found["video"].add(src)
    return found
