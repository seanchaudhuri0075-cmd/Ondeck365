"""
Compute synthetic expected JSONs for Phase 1c fixture surface.

Outputs:
  phase_1c/fixtures/synthetic_01.expected.json
  phase_1c/fixtures/synthetic_02.expected.json
  phase_1c/fixtures/synthetic_03.expected.json

Run from the ondeck-pipeline directory:
  python3 compute_synthetic_expecteds.py
"""

import json
import colorsys
import os


def hex_of(rgb):
    return "#" + "".join(f"{int(round(c)):02X}" for c in rgb)


def to_hls(rgb):
    r, g, b = [c / 255.0 for c in rgb]
    return colorsys.rgb_to_hls(r, g, b)


def from_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255, g * 255, b * 255)


def apply_lumMod(rgb, val):
    v = val / 100000
    h, l, s = to_hls(rgb)
    l = max(0.0, min(1.0, l * v))
    return from_hls(h, l, s)


def apply_lumOff(rgb, val):
    v = val / 100000
    h, l, s = to_hls(rgb)
    l = max(0.0, min(1.0, l + v))
    return from_hls(h, l, s)


def apply_satMod(rgb, val):
    v = val / 100000
    h, l, s = to_hls(rgb)
    s = max(0.0, min(1.0, s * v))
    return from_hls(h, l, s)


def apply_tint(rgb, val):
    v = val / 100000
    return tuple(c * (1 - v) + 255 * v for c in rgb)


def apply_shade(rgb, val):
    v = val / 100000
    return tuple(c * v for c in rgb)


OPS = {
    "lumMod": apply_lumMod,
    "lumOff": apply_lumOff,
    "satMod": apply_satMod,
    "tint": apply_tint,
    "shade": apply_shade,
}

ACCENT1 = (0x15, 0x60, 0x82)


def trace(start_rgb, transforms, alpha=None, label_in="input"):
    rgb = start_rgb
    steps = [{"step": label_in, "rgb": [round(c, 3) for c in rgb], "hex": hex_of(rgb)}]
    for kind, val in transforms:
        rgb = OPS[kind](rgb, val)
        steps.append({"step": f"{kind} {val}", "rgb": [round(c, 3) for c in rgb], "hex": hex_of(rgb)})
    out = {
        "final_hex": hex_of(rgb),
        "steps": steps,
        "final_rgb_int": [int(round(c)) for c in rgb],
    }
    if alpha is not None:
        a = alpha / 100000
        out["final_alpha"] = a
        out["final_rgba"] = (
            "rgba("
            + str(int(round(rgb[0])))
            + ","
            + str(int(round(rgb[1])))
            + ","
            + str(int(round(rgb[2])))
            + ","
            + str(a)
            + ")"
        )
    return out, rgb


# === synthetic_01 ===
shape_side, intermed = trace(ACCENT1, [("shade", 80000)], label_in="accent1 #156082")
intermed_hex = hex_of(intermed)
theme_side, _ = trace(
    intermed,
    [("lumMod", 110000), ("satMod", 105000), ("tint", 67000)],
    label_in="phClr from shape-side " + intermed_hex,
)
syn1 = {
    "fixture": "synthetic_01.xml",
    "case": "shape-side mods composed with theme-side mods across fillRef (order-of-application case)",
    "scheme_color": "accent1 = #156082",
    "shape_side": {
        "transforms": [["shade", 80000]],
        "phase_label": "applied first; result becomes phClr for theme template",
        **shape_side,
    },
    "theme_side": {
        "template": "fmtScheme/fillStyleLst[2] stop 0",
        "transforms": [["lumMod", 110000], ["satMod", 105000], ["tint", 67000]],
        "phase_label": "applied second; consumes phClr from shape-side",
        **theme_side,
    },
    "final_hex": theme_side["final_hex"],
    "audit_chain": (
        "accent1 #156082 -> shade 80000 -> "
        + intermed_hex
        + " -> lumMod 110000 -> satMod 105000 -> tint 67000 -> "
        + theme_side["final_hex"]
    ),
}

# === synthetic_02 ===
syn2_trace, _ = trace(
    ACCENT1,
    [("lumMod", 50000), ("lumOff", 50000)],
    alpha=60000,
    label_in="accent1 #156082",
)
syn2 = {
    "fixture": "synthetic_02.xml",
    "case": "alpha + lumMod + lumOff stacked on accent1 (color-space crossings: RGB->HSL->RGB; alpha on separate channel)",
    "scheme_color": "accent1 = #156082",
    "transforms": [["lumMod", 50000], ["lumOff", 50000], ["alpha", 60000]],
    **syn2_trace,
    "audit_chain": (
        "accent1 #156082 -> lumMod 50000 -> "
        + syn2_trace["steps"][1]["hex"]
        + " -> lumOff 50000 -> "
        + syn2_trace["steps"][2]["hex"]
        + " -> alpha 60000 -> "
        + syn2_trace["final_rgba"]
    ),
}

# === synthetic_03 ===
NEARBLACK = (0x18, 0x10, 0x20)
syn3_trace, _ = trace(NEARBLACK, [("shade", 50000)], label_in="srgbClr #181020")
syn3 = {
    "fixture": "synthetic_03.xml",
    "case": "shade applied to a near-black color (RGB-blend-toward-black boundary; verifies non-HSL behavior)",
    "input_rgb": list(NEARBLACK),
    "input_hex": "#181020",
    "transforms": [["shade", 50000]],
    **syn3_trace,
    "audit_chain": (
        "#181020 (24,16,32) -> shade 50000 (x0.50 per RGB channel) -> "
        + syn3_trace["final_hex"]
        + " ("
        + ",".join(str(x) for x in syn3_trace["final_rgb_int"])
        + ")"
    ),
    "boundary_note": (
        "ECMA-376 wording suggests shade operates in HSL Luminance; PPT empirically performs RGB"
        " blend toward black. With v=0.5, each RGB channel halves, preserving hue exactly. Tests"
        " the deliberate deviation from spec at the dark end of the gamut."
    ),
}


# Write out the three expected JSON files
out_dir = "phase_1c/fixtures"
os.makedirs(out_dir, exist_ok=True)

for name, data in [("synthetic_01", syn1), ("synthetic_02", syn2), ("synthetic_03", syn3)]:
    path = os.path.join(out_dir, name + ".expected.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print("wrote", path)

print()
print("--- syn1:", syn1["audit_chain"])
print("--- syn2:", syn2["audit_chain"])
print("--- syn3:", syn3["audit_chain"])
