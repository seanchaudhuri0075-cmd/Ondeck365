"""
Tests for ondeck.parse.color.ColorResolver

Loads fixtures from phase_1c/fixtures/ and compares resolver output against
the expected JSON files.

Phase 1c covers:
    - synthetic_01: shape-side + theme-side fillRef composition (resolve_with_theme)
    - synthetic_02: schemeClr with lumMod + lumOff + alpha (resolve)
    - synthetic_03: srgbClr with shade on near-black; RGB-blend boundary (resolve)

Theme fixtures (theme_fillstyle_*) are a separate surface (gradient fill
definitions) and are NOT covered by ColorResolver. See NOTES.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ondeck.parse.color import ColorResolver, NS, parse_theme_xml

FIXTURES = Path(__file__).resolve().parent.parent / "phase_1c" / "fixtures"

# Theme used for all synthetic fixtures (accent1 = #156082 per fixture data)
THEME = {"accent1": "#156082"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_xml(name: str) -> ET.Element:
    return ET.parse(FIXTURES / name).getroot()


def _load_expected(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _approx_rgb(actual, expected, tol=0.01):
    """Compare two RGB float lists with a tolerance for floating-point noise."""
    assert len(actual) == len(expected), f"length mismatch: {actual} vs {expected}"
    for a, e in zip(actual, expected):
        assert abs(a - e) < tol, f"rgb mismatch: {actual} vs {expected}"


def _assert_steps_match(actual_steps, expected_steps):
    """Compare step lists field-by-field, with rgb tolerance."""
    assert len(actual_steps) == len(expected_steps), (
        f"step count mismatch: got {len(actual_steps)}, expected {len(expected_steps)}\n"
        f"actual: {actual_steps}\nexpected: {expected_steps}"
    )
    for i, (a, e) in enumerate(zip(actual_steps, expected_steps)):
        assert a["step"] == e["step"], f"step {i} label mismatch: {a['step']!r} vs {e['step']!r}"
        assert a["hex"] == e["hex"], f"step {i} hex mismatch: {a['hex']} vs {e['hex']}"
        _approx_rgb(a["rgb"], e["rgb"])


# ---------------------------------------------------------------------------
# synthetic_02: schemeClr + lumMod + lumOff + alpha
# ---------------------------------------------------------------------------

def test_synthetic_02_lummod_lumoff_alpha():
    xml = _load_xml("synthetic_02.xml")
    expected = _load_expected("synthetic_02.expected.json")

    resolver = ColorResolver(THEME)
    result = resolver.resolve(xml)

    assert result["final_hex"] == expected["final_hex"]
    assert result["final_rgb_int"] == expected["final_rgb_int"]
    assert result["final_alpha"] == expected["final_alpha"]
    assert result["final_rgba"] == expected["final_rgba"]
    assert result["audit_chain"] == expected["audit_chain"]
    _assert_steps_match(result["steps"], expected["steps"])


# ---------------------------------------------------------------------------
# synthetic_03: srgbClr + shade (RGB-blend boundary)
# ---------------------------------------------------------------------------

def test_synthetic_03_shade_near_black():
    xml = _load_xml("synthetic_03.xml")
    expected = _load_expected("synthetic_03.expected.json")

    resolver = ColorResolver(THEME)
    result = resolver.resolve(xml)

    assert result["final_hex"] == expected["final_hex"]
    assert result["final_rgb_int"] == expected["final_rgb_int"]
    _assert_steps_match(result["steps"], expected["steps"])


# ---------------------------------------------------------------------------
# synthetic_01: shape-side + theme-side composition (fillRef)
# ---------------------------------------------------------------------------

def test_synthetic_01_shape_and_theme_composition():
    root = _load_xml("synthetic_01.xml")
    expected = _load_expected("synthetic_01.expected.json")

    shape_side = root.find("test:shape-side", NS)
    theme_side = root.find("test:theme-side", NS)
    assert shape_side is not None and theme_side is not None

    # The shape-side fillRef wraps the schemeClr; pass the schemeClr directly
    shape_color = shape_side.find(".//{%s}schemeClr" % NS["a"])
    theme_color = theme_side.find("{%s}schemeClr" % NS["a"])

    resolver = ColorResolver(THEME)
    result = resolver.resolve_with_theme(shape_color, theme_color)

    # Top-level
    assert result["final_hex"] == expected["final_hex"]
    assert result["audit_chain"] == expected["audit_chain"]
    assert result["scheme_color"] == expected["scheme_color"]

    # Shape-side block
    assert result["shape_side"]["final_hex"] == expected["shape_side"]["final_hex"]
    assert result["shape_side"]["final_rgb_int"] == expected["shape_side"]["final_rgb_int"]
    assert result["shape_side"]["transforms"] == expected["shape_side"]["transforms"]
    _assert_steps_match(result["shape_side"]["steps"], expected["shape_side"]["steps"])

    # Theme-side block
    assert result["theme_side"]["final_hex"] == expected["theme_side"]["final_hex"]
    assert result["theme_side"]["final_rgb_int"] == expected["theme_side"]["final_rgb_int"]
    assert result["theme_side"]["transforms"] == expected["theme_side"]["transforms"]
    assert result["theme_side"]["template"] == expected["theme_side"]["template"]
    _assert_steps_match(result["theme_side"]["steps"], expected["theme_side"]["steps"])


# ---------------------------------------------------------------------------
# theme_demert_default_office: parse_theme_xml against a real PPT theme
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# theme_fillstyle_* : real theme gradient / solid fill definitions
#
# These fixtures use <a:schemeClr val="phClr"> with phClr resolved as
# accent1 = #156082 (same as the synthetic fixtures). resolve() looks the
# input color up in the theme, so phClr must be present in the theme dict.
#
# Note on the input step label: expected.json was produced by a separate
# fixture generator that labels the input "input (accent1)". ColorResolver
# labels the input from the schemeClr's val attribute ("phClr #156082"). The
# rgb/hex of the input agree; only the label string differs, so the input step
# is asserted by color (rgb + hex) and the transform steps are compared with
# _assert_steps_match (their labels and math match exactly).
# ---------------------------------------------------------------------------

# Resolver theme for the theme_fillstyle fixtures: phClr -> accent1 = #156082.
_FILLSTYLE_THEME = {**THEME, "phClr": THEME["accent1"]}


def _assert_stop_matches(result, expected_stop):
    """Compare a resolve() result against one expected gradient stop / solid fill.

    Asserts final_hex, the input color (rgb + hex; label format differs from
    the resolver — see module note), and the transform steps via
    _assert_steps_match.
    """
    assert result["final_hex"] == expected_stop["final_hex"]
    actual_input = result["steps"][0]
    expected_input = expected_stop["steps"][0]
    assert actual_input["hex"] == expected_input["hex"]
    _approx_rgb(actual_input["rgb"], expected_input["rgb"])
    _assert_steps_match(result["steps"][1:], expected_stop["steps"][1:])


def test_theme_fillstyle_0002_gradient_stops():
    """gradFill: 3 stops, each schemeClr(phClr) + lumMod/satMod/tint."""
    root = _load_xml("theme_fillstyle_0002.xml")
    expected = _load_expected("theme_fillstyle_0002.expected.json")

    resolver = ColorResolver(_FILLSTYLE_THEME)
    stops = root.findall(".//{%s}gs" % NS["a"])
    assert len(stops) == len(expected["stops"])

    for gs, expected_stop in zip(stops, expected["stops"]):
        color_el = gs.find("{%s}schemeClr" % NS["a"])
        result = resolver.resolve(color_el)
        assert int(gs.get("pos")) == expected_stop["pos"]
        _assert_stop_matches(result, expected_stop)


def test_theme_fillstyle_0003_gradient_stops():
    """gradFill: 3 stops, each schemeClr(phClr) with transforms per stop."""
    root = _load_xml("theme_fillstyle_0003.xml")
    expected = _load_expected("theme_fillstyle_0003.expected.json")

    resolver = ColorResolver(_FILLSTYLE_THEME)
    stops = root.findall(".//{%s}gs" % NS["a"])
    assert len(stops) == len(expected["stops"])

    for gs, expected_stop in zip(stops, expected["stops"]):
        color_el = gs.find("{%s}schemeClr" % NS["a"])
        result = resolver.resolve(color_el)
        assert int(gs.get("pos")) == expected_stop["pos"]
        _assert_stop_matches(result, expected_stop)


def test_theme_fillstyle_1002_solid_tint_satmod():
    """solidFill (flat shape, not stops): schemeClr(phClr) + tint + satMod."""
    xml = _load_xml("theme_fillstyle_1002.xml")
    expected = _load_expected("theme_fillstyle_1002.expected.json")

    resolver = ColorResolver(_FILLSTYLE_THEME)
    result = resolver.resolve(xml)

    _assert_stop_matches(result, expected)


def test_theme_fillstyle_1003_gradient_stops():
    """gradFill: 3 stops; stop[2] omits tint/lumMod (only shade + satMod)."""
    root = _load_xml("theme_fillstyle_1003.xml")
    expected = _load_expected("theme_fillstyle_1003.expected.json")

    resolver = ColorResolver(_FILLSTYLE_THEME)
    stops = root.findall(".//{%s}gs" % NS["a"])
    assert len(stops) == len(expected["stops"])

    for gs, expected_stop in zip(stops, expected["stops"]):
        color_el = gs.find("{%s}schemeClr" % NS["a"])
        result = resolver.resolve(color_el)
        assert int(gs.get("pos")) == expected_stop["pos"]
        _assert_stop_matches(result, expected_stop)


def test_parse_theme_xml_demert_default_office():
    """Real theme.xml extracted from a 2026 GIF deck (Office default scheme).

    Locks parse_theme_xml() behavior: all 12 standard scheme color names,
    sysClr (dk1/lt1) resolved via lastClr attribute.
    """
    xml = _load_xml("theme_demert_default_office.xml")
    expected = _load_expected("theme_demert_default_office.expected.json")

    result = parse_theme_xml(xml)

    assert result == expected["expected_theme_dict"]
