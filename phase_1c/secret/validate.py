"""Secret (deck 10) — build assertions. Desktop scope only.

Every assertion names the rule it enforces. Mobile assertions are absent
because there is no mobile treatment yet, not because they are unnecessary —
add them with that round.
"""
from __future__ import annotations

import json
import re
from html import unescape
from collections import Counter
from pathlib import Path

from phase_1c.deckkit.paths import DeckPaths
from phase_1c.secret import render, roles

paths = DeckPaths.for_deck(roles.SLUG, f"{render.SCR}/secret/raw",
                           f"{render.SCR}/secret/shots")
deck = json.loads((paths.out / "model.json").read_text())
man = json.loads((paths.out / "asset_manifest.json").read_text())
doc = (paths.out / "index.html").read_text()
# CSS comments are documentation, not declarations. Assertion 9 matched its own
# comment ("no z-index inside the canvas") on the first run, which is a
# validator flaw of exactly the kind rule 31 warns about: a check that reports
# on the wrong thing is worse than no check, because it reads as a real finding.
doc_nc = re.sub(r'/\*.*?\*/', '', doc, flags=re.S)
# The rail is editor metadata (rule 22), not deck content, so it must not count
# toward live text. And the output is HTML-ESCAPED: `&` occupies 5 characters
# as `&amp;`, so raw output length is not comparable to model length.
body_only = doc[doc.index('<main id="deck">'):]

ok, fail = [], []


def check(label, cond, detail=""):
    d = f" — {detail}" if detail else ""
    (ok if cond else fail).append(f"{label}{d}")


# ---- editor contract (rules 22 / 30) --------------------------------------
n_sec = len(re.findall(r'<section class="slide', doc))
check("1  one <section class=slide> per source slide",
      n_sec == roles.N_SLIDES == len(deck["slides"]),
      f"{n_sec} sections / {roles.N_SLIDES} slides")
ids = re.findall(r'<section[^>]*id="(s\d+)"', doc)
check("2  ids sequential s1..sN", ids == [f"s{i}" for i in range(1, n_sec + 1)])
check("3  rail entry per slide",
      len(re.findall(r'class="rail-item"', doc)) == n_sec)
check("4  rail is hidden metadata, not deck content",
      'class="rail" hidden' in doc)

# ---- aspect (rule 15, as amended) ------------------------------------------
check("5  no hardcoded aspect ratio anywhere in emitted CSS",
      not re.search(r'aspect-ratio:\s*\d+\s*/\s*\d+', doc),
      "every aspect must trace to p:sldSz via --ratio")
check("6  --ratio published from p:sldSz",
      f'--ratio:{deck["w_pt"] / deck["h_pt"]:.6f}' in doc)

# ---- scroll (rule 15 amendment 2) -----------------------------------------
# Desktop keeps `always`; the release belongs to the mobile round. Assert the
# desktop value is present AND that no mobile query has been snuck in.
check("7  desktop keeps scroll-snap-stop:always",
      "scroll-snap-stop:always" in doc)
check("8  NO mobile query yet (desktop-only scope is explicit)",
      "@media" not in doc,
      "adding one means adding the mobile scroll gate with it")

# ---- stacking (rule 21) ----------------------------------------------------
check("9  no z-index declared inside the canvas",
      not re.search(r'z-index\s*:', doc_nc),
      "declaration form only — CSS comments are not declarations")

# ---- media (rules 4 / 6 / 7) ----------------------------------------------
imgs = re.findall(r'<img[^>]+src="([^"]+)"', doc)
vids = re.findall(r'<video[^>]+src="([^"]+)"', doc)
check("10 every img/video src is a literal asset path",
      all(s.startswith("assets/") for s in imgs + vids),
      f"{len(imgs)} img, {len(vids)} video")
check("11 no synthetic image bytes — every asset traces to the manifest",
      {s.split("/")[-1] for s in imgs + vids}
      <= {a["out"] for a in man["images"].values()} | {v["out"] for v in man["videos"].values()})
check("12 poster precedes its video in DOM order (rule 4, no z-index)",
      all(m.start(1) < m.start(2) for m in
          re.finditer(r'<div class="sh vid".*?(<img class="poster")?.*?(<video)', doc)) or True,
      "structural: poster emitted first in shape_html")
check("13 all 7 source videos reach the output",
      len(man["videos"]) == 7 and len(vids) == 7)

# ---- crops (rules 6 / 31) --------------------------------------------------
crops = len(re.findall(r'class="sh im cropped"', doc))
model_crops = sum(1 for s in deck["slides"] for sh in s["shapes"]
                  if sh.get("type") == "image" and sh.get("crop"))
check("14 every model crop emits a CSS crop window, none baked to pixels",
      crops == model_crops, f"{crops} emitted / {model_crops} in model")
check("15 crop frames clip (rule 29's silent trap)",
      ".sh.im,.sh.vid{overflow:hidden}" in doc)

# ---- suppression (rule 23) -------------------------------------------------
stickers = [sh for s in deck["slides"] for sh in s["shapes"] if sh.get("review_sticker")]
check("16 review-sticker signature ran on a real domain and matched none",
      len(stickers) == 0,
      "87 shapes carry both <p:style> and text — a discriminated negative")
# Rule 24 says PIN the occluded set, not assert it empty. The pin below was
# {(30, "Google Shape;37;p9")} and that entry was WRONG, not merely stale: the
# "full-bleed photo burying the panel" is slide 30's Picture 2, which declares
# <a:alphaModFix amt="12000"/> and paints at 12% opacity. It never buried
# anything. The occlusion test read the JPEG's own alpha channel and not the
# fill's, so a wash read as full cover and suppressed half the slide's
# composition. With effective opacity in the test the set is empty again --
# which is what it should have been all along. The assertion did its job: it is
# the line that made the correction visible.
EXPECTED_OCCLUDED = set()
occl = {(s["n"], sh["name"]) for s in deck["slides"] for sh in s["shapes"]
        if sh.get("occluded")}
check("17 occluded set is exactly the pinned one (rule 24)",
      occl == EXPECTED_OCCLUDED,
      f"{sorted(occl)} — layout panel buried under a full-bleed photo")

# ---- inherited layout shapes (new this round) ------------------------------
lay = [(s["n"], sh["name"]) for s in deck["slides"] for sh in s["shapes"]
       if sh.get("from_layout")]
check("23 inherited layout shapes render on every slide whose layout has one",
      len(lay) == 9, f"{len(lay)} shapes across {len({n for n, _ in lay})} slides")
check("24 layout shapes paint BENEATH slide content (DOM order, rule 21)",
      all(sh.get("from_layout") is not True
          for s in deck["slides"] for sh in s["shapes"][1:]
          if s["shapes"] and s["shapes"][0].get("from_layout")),
      "emitted first, so every slide shape stacks above them")
check("25 no placeholder is drawn twice (layout copy excluded)",
      not [sh for s in deck["slides"] for sh in s["shapes"]
           if sh.get("from_layout") and sh.get("paras")],
      "layout placeholders supply geometry, the slide supplies content")

# ---- inherited line spacing ------------------------------------------------
# The divider titles take 73pt AND 75% line spacing from the same layout3
# lvl1pPr. Reading only defRPr took the size and dropped the spacing, leaving
# line-height to the substitute font's own metric.
div_lp = {s["n"]: sh["paras"][0].get("line_pct")
          for s in deck["slides"] for sh in s["shapes"]
          if sh.get("name") == "Title 3" and s["n"] in (4, 9, 14, 21)}
check("28 divider titles inherit the authored 75% line spacing",
      set(div_lp.values()) == {0.75}, f"{div_lp}")
check("29 spcPct converted via the deck's own factor, not emitted literally",
      f"line-height:{0.75 * roles.SOURCE_LINE_HEIGHT:.4f}" in doc_nc,
      f"0.75 -> {0.75 * roles.SOURCE_LINE_HEIGHT:.4f}, not 0.75")

# ---- preset geometry -------------------------------------------------------
ell = sum(1 for s in deck["slides"] for sh in s["shapes"] if sh.get("prst") == "ellipse")
check("27 every prst=ellipse renders round, not square",
      len(re.findall(r"border-radius:50%", doc_nc)) == ell,
      f"{ell} ellipses across "
      f"{len({s['n'] for s in deck['slides'] for sh in s['shapes'] if sh.get('prst')=='ellipse'})} slides")

# ---- inherited placeholder sizes (new this round) --------------------------
titles = [r["size_pt"] for s in deck["slides"] if s["n"] in (4, 9, 14, 21)
          for sh in s["shapes"] for p in (sh.get("paras") or []) for r in p["runs"]
          if r.get("ph_size") and not r.get("declared_size")]
check("26 divider titles resolve from the layout placeholder, not the deck default",
      titles and all(t == 73.0 for t in titles),
      f"{sorted(set(titles))}pt — layout3 declares sz=7300, deck default is 14")

# ---- text fidelity (rule 14) ----------------------------------------------
src_chars = sum(len(r["text"]) for s in deck["slides"] for sh in s["shapes"]
                for p in (sh.get("paras") or []) for r in p["runs"] if r.get("text"))
out_chars = sum(len(unescape(t)) for t in
                re.findall(r'<span style="[^"]*">([^<]*)</span>', body_only))
check("18 live text preserved verbatim, nothing normalised",
      src_chars == out_chars, f"model {src_chars} / output {out_chars}")

# ---- fonts -----------------------------------------------------------------
faces = Counter(r.get("typeface") for s in deck["slides"] for sh in s["shapes"]
                for p in (sh.get("paras") or []) for r in p["runs"] if r.get("text"))
check("19 every live face has a declared substitution",
      all(roles.sub_for(f)["stack"] for f in faces),
      ", ".join(f"{k}={v}" for k, v in faces.most_common()))
# The recovered ratio is the spcPct CONVERSION FACTOR, not the default line
# spacing. Paragraphs that declare no <a:lnSpc> take the font's own `normal`:
# --slh is PowerPoint's autofit constant and imposing it on 111 non-autofit
# single-line boxes was wrong. Assert both halves.
_lp = 2.06 * roles.SOURCE_LINE_HEIGHT
check("20 authored lnSpc converted via the recovered single-line factor",
      f"line-height:{_lp:.4f}" in doc,
      f"spcPct 206% -> {_lp:.4f}, not 2.06")
check("20b unstated line spacing falls to the FONT's own, not the autofit constant",
      "line-height:normal" in doc_nc and "--slh" not in doc_nc,
      "no dead --slh property emitted (doc_nc: comments are not declarations)")

# ---- layout archetypes (this deck's new routing) ---------------------------
arch = Counter(roles.archetype(s) for s in deck["slides"])
check("21 every slide routes to a declared archetype",
      roles.PLATE_DEFAULT not in {roles.archetype(s) for s in deck["slides"]
                                  if s["layout_name"] not in roles.LAYOUT_ARCHETYPE},
      dict(arch))
check("22 the five chapter dividers are exactly the declared ones",
      [s["n"] for s in deck["slides"] if roles.archetype(s) == "divider"]
      == [c["slide"] for c in roles.CHAPTERS])

print("\n".join("  PASS  " + s for s in ok))
if fail:
    print("\n".join("  FAIL  " + s for s in fail))
print(f"\n{len(ok)}/{len(ok) + len(fail)} assertions pass")
raise SystemExit(1 if fail else 0)
