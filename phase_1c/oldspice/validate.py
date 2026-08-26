"""LEARNINGS assertions for deck 7, plus this deck's own invariants."""
from __future__ import annotations
import html as _h, json, re, sys
from collections import Counter
from pathlib import Path

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/oldspice")
fails = []
def check(cond, rule, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {rule:<9} {msg}")
    if not cond: fails.append(msg)

doc = (OUT / "index.html").read_text()
model = json.load(open(OUT / "model.json"))
man = json.load(open(OUT / "image_manifest.json"))
body_only = re.sub(r"<style\b.*?</style>", "", doc, flags=re.S)

print("\n== structure / editor contract ==")
check(len(re.findall(r'<section class="slide"', doc)) == 34, "editor", "34 sections with class=slide")
ids = re.findall(r'<section class="slide" id="s(\d+)"', doc)
check(ids == [str(i) for i in range(1, 35)], "editor", "ids sequential s1..s34")
imgs = re.findall(r"<img\b[^>]*>", body_only)
check(all(re.search(r'\ssrc="[^"]+"', t) for t in imgs) and imgs, "editor",
      f"every <img> carries a literal src ({len(imgs)})")
check("srcset" not in body_only and "<picture" not in body_only, "editor", "no srcset/<picture>")
check(doc.count('class="t"') == 34, "editor", f"34 headline hooks (.L > .t), one per slide")
nbody = len(re.findall(r'class="sh tx (cbi|sl)"', doc)) + doc.count('class="ci"')
check(nbody >= 25, "editor", f"body hooks present on the prose slides ({nbody})")

print("\n== rules 6 / 7: assets ==")
refs = set(re.findall(r'src="assets/([^"]+)"', doc))
check(all((OUT / "assets" / r).exists() for r in refs), "6", f"all {len(refs)} referenced assets exist")
svg = [v for v in man.values() if v["kind"] == "svg"]
check(len(svg) == 1 and any(r.endswith(".svg") for r in refs), "6",
      "SVG-only wordmark embedded as the actual vector, not rasterised")
h = [v["sha"] for v in man.values()]
check(len(set(h)) == len(h), "7", f"content-addressed, no hash collisions ({len(h)} assets)")
check(not list((OUT / "assets").glob("*.__partial.*")), "8", "no partial files")

print("\n== rule 9: type units ==")
sizes = re.findall(r"font-size:[^;\"]*", doc)
check(not [t for t in sizes if "vh" in t or ("vw" in t and "cqw" not in t)], "9",
      f"no vh/vw font-size ({len(sizes)} declarations)")
check("container-type:size" in doc.replace(" ", ""), "9", "canvas declares container-type: size")

print("\n== rule 13: colour transforms ==")
tbl = [s for sl in model["slides"] for s in sl["shapes"] if s["type"] == "table"][0]
cell = tbl["table"]["rows"][1]["cells"][2]
check(cell["paras"][0]["runs"][0]["color"] == "#808080", "13",
      "table body text resolves bg1+lumMod50% to #808080, not white")
ti = [s for sl in model["slides"] if sl["n"] == 3 for s in sl["shapes"] if s["type"] == "text"][0]
check(ti.get("fill") == "#AF000F" and ti.get("prst") == "ellipse", "13",
      "slide-3 title keeps its brand-red fill and ellipse geometry")
check("border-radius:50%" in doc, "13", "ellipse geometry emitted, not squared off")

print("\n== bullets ==")
src_bul = sum(1 for sl in model["slides"] for s in sl["shapes"]
              for p in (s["table"]["rows"] and [] if s["type"] == "table" else s.get("paras", []))
              if p.get("bullet"))
tbl_bul = sum(1 for r in tbl["table"]["rows"] for c in r["cells"]
              for p in c["paras"] if p.get("bullet") and
              "".join(x["text"] for x in p["runs"]).strip())
check(doc.count('class="li"') == tbl_bul + src_bul, "14",
      f"every bulleted paragraph renders its bullet ({tbl_bul + src_bul})")

print("\n== table + mobile transposition ==")
check(doc.count("<table>") == 1, "table", "desktop keeps one real <table>")
check(doc.count('class="card"') == 3, "table", "mobile gets 3 transposed variant cards")
check(len(re.findall(r"<t[hd]\b", doc)) >= 20, "table", "all 4x5 cells emitted")

print("\n== suppression rules ==")
st = [s["name"] for sl in model["slides"] for s in sl["shapes"] if s.get("review_sticker")]
check(st == [], "23", f"P&G review-sticker rule fires cleanly: {len(st)} matches")
occ = sorted((sl["n"], s["name"]) for sl in model["slides"] for s in sl["shapes"] if s.get("occluded"))
check(occ == [(15, "Content Placeholder 2"), (15, "Title 1"),
              (25, "Content Placeholder 2"), (25, "Title 1")], "24",
      f"occlusion limited to the buried Maldives copy on 15/25 ({len(occ)})")
# Slide 5 IS the Maldives key visual, so that copy belongs there exactly once.
# What must not happen is it resurfacing on 15 and 25, where it was buried.
n_mald = doc.count("Exclusive and secluded Island")
check(n_mald == 1, "24", f"Maldives copy appears once, on its own slide ({n_mald})")
for sn in (15, 25):
    sec = re.search(rf'<section class="slide" id="s{sn}".*?</section>', doc, re.S).group(0)
    check("Exclusive and secluded Island" not in sec, "24",
          f"slide {sn} does not reveal the buried Maldives copy")
check("Ipanema" in doc and "Red Rock Vistas" in doc, "24", "the visible Rio/Sedona copy survives")

print("\n== rule 14: text ==")
src = 0
for sl in model["slides"]:
    for s in sl["shapes"]:
        if s.get("occluded") or s.get("review_sticker"): continue
        if s["type"] == "text":
            src += sum(len(r["text"]) for p in s["paras"] for r in p["runs"])
        elif s["type"] == "table":
            src += sum(len(r["text"]) for row in s["table"]["rows"] for c in row["cells"]
                       for p in c["paras"] for r in p["runs"])
check(src == 2058, "14", f"deliverable text 2058 chars (2600 authored - 542 occluded) [{src}]")

print("\n== rules 3 / 4 / 5 ==")
sk = sum(len(c["skipped"]) for c in model["coverage"])
check(sk == 0, "3", f"no unexplained skipped shapes (lockers {sum(c['design_lockers'] for c in model['coverage'])})")
check(all(not c["unbound_rels"] for c in model["coverage"]), "3", "no unbound media rels")
ok = True
for sl in model["slides"]:
    sec = re.search(rf'<section class="slide" id="s{sl["n"]}".*?</section>', doc, re.S).group(0)
    o = [int(m) for m in re.findall(r"--o:(\d+);", sec)]
    if o != sorted(o): ok = False
check(ok, "4/5", "shapes emitted in source z-order on every slide")

print("\n== mobile treatment (rules 29 / 30 / 31) ==")
units = json.loads((OUT / "units.json").read_text())
multi = [k for k, v in units.items() if len(v["units"]) > 1]
solo = [k for k, v in units.items() if len(v["units"]) <= 1]
check(len(multi) == 15 and len(solo) == 9, "31",
      f"15 slides split into units, 9 correctly refused ({len(multi)}/{len(solo)})")
cells = sum(len(v["units"]) for v in units.values())
check(doc.count('class="unit"') == cells, "31",
      f"every detected unit emits a cell ({cells}), none invented")
srcs = set(re.findall(r'<div class="uf"[^>]*><img src="assets/([^"]+)"', doc))
check(srcs <= set(v["out"] for v in man.values()), "31",
      "unit cells reference existing assets — no new image files created")
check(doc.count("units carousel") == 15 and doc.count("units solo") == 9, "31",
      "carousels only where units were measured")
css_block = re.search(r"<style\b.*?</style>", doc, re.S).group(0)
flat = css_block.replace(" ", "").replace("\n", "")
check("overflow:hidden" in flat, "29", "crop frames clip (a crop scales ~5.5x past the frame)")
check("container-type:size" in flat and "min(100cqw" in flat, "29",
      "unit fit computed exactly, not via height+aspect-ratio")
# rule 30: the merge must not change what the editor sees
check(len(re.findall(r'data-arch="divider"', doc)) == 3, "30", "3 divider sections still present")
check(len(re.findall(r'<section class="slide"', doc)) == 34, "30",
      "merging changed no section count — editor still sees 34 slides")
check(doc.count('class="t"') == 34, "30", "all 34 headline hooks survive the merge")

# rule 32 + the unstretch decision
import sys as _sys; _sys.path.insert(0, "/Users/gif025/Downloads/ondeck-pipeline/phase_1c/oldspice")
from roles import KEEP_AUTHORED_STRETCH
check(KEEP_AUTHORED_STRETCH is False, "29",
      "mobile uses true source aspect — fill by scaling, never by distorting")
for sn in (4, 14, 24):
    sec = re.search(rf'<section class="slide" id="s{sn}"[^>]*>', doc).group(0)
    check('--dbg:' in sec, "32",
          f"slide {sn} carries its own ground for the merged title")
check("height:auto!important" in flat, "32",
      "merged title restates height:auto (a collapsed section zeroes percent heights)")
check(".sh.tx.L.t{align-self:flex-start;background:#FFFFFF" in flat
      or "background:#FFFFFF;padding:3px10px2px" in flat, "32",
      "key-visual label carries its own light ground (dark scrim cannot lift #AF000F)")
check("border-radius:0!important" in flat and "order:-1" in flat, "33",
      "slide-3 title drops its ellipse and leads the section on mobile")
t3 = [x for sl in model["slides"] if sl["n"] == 3 for x in sl["shapes"] if x["type"] == "text"][0]
check(t3.get("fill") == "#AF000F"
      and t3["paras"][0]["runs"][0]["color"] == "#FFFFFF", "33",
      "slide-3 title keeps its authored ground and text colour (white on white would be 1:1)")
check(".sh.rect.backdrop.rail{display:none}" in flat, "33",
      "only the partial-width rail is dropped; the full-canvas ground survives")
check("background:var(--dbg" in flat, "32",
      "merged title scrim comes from the source slide's background, not a literal")

print("\n== weight ==")
ab = sum(v["out_bytes"] for v in man.values())
print(f"  html {len(doc.encode())/1e6:.2f}MB + assets {ab/1e6:.2f}MB = "
      f"{(len(doc.encode())+ab)/1e6:.2f}MB   (source pptx 331.4MB)")
print()
if fails:
    print(f"{len(fails)} FAILURES"); [print("  -", f) for f in fails]; sys.exit(1)
print("all assertions pass")
