# DrawingML Color Transform Reference

ECMA-376-1 5th ed. §20.1.2.3 — Color Transform Element Containers. Children of a color element (`a:srgbClr`, `a:schemeClr`, etc.) modify the resolved color **in document order**; a resolver must respect XML order, not a normalized canonical order.

## Per-transform spec

| transform | ECMA-376-1 § | space | formula (val ∈ [0, 100000]; v = val / 100000) |
|---|---|---|---|
| `<a:lumMod val="N"/>` | §20.1.2.3.20 | HSL — L | `L_new = L × v` |
| `<a:lumOff val="N"/>` | §20.1.2.3.21 | HSL — L | `L_new = clamp(L + v, 0, 1)` |
| `<a:satMod val="N"/>` | §20.1.2.3.34 | HSL — S | `S_new = clamp(S × v, 0, 1)` (val can exceed 100000) |
| `<a:tint val="N"/>` | §20.1.2.3.51 | RGB | `C_new = C × (1 − v) + 255 × v` per channel (blend toward white) |
| `<a:shade val="N"/>` | §20.1.2.3.31 | RGB | `C_new = C × v` per channel (val=100000 ⇒ no change; val<100000 darkens — confirms reverse-engineered behavior, NOT the literal spec wording) |
| `<a:alpha val="N"/>` | §20.1.2.3.1 | A channel | `A = v` (replaces; not multiplied) |
| `<a:hueMod val="N"/>` | §20.1.2.3.14 | HSL — H | `H_new = (H × v) mod 360` (UNUSED in P&G; verify before relying) |

**Note on `tint`/`shade` color space:** spec says HSL-luminance; PPT's actual implementation is the equivalent RGB blend above. Resolvers that do HSL get visibly different output for saturated colors. Use the RGB form.

## Compose order (within one color element)

XML document order of children. Typical authoring tool emission:
1. `tint` OR `shade` (mutually exclusive, but both legal)
2. `lumMod`
3. `lumOff`
4. `satMod`
5. `hueMod`
6. `alpha`

Order matters: `lumMod 75000 + lumOff 25000` ≠ `lumOff 25000 + lumMod 75000`. Resolver walks children sequentially.

## Worked example — P&G `accent1` + `lumMod 75000` + `lumOff 25000`

Real value from `ppt/theme/theme1.xml`: `accent1 = #156082`.

```
input          #156082         RGB (21, 96, 130)
                               HSL H=198.7° S=0.7219 L=0.2961

apply lumMod 75000   L = 0.2961 × 0.75    = 0.2221
apply lumOff 25000   L = 0.2221 + 0.25    = 0.4721
                               HSL H=198.7° S=0.7219 L=0.4721

output         #2199CF         RGB (33, 153, 207)
```

Net effect: takes the deep theme blue and lifts luminance ~+59% — produces a mid-cyan tint commonly used in PowerPoint's "Light Variant" auto-generated palette.

## Resolver invariants

- Convert RGB↔HSL via standard formula (Python `colorsys.rgb_to_hls` / `hls_to_rgb` — note `hls`, not `hsl`; L and S argument order is swapped from common convention).
- Clamp L and S to [0, 1] after every step. `satMod` allows val > 100000 which can push S past 1; clamp.
- `alpha` is a separate channel — never mixed into RGB; emit as `rgba()` in CSS.
- Output must round to nearest integer per RGB channel for hex emission. Python's `round()` uses banker's rounding; that matches PPT's apparent behavior empirically (no off-by-one drift observed against bundle references).


## Documented deviations from ECMA-376

ECMA-376-1 §20.1.2.3.31 (`shade`) and §20.1.2.3.51 (`tint`) describe these transforms in terms of HSL Luminance. PowerPoint does not implement them that way. Empirically, PPT applies a per-channel RGB blend — `shade` blends each RGB channel toward black (`C × v`), `tint` blends each RGB channel toward white (`C × (1−v) + 255 × v`) — which preserves hue exactly and produces visibly different output for saturated colors. This resolver matches the empirical PPT behavior, not the literal spec wording. The deviation is most visible at the dark end of the gamut: see `phase_1c/fixtures/synthetic_03`, which applies `shade 50000` to `#181020 (24,16,32)` and produces `#0C0810 (12,8,16)` — each RGB channel exactly halved. An HSL-Luminance implementation would compress luminance by 0.5 instead, yielding a different result and breaking visual round-trips against PPT-rendered references.
