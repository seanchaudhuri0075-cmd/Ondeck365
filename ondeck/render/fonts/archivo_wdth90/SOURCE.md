# Archivo at wdth 90, wght 500-600 -- web subset for deck 11 (unilever_shpc)

Licence: SIL Open Font License 1.1 -- `OFL.txt` in this folder, byte-identical
to upstream's. Copyright 2020 The Archivo Project Authors
(https://github.com/Omnibus-Type/Archivo). The name table's copyright and
licence strings are kept in the subset.

| | |
|:--|:--|
| file | `Archivo-wdth90-wght500-600.woff2` -- 21,228 B, sha256 `6e9f1da647173f0641a37885ce011b4aeae10a1152c1ff66c87bd3485ceeb040` |
| source | `ofl/archivo/Archivo[wdth,wght].ttf` in github.com/google/fonts, Version 2.001, 658,596 B |
| source commit | google/fonts `ea9bc40cb0323afec81e7f1005453eea36f51708` (main, 2026-09-17); git blob `cc64253d36665a5ca0d6719cdf1e32b3de453b51`; sha256 `0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053`. The file itself last changed in google/fonts `6c70c829f09ea345d3590406693220ea35c6553f` (2021-02-04, "Archivo: Version 2.001 added"); upstream design source Omnibus-Type/Archivo `b5d63988ce19d044d3e10362de730af00526b672`. |
| axes | `wdth` pinned at 90 (removed); `wght` restricted to 500-600 (default 600) |
| glyphs | 229 codepoints: U+0020-007E, U+00A0-00FF, and common punctuation/signs incl. U+00D7, U+2011, U+2013/2014, U+2018/2019, U+2022, U+2212, U+221E |
| features | pyftsubset defaults: `kern`, `liga`, `locl`, `ccmp`, `frac`, `numr`, `dnom`, `rvrn` |
| tools | fontTools 4.60.2, brotli 1.2.0; built twice, byte-identical |

Why one variable file: two static instances (500, 600) came to 12,924 +
12,920 = 25,844 B; the single variable file is 21,228 B.

Why a separate file at all: `../Archivo-var.woff2` (Olay, deck 9) is
baselined byte-for-byte and its subset lacks `×`, U+2011 and `∞`, which deck
11 uses. It was not touched.

CSS: `@font-face{font-family:"Archivo wdth90"; font-weight:500 600;
src:url(...) format("woff2-variations")}` -- never `local()`.

## Recipe

    python3 build_archivo_wdth90.py "Archivo[wdth,wght].ttf" out/unilever_shpc/model.json <out dir>

```python
#!/usr/bin/env python3
"""Archivo at wdth 90, wght 500-600, as one web-subset variable woff2. Deck 11 step 12.

Source: google/fonts ofl/archivo/Archivo[wdth,wght].ttf (SIL OFL 1.1), fetched
at a pinned commit. Pipeline: subset (pyftsubset's default layout features, so
kern / liga / locl survive) -> instantiate -> woff2. `recalcTimestamp=False`
keeps head.modified at the source's value so the output is reproducible.

    python3 build_archivo_wdth90.py <Archivo[wdth,wght].ttf> <model.json> <out dir>
"""
import io
import json
import os
import sys

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

WDTH = 90
WEIGHTS = (500, 600)
OUT_NAME = "Archivo-wdth90-wght500-600.woff2"
MAPPED_FACES = ("SF Pro Semibold", "SF Pro Medium")   # the runs Archivo stands in for

# Basic Latin + Latin-1, then the punctuation and signs a deck revision is
# likely to reach for. U+2011 (non-breaking hyphen), U+00D7 and U+221E are IN
# this deck; U+2212 (minus) is not, and is included on Sean's instruction.
BASE = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) +
        [0x131, 0x152, 0x153, 0x2C6, 0x2DC] +
        list(range(0x2010, 0x2016)) + list(range(0x2018, 0x201F)) +
        [0x2020, 0x2021, 0x2022, 0x2026, 0x2030, 0x2032, 0x2033, 0x2039, 0x203A,
         0x2044, 0x20AC, 0x2122, 0x2190, 0x2191, 0x2192, 0x2193,
         0x2212, 0x221E, 0x2248, 0x2260, 0x2264, 0x2265])


def deck_chars(model_path):
    m = json.load(open(model_path))
    return {ord(ch) for s in m["slides"] for sh in s["shapes"]
            for p in sh.get("paras", []) for r in p["runs"]
            if r["typeface"] in MAPPED_FACES for ch in r["text"]}


def subset(font, unicodes):
    o = Options()
    o.name_IDs = ["*"]            # keep the copyright + licence strings
    o.name_languages = ["*"]
    o.notdef_outline = True
    o.recalc_timestamp = False
    s = Subsetter(o)
    s.populate(unicodes=sorted(unicodes))
    s.subset(font)
    return font


def save_woff2(font, path):
    font.flavor = "woff2"
    font.save(path)
    return os.path.getsize(path)


def main(src, model, out):
    os.makedirs(out, exist_ok=True)
    want = set(BASE) | deck_chars(model)
    have = set(TTFont(src).getBestCmap())
    missing = sorted(want & deck_chars(model) - have)
    assert not missing, "deck characters absent from upstream Archivo: %s" % missing
    want &= have
    sizes = {}
    # The brief: static 500 + 600, or ONE variable file restricted to those
    # axes, whichever is smaller. Measured: the variable file wins, so it is
    # what gets written; the statics are built in memory for the comparison.
    for w in WEIGHTS:
        f = subset(TTFont(src, recalcTimestamp=False), want)
        f = instantiateVariableFont(f, {"wdth": WDTH, "wght": w})
        buf = io.BytesIO()
        f.flavor = "woff2"
        f.save(buf)
        sizes["(static wght %d, not written)" % w] = len(buf.getvalue())
    f = subset(TTFont(src, recalcTimestamp=False), want)
    f = instantiateVariableFont(f, {"wdth": WDTH, "wght": (WEIGHTS[0], WEIGHTS[-1])})
    sizes[OUT_NAME] = save_woff2(f, os.path.join(out, OUT_NAME))
    for k, v in sizes.items():
        print("%8d  %s" % (v, k))
    print("codepoints in subset:", len(want))


if __name__ == "__main__":
    main(*sys.argv[1:4])
```
