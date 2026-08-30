#!/usr/bin/env python3
"""Source .pptx -> out/secret/. The entry point that was missing.

There is no `secret/model.py`, and that is BY DESIGN, not an omission:
`deckkit/model.py` is the parser, and this is the first deck routed through it
(see roles.py's note on LAYOUT_ARCHETYPE and `deckkit.model.build_layout_index`).
Olay and Old Spice carry deck-local `model.py` files because they predate the
shared spine. Secret needs only a driver, and this is it.

What was actually missing was the KNOWLEDGE of which calls, in what order, with
which per-deck switch -- which lived nowhere but a session transcript. That is
the thing this file exists to stop being lost.

    python3 -m phase_1c.secret.build "/Volumes/T7 Touch/2026 AUG 1/SecretBeautyCreativeStrategy_OSR.pptx"

Source of record for that deck: see DECK10_MOBILE_HANDOFF.md. It is NOT in
~/Downloads and NOT in git (74 MB); the T7 is the only copy, and Time Machine
has no destination configured.

`--out` builds into a scratch directory instead of `out/secret`, which is how
the regeneration path is checked against the committed artifacts without
overwriting them.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from phase_1c.deckkit import assets as dkassets
from phase_1c.deckkit import model as dkmodel
from phase_1c.deckkit.paths import REPO, DeckPaths
from phase_1c.secret import roles


def build(pptx: Path, raw: Path, out: Path, shots: Path) -> tuple[DeckPaths, dict, dict]:
    """Unzip, parse, transcode. Returns (paths, deck, asset_manifest)."""
    raw, out = Path(raw), Path(out)
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    with zipfile.ZipFile(pptx) as z:
        z.extractall(raw)

    # DeckPaths directly, not for_deck(): for_deck pins out to REPO/out/<slug>, and
    # a verification run must be able to build somewhere else.
    paths = DeckPaths(slug=roles.SLUG, raw=raw, out=out, shots=Path(shots))
    deck, used_images, used_videos = dkmodel.write_model(paths)
    # copy=True, and it is a per-deck measured call, not a default: these seven
    # clips are already 0.97-2.73 Mbps, so re-encoding is generation loss
    # bought with CPU. The container is still rewritten for +faststart and -an,
    # which is why six of seven change size while none is re-encoded.
    man = dkassets.build_all(paths, used_images, used_videos,
                             video_kw={"copy": True})
    return paths, deck, man


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pptx", type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "out" / roles.SLUG)
    ap.add_argument("--raw", type=Path, default=None)
    a = ap.parse_args()
    out = a.out
    raw = a.raw or out.parent / f".raw-{roles.SLUG}"
    paths, deck, man = build(a.pptx, raw, out, out.parent / f".shots-{roles.SLUG}")
    print(f"slides {len(deck['slides'])}  images {len(man['images'])}  "
          f"videos {len(man['videos'])}  -> {paths.out}")


if __name__ == "__main__":
    main()
