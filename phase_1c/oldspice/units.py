"""Detect separable product units inside a single product photograph.

Every plate slide in this deck is ONE image shape, so a mobile carousel can
only come from splitting a photograph. This does it WITHOUT creating new image
bytes: it measures where the transparent gutters are and emits crop windows,
which the renderer applies as CSS on the same asset — the technique Olay used
for its 7-badge sprite. Rule 6 (nothing recreated) and rule 7 (one asset, one
URL) both hold.

The signature is measured, not tagged: project alpha down each column, find
runs of fully-transparent columns, and treat those as gutters. Units that
overlap or share a shadow produce no full-height gutter and so return a single
run — which is exactly the right answer for them (the box dieline is one
connected object; the STICK+BOX and GROUP SHOT plates overlap). No slide needs
a hand-written rule.
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
from PIL import Image

RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/oldspice/raw/ppt/media")
OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")

# Two backgrounds appear in this deck and they need different measurements:
#
#   RGBA product shots — the units are separated by a SOFT GROUND SHADOW, not by
#     transparency. Alpha spans the full width, so an "is it transparent" test
#     finds one unit and is wrong. The product is opaque and the shadow is not,
#     so threshold high: alpha > 200 isolates product bodies and drops shadow.
#   RGB label artworks — no alpha channel at all; the gutters are literally
#     white. Measure distance from the corner background colour instead.
#
# Getting this wrong is silent: the first version tested alpha > 8 and reported
# zero splittable slides across the whole deck, which looked like a clean
# negative result rather than a broken probe.
ALPHA_OPAQUE = 200        # product body, above soft-shadow opacity
BG_DIST = 18              # colour distance counting as "not background"
MIN_INK = 0.005           # a gutter column carries under 0.5% ink
MIN_GUTTER_FRAC = 0.012   # and the gutter spans >=1.2% of image width
MIN_UNIT_FRAC = 0.06      # ignore specks narrower than 6% of image width


def _ink_profile(im):
    """Per-column fraction of pixels that are product rather than ground."""
    if im.mode in ("RGBA", "LA"):
        a = np.asarray(im.convert("RGBA").getchannel("A")).astype(int)
        return (a > ALPHA_OPAQUE).mean(axis=0), a > ALPHA_OPAQUE
    rgb = np.asarray(im.convert("RGB")).astype(int)
    corners = np.vstack([rgb[0, :5], rgb[-1, :5], rgb[0, -5:], rgb[-1, -5:]])
    bg = np.median(corners, axis=0)
    mask = np.abs(rgb - bg).max(axis=2) > BG_DIST
    return mask.mean(axis=0), mask


def detect(src: str) -> dict:
    im = Image.open(RAW / src)
    ink, mask = _ink_profile(im)
    H, W = mask.shape
    occupied = ink > MIN_INK
    if not occupied.any():
        return {"units": [], "why": "no content found"}

    # maximal runs of occupied columns
    runs, start = [], None
    for x, on in enumerate(occupied):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x)); start = None
    if start is not None:
        runs.append((start, W))

    runs = [(x0, x1) for x0, x1 in runs if (x1 - x0) >= MIN_UNIT_FRAC * W]
    # merge runs separated by a gutter narrower than the threshold
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) < MIN_GUTTER_FRAC * W:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(list(r) if False else (r[0], r[1]))
    merged = [tuple(r) for r in merged]

    rows = mask.any(axis=1)
    y0, y1 = int(rows.argmax()), int(H - rows[::-1].argmax())

    units = []
    for x0, x1 in merged:
        r = mask[:, x0:x1].any(axis=1)
        uy0, uy1 = int(r.argmax()), int(len(r) - r[::-1].argmax())
        units.append({"l": x0 / W, "r": 1 - x1 / W, "t": uy0 / H, "b": 1 - uy1 / H,
                      "w_px": x1 - x0, "h_px": uy1 - uy0})
    return {"units": units, "content": {"x": [int(merged[0][0]), int(merged[-1][1])],
                                        "y": [y0, y1]}, "why": None}


def main():
    model = json.load(open(OUT / "model.json"))
    sys.path.insert(0, str(Path(__file__).parent))
    from roles import archetype
    out = {}
    for sl in model["slides"]:
        if archetype(sl["n"]) != "plate":
            continue
        img = [s for s in sl["shapes"] if s["type"] == "image"][0]
        d = detect(img["poster"])
        out[str(sl["n"])] = {"src": img["poster"], **d}
    (OUT / "units.json").write_text(json.dumps(out, indent=1))
    multi = {k: v for k, v in out.items() if len(v["units"]) > 1}
    single = {k: v for k, v in out.items() if len(v["units"]) <= 1}
    print(f"plate slides analysed: {len(out)}")
    print(f"  splittable (>=2 units): {len(multi)}  -> {sorted(map(int, multi))}")
    print(f"  single object          : {len(single)}  -> {sorted(map(int, single))}")
    print()
    seen = set()
    for k, v in sorted(out.items(), key=lambda kv: int(kv[0])):
        if v["src"] in seen: continue
        seen.add(v["src"])
        n = len(v["units"])
        widths = ", ".join(f"{u['w_px']}x{u['h_px']}" for u in v["units"][:4])
        print(f"  s{k:<3} {v['src']:<13} {n} unit(s)  {widths}{'' if not v['why'] else '  ('+v['why']+')'}")


if __name__ == "__main__":
    main()
