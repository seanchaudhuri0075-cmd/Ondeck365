#!/usr/bin/env python3
"""Source .pptx -> out/unilever_shpc/. Deck 11's driver, on Secret's pattern.

There is no `unilever_shpc/model.py`, by design: `deckkit/model.py` is the
parser (see secret/build.py). This file holds only the knowledge of which
calls, in what order, with which per-deck switches.

    python3 -m phase_1c.unilever_shpc.build --raw ~/DeckBuild/unilever_shpc/raw

Source of record: `/Volumes/T7 Touch/…_UNILEVER_OSR.pptx`. The default source
is the hash-verified local copy in ~/DeckSources/unilever_shpc/ (see its
SHA256SUMS and DECK11_HANDOFF.md OPEN ITEMS 4); it is NOT in git (1.57 GB).

THREE THINGS THIS DRIVER DOES THAT SECRET'S DOES NOT, and why:

* **It refuses a populated output directory.** Assets are named by SOURCE hash
  and an existing file is reused, so building into a directory that already
  holds a clip encoded under another mode or audio setting silently keeps the
  old bytes (DECK11_HANDOFF.md section 7 item 2). `--out` must not exist, or
  must be empty.

* **`--raw` has no in-repo default that is safe to forget.** The extract is
  1.57 GB. It defaults beside the output like Secret's, but the documented
  invocation puts it on the boot volume, outside the repo and off the T7 --
  and `build()` does `rmtree(raw)`, so it must never point at anything else.

* **Videos are built ONE FILE PER CALL, and a failed encode does not stop the
  run.** `deckkit.assets.build_videos` is already sequential and atomic (rule
  8) but raises on the first ffmpeg failure, which on a 49-clip, ten-minute
  build throws away everything after it. So this loops over the files in the
  same sorted order `build_videos` uses -- the manifest comes out identical to
  a single call -- times each one, and on failure removes the partial, records
  it, and carries on. Failures are REPORTED and make the exit status non-zero;
  they are never written into the manifest as if they were assets.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from phase_1c.deckkit import assets as dkassets
from phase_1c.deckkit import model as dkmodel
from phase_1c.deckkit.paths import REPO, DeckPaths
from phase_1c.unilever_shpc import roles

SOURCE = (Path.home() / "DeckSources" / "unilever_shpc" /
          "2026_GIF_AI_GlobalCapabiltiesPresentation_SKIN_HAIR_PERSONAL_CARE_UNILEVER_OSR.pptx")


def _log(msg: str) -> None:
    print(msg, flush=True)


def build(pptx: Path, raw: Path, out: Path, shots: Path) -> tuple[DeckPaths, dict, dict, list]:
    """Unzip, parse, transcode. Returns (paths, deck, asset_manifest, failures)."""
    raw, out = Path(raw), Path(out)
    assert not out.exists() or not any(out.iterdir()), (
        f"{out} is not empty. Assets are named by source hash and an existing file is "
        f"reused, so a stale clip would survive a change of mode or audio. Build into an "
        f"empty directory.")
    t0 = time.time()
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    with zipfile.ZipFile(pptx) as z:
        z.extractall(raw)
    _log(f"[{time.time() - t0:6.1f}s] extracted {pptx.name} -> {raw}")

    paths = DeckPaths(slug=roles.SLUG, raw=raw, out=out, shots=Path(shots))
    deck, used_images, used_videos = dkmodel.write_model(paths)
    _log(f"[{time.time() - t0:6.1f}s] model: {len(deck['slides'])} slides, "
         f"{len(used_images)} images, {len(used_videos)} videos")

    # The mode map is a per-file DECISION (roles.py). A deck revision that adds
    # or drops a clip must reopen it, not fall through to a default.
    missing = sorted(used_videos - set(roles.VIDEO_MODES))
    extra = sorted(set(roles.VIDEO_MODES) - used_videos)
    assert not missing and not extra, (
        f"roles.VIDEO_MODES does not match the deck: no mode for {missing}, "
        f"modes for files the deck does not use {extra}")

    # deck=... is spelled out rather than hidden in build_all: the crop-window
    # cap (slide 30's 1920x9419 capture) and the GIF matte both come from it.
    imgs = dkassets.build_images(paths, used_images,
                                 needs=dkassets.image_needs(deck),
                                 mattes=dkassets.image_mattes(deck))
    _log(f"[{time.time() - t0:6.1f}s] images: {len(imgs)} written, "
         f"{sum(e['out_bytes'] for e in imgs.values()) / 1e6:.2f} MB")

    vids, failures = {}, []
    names = sorted(used_videos)                  # build_videos' own order
    for i, name in enumerate(names, 1):
        t1 = time.time()
        try:
            entry = dkassets.build_videos(
                paths, {name}, crf=roles.VIDEO_CRF, preset=roles.VIDEO_PRESET,
                modes={name: roles.VIDEO_MODES[name]}, audio=roles.AUDIO)[name]
        except (subprocess.CalledProcessError, OSError, KeyError) as e:
            for p in paths.assets.glob("*.__partial.*"):
                p.unlink()
            failures.append({"name": name, "mode": roles.VIDEO_MODES[name],
                             "error": f"{type(e).__name__}: {e}"})
            _log(f"[{time.time() - t0:6.1f}s] {i:>2}/{len(names)}  {name:12} "
                 f"FAILED after {time.time() - t1:5.1f}s  {type(e).__name__}: {e}")
            continue
        vids[name] = entry
        _log(f"[{time.time() - t0:6.1f}s] {i:>2}/{len(names)}  {name:12} {entry['mode']:6} "
             f"{entry['src_bytes'] / 1e6:7.2f} -> {entry['out_bytes'] / 1e6:6.2f} MB  "
             f"audio={'yes' if entry['audio'] else 'no '}  {time.time() - t1:5.1f}s")

    leftovers = sorted(p.name for p in paths.assets.glob("*.__partial.*"))
    assert not leftovers, f"partial files left in outputs (rule 8): {leftovers}"
    man = {"images": imgs, "videos": vids}       # build_all's shape and serialisation
    (paths.out / "asset_manifest.json").write_text(json.dumps(man, indent=1))
    _log(f"[{time.time() - t0:6.1f}s] done: {len(vids)} of {len(names)} videos, "
         f"{sum(e['out_bytes'] for e in vids.values()) / 1e6:.2f} MB, {len(failures)} failed")
    return paths, deck, man, failures


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pptx", type=Path, nargs="?", default=SOURCE)
    ap.add_argument("--out", type=Path, default=REPO / "out" / roles.SLUG)
    ap.add_argument("--raw", type=Path, default=None,
                    help="extract directory; WIPED first. Keep it off the T7 and out of the repo.")
    a = ap.parse_args()
    out = a.out
    raw = a.raw or out.parent / f".raw-{roles.SLUG}"
    paths, deck, man, failures = build(a.pptx, raw, out, out.parent / f".shots-{roles.SLUG}")
    print(f"slides {len(deck['slides'])}  images {len(man['images'])}  "
          f"videos {len(man['videos'])}  -> {paths.out}")
    if failures:
        print(f"FAILED ENCODES ({len(failures)}):")
        for f in failures:
            print(f"  {f['name']}  [{f['mode']}]  {f['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
