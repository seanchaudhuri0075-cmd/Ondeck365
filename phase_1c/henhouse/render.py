"""HenHouse (deck 8) renderer — single-DOM dual build.

Rule 22: exactly ONE <section class="slide"> per source slide. Desktop is the
pixel-faithful 16:9 canvas (absolute %, type in cqw). Mobile is the same DOM
switched to flow layout in CSS, with per-shape `order`, so the editor sees 52
sections at any viewport and every live string exists exactly once.

Rule 21: nothing inside the canvas carries a z-index — paint order is DOM
order, which is source z-order.

The mobile ORDER is derived, not tagged: shapes sort by (row band, x). On the
13 brochure slides that turns side-by-side columns into stacked bands in
reading order without a per-slide rule, which is the whole point — the columns
are peers, and their reading order on the canvas is left-to-right.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ondeck.parse.font_calibration import (
    classify_substitution, family_and_weight, normalize_typeface,
    MATCHED_METRIC_SUBS, MATCHED_METRIC_AXES, SOURCE_LINE_HEIGHT_RATIOS,
)
from ondeck.render.fonts import font_face_css
from phase_1c.deckkit import css as dkcss
from phase_1c.deckkit.paths import DeckPaths
from phase_1c.henhouse import roles

E = lambda s: html.escape(s, quote=True)

# Weight names PowerPoint expresses as a face rather than a b flag (rule 11).
_WEIGHT_FALLBACK = {100: 100, 200: 200, 300: 300, 400: 400, 500: 500,
                    600: 600, 700: 700, 800: 800, 900: 900}


def font_for(run) -> tuple[str, int]:
    """(css font-family stack, weight) for a run — rule 10/11.

    Weight comes from the typeface NAME first ("Gotham Black" is weight 900 as
    a face, not as a b flag) and only then from b="1".
    """
    face = run.get("declared_face")
    fam, wt = family_and_weight(face)
    cls = classify_substitution(face)
    if face and cls == "matched":
        sub = MATCHED_METRIC_SUBS.get(normalize_typeface(face)) or MATCHED_METRIC_SUBS.get(fam)
        if sub == "montserrat":
            stack = roles.DISPLAY_STACK
        else:
            stack = roles.BODY_STACK
    else:
        stack = roles.BODY_STACK
    weight = wt or (700 if run.get("bold") else 400)
    if run.get("bold") and wt and wt < 700:
        weight = max(weight, 700)
    return stack, _WEIGHT_FALLBACK.get(weight, weight)


def cell_run_css(r, W) -> str:
    """Inline run style for a table cell. Quoted family names in the stack make
    escaping at the attribute boundary mandatory -- see callers."""
    stack, weight = font_for(r)
    sz = (r.get("size_pt") or 18) / W * 100.0
    return (f"font-family:{stack};font-weight:{weight};"
            f"font-size:{sz:.4f}cqw;color:{r.get('color') or 'inherit'};"
            f"--ms:{roles.mobile_rem(r.get('size_pt'))}")


def line_ratio(run) -> float:
    face = run.get("declared_face")
    fam, _ = family_and_weight(face)
    return (SOURCE_LINE_HEIGHT_RATIOS.get(normalize_typeface(face) or "")
            or SOURCE_LINE_HEIGHT_RATIOS.get(fam or "")
            or SOURCE_LINE_HEIGHT_RATIOS.get("aptos", 1.2132))


def rgba(hexv, alpha):
    if not hexv:
        return None
    h = hexv.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if alpha is None or alpha >= 1.0:
        return f"#{h.upper()}"
    return f"rgba({r},{g},{b},{round(alpha,4)})"


def composite(hexv, alpha, master):
    """Rule 20: a slide background's alpha composites over the MASTER
    background, not over the page. Emitting rgba() lets the page's own #111
    show through -- slide 1 lands on #1B1C14 and its black title measures
    1.22:1 instead of 19.48:1 on the correct #F6F7F0."""
    if not hexv:
        return None
    if alpha is None or alpha >= 1.0:
        return "#" + hexv.lstrip("#").upper()
    f = [int(hexv.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(master.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


def grad_css(g):
    stops = ", ".join(f"{rgba(s['hex'], s['alpha'])} {round(s['pos']*100,2)}%"
                      for s in g["stops"])
    if g.get("kind") == "radial":
        c = g.get("center") or {}
        cx = round((c.get("l", 0.5) + (1 - c.get("r", 0.5))) / 2 * 100, 1)
        cy = round((c.get("t", 0.5) + (1 - c.get("b", 0.5))) / 2 * 100, 1)
        return f"radial-gradient(circle at {cx}% {cy}%, {stops})"
    # OOXML measures the angle clockwise from +x; CSS measures from +y.
    ang = (g.get("angle_deg", 0.0) + 90.0) % 360.0
    return f"linear-gradient({round(ang,2)}deg, {stops})"


# ---------------------------------------------------------------- shape emit
def order_key(sh, band=6.0):
    """Reading order: banded by y, then by x. The band tolerance keeps a row of
    columns together when their tops differ by a few points."""
    return (round((sh["y"] or 0) / band), round(sh["x"] or 0, 1))


def _vspan(sh):
    y = sh.get("y") or 0.0
    return (y, y + (sh.get("h") or 0.0))


def _hspan(sh):
    x = sh.get("x") or 0.0
    return (x, x + (sh.get("w") or 0.0))


def side_by_side(a, b) -> bool:
    """The BROCHURE signature: overlaps vertically, disjoint horizontally.

    This is the measured property the BROCHURE set was derived from -- two
    shapes that a 390px viewport cannot hold beside each other.
    """
    ay0, ay1 = _vspan(a); by0, by1 = _vspan(b)
    if min(ay1, by1) - max(ay0, by0) <= 0:
        return False
    ax0, ax1 = _hspan(a); bx0, bx1 = _hspan(b)
    return ax1 <= bx0 or bx1 <= ax0


def _has_text(sh) -> bool:
    return any(r.get("text") for p in sh.get("paras", []) or [] for r in p["runs"])


def _area(sh) -> float:
    return max(0.0, sh.get("w") or 0.0) * max(0.0, sh.get("h") or 0.0)


def _covered(g, sh) -> float:
    """Fraction of `sh`'s area lying inside `g`."""
    a = _area(sh)
    if not a:
        return 0.0
    gx0, gy0 = g.get("x") or 0.0, g.get("y") or 0.0
    gx1, gy1 = gx0 + (g.get("w") or 0.0), gy0 + (g.get("h") or 0.0)
    sx0, sy0 = sh.get("x") or 0.0, sh.get("y") or 0.0
    sx1, sy1 = sx0 + (sh.get("w") or 0.0), sy0 + (sh.get("h") or 0.0)
    return (max(0.0, min(gx1, sx1) - max(gx0, sx0))
            * max(0.0, min(gy1, sy1) - max(gy0, sy0))) / a


# A shape counts as sitting ON a decorative ground at this coverage. Measured,
# not picked: across the 13 brochure slides the only two grounds cover their
# real members at 45.6-100% and merely graze everything else at 1.3-2.6%. Any
# threshold in that 17x gap gives the same partition.
GROUND_COVER = 0.25


def clique_rows(shapes, banded):
    """Rows of side-by-side shapes. A row is a CLIQUE, not a connected
    component: chaining A|B with B|C merges bands whose members overlap."""
    idx = sorted((i for i in range(len(shapes)) if banded[i]),
                 key=lambda i: (_vspan(shapes[i])[0], _hspan(shapes[i])[0]))
    rows: list[list[int]] = []
    for i in idx:
        for r in rows:
            if all(side_by_side(shapes[i], shapes[j]) for j in r):
                r.append(i)
                break
        else:
            rows.append([i])
    return rows


def ground_groups(shapes, banded):
    """{ground index: [members]} -- a filled, textless, non-backdrop shape and
    everything sitting on it. Rule 33: on mobile the geometry is dropped and
    only the fill is carried, so the ground and its riders must band together."""
    out = {}
    for gi, g in enumerate(shapes):
        if not banded[gi] or _has_text(g):
            continue
        # A rotated shape's axis-aligned box is not its painted area, so it
        # cannot be tested for containment. Slide 24's trapezoid (rot 270) has
        # a box straddling the heading and the left image while painting over
        # neither; admitting it invents a ground that does not exist.
        if g.get("rot"):
            continue
        if not (g.get("fill") or g.get("grad")):
            continue
        mem = [i for i in range(len(shapes))
               if i != gi and banded[i] and _covered(g, shapes[i]) >= GROUND_COVER]
        if mem:
            out[gi] = mem
    return out


def _content_paras(sh):
    return [i for i, p in enumerate(sh.get("paras", []) or [])
            if any(r.get("text") for r in p["runs"])]


def alternating_list(sh) -> bool:
    """A list whose items sit at EVEN paragraph indices with blank spacer
    paragraphs between them -- PowerPoint's way of leading a column so it lines
    up with the column beside it. Two such columns are a paired list."""
    idx = _content_paras(sh)
    if len(idx) < 2 or any(i % 2 for i in idx):
        return False
    blank = set(range(len(sh.get("paras", []) or []))) - set(idx)
    return all(j in blank for j in range(1, max(idx), 2))


def pair_bands(shapes, rows, n):
    """{band: (term index, description index)} for paired-list bands.

    Signature: a row of exactly two text shapes, both leading their items on
    even paragraph indices. The leftmost column is the term. Measured across
    the deck this matches one band and nothing else -- slides 2, 18 and 31 are
    also two-shape rows but carry prose, with neither the alternating structure
    nor equal item counts.
    """
    out = {}
    for r, mem in enumerate(rows):
        if len(mem) != 2 or not all(_has_text(shapes[i]) for i in mem):
            continue
        if not all(alternating_list(shapes[i]) for i in mem):
            continue
        a, b = sorted(mem, key=lambda i: shapes[i].get("x") or 0.0)
        na, nb = len(_content_paras(shapes[a])), len(_content_paras(shapes[b]))
        if na != nb:
            raise ValueError(
                f"slide {n}: paired-list columns do not zip -- "
                f"{na} items at x={shapes[a].get('x'):.1f} vs "
                f"{nb} at x={shapes[b].get('x'):.1f}. The pairing is by item "
                f"index, so an unequal count would silently mis-pair.")
        out[r] = (a, b)
    return out


def _all_bold(sh) -> bool:
    runs = [r for pp in sh.get("paras", []) or [] for r in pp["runs"] if r.get("text")]
    return bool(runs) and all(r.get("bold") for r in runs)


def staggered(a, b) -> bool:
    """Overlaps horizontally, does NOT overlap vertically -- the exact inverse
    of side_by_side(). A staggered pair is a horizontal sequence, not a row."""
    ay0, ay1 = _vspan(a); by0, by1 = _vspan(b)
    if min(ay1, by1) - max(ay0, by0) > 0:
        return False
    ax0, ax1 = _hspan(a); bx0, bx1 = _hspan(b)
    return min(ax1, bx1) - max(ax0, bx0) > 0


def lockup_groups(shapes, ids):
    """{band: [members, in x order]} -- a staggered run of BOLD shapes.

    Bold is the separator. On slide 25 the display words and the small word
    between them are all bold; the meal list sharing their ground is not, and
    is otherwise indistinguishable from the small word (same colour #FFFFFF,
    same inherited face, 14pt against 16pt). Bold is one authored property and
    generalises better than counting paragraphs.
    """
    out = {}
    for b in {i for i in ids if i is not None}:
        cand = [i for i in range(len(shapes))
                if ids[i] == b and _has_text(shapes[i]) and _all_bold(shapes[i])]
        if len(cand) < 2:
            continue
        seen, groups = set(), []
        for i in cand:
            if i in seen:
                continue
            grp = {i}
            grew = True
            while grew:
                grew = False
                for j in cand:
                    if j not in grp and any(staggered(shapes[j], shapes[k]) for k in grp):
                        grp.add(j)
                        grew = True
            seen |= grp
            if len(grp) > 1:
                groups.append(grp)
        if groups:
            big = max(groups, key=len)
            out[b] = sorted(big, key=lambda i: shapes[i].get("x") or 0.0)
    return out


# A gallery header labels the image it sits on: horizontally over it, and
# aligned to its top edge or resting just above. Measured deck-wide this
# separates slides 19/20/21 from the prose blocks on 16/17/18/43, which sit
# 5-6% of canvas height INSIDE their plate image rather than on its edge.
HDR_EDGE = 0.025      # header top within this much of the image top
HDR_GAP = 0.05        # or header bottom this far above the image top
HDR_OVER = 0.60       # this much of the header's width lies over the image


def gallery_headers(shapes, banded, H):
    """{image index: [header indices, in x order]}."""
    out = {}
    imgs = [i for i, sh in enumerate(shapes)
            if banded[i] and sh.get("type") == "image"]
    for ti, t in enumerate(shapes):
        if not banded[ti] or not _has_text(t):
            continue
        tx0, tx1 = _hspan(t); ty0, ty1 = _vspan(t)
        tw = tx1 - tx0
        if not tw:
            continue
        for ii in imgs:
            ix0, ix1 = _hspan(shapes[ii]); iy0, _ = _vspan(shapes[ii])
            if (max(0.0, min(tx1, ix1) - max(tx0, ix0)) / tw) < HDR_OVER:
                continue
            if abs(ty0 - iy0) <= HDR_EDGE * H or 0 <= (iy0 - ty1) <= HDR_GAP * H:
                out.setdefault(ii, []).append(ti)
                break
    for ii in out:
        out[ii].sort(key=lambda i: shapes[i].get("x") or 0.0)
    return out


# A brochure spread is one image of a two-page layout. The split is the
# SPINE, so the gutter must sit near the middle: slides 19/20 carry an internal
# gap at ~64% and slide 21 a two-panel divide at 43.6%, and neither is a spine.
# The six spreads that split measure 47.6-52.1%.
SPREAD_MIN_W = 0.75
SPINE_WINDOW = (0.45, 0.55)


def splittable(sh, man, assets, window):
    """The measured gutter for a shape's asset, or None. Marking a shape as
    split hides the original on mobile, so nothing may claim a split before
    the gutter is confirmed -- slides 15 and 37 have no spine, and hiding
    their originals would have left the slide blank."""
    key = sh.get("svg") or sh.get("poster")
    rec = man["images"].get(key) if key else None
    if not rec:
        return None
    return measure_gutter(assets / rec["out"], *window)


def spread_image(shapes, W):
    """Index of the spread image on a textless slide, or None."""
    if any(_has_text(sh) for sh in shapes):
        return None
    imgs = [i for i, sh in enumerate(shapes)
            if sh.get("type") == "image" and (sh.get("w") or 0) / W >= SPREAD_MIN_W]
    return imgs[0] if len(imgs) == 1 else None


_GUTTER_CACHE = {}


def measure_gutter(path, lo=0.15, hi=0.85):
    """Fraction across the asset of the widest empty vertical band, or None.

    Rule 31: a multi-unit image is split with crop windows over the same bytes,
    never by cutting new files -- so the split point has to be measured in the
    asset rather than assumed at the midpoint. On slide 21 the real gutter is
    at 43.6%, and a 50/50 guess would have cut through the left group.
    """
    key = (str(path), lo, hi)
    if key in _GUTTER_CACHE:
        return _GUTTER_CACHE[key]
    out = None
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(path).convert("RGBA")).astype(np.int16)
        h, w = a.shape[0], a.shape[1]
        bg = np.median(np.concatenate([a[0, :, :3], a[-1, :, :3]]), axis=0)
        ink = (a[..., 3] > 16) & (np.abs(a[..., :3] - bg).sum(axis=2) > 40)
        col = ink.mean(axis=0) < 0.005
        runs, st = [], None
        for i, e in enumerate(col):
            if e and st is None:
                st = i
            elif not e and st is not None:
                runs.append((st, i))
                st = None
        if st is not None:
            runs.append((st, len(col)))
        # only interior gaps -- the outer runs are the asset's own margins
        runs = [r for r in runs
                if (r[1] - r[0]) >= 0.02 * w and lo * w < (r[0] + r[1]) / 2 < hi * w]
        if runs:
            g0, g1 = max(runs, key=lambda r: r[1] - r[0])
            out = (g0 + g1) / 2.0 / w
    except Exception:
        out = None
    _GUTTER_CACHE[key] = out
    return out


def split_clones(sh, rec, assets, pos, orders, window=(0.15, 0.85)):
    """Two crop windows over ONE asset, hidden on desktop (rule 31)."""
    frac = measure_gutter(assets / rec["out"], *window)
    if frac is None:
        return []
    ar = ((sh.get("w") or 1.0) / (sh.get("h") or 1.0))
    out = []
    for (l, r), o in zip(((0.0, 1.0 - frac), (frac, 0.0)), orders):
        vw = max(1e-6, 1.0 - l - r)
        out.append(
            f'<div class="sh im cropped split" data-role="split" '
            f'style="{pos};order:{o};--car:{vw * ar:.4f}">'
            f'<span class="cropw"><img src="assets/{rec["out"]}" alt="" loading="lazy" '
            f'decoding="async" style="{crop_style({"l": l, "t": 0.0, "r": r, "b": 0.0})}">'
            f'</span></div>')
    return out


# A hero image is the slide's ground rather than an item in it. Measured
# deck-wide, coverage of the largest image falls 54.6% -> 46.5% with no slide
# in between: the widest gap in that range, so 50% is the break the deck
# itself draws rather than a number picked to fit.
HERO_COVER = 0.50
# How close an image's own aspect must sit to the canvas aspect to count as a
# full-bleed photograph rather than a document reproduced on the page.
FULLBLEED_TOL = 0.06
# A corner badge: small, hard against the top-right. Fires on the agency mark
# on slides 1 and 52 and on nothing else in the deck.
BADGE_W, BADGE_RIGHT, BADGE_TOP = 0.15, 0.95, 0.10
# A centred client mark: wide and centred on its slide.
LOGO_MIN_W, LOGO_CENTRE = 0.40, 0.02
# An icon is a badge, not a picture: it must never grow to fill a screen just
# because a phone is narrow.
# Measured: the true icons on slide 35 occupy 0.7-1.3% of the canvas; the
# square social-ad creatives on slide 27 occupy 12.2%. A ~9x gap, so 4% caps
# badges without shrinking an ad that should fill the screen.
ICON_W, ICON_AREA = 0.34, 0.04


def _cov(sh, W, H):
    return ((sh.get("w") or 0.0) * (sh.get("h") or 0.0)) / (W * H)


def is_badge(sh, W, H):
    return (sh.get("type") == "image"
            and (sh.get("w") or 0) / W <= BADGE_W
            and ((sh.get("x") or 0) + (sh.get("w") or 0)) / W >= BADGE_RIGHT
            and (sh.get("y") or 0) / H <= BADGE_TOP)


def is_mark(sh):
    """A vector asset is a logo, not a picture. image1.svg is the only one in
    this deck -- the client mark, drawn at 63.7% on the covers and 24.6% on the
    route slides. Marks never bleed; photographs do."""
    return sh.get("type") == "image" and bool(sh.get("svg"))


def is_logo(sh, W, H):
    """The client mark at cover size: vector, centred, and wide. Photographs
    are centred and wide all over this deck, so width and centring alone
    matched eight shapes; vector-ness is what actually separates them."""
    if not is_mark(sh) or (sh.get("w") or 0) / W < LOGO_MIN_W:
        return False
    cx = ((sh.get("x") or 0) + (sh.get("w") or 0) / 2) / W
    return abs(cx - 0.5) <= LOGO_CENTRE


def is_icon(sh, W, H):
    return (sh.get("type") == "image" and not sh.get("svg")
            and (sh.get("w") or 0) / W <= ICON_W and _cov(sh, W, H) <= ICON_AREA)


def hero_band(shapes, banded, W, H):
    """(hero image index, [text indices], anchor) or None.

    The reader gets one screen per slide, so a dominant image becomes the
    ground and the text sits on it -- rather than a small picture with the
    words stacked underneath in the dead space below.
    """
    # A scrim darkens a PHOTOGRAPH so type stays legible on it. A vector mark
    # or a solid ground needs no scrim, and painting one over blank page is
    # what made the cover-style slides read as a grey wash.
    imgs = [i for i, sh in enumerate(shapes)
            if banded[i] and sh.get("type") in ("image", "video")
            and not is_mark(shapes[i])]
    if not imgs:
        return None
    big = max(imgs, key=lambda i: _cov(shapes[i], W, H))
    if _cov(shapes[big], W, H) < HERO_COVER:
        return None
    txts = [i for i, sh in enumerate(shapes) if banded[i] and _has_text(sh)]
    if not txts:
        # A textless slide still needs its ground to fill the screen. An image
        # drawn at the DECK's own aspect is a full-bleed photograph -- slide 46
        # measures 1.811 against a 1.778 canvas. A brochure spread measures
        # 1.545, so documents that must be read whole are left alone rather
        # than cover-cropped.
        gb = shapes[big]
        ar = (gb.get("w") or 0) / (gb.get("h") or 1)
        if abs(ar - (W / H)) / (W / H) <= FULLBLEED_TOL:
            return big, [], "bottom"
        return None
    mid = sum(((shapes[i].get("y") or 0) + (shapes[i].get("h") or 0) / 2)
              for i in txts) / len(txts) / H
    return big, txts, ("bottom" if mid >= 0.5 else "top")


# ---------------------------------------------------------------- layout role
# ONE decision per shape, made here, in this order. Every mobile box rule keys
# off the result and nothing else, so two rules can never both claim a shape
# and the later one silently win. Two regressions came from exactly that: the
# corner mark was pulled into the centred lockup by a later position rule, and
# full-bleed grounds were re-inset by a competing margin rule.
LAYOUT_ROLES = ("backdrop", "hidden", "split", "badge", "logo", "mark",
                "ground", "icon", "caption", "bleed", "flow")


def layout_role(sh, W, H, *, is_ground=False, is_caption=False,
                is_split=False, is_hidden=False):
    if sh.get("backdrop"):
        return "backdrop"
    if is_hidden:
        return "hidden"
    if is_split:
        return "split"
    if is_badge(sh, W, H):
        return "badge"
    if is_mark(sh):
        return "logo" if is_logo(sh, W, H) else "mark"
    if is_ground:
        return "ground"
    if sh.get("type") in ("image", "video"):
        return "icon" if is_icon(sh, W, H) else "bleed"
    if is_caption:
        return "caption"
    return "flow"


def band_plan(shapes, banded, n, W, H):
    """(band ids, `col` flags, {band: ground}, {band: (term, desc)}).

    Rows come first; a ground then pulls its riders into one band with it.
    """
    rows = clique_rows(shapes, banded)
    pairs = pair_bands(shapes, rows, n)
    ids = [None] * len(shapes)
    for r, mem in enumerate(rows):
        for i in mem:
            ids[i] = r

    # `col` marks a member of a row of 3+ -- the column-stack signature that
    # earns a hairline between the stacked columns on mobile.
    col = [False] * len(shapes)
    for mem in rows:
        if len(mem) >= 3:
            for i in mem:
                col[i] = True

    # A ground forms a NEW band with its riders. Reusing the ground's own row
    # id would drag in whatever merely sits beside it -- on slide 25 the left
    # prose column shares a row with the ellipse without sitting on it, and
    # would inherit the ellipse's fill as its mobile ground.
    ground = {}
    nxt = (max((b for b in ids if b is not None), default=-1)) + 1
    for gi, mem in ground_groups(shapes, banded).items():
        ids[gi] = nxt
        for i in mem:
            ids[i] = nxt
        ground[nxt] = gi
        nxt += 1

    # A gallery header travels with its image, in its own band, so it cannot
    # drift to wherever the y-sort happens to put it.
    heads = {}
    for ii, hdrs in gallery_headers(shapes, banded, H).items():
        ids[ii] = nxt
        for i in hdrs:
            ids[i] = nxt
        heads[nxt] = (hdrs, ii)
        nxt += 1

    hero = None
    hb = hero_band(shapes, banded, W, H)
    if hb:
        big, txts, anch = hb
        ids[big] = nxt
        for i in txts:
            ids[i] = nxt
        hero = (nxt, big, anch)
        nxt += 1
    return ids, col, ground, pairs, lockup_groups(shapes, ids), heads, hero


def band_layout(shapes, banded, ids):
    """(fragments, order_of_band) for one slide.

    `banded[i]` says whether shape i may be wrapped -- backdrops never are, so
    they stay direct children of .canvas and keep .canvas as their containing
    block for `inset:0`.

    Rule 21 forbids z-index inside the canvas, so paint order IS DOM order and
    desktop identity requires the flattened tree order to be unchanged. A band
    whose members are NOT contiguous in z-order is therefore emitted as several
    contiguous FRAGMENTS sharing one `order` value: `display:contents` flattens
    them back to the original sequence on desktop, and on mobile equal `order`
    keeps them adjacent (ties resolve in DOM order). Wrapping never reorders.
    """
    # reading rank of each band: ascending min-y, then ascending min-x
    key = {}
    for i, sh in enumerate(shapes):
        if ids[i] is None:
            continue
        b = ids[i]
        cand = ((sh.get("y") or 0.0), (sh.get("x") or 0.0))
        key[b] = min(key.get(b, cand), cand)
    # Rank by CLUSTERED y, then x. Plain min-y quantisation puts a band 3.8pt
    # higher than its neighbour in a different bucket, which on slide 19 ranks
    # the image column ahead of the prose column beside it. Bands whose tops
    # fall within one order_key band are one rank cluster, ordered left to
    # right inside it.
    ordered = sorted(key, key=lambda b: key[b])
    clusters, cur = [], []
    for b in ordered:
        if cur and key[b][0] - key[cur[0]][0] < 6.0:
            cur.append(b)
        else:
            if cur:
                clusters.append(cur)
            cur = [b]
    if cur:
        clusters.append(cur)
    rank, r = {}, 0
    for cl in clusters:
        for b in sorted(cl, key=lambda b: key[b][1]):
            rank[b] = r
            r += 1

    frags, cur = [], None
    for i in range(len(shapes)):
        if ids[i] is None:
            cur = None
            frags.append(None)
            continue
        if cur is not None and ids[i] == cur:
            frags.append(ids[i])
            continue
        cur = ids[i]
        frags.append(ids[i])
    return frags, rank


def text_html(sh, W, cls_extra="", pair_slot=None):
    out = []
    item = 0
    for p in sh["paras"]:
        runs = [r for r in p["runs"] if r["text"]]
        if not runs:
            # spacer: desktop leading, dropped on mobile inside a paired list
            out.append('<p class="t sp"><br></p>')
            continue
        parts = []
        for r in runs:
            stack, weight = font_for(r)
            sz = (r.get("size_pt") or 18.0) / W * 100.0
            st = [f"font-family:{stack}", f"font-weight:{weight}",
                  f"font-size:{sz:.4f}cqw",
                  f"--ms:{roles.mobile_rem(r.get('size_pt'))}"]
            if r.get("color"):
                st.append(f"color:{r['color']}")
            if r.get("italic"):
                st.append("font-style:italic")
            parts.append(f'<span style="{E(";".join(st))}">{E(r["text"])}</span>')
            if r.get("br_after"):
                parts.append("<br>")
        align = {"ctr": "center", "r": "right", "just": "justify"}.get(p.get("align"), "left")
        lh = line_ratio(runs[0])
        if p.get("line_pct"):
            lh = lh * p["line_pct"]
        bullet = ' data-bullet="1"' if p.get("bullet") else ""
        # --pr places the item in the zipped grid; inert on desktop, where the
        # paragraph is not a grid item.
        pr = ""
        if pair_slot is not None:
            pr = f";--pr:{item * 2 + 1 + pair_slot}"
            item += 1
        out.append(f'<p class="t" style="text-align:{align};line-height:{lh:.4f}{pr}"{bullet}>'
                   + "".join(parts) + "</p>")
    return f'<div class="tw {cls_extra}">' + "".join(out) + "</div>"


def crop_style(crop):
    """srcRect -> a CSS window over the WHOLE asset (rule 6/31: no new bytes).
    The wrapper is positioned and clips; the img inside is scaled and offset."""
    l, t, r, b = crop["l"], crop["t"], crop["r"], crop["b"]
    vw, vh = max(1e-6, 1 - l - r), max(1e-6, 1 - t - b)
    return (f"width:{100/vw:.4f}%;height:{100/vh:.4f}%;"
            f"left:{-l/vw*100:.4f}%;top:{-t/vh*100:.4f}%")


def shape_html(sh, deck, man, W, H, idx, extra_cls=(), pair_slot=None, role='flow'):
    x, y, w, h = sh["x"], sh["y"], sh["w"], sh["h"]
    pos = (f"left:{x/W*100:.4f}%;top:{y/H*100:.4f}%;"
           f"width:{w/W*100:.4f}%;height:{h/H*100:.4f}%")
    rot = sh.get("rot") or 0.0
    if rot:
        pos += f";transform:rotate({rot}deg)"
    style = [pos, f"order:{idx}"]
    cls = ["sh", *extra_cls]
    if sh.get("backdrop"):
        cls.append("backdrop")
    inner = ""

    if sh["type"] == "text":
        cls.append("tx")
        if sh.get("fill"):
            style.append(f"background:{rgba(sh['fill'], sh.get('fill_alpha'))}")
        if sh.get("grad"):
            style.append(f"background:{grad_css(sh['grad'])}")
        if sh.get("stroke"):
            s = sh["stroke"]
            style.append(f"border:{max(s['w_pt'],0.75)/W*100:.4f}cqw solid "
                         f"{rgba(s['hex'], s.get('alpha'))}")
        if sh.get("prst") == "ellipse":
            style.append("border-radius:50%")
        ins = sh.get("insets") or {}
        if ins:
            style.append(f"padding:{ins.get('t',3.6)/H*100:.4f}% {ins.get('r',7.2)/W*100:.4f}% "
                         f"{ins.get('b',3.6)/H*100:.4f}% {ins.get('l',7.2)/W*100:.4f}%")
        anchor = {"ctr": "center", "b": "flex-end"}.get(sh.get("anchor"), "flex-start")
        style.append(f"justify-content:{anchor}")
        inner = text_html(sh, W, pair_slot=pair_slot)

    elif sh["type"] in ("image", "video"):
        cls.append("im" if sh["type"] == "image" else "vid")
        key = sh.get("svg") or sh.get("poster")
        rec = man["images"].get(key) if key else None
        if sh["type"] == "video":
            v = man["videos"].get(sh["video"])
            poster = man["images"].get(sh.get("poster") or "")
            pa = f' poster="assets/{poster["out"]}"' if poster else ""
            # preload="none" + autoplay: nothing is fetched until the element
            # is near playback, so a reader who never reaches slide 44 never
            # pays for it. autoplay is what makes the fetch happen at all --
            # without it, and with no script in this deck, zero video bytes are
            # ever requested.
            inner = (f'<video src="assets/{v["out"]}"{pa} autoplay muted loop '
                     f'playsinline preload="none"></video>')
            # Real custom property, consumed on mobile. The old data-ar was
            # emitted on every video and read by nothing -- so the box had no
            # reserved height and collapsed until the poster decoded.
            style.append(f"--ar:{v['aspect']}")
        elif rec:
            if sh.get("crop"):
                inner = (f'<span class="cropw"><img src="assets/{rec["out"]}" alt="" '
                         f'loading="lazy" decoding="async" style="{crop_style(sh["crop"])}"></span>')
                cls.append("cropped")
                # The crop window fills the authored box on desktop, so its
                # aspect IS the box's. On mobile the window is width:100% and
                # takes its height from --car; without it the fallback of 1
                # squares the window and the image inside is distorted to fit.
                # Same producer the sibling decks write as --ar on .sh.im.
                if sh.get("h"):
                    style.append(f"--car:{sh['w'] / sh['h']:.4f}")
            else:
                inner = (f'<img src="assets/{rec["out"]}" alt="" loading="lazy" '
                         f'decoding="async">')
        else:
            return ""

    elif sh["type"] == "rect":
        cls.append("rect")
        if sh.get("grad"):
            style.append(f"background:{grad_css(sh['grad'])}")
        elif sh.get("fill"):
            style.append(f"background:{rgba(sh['fill'], sh.get('fill_alpha'))}")
        if sh.get("stroke"):
            s = sh["stroke"]
            style.append(f"border:{max(s['w_pt'],0.75)/W*100:.4f}cqw solid "
                         f"{rgba(s['hex'], s.get('alpha'))}")
        if sh.get("prst") == "ellipse":
            style.append("border-radius:50%")

    elif sh["type"] == "table":
        cls.append("tbl")
        t = sh["table"]
        total = sum(t["grid_pt"]) or 1
        cols = "".join(f'<col style="width:{c/total*100:.3f}%">' for c in t["grid_pt"])
        rows = []
        for tr in t["rows"]:
            cells = []
            for tc in tr["cells"]:
                if tc.get("h_merge"):
                    continue
                cs = f' colspan="{tc["grid_span"]}"' if tc.get("grid_span", 1) > 1 else ""
                bg = rgba(tc.get("fill"), tc.get("fill_alpha"))
                st = f' style="background:{bg}"' if bg else ""
                body = "".join(
                    f'<p class="ci" style="line-height:{line_ratio((p["runs"] or [{}])[0]):.4f}">'
                    + "".join(
                        f'<span style="{E(cell_run_css(r, W))}">{E(r["text"])}</span>'
                        for r in p["runs"] if r["text"])
                    + "</p>"
                    for p in tc["paras"])
                cells.append(f"<td{cs}{st}>{body}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        inner = f'<table><colgroup>{cols}</colgroup>{"".join(rows)}</table>'

    return (f'<div class="{" ".join(cls)}" data-role="{role}" '
            f'style="{";".join(style)}">{inner}</div>')


# ---------------------------------------------------------------- page
def build_css(deck, W, H):
    ratio = dkcss.ratio(W, H)
    return f"""
:root{{
  --deck-font:{roles.BODY_STACK};
  --display-font:{roles.DISPLAY_STACK};
  --ratio:{ratio:.6f};
}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:#111;color:#111}}
body{{font-family:var(--deck-font);-webkit-text-size-adjust:100%}}
img,video{{display:block;max-width:100%}}

#deck{{height:100svh;overflow-y:auto;overflow-x:hidden;
      scroll-snap-type:y proximity;-webkit-overflow-scrolling:touch}}
section.slide{{scroll-snap-align:start;scroll-snap-stop:always;
      display:flex;align-items:center;justify-content:center;
      min-height:100svh;background:#111}}

/* ---- desktop: the authored canvas, absolutely positioned ---- */
.canvas{{position:relative;width:{dkcss.CANVAS_WIDTH_FIT};
        aspect-ratio:var(--ratio);container-type:size;overflow:hidden;
        background:var(--bg-solid,var(--bg,#fff))}}
/* A band is inert on desktop: display:contents removes its box, so the
   absolutely-positioned .sh children still resolve against .canvas and the
   flattened tree order -- which IS paint order, per rule 21 -- is unchanged. */
.band{{display:contents}}
.sh{{position:absolute;display:flex;flex-direction:column;overflow:visible}}
.sh.im,.sh.vid{{overflow:hidden}}
.sh.im>img,.sh.vid>video{{width:100%;height:100%;object-fit:cover}}
.sh.cropped>.cropw{{position:absolute;inset:0;overflow:hidden;display:block}}
.sh.cropped>.cropw>img{{position:absolute;max-width:none;object-fit:fill}}
/* rule 31: the split halves exist only for the mobile idiom; desktop keeps the
   single authored image, so they generate no box at all there. */
.sh.split{{display:none}}
.sh.tbl{{overflow:visible}}
.sh.tbl table{{width:100%;height:100%;border-collapse:collapse;table-layout:fixed}}
.sh.tbl td{{vertical-align:middle;padding:0.35cqw 0.6cqw}}
.tw{{width:100%}}
p.t,p.ci{{margin:0}}
p.t[data-bullet]{{padding-left:1.6em;text-indent:-1.6em}}
p.t[data-bullet]::before{{content:attr(data-bullet) " "}}

/* ---- mobile: same DOM, flow layout ---- */
@media (max-width:820px){{
  html,body{{height:100%}}
  #deck{{height:100%}}
  section.slide{{align-items:stretch}}
  .canvas{{--pad:clamp(14px,4.6vw,26px);background:var(--bg-solid,var(--bg,#fff));
           width:100%;aspect-ratio:auto;min-height:100svh;height:auto;
           container-type:inline-size;
           display:flex;flex-direction:column;align-content:center;
           gap:clamp(10px,2.6vw,18px);padding:var(--pad)}}
  /* Routes carry one idea each -- centre them on their screen rather than
     leaving the title stranded at the bottom of an empty one. */
  /* Centre every slide's content. A 1.5:1 spread on a 0.46:1 phone cannot
     fill the screen without cropping away half the artwork, so the honest fix
     is to centre the shortfall rather than bank it all below the fold, where
     it reads as a blank screen with a strip at the top. */
  .canvas{{justify-content:center}}
  /* no dark strip between sections: the canvas carries its own ground and
     its own padding, so the section adds nothing around it */
  section[data-fit="content"]{{min-height:0;padding-block:0}}
  section[data-fit="content"] .canvas{{min-height:0}}
  section[data-arche="cover"] .sh.tx p.t{{text-align:center !important}}
  /* rule 22's two mechanics: shapes go static, and every inline left/top
     must be neutralised or a positioned wrapper re-applies it as a flow
     offset and tears holes in the stack. */
  .sh{{position:static !important;inset:auto !important;
       left:auto !important;top:auto !important;
       width:auto !important;height:auto !important;
       transform:none !important;
       flex:0 0 auto;padding:0 !important}}
  .sh.backdrop{{position:absolute !important;inset:0 !important;
       width:100% !important;height:100% !important;aspect-ratio:auto !important;
       z-index:0;order:-1 !important}}
  /* descendant, not child: shapes on brochure slides now sit inside a band */

  /* the band becomes the stacking unit; fragments of one band share an `order`
     and so land adjacent, ties resolving in DOM order */
  .band{{display:flex;flex-direction:column;min-width:0;
        gap:clamp(10px,2.6vw,18px)}}
  /* rule 33: carry the ground, drop the geometry. The arrow/ellipse is a
     canvas composition device; its FILL is what the riders sit on. */
  .band.ground{{background:var(--bandbg);border-radius:clamp(10px,2.8vw,16px);
        padding:clamp(12px,3.4vw,20px)}}
  .band.ground>.sh.gnd{{display:none !important}}
  /* a row of 3+ becomes a stack; a hairline keeps the columns reading as
     separate points rather than one run-on block */
  .band>.sh.col+.sh.col{{border-top:1px solid rgba(0,0,0,.14)}}
  /* paired list: the two columns interleave into term/description rows. The
     shapes and their text wrappers go display:contents so the paragraphs
     themselves become the grid items, which zips them without reordering the
     DOM -- paint order stays z-order (rule 21). */
  .band.pairs{{display:grid;grid-template-columns:minmax(0,1fr);
        row-gap:clamp(3px,1vw,6px)}}
  .band.pairs>.sh,.band.pairs>.sh>.tw{{display:contents}}
  .band.pairs p.t{{grid-column:1;grid-row:var(--pr)}}
  .band.pairs p.t.sp{{display:none}}
  /* reserve the box from the asset's own ratio so nothing collapses or shifts
     while preload="none" holds the bytes back */
  .sh.vid>video{{aspect-ratio:var(--ar,16/9);height:auto}}
  /* a crop stays a crop on mobile: the wrapper keeps the authored aspect and
     the img inside keeps its window, so no new bytes are cut (rule 31) */
  .sh.cropped{{height:auto !important}}
  .sh.cropped>.cropw{{position:relative;display:block;width:100%;
       aspect-ratio:var(--car,1);overflow:hidden}}
  .sh.cropped>.cropw>img{{position:absolute}}
  /* ---- hero: the image is the ground, the words sit on it ---- */
  /* the hero IS the screen: it grows to fill the section rather than ending
     at 74svh and leaving blank page under it */
  .band.hero{{position:relative;margin-inline:calc(-1 * var(--pad));
       padding:calc(var(--pad) * 1.15);min-height:74svh;gap:.5em;
       flex:1 1 auto;justify-content:flex-end}}
  .band.hero.anchor-top{{justify-content:flex-start}}
  /* .sh sets position:static with !important, which beats any specificity,
     so a caption stayed unpositioned while its ground image was absolutely
     positioned -- and a positioned element paints above non-positioned
     content, so the photo covered the words entirely. It needs !important
     to win, not more specificity. */
  /* A backdrop image is already the ground; it needs the scrim and the
     reversed text, not the repositioning. */
  .sh.bgimg::after{{content:"";position:absolute;inset:0;
       background:linear-gradient(to top,rgba(0,0,0,.72) 0%,
                  rgba(0,0,0,.34) 38%,rgba(0,0,0,0) 70%)}}
  section:has(.sh.bgimg) .canvas>.sh.tx span,
  section:has(.sh.bgimg) .band>.sh.tx span{{color:#fff !important}}
  /* Gallery label rides on its image rather than sitting above it. */
  .band.ghead{{position:relative;margin-inline:calc(-1 * var(--pad));
       padding:calc(var(--pad) * .9);min-height:52svh;flex:1 1 auto;
       justify-content:flex-start}}
  .band.ghead>.sh.im::after{{content:"";position:absolute;inset:0;
       background:linear-gradient(to bottom,rgba(0,0,0,.72) 0%,
                  rgba(0,0,0,.30) 34%,rgba(0,0,0,0) 62%)}}

  /* ================= LAYOUT ROLES =================================
     Every shape carries exactly one data-role, decided once in Python (see
     layout_role). These selectors are mutually exclusive by construction, so
     source order cannot change the outcome and no rule can capture a shape
     that another rule already claimed. Do not add a box rule that targets
     .sh by class -- add a role. */
  .sh[data-role]{{margin-inline:0}}

  /* full-bleed picture: edge to edge, no well of white around it */
  .sh[data-role="bleed"]{{position:relative !important;
       margin-inline:calc(-1 * var(--pad)) !important;align-items:center}}
  .sh[data-role="bleed"]>img,.sh[data-role="bleed"]>video{{width:100%;height:auto}}

  /* ground: the picture IS the screen */
  .sh[data-role="ground"]{{position:absolute !important;inset:0 !important;
       margin:0 !important;overflow:hidden}}
  .sh[data-role="ground"]>img,.sh[data-role="ground"]>video{{width:100%;
       height:100%;object-fit:cover;aspect-ratio:auto}}
  .sh[data-role="ground"].cropped>.cropw,.sh.bgimg.cropped>.cropw{{
       position:absolute !important;inset:0 !important;width:auto !important;
       height:auto !important;aspect-ratio:auto !important}}
  .sh[data-role="ground"].cropped>.cropw>img,.sh.bgimg.cropped>.cropw>img{{
       position:absolute;width:100% !important;height:100% !important;
       left:0 !important;top:0 !important;object-fit:cover !important}}
  .band.hero.scrim>.sh[data-role="ground"]::after{{content:"";position:absolute;
       inset:0;background:linear-gradient(to top,rgba(0,0,0,.80) 0%,
       rgba(0,0,0,.45) 32%,rgba(0,0,0,0) 62%)}}
  .band.hero.anchor-top.scrim>.sh[data-role="ground"]::after{{
       background:linear-gradient(to bottom,rgba(0,0,0,.80) 0%,
       rgba(0,0,0,.45) 32%,rgba(0,0,0,0) 62%)}}
  .band.ghead>.sh[data-role="ground"]::after{{content:"";position:absolute;
       inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.72) 0%,
       rgba(0,0,0,.30) 34%,rgba(0,0,0,0) 62%)}}

  /* caption: type on media, always on its own dark ground */
  .sh[data-role="caption"]{{position:relative !important;margin:0 !important;
       background:rgba(0,0,0,.72);border-radius:10px;
       padding:calc(var(--pad) * .62) calc(var(--pad) * .72) !important}}
  .sh[data-role="caption"] span{{color:#fff !important}}

  /* corner mark: pinned, never part of a centred lockup */
  .sh[data-role="badge"]{{position:absolute !important;top:var(--pad) !important;
       right:var(--pad) !important;left:auto !important;bottom:auto !important;
       width:clamp(72px,22vw,108px) !important;margin:0 !important;
       order:-2 !important}}
  .sh[data-role="badge"]>img{{width:100%;height:auto}}

  /* centred marks, capped so a logo or badge never fills a screen */
  .sh[data-role="logo"]{{position:relative !important;width:min(74%,320px) !important;
       margin-inline:auto !important}}
  .sh[data-role="mark"]{{position:relative !important;width:min(52%,210px) !important;
       margin-inline:auto !important}}
  .sh[data-role="icon"]{{position:relative !important;width:min(58%,240px) !important;
       margin-inline:auto !important}}
  .sh[data-role="logo"]>img,.sh[data-role="mark"]>img,
  .sh[data-role="icon"]>img,.sh[data-role="icon"]>.cropw{{width:100%;height:auto;
       object-fit:contain}}

  /* crop halves replace the whole spread on mobile */
  .sh[data-role="split"]{{display:flex !important;position:relative !important;
       margin-inline:calc(-1 * var(--pad)) !important}}
  .sh[data-role="hidden"]{{display:none !important}}

  /* everything else flows, positioned so it paints above any ground */
  .sh[data-role="flow"]{{position:relative !important}}
  /* ================================================================ */
  /* Deck-specific measurement, kept: at 390x844, 28 of 51 snap points sit
     exactly one viewport apart, so proximity had nowhere to rest that was
     NOT within its threshold -- it re-targeted every fling and animated on
     its own curve, behaving identically to mandatory. Geometry, not the
     keyword, was doing that. */
{dkcss.mobile_scroll_release("section.slide")}
  .sh.tx{{justify-content:flex-start !important}}
  .sh.tbl table{{height:auto}}
  p.t,p.ci{{font-size:inherit}}
  /* var() with no fallback is invalid-at-computed-value-time when --ms is
     missing, which silently drops font-size to the inherited default; the
     fallback keeps a missing producer legible instead of broken. */
  .tw span,p.ci span{{font-size:var(--ms, 1rem) !important}}
}}

/* editor rail — inert in the browser, real names for the slide list */
nav.rail[hidden]{{display:none !important}}
"""


def build_html(deck, man, paths: DeckPaths, labels):
    W, H = deck["w_pt"], deck["h_pt"]
    secs, rail = [], []
    for sl in deck["slides"]:
        n = sl["n"]
        arche = roles.archetype(n)
        shapes = [s for s in sl["shapes"] if not (s.get("occluded") and roles.SUPPRESS_OCCLUDED_SHAPES)]
        shapes = [s for s in shapes if not (s.get("review_sticker") and roles.SUPPRESS_REVIEW_STICKERS)]
        # DOM order stays source z-order (rules 4/5/21); only `order` reflows.
        ranked = sorted(range(len(shapes)), key=lambda i: order_key(shapes[i]))
        order_of = {src: pos for pos, src in enumerate(ranked)}

        bg = sl.get("bg") or deck["master_bg"]
        bg_css = rgba(bg, sl.get("bg_alpha"))
        bg_solid = composite(bg, sl.get("bg_alpha"), deck["master_bg"])
        body = []
        if sl.get("bg_image"):
            rec = man["images"].get(sl["bg_image"]["src"])
            if rec:
                body.append(f'<div class="sh im backdrop" style="left:0;top:0;width:100%;'
                            f'height:100%;order:-1"><img src="assets/{rec["out"]}" alt=""></div>')
        # Bands wrap only the brochure slides (rule 22: no new <section>s, and
        # 52 sections stay 52 -- a band is a wrapper INSIDE the canvas).
        # Backdrops are never wrapped: `.sh.backdrop{inset:0}` needs .canvas as
        # its containing block, not a band.
        banded = [not sh.get("backdrop") for sh in shapes]
        if roles.is_brochure(n) or hero_band(shapes, banded, W, H):
            ids, col, ground, pairs, locks, heads, hero = band_plan(shapes, banded, n, W, H)
            split_at = {}
            frags, brank = band_layout(shapes, banded, ids)
            # A lockup reads left-to-right, so its members must be CONSECUTIVE
            # in the band and ordered by x. They keep the order slots the band
            # already owned, so nothing outside the band moves. `order` is
            # inert on desktop (the canvas is never a flex container there).
            for b, lock in locks.items():
                mem = [i for i in range(len(shapes)) if ids[i] == b]
                slots = sorted(order_of[i] for i in mem)
                units = [tuple(lock)] + [(i,) for i in mem if i not in lock]
                units.sort(key=lambda u: min(order_of[i] for i in u))
                flat = [i for u in units for i in u]
                for slot, i in zip(slots, flat):
                    order_of[i] = slot
            # A header labels the image below it, so it must precede it.
            for b, (hdrs, ii) in heads.items():
                mem = [i for i in range(len(shapes)) if ids[i] == b]
                slots = sorted(order_of[i] for i in mem)
                flat = list(hdrs) + [ii] + [i for i in mem if i not in hdrs and i != ii]
                for slot, i in zip(slots, flat):
                    order_of[i] = slot
                # Two headers over one image: each labels half of it, so the
                # image is split into two crop windows at its measured gutter
                # and each half follows its own header.
                if len(hdrs) == 2 and splittable(
                        shapes[ii], man, paths.out / "assets", (0.15, 0.85)) is not None:
                    base = min(slots)
                    order_of[hdrs[0]] = base
                    order_of[hdrs[1]] = base + 2
                    order_of[ii] = base + 4
                    split_at[ii] = (b, base + 1, base + 3)
        else:
            ids = [None] * len(shapes)
            col, ground, pairs, locks, heads, hero = [False] * len(shapes), {}, {}, {}, {}, None
            split_at = {}
            frags, brank = [None] * len(shapes), {}

        si = spread_image(shapes, W)
        if si is not None and splittable(shapes[si], man, paths.out / "assets",
                                         SPINE_WINDOW) is not None:
            split_at[si] = (None, order_of[si] + 1, order_of[si] + 2)

        open_band = None
        for i, sh in enumerate(shapes):
            b = frags[i]
            if b != open_band:
                if open_band is not None:
                    body.append("</div>")
                open_band = b
                if b is not None:
                    bc, bst = ["band"], [f"order:{brank[b]}"]
                    if b in pairs:
                        bc.append("pairs")
                    if hero and hero[0] == b:
                        bc += ["hero", f"anchor-{hero[2]}"]
                        if (shapes[hero[1]].get("type") in ("image", "video")
                                and any(ids[k] == b and _has_text(shapes[k])
                                        for k in range(len(shapes)))):
                            bc.append("scrim")
                    if b in heads and len(heads[b][0]) == 1:
                        bc.append("ghead")
                    gi = ground.get(b)
                    if gi is not None:
                        # rule 33: the geometry is a desktop composition device,
                        # the fill is the ground the riders' colours were chosen
                        # against. Carry the fill, drop the shape.
                        bc.append("ground")
                        bst.append(f"--bandbg:{rgba(shapes[gi]['fill'], shapes[gi].get('fill_alpha'))}")
                    body.append(f'<div class="{" ".join(bc)}" style="{E(";".join(bst))}">')
            extra = []
            if hero and hero[1] == i:
                extra.append("ground-img")
            if is_badge(sh, W, H):
                extra.append("badge")
            elif is_mark(sh):
                extra.append("logo" if is_logo(sh, W, H) else "mark")
            elif is_icon(sh, W, H):
                extra.append("icon")
            if sh.get("backdrop") and sh.get("type") == "image":
                extra.append("bgimg")
            if i in split_at:
                extra.append("hassplit")
            if col[i]:
                extra.append("col")
            if ids[i] is not None and ground.get(ids[i]) == i:
                extra.append("gnd")
            slot = None
            if ids[i] in pairs:
                slot = 0 if pairs[ids[i]][0] == i else 1
            in_hero = hero is not None and ids[i] == hero[0]
            in_ghead = ids[i] in heads
            role = layout_role(
                sh, W, H,
                is_ground=(hero is not None and hero[1] == i)
                          or (in_ghead and heads[ids[i]][1] == i),
                is_caption=(in_hero or in_ghead) and _has_text(sh),
                is_hidden=(i in split_at))
            body.append(shape_html(sh, deck, man, W, H, order_of[i], extra, slot, role))
            if i in split_at:
                key = sh.get("svg") or sh.get("poster")
                rec = man["images"].get(key) if key else None
                if rec:
                    pos = (f"left:{sh['x']/W*100:.4f}%;top:{sh['y']/H*100:.4f}%;"
                           f"width:{sh['w']/W*100:.4f}%;height:{sh['h']/H*100:.4f}%")
                    win = SPINE_WINDOW if split_at[i][0] is None else (0.15, 0.85)
                    body.extend(split_clones(sh, rec, paths.out / "assets", pos,
                                             split_at[i][1:], win))
        if open_band is not None:
            body.append("</div>")

        label = labels.get(n, f"Slide {n}")
        rail.append(f'<li class="rail-item" data-target="s{n}">'
                    f'<span class="rail-num">{n:02d}</span>'
                    f'<span class="rail-label">{E(label)}</span></li>')
        broch = ' data-brochure="1"' if roles.is_brochure(n) else ""
        # A textless slide holding one document spread that is NOT full-bleed
        # aspect cannot fill a phone screen without cropping the artwork, so
        # the section sizes to the spread instead of banking the shortfall as
        # dead screen above and below it.
        fit = ""
        si_ = spread_image(shapes, W)
        # A spread that SPLIT already fills the screen as two stacked halves;
        # only the ones left whole need the section sized down to them.
        if si_ is not None and si_ not in split_at:
            gb = shapes[si_]
            ar = (gb.get("w") or 0) / (gb.get("h") or 1)
            if abs(ar - (W / H)) / (W / H) > FULLBLEED_TOL:
                fit = ' data-fit="content"'
        secs.append(
            f'<section class="slide" id="s{n}" data-slide="{n}" data-arche="{arche}"'
            f'{broch}{fit} aria-label="{E(label)}">'
            f'<div class="canvas" style="--bg:{bg_css};--bg-solid:{bg_solid}">' + "".join(body) + "</div></section>")

    css = font_face_css(families=roles.FONT_FAMILIES) + build_css(deck, W, H)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(roles.DECK_TITLE)}</title>
<style>{css}</style>
</head>
<body>
<nav class="rail" hidden aria-hidden="true"><ol class="rail-list">
{chr(10).join(rail)}
</ol></nav>
<main id="deck">
{chr(10).join(secs)}
</main>
</body>
</html>
"""


def main():
    SCR = Path("/private/tmp/claude-501/-Users-gif025-Downloads-PG-Deck-for-client"
               "/2976dea1-d497-4885-bd77-f2d89957998f/scratchpad")
    paths = DeckPaths.for_deck("henhouse", SCR / "henhouse/raw", SCR / "henhouse/shots")
    deck = json.loads((paths.out / "model.json").read_text())
    man = json.loads((paths.out / "asset_manifest.json").read_text())
    labels = json.loads((Path(__file__).parent / "labels.json").read_text())
    labels = {int(k): v for k, v in labels.items()}
    out = build_html(deck, man, paths, labels)
    (paths.out / "index.html").write_text(out)
    n_sec = out.count('class="slide"')
    print(f"index.html {len(out)/1024:.0f} KB  sections={n_sec}")


if __name__ == "__main__":
    main()
