"""Assertions from LEARNINGS.md, run against the built deck.

Each check names the rule it enforces. This is the "stop rediscovering these"
half of the file being executable rather than prose.
"""
from __future__ import annotations

import json, re, sys
from collections import Counter
from pathlib import Path

OUT = Path("/Users/gif025/Downloads/ondeck-pipeline/out/olay")
RAW = Path("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline/4bbac21b-8daa-486f-8c5d-924b6e198861/scratchpad/olay/raw")

fails, warns = [], []
def check(cond, rule, msg):
    (fails if not cond else []).append(f"[{rule}] {msg}") if not cond else None
    print(f"  {'PASS' if cond else 'FAIL'}  {rule:<8} {msg}")

doc = (OUT / "index.html").read_text()
model = json.load(open(OUT / "model.json"))
imgman = json.load(open(OUT / "image_manifest.json"))
vidman = json.load(open(OUT / "video_manifest.json"))

print("\n== structure / editor contract ==")
slides = re.findall(r'<section class="slide"', doc)
check(len(slides) == 34, "editor", f'34 sections with class="slide" (found {len(slides)})')

# Editor parses with DOMParser and never runs JS: every media ref must be a
# literal attribute, not assigned later. Scan the body only — a CSS comment
# mentioning <img>/<video> is not a media element.
body_only = re.sub(r"<style\b.*?</style>", "", doc, flags=re.S)
imgs = re.findall(r"<img\b[^>]*>", body_only)
vids = re.findall(r"<video\b[^>]*>", body_only)
no_src = [t for t in imgs + vids if not re.search(r'\ssrc="[^"]+"', t)]
check(not no_src, "editor", f"every <img>/<video> carries a literal src ({len(imgs)} img, {len(vids)} video)")
check("data-src" not in doc and "javascript:" not in doc, "editor", "no deferred/JS-assigned sources")

# 22 authored blocks: 20 body (.ci/.cbi) + 2 titles (.L > .t). The 6 .fn
# blocks were the review stickers, so no .fn survives suppression.
harvest = re.findall(r'class="sh tx (ci|cbi|fn)"', doc) + re.findall(r'class="t"', doc)
check(len(harvest) == 20, "editor", f"20 editor-harvestable text blocks ({len(harvest)})")

print("\n== rule 6 / 7: assets extracted + content-addressed ==")
refs = set(re.findall(r'src="assets/([^"]+)"', doc)) | set(re.findall(r'poster="assets/([^"]+)"', doc))
missing = [r for r in refs if not (OUT / "assets" / r).exists()]
check(not missing, "6", f"all {len(refs)} referenced assets exist on disk ({missing[:3]})")
hashes = [v["sha"] for v in imgman.values()] + [v["sha"] for v in vidman.values()]
dupe = [h for h, c in Counter(hashes).items() if c > 1]
check(not dupe, "7", f"no two distinct assets share a content hash ({len(hashes)} assets)")
check(not list((OUT / "assets").glob("*.__partial.*")), "8", "no partial files in outputs")

print("\n== rule 9: type units ==")
type_units = re.findall(r"font-size:[^;\"]*", doc)
bad = [t for t in type_units if "vh" in t or ("vw" in t and "cqw" not in t)]
check(not bad, "9", f"no vh/vw font-size ({len(type_units)} declarations, all cqw/rem)")
check("container-type:size" in doc.replace(" ", ""), "9", "slide canvas declares container-type: size")

print("\n== review stickers: detection + opt-in suppression ==")
EXPECTED_STICKERS = [(9, "Rectangle 12"), (10, "Rectangle 5"), (10, "Rectangle 9"),
                     (21, "Rectangle 7"), (21, "Rectangle 8"), (22, "Rectangle 11")]
flagged = [(sl["n"], s["name"]) for sl in model["slides"] for s in sl["shapes"]
           if s["type"] == "text" and s.get("review_sticker")]
check(sorted(flagged) == sorted(EXPECTED_STICKERS), "sticker",
      f"exactly the 6 confirmed stickers match the signature (got {len(flagged)})")
sticker_text = ["".join(r["text"] for p in s["paras"] for r in p["runs"])
                for sl in model["slides"] for s in sl["shapes"]
                if s["type"] == "text" and s.get("review_sticker")]
leaked = sorted({t for t in sticker_text if t and t in doc})
check(not leaked, "sticker", f"no sticker text reaches the output ({leaked})")
# Guard the signature from drifting onto real captions.
non = [s for sl in model["slides"] for s in sl["shapes"]
       if s["type"] == "text" and not s.get("review_sticker")]
check(len(non) == 22, "sticker", f"22 non-sticker text blocks remain unflagged (got {len(non)})")

print("\n== occlusion + backdrop (mobile reflow correctness) ==")
occ = [(sl["n"], s["name"]) for sl in model["slides"] for s in sl["shapes"] if s.get("occluded")]
check(sorted(occ) == [(33, "Picture 35"), (33, "Picture 8"),
                      (33, "TextBox 33"), (33, "TextBox 4")], "occlusion",
      f"only slide 33's buried copy of slide 2 is occluded ({occ})")
# Slide 2 legitimately carries this banner; slide 33's buried copy must not.
cb = doc.count('alt="Creative Brief"')
check(cb == 1, "occlusion", f"'Creative Brief' banner appears exactly once, on slide 2 (found {cb})")
s33 = re.search(r'<section class="slide" id="s33".*?</section>', doc, re.S).group(0)
check("Creative Brief" not in s33, "occlusion", "slide 33 carries no 'Creative Brief' banner")
check("Focus on product-centric" not in s33, "occlusion",
      "slide 33 carries none of slide 2's buried body copy")
bpat = re.findall(r'id="s(\d+)"[^>]*data-backdrop', doc)
check(sorted(map(int, bpat)) == [2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 24, 33], "backdrop",
      f"backdrop slides tagged: {sorted(map(int,bpat))}")
# A backdrop must never be the only thing on a slide, and must be behind content.
check(doc.count('class="sh im tile backdrop"') + doc.count('class="sh rect backdrop"')
      + doc.count('class="sh bgimg backdrop"') >= 12, "backdrop",
      "backdrop layers emitted with the backdrop class")
css = re.search(r"<style\b.*?</style>", doc, re.S).group(0)
check("aspect-ratio:auto!important" in css.replace(" ", ""), "backdrop",
      "backdrops clear aspect-ratio (else they collapse to an aspect box)")
flat = css.replace(" ", "").replace("\n", "")
check("--th:min(58svh,520px)" in flat and "height:var(--th)!important" in flat, "strip",
      "Renders tiles sized by height from a single --th, so a whole render fits")
check("calc(var(--th)*var(--bl-ar)+var(--bl-px))" in flat, "strip",
      "strip ground panels are measured in the same --th as the tiles")
# Every strip slide must carry the ground custom properties, or a panel would
# fall back to a percentage of the 390px viewport and stop mid-scroll.
for sn in (4, 5, 6, 7):
    sec = re.search(rf'<section class="slide" id="s{sn}".*?</section>', doc, re.S).group(0)
    n_ground = len(re.findall(r'--bl-ar:', sec))
    check(n_ground == 2, "strip", f"slide {sn} emits both ground panels with span metrics ({n_ground})")

print("\n== rule 14: text emitted verbatim ==")
src_chars = 0
for sl in model["slides"]:
    for s in sl["shapes"]:
        if s["type"] == "text":
            if s.get("review_sticker"):
                continue          # intentionally suppressed, see above
            if s.get("occluded"):
                continue          # invisible in the source render; see above
            for p in s["paras"]:
                src_chars += sum(len(r["text"]) for r in p["runs"])
import html as _h
body_text = "".join(_h.unescape(m) for m in re.findall(r"<p[^>]*>([^<]*)</p>", doc))
body_text = body_text.replace("\xa0", "")
out_chars = len(body_text)
check(abs(out_chars - src_chars) <= 2, "14",
      f"deliverable text preserved: expected {src_chars} chars, output {out_chars}")
check(src_chars == 4051, "14",
      "deliverable total is 4051 (4874 authored - 240 sticker - 583 occluded)")

# Authored content that must survive verbatim, including its en-dash and typo.
check("Group shots in lifestyle \u2013 bathroom vanity luxury environments" in doc, "14",
      "authored caption preserved verbatim (en-dash intact)")
check("This looks too fake" not in doc, "14", "internal comment absent from deliverable")

print("\n== rule 4/5: z-order preserved ==")
ok = True
for sl in model["slides"]:
    sec = re.search(rf'<section class="slide" id="s{sl["n"]}".*?</section>', doc, re.S)
    if not sec: ok = False; break
    orders = [int(m) for m in re.findall(r"--o:(\d+);", sec.group(0))]
    if orders != sorted(orders): ok = False; break
check(ok, "4/5", "shapes emitted in source z-order on every slide")

print("\n== rule 1: media bound via rels ==")
vids_in_model = [s for sl in model["slides"] for s in sl["shapes"] if s["type"] == "video"]
check(len(vids_in_model) == 31, "1", f"31 videos bound by rId ({len(vids_in_model)} found)")
check(all(v.get("poster") for v in vids_in_model), "1", "every video carries its own poster rId")
both = [v for v in vids_in_model if v["video"] and v["poster"] and v["video"] != v["poster"]]
check(len(both) == 31, "1", "video and poster resolve to two distinct rIds")

print("\n== coverage map (rule 3) ==")
skipped = sum(len(c["skipped"]) for c in model["coverage"])
lockers = sum(c["design_lockers"] for c in model["coverage"])
emitted = sum(len(s["shapes"]) for s in model["slides"])
check(skipped == 0, "3", f"no unexplained skipped shapes (emitted={emitted}, true-lockers={lockers})")
unbound = {c["slide"]: c["unbound_rels"] for c in model["coverage"] if c["unbound_rels"]}
check(all(all(r.endswith(".wdp") for r in v) for v in unbound.values()), "3",
      f"only known-unrenderable rels unbound: {unbound}")

print("\n== weight ==")
img_b = sum(v["out_bytes"] for v in imgman.values())
vid_b = sum(v["out_bytes"] for v in vidman.values())
htm_b = len(doc.encode())
print(f"  html {htm_b/1e6:.2f}MB + images {img_b/1e6:.1f}MB + video {vid_b/1e6:.1f}MB "
      f"= {(htm_b+img_b+vid_b)/1e6:.1f}MB   (source pptx 746.7MB)")

print()
if fails:
    print(f"{len(fails)} FAILURES:")
    for f in fails: print("  -", f)
    sys.exit(1)
print("all assertions pass")
