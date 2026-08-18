"""Deck-archetype signal extraction — evidence pass, not the classifier itself.

Run this against a deck and report raw numbers. Do NOT hardcode a
corporate/creative threshold here — that gets calibrated only after
seeing real signal values from all five known decks side by side (see
PHASE_1C_ARCHITECTURE.md). Reports counts, not conclusions.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def extract_signals(pptx_path: str) -> dict:
    z = zipfile.ZipFile(pptx_path)
    slide_files = sorted(
        n for n in z.namelist()
        if n.startswith("ppt/slides/slide") and n.endswith(".xml")
    )

    total_shapes = 0
    total_runs = 0
    tab_runs = 0
    offcanvas_shapes = 0
    explicit_size_runs = 0
    explicit_color_runs = 0
    animated_slides = 0
    typefaces = set()

    for name in slide_files:
        root = ET.fromstring(z.read(name))
        if root.find(".//p:timing", NS) is not None:
            animated_slides += 1
        for sp in root.iter("{%s}sp" % NS["p"]):
            total_shapes += 1
            xfrm = sp.find(".//a:xfrm/a:off", NS)
            if xfrm is not None:
                x = int(xfrm.get("x", "0"))
                if x < 0:
                    offcanvas_shapes += 1
            for r in sp.findall(".//a:r", NS):
                total_runs += 1
                t = r.find("a:t", NS)
                if t is not None and t.text and "\t" in t.text:
                    tab_runs += 1
                rpr = r.find("a:rPr", NS)
                if rpr is not None:
                    if rpr.get("sz") is not None:
                        explicit_size_runs += 1
                    if rpr.find("a:solidFill", NS) is not None:
                        explicit_color_runs += 1
                    latin = rpr.find("a:latin", NS)
                    if latin is not None and latin.get("typeface"):
                        typefaces.add(latin.get("typeface"))

    n_slides = len(slide_files)
    return {
        "deck": Path(pptx_path).name,
        "n_slides": n_slides,
        "total_shapes": total_shapes,
        "total_runs": total_runs,
        "tab_positioned_runs": tab_runs,
        "tab_runs_pct_of_total": round(100 * tab_runs / max(total_runs, 1), 2),
        "offcanvas_shapes": offcanvas_shapes,
        "offcanvas_shapes_per_slide": round(offcanvas_shapes / max(n_slides, 1), 2),
        "explicit_size_override_pct": round(100 * explicit_size_runs / max(total_runs, 1), 2),
        "explicit_color_override_pct": round(100 * explicit_color_runs / max(total_runs, 1), 2),
        "distinct_typefaces": len(typefaces),
        "typeface_list": sorted(typefaces),
        "animated_slides": animated_slides,
    }


if __name__ == "__main__":
    import json
    result = extract_signals(sys.argv[1])
    print(json.dumps(result, indent=2))
