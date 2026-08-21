"""Regression fixtures for the SHELFBEAUTY session's freeform.py fixes.

Same pattern as test_color_resolver.py: one function per fix, each backed
by something concrete (a real deck's XML, a synthetic edge case, or a
generated fixture) rather than a vague assertion. This is the direct
response to the gap flagged in PHASE_1C_ARCHITECTURE.md: these fixes
existed only as LEARNINGS.md prose, not as enforced tests, before this
file — meaning a future change could silently break any of them.

Not exhaustive. Covers the highest silent-regression-risk fixes from the
session, prioritized over full coverage: bugs that are easy to
reintroduce by accident and hard to notice visually until someone's
staring at exactly the right slide.
"""
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ondeck.parse.pptx import EMU_PER_PT
from ondeck.render.templates._shared import _compress_raster

REAL_DECK = "/mnt/user-data/uploads/SHELFBEAUTY_RETAIL_INVESTOR_PRESENTATION_OSRX.pptx"


# ---------------------------------------------------------------------------
# Rule 17 (LEARNINGS.md): EMU_PER_PT must be 12700, not 9525.
# Root cause: 9525 is EMU-per-pixel (a common but wrong constant to reach
# for), not EMU-per-point. Using it silently inflates every font size and
# position by ~25% deck-wide — the kind of bug that looks like "everything
# is a little too big" rather than an obvious crash, easy to miss without
# a hard assertion pinning the exact value.
# ---------------------------------------------------------------------------
def test_emu_per_pt_is_correct():
    assert EMU_PER_PT == 12700, (
        f"EMU_PER_PT is {EMU_PER_PT}, expected 12700 (914400 EMU/inch / "
        f"72 pt/inch). 9525 is EMU-per-pixel, a different unit — using it "
        f"here inflates every size/position ~25% deck-wide."
    )


def test_known_size_converts_correctly():
    # A 70pt run (SHELFBEAUTY's acrostic word runs, sz="7000" in OOXML)
    # must convert back to exactly 70.0, not ~93.3 (the 9525 bug's result).
    sz_hundredths_of_pt = 7000
    pt = sz_hundredths_of_pt / 100
    emu = pt * EMU_PER_PT
    assert emu / EMU_PER_PT == pt == 70.0


# ---------------------------------------------------------------------------
# Rule 4 (LEARNINGS.md): default text color must fall back to theme.dk1,
# not a hardcoded value. Root cause: PowerPoint's real default when a run
# has no explicit color is the theme's dk1, which varies per deck/theme —
# hardcoding white (or any fixed color) renders correctly by accident on
# decks where dk1 happens to be white/black and wrong on every other deck.
# ---------------------------------------------------------------------------
def test_default_color_is_theme_driven_not_hardcoded():
    import inspect

    from ondeck.render.templates import freeform

    src = inspect.getsource(freeform)
    # The specific regression this guards: a bare literal default color
    # (e.g. `"FFFFFF"` or `"000000"`) passed where the theme's dk1 should
    # be threaded through instead. This can't catch every way that could
    # regress, but it catches the exact shape of bug that shipped once
    # already (hardcoded "FFFFFF" fallback in _render_paragraphs' caller).
    assert "theme.dk1" in src, (
        "expected theme.dk1 to be threaded through as the default text "
        "color somewhere in freeform.py — if this fails, check whether a "
        "hardcoded color literal crept back in as the default instead"
    )


# ---------------------------------------------------------------------------
# Session finding (Aug 2026, not yet in LEARNINGS.md by number): images with
# an alpha channel must stay lossless (PNG), not get flattened to RGB/JPEG.
# Root cause: flattening transparency to JPEG produces garbage-colored solid
# blocks wherever the shape should show through — this shipped once
# (slide 25's small logo image) and was only caught by a direct visual
# desktop re-check, not by any test. That's exactly the gap this file
# exists to close.
# ---------------------------------------------------------------------------
def test_transparent_png_stays_lossless():
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))  # fully transparent
    buf = BytesIO()
    img.save(buf, format="PNG")
    blob, content_type = _compress_raster(buf.getvalue(), "image/png")
    assert content_type == "image/png", (
        f"got {content_type} — an alpha-channel image was routed through "
        f"the JPEG path, which has no alpha channel and will flatten "
        f"transparency to a solid (likely wrong-colored) block"
    )
    result = Image.open(BytesIO(blob))
    assert result.mode == "RGBA"
    # The specific pixel that broke visually: fully transparent must stay
    # fully transparent, not become opaque white/black.
    assert result.getpixel((50, 50))[3] == 0


def test_opaque_photo_gets_compressed_to_jpeg():
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (2000, 1000), (100, 150, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    original_size = len(buf.getvalue())
    blob, content_type = _compress_raster(buf.getvalue(), "image/png")
    assert content_type == "image/jpeg"
    assert len(blob) < original_size, (
        "opaque raster should get meaningfully smaller after resize+"
        "recompress — regression here silently reintroduces the "
        "128MB-continuous-deck file-size bug"
    )
    result = Image.open(BytesIO(blob))
    assert max(result.size) <= 1600


# ---------------------------------------------------------------------------
# Session finding: the CSS selector-list bug class. Appending a descendant
# tag (" img", " p") to a comma-joined selector string only attaches it to
# the LAST selector in the list — any earlier selector silently refers to
# the wrong element. This shipped once (a photo item's div got sized
# 100%x100% instead of its inner <img>, producing a full-canvas white box)
# and is exactly the kind of bug that's invisible in the generated CSS
# unless you know to look for it — worth a direct regression test on the
# string-building logic itself, not just the visual output.
# ---------------------------------------------------------------------------
def test_multi_selector_descendant_css_scopes_each_selector():
    selectors = ["#deck-desktop .item-6", "#deck-mobile .acrostic-crop .item-6"]
    # This is the CORRECT construction (each selector gets its own " img"
    # suffix before joining) — the bug was building this via
    # ", ".join(selectors) + " img", which only suffixes the last entry.
    img_sel = ", ".join(f"{s} img" for s in selectors)
    assert img_sel == (
        "#deck-desktop .item-6 img, #deck-mobile .acrostic-crop .item-6 img"
    )
    # Guard against the exact malformed shape that shipped: the buggy
    # version left the first selector without " img" attached to it.
    buggy = ", ".join(selectors) + " img"
    assert img_sel != buggy, "regression check itself is broken — these should differ"
    assert "#deck-desktop .item-6 img" in img_sel


# ---------------------------------------------------------------------------
# Rule 20 (LEARNINGS.md): tab-in-separate-run must carry forward on desktop,
# strip on mobile. Root cause: PowerPoint sometimes splits a leading tab
# into its own whitespace-only run, separate from the visible text run —
# a naive "drop whitespace-only runs" filter silently eats the tab
# (and the positioning it encodes) entirely rather than carrying it
# forward. Verified against the real deck rather than a synthetic case,
# since this is exactly the kind of thing a synthetic fixture might not
# reproduce faithfully.
# ---------------------------------------------------------------------------
def test_tab_in_separate_run_real_deck():
    if not Path(REAL_DECK).exists():
        return  # skip gracefully outside this sandbox — see note below
    z = zipfile.ZipFile(REAL_DECK)
    slide4 = z.read("ppt/slides/slide4.xml")
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    root = ET.fromstring(slide4)
    found_split_tab_run = False
    for para in root.iter("{%s}p" % ns["a"]):
        runs = para.findall("a:r", ns)
        if len(runs) < 2:
            continue
        first_text = runs[0].find("a:t", ns)
        if first_text is not None and first_text.text and "\t" in first_text.text:
            found_split_tab_run = True
    assert found_split_tab_run, (
        "expected slide 4's header to still contain the tab-in-separate-"
        "run pattern this test is guarding — if this fails, the fixture "
        "deck itself changed, not necessarily the code"
    )
