"""LEARNINGS assertions for HenHouse (deck 8), plus this deck's invariants.

The layout-role assertions exist because two regressions in two passes came
from mobile rules competing for the same shape and the last one winning. The
role set below is the CONTRACT: if it changes, that must be a deliberate
instruction, not a side effect of adding a rule.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "out" / "henhouse"
fails = []


def check(cond, rule, msg):
    print(f"  {'PASS' if cond else 'FAIL'}  {rule:<10} {msg}")
    if not cond:
        fails.append(msg)


doc = (OUT / "index.html").read_text()
body = doc[doc.index("<body>"):]
sections = re.findall(r'<section class="slide" id="s(\d+)".*?</section>', body, re.S)
secs = re.findall(r'<section class="slide".*?</section>', body, re.S)

# ---- rule 22 / 30: the section set is fixed --------------------------------
print("\n== rule 22 / 30: section count ==")
N_SECTIONS = 52
check(len(secs) == N_SECTIONS, "22/30", f"{N_SECTIONS} section.slide elements")
check([int(i) for i in sections] == list(range(1, N_SECTIONS + 1)),
      "22/30", "ids sequential s1..s52 with none missing")
empty = [int(re.search(r'id="s(\d+)"', s).group(1)) for s in secs
         if not re.search(r"<img |<video |<span style=", s)]
check(not empty, "22/30", f"no section renders empty (offenders: {empty})")

# ---- one decision per shape ------------------------------------------------
print("\n== layout roles: one decision per shape ==")
ROLES = {"backdrop", "hidden", "split", "badge", "logo", "mark",
         "ground", "icon", "caption", "bleed", "flow"}
shapes = re.findall(r'<div class="sh[^"]*"([^>]*)>', body)
roled = [a for a in shapes if "data-role=" in a]
check(len(roled) == len(shapes), "roles",
      f"every .sh carries a data-role ({len(roled)}/{len(shapes)})")
seen = set(re.findall(r'data-role="([a-z]+)"', body))
check(seen <= ROLES, "roles", f"no unknown role emitted ({sorted(seen)})")
check(all(a.count("data-role=") == 1 for a in roled), "roles",
      "no shape carries two roles")
# every mobile box rule must key off a role, never off .sh by class
style = doc[doc.index("<style>"):doc.index("</style>")]
mq = style[style.index("@media (max-width:820px)"):]
desk = style[:style.index("@media (max-width:820px)")]
offenders = [sel.strip() for sel, decls in re.findall(r"([^{}]+)\{([^{}]+)\}", mq)
             if re.search(r"position:|margin-inline:|(?<!max-)width:", decls)
             and re.search(r"\.sh\.[a-z]", sel.split("/*")[-1]) and "data-role" not in sel
             and "::" not in sel and ".cropw" not in sel and ".backdrop" not in sel]
check(not offenders, "roles",
      f"no mobile box rule targets .sh by class instead of by role ({offenders[:3]})")

# ---- the full-bleed contract ----------------------------------------------
print("\n== full-bleed contract ==")
GROUND = [3, 10, 17, 19, 20, 22, 31, 35, 41, 43, 46, 47, 48]
BLEED = [6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 18, 21, 23, 24, 26, 27, 28, 29,
         30, 33, 34, 36, 37, 38, 39, 40, 42, 44, 49, 50, 51]
ground, bleed = [], []
for s in secs:
    n = int(re.search(r'id="s(\d+)"', s).group(1))
    rs = set(re.findall(r'data-role="([a-z]+)"', s))
    if rs & {"ground", "backdrop"}:
        ground.append(n)
    elif rs & {"bleed", "split"}:
        bleed.append(n)
check(ground == GROUND, "bleed",
      f"full-screen ground sections unchanged (got {ground})")
check(bleed == BLEED, "bleed", f"edge-to-edge sections unchanged (got {bleed})")
for n, lbl in ((10, "pop-up displays"), (31, "taco truck"), (46, "meat aisle")):
    check(n in ground, "bleed", f"s{n} ({lbl}) is full-bleed")

# ---- desktop must stay inert ----------------------------------------------
print("\n== desktop inertness ==")
# --bg-solid is deliberately consumed on BOTH breakpoints: rule 20 makes the
# slide background opaque at build time, so desktop must read it too. The
# mobile-only tokens are the layout ones.
for tok in ("data-role", "data-fit"):
    check(tok not in desk, "desktop", f"{tok} is never consumed outside the mobile query")

# ---- rule 20: a slide background is opaque at build time --------------------
print("\n== rule 20: slide-background alpha ==")
canvases = re.findall(r'<div class="canvas" style="([^"]*)"', body)
check(len(canvases) == N_SECTIONS, "20", f"{N_SECTIONS} canvases carry a background")
solids = [c for c in canvases if re.search(r"--bg-solid:#[0-9A-F]{6}", c)]
check(len(solids) == N_SECTIONS, "20",
      f"every canvas declares an opaque --bg-solid ({len(solids)}/{len(canvases)})")
# The consumed value must never carry alpha, on EITHER breakpoint. A slide
# background composites against the master background at build time; leaving
# rgba() lets whatever the page paints behind the canvas become the ground.
for label, blk in (("desktop", desk), ("mobile", mq)):
    used = re.findall(r"background:var\((--bg[a-z-]*)", blk)
    check(all(u == "--bg-solid" for u in used), "20",
          f"{label} .canvas composites the opaque value, not rgba ({used})")
translucent = [c for c in canvases
               if re.search(r"--bg-solid:rgba", c)]
check(not translucent, "20", "no --bg-solid carries an alpha channel")

print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
