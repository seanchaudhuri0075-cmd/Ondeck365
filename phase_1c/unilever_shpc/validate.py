"""Unilever SHPC (deck 11) -- build assertions and the regression screenshots.

    python3 -m phase_1c.unilever_shpc.validate            # assertions only
    python3 -m phase_1c.unilever_shpc.validate --shots    # + Chrome vs LibreOffice

Desktop scope only (step 13). Every assertion names what it enforces.

The screenshot pass is a REGRESSION SIGNAL, not a fidelity gate: LibreOffice
draws the source with whatever fonts it has (no SF Pro), the videos there are
posters, and the Chrome side is the QA variant with the Apple entries removed
(handoff section 4's rule -- on this Mac the shipped stack would show the
system font on every display run). The per-slide number is the mean absolute
grey-level difference at 960x540, 0-255; watch it MOVE between builds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path

from phase_1c.unilever_shpc import render, roles

paths = render.paths_for()
OUT = paths.out
deck = json.loads((OUT / "model.json").read_text())
man = json.loads((OUT / "asset_manifest.json").read_text())
doc = (OUT / "index.html").read_text()
doc_nc = re.sub(r"/\*.*?\*/", "", doc, flags=re.S)          # CSS comments are not declarations
doc_nc = re.sub(r"<!--.*?-->", "", doc_nc, flags=re.S)     # nor are HTML comments

ok, fail = [], []

# The model flags 4 shapes on slide 14 `occluded` -- two logos and two text
# boxes that sit UNDER the full-bleed click-to-play film in z-order and are
# invisible in the source. roles.SUPPRESS_OCCLUDED_SHAPES drops them
# (reconnaissance section 7 said "none"; the built model says four). Every
# count below is against the model LESS what roles suppresses.
def live(sh):
    return not ((roles.SUPPRESS_REVIEW_STICKERS and sh.get("review_sticker"))
                or (roles.SUPPRESS_OCCLUDED_SHAPES and sh.get("occluded")))


LIVE = [[sh for sh in sl["shapes"] if live(sh)] for sl in deck["slides"]]
N_LIVE = sum(len(x) for x in LIVE)
N_SUPPRESSED = sum(len(sl["shapes"]) for sl in deck["slides"]) - N_LIVE


def check(label, cond, detail=""):
    (ok if cond else fail).append(f"{label}" + (f" — {detail}" if detail else ""))


def sections(d):
    return re.findall(r'<section class="slide"[^>]*>(.*?)</section>', d, flags=re.S)


def text_of(html_fragment: str) -> str:
    """Live text of a fragment: tags stripped, entities decoded. `<br>` is an
    authored break and carries no character, matching the model."""
    return unescape(re.sub(r"<[^>]+>", "", html_fragment))


secs = sections(doc)
# ---- structure ---------------------------------------------------------------
check("1  35 <section class=slide> in #deck-desktop", len(secs) == roles.N_SLIDES == len(deck["slides"]),
      f"{len(secs)} sections")
ids = re.findall(r'<section class="slide" id="(s\d+)"', doc)
check("2  ids sequential s1..s35", ids == [f"s{i}" for i in range(1, roles.N_SLIDES + 1)])
check("3  #deck-mobile present, hidden and EMPTY (reserved)",
      re.search(r'<main id="deck-mobile" hidden>\s*</main>', doc) is not None)
check("4  exactly one class=\"slide\" per source slide, none in #deck-mobile",
      doc.count('class="slide"') == roles.N_SLIDES)

n_sh = sum(len(re.findall(r'<div class="sh ', s)) for s in secs)
check("5  268 model shapes: every live one emitted, the occluded ones suppressed",
      n_sh == N_LIVE and N_LIVE + N_SUPPRESSED == 268, f"{n_sh} emitted, {N_SUPPRESSED} suppressed (slide 14, under the film)")
n_vid = doc.count("<video ")
n_gif = len(re.findall(r'<div class="sh vid[^"]*\bgif\b', doc))
check("6  49 videos + the slide-26 GIF clip = 50 <video>", n_vid == 50 and n_gif == 1, f"{n_vid} video, {n_gif} gif")

# ---- text: per slide, equal to the model after entity decoding ------------------
bad = []
for sl, sec in zip(deck["slides"], secs):
    want = "".join(r.get("text") or "" for sh in sl["shapes"] if live(sh) for p in sh.get("paras") or [] for r in p["runs"])
    got = "".join(text_of(m) for m in re.findall(r"<p class=\"t[^\"]*\"[^>]*>(.*?)</p>", sec, flags=re.S))
    if want != got:
        bad.append((sl["n"], len(want), len(got)))
check("7  per-slide text == model.json (entities decoded)", not bad, f"mismatch on {bad[:5]}")
amp = sum(1 for sl in deck["slides"] if any("&" in (r.get("text") or "") for sh in sl["shapes"]
                                             for p in sh.get("paras") or [] for r in p["runs"]))
check("7b &-bearing slides compared decoded (section 8's tell)", amp >= 30, f"{amp} slides carry &")

# ---- media ------------------------------------------------------------------
refs = set(re.findall(r'(?:src|poster)="assets/([^"]+)"', doc))
missing = sorted(f for f in refs if not (OUT / "assets" / f).exists())
check("8  every referenced media file exists in out/unilever_shpc/assets", not missing, f"{len(refs)} refs, missing {missing[:3]}")
n_pic = sum(1 for x in LIVE for sh in x if sh["type"] == "image" and not sh.get("animated_gif"))
check("8b every live picture is an <img data-media>", len(re.findall(r"<img data-media ", doc)) == n_pic, f"{n_pic} pictures")
check("8c crops are CSS windows, never baked", doc.count('class="sh im cropped"') == 3 and doc.count('class="sh vid cropped"') == 1)
check("9  <video preload=\"none\"> on all", doc.count('preload="none"') == n_vid)
check("9b every <video> has a poster", len(re.findall(r'<video [^>]*poster="assets/', doc)) == n_vid)
check("9c playback attribute on every <video> (auto/click)",
      len(re.findall(r'data-playback="(?:auto|click)"', doc)) == n_vid and doc.count('data-playback="click"') == 6)
model_muted = sum(1 for s in deck["slides"] for sh in s["shapes"] if sh["type"] == "video" and sh.get("muted"))
model_loop = sum(1 for s in deck["slides"] for sh in s["shapes"] if sh["type"] == "video" and sh.get("loop"))
check("9d muted/loop follow model.json (+1 each for the GIF clip)",
      len(re.findall(r"<video [^>]* muted", doc)) == model_muted + 1
      and len(re.findall(r"<video [^>]* loop", doc)) == model_loop + 1,
      f"model muted {model_muted}, loop {model_loop}")
check("9e IntersectionObserver player present", "new IntersectionObserver(" in doc and 'getElementById(\'deck-desktop\')' in doc)
check("9f MEDIA_BASE constant exists and is empty for the preview", render.MEDIA_BASE == "" and 'src="assets/' in doc)

# ---- fonts ------------------------------------------------------------------
check("10 no local() anywhere", "local(" not in doc)
check("10b 'Archivo wdth90' @font-face from the committed woff2, inlined",
      f"font-family:'{roles.ARCHIVO_FAMILY}'" in doc and "data:font/woff2;base64," in doc)
spans = re.findall(r'<span[^>]*style="([^"]*)"', doc)
wrong = 0
for st in spans:
    m_ = re.search(r"font-size:([\d.]+)cqw", st)
    if not m_ or roles.ARCHIVO_FAMILY not in st:
        continue
    pt = float(m_.group(1)) * deck["w_pt"] / 100
    apple = "-apple-system" in st
    if (pt >= roles.APPLE_MIN_PT) != apple:
        wrong += 1
check("10c stacks follow roles: Apple entries lead >=30pt runs only", wrong == 0, f"{wrong} spans disagree")
check("10d Apple entries present in the shipped document", "-apple-system,BlinkMacSystemFont" in doc)
todo = re.findall(r'data-font-todo="([^"]+)"', doc)
check("10e pending faces flagged, one run each", sorted(todo) == ["Calibri", "League Gothic"], f"{todo}")

# ---- editor vocabulary ------------------------------------------------------
ci = re.findall(r'<span class="ci"[^>]*>(.*?)</span>', doc, flags=re.S)
edge = [text_of(t) for t in ci if not text_of(t) or text_of(t) != text_of(t).strip()]
check("11 no .ci on whitespace-only or edge-whitespace runs", not edge, f"{len(ci)} .ci runs, {len(edge)} bad")
check("11b headlines are .L > .t", doc.count('class="sh tx L') >= 40 and doc.count('class="t"') > 0)
check("11c rail hidden, one entry per slide", 'class="rail" hidden' in doc and doc.count('class="rail-item"') == roles.N_SLIDES)

# ---- canvas rules -----------------------------------------------------------
check("12 no z-index inside the canvas (rule 21)", "z-index" not in doc_nc)
check("12b no hardcoded aspect ratio; --ratio from p:sldSz (rule 15)",
      not re.search(r"aspect-ratio:\s*\d+\s*/\s*\d+", doc_nc) and f'--ratio:{deck["w_pt"]/deck["h_pt"]:.6f}' in doc)
check("12c geometry in cqw/cqh, type in cqw",
      "left:" in doc and "cqw;top:" in doc and "cqh;width:" in doc and not re.search(r"font-size:[\d.]+(px|vw|vh)", doc_nc))
check("12d one desktop snap point per slide, released below the breakpoint",
      "scroll-snap-type:y mandatory" in doc and "scroll-snap-align:start" in doc and "scroll-snap-type:none" in doc)
check("12e every p.t carries line-height and its own font-size (41(s))",
      all("line-height:" in st and "font-size:" in st
          for st in re.findall(r'<p class="t[^"]*" style="([^"]*)"', doc)))


def report():
    for line in ok:
        print("  ok  ", line)
    for line in fail:
        print("  FAIL", line)
    print(f"\n{len(ok)} passed, {len(fail)} failed")


# =============================================================================
# Screenshots: Chrome (QA variant, Archivo forced) vs LibreOffice (source).
# =============================================================================
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SOFFICE = "/opt/homebrew/bin/soffice"


def shots(scratch: Path, source: Path, width=1920):
    from PIL import Image, ImageChops
    import numpy as np
    scratch.mkdir(parents=True, exist_ok=True)
    qa = scratch / "qa"
    qa.mkdir(exist_ok=True)
    # 1. the QA document (Apple entries removed), beside a link to the assets
    (qa / "index.html").write_text(render.build_html(deck, man, apple=False))
    if not (qa / "assets").exists():
        os.symlink(OUT / "assets", qa / "assets")
    # 2. serve it (Chrome will not fetch the woff2 data URI otherwise? it will;
    #    the server is for assets/ over http so preload/poster behave as shipped)
    port = _free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                            "--directory", str(qa)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.8)
        cdir = scratch / "chrome"
        cdir.mkdir(exist_ok=True)
        for n in range(1, roles.N_SLIDES + 1):
            png = cdir / f"s{n:02d}.png"
            if png.exists():
                continue
            # Headless Chrome on this Mac writes the PNG and then does not
            # exit, so wait for the file, not the process.
            pr = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                   f"--user-data-dir={scratch}/chrome-prof",
                                   f"--window-size={width},{round(width * deck['h_pt'] / deck['w_pt'])}",
                                   "--virtual-time-budget=8000", f"--screenshot={png}",
                                   f"http://127.0.0.1:{port}/index.html?noplay#s{n}"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(90):
                time.sleep(1)
                if png.exists() and png.stat().st_size > 0:
                    break
            time.sleep(1)
            pr.kill()
            pr.wait()
            print(f"  chrome s{n:02d} {'ok' if png.exists() else 'MISSING'}", flush=True)
    finally:
        srv.terminate()
    # 3. LibreOffice: source -> pdf -> png per page (posters where the videos are)
    lo = scratch / "lo"
    lo.mkdir(exist_ok=True)
    pdf = lo / (source.stem + ".pdf")
    if not pdf.exists():
        subprocess.run([SOFFICE, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(lo), str(source)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    if not list(lo.glob("p-*.png")):
        subprocess.run(["pdftoppm", "-png", "-r", str(round(width / (deck["w_pt"] / 72))), str(pdf), str(lo / "p")], timeout=600)
    lo_pngs = sorted(lo.glob("p-*.png"))
    # 4. compare at 960x540 grey, mean |diff|
    rows = []
    for n in range(1, roles.N_SLIDES + 1):
        a = cdir / f"s{n:02d}.png"
        b = lo_pngs[n - 1] if n - 1 < len(lo_pngs) else None
        if not a.exists() or b is None:
            rows.append((n, None))
            continue
        ia = Image.open(a).convert("L").resize((960, 540), Image.LANCZOS)
        ib = Image.open(b).convert("L").resize((960, 540), Image.LANCZOS)
        d = np.asarray(ImageChops.difference(ia, ib), dtype=np.float64)
        rows.append((n, float(d.mean())))
    return rows


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--scratch", default=os.environ.get("DECK11_SCRATCH", str(Path.home() / "DeckBuild/unilever_shpc/validate")))
    ap.add_argument("--source", default=None, help="the .pptx LibreOffice renders (default: a video-stripped copy in scratch)")
    a = ap.parse_args()
    report()
    if a.shots:
        scratch = Path(a.scratch)
        src = Path(a.source) if a.source else scratch / "lo" / "slim.pptx"
        if not src.exists():
            sys.exit(f"no source for LibreOffice at {src}; pass --source")
        rows = shots(scratch, src)
        print("\nslide  mean|diff| (0-255)   Chrome(Archivo forced) vs LibreOffice(source), regression signal only")
        for n, v in rows:
            print(f"  {n:2d}   {'n/a' if v is None else f'{v:6.2f}'}")
        worst = sorted((r for r in rows if r[1] is not None), key=lambda r: -r[1])[:5]
        print("worst 5:", ", ".join(f"s{n} {v:.1f}" for n, v in worst))
    sys.exit(1 if fail else 0)
