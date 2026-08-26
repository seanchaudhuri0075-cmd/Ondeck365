"""Where a deck's bytes live. One object so no module hardcodes a path.

Every builder before this one (`phase_1c/olay/`, `phase_1c/oldspice/`) opened
with a module-level `RAW = Path("/private/tmp/.../raw")` and `OUT = Path(...)`,
which is the single biggest reason the two builders could not be shared: every
function was bound to one deck by import time.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DeckPaths:
    slug: str            # e.g. "henhouse" — output dir name and asset prefix
    raw: Path            # unzipped .pptx tree (contains ppt/, docProps/)
    out: Path            # build output dir
    shots: Path          # capture scratch dir (never inside out/)

    @classmethod
    def for_deck(cls, slug: str, raw: str | Path, shots: str | Path) -> "DeckPaths":
        return cls(slug=slug, raw=Path(raw), out=REPO / "out" / slug, shots=Path(shots))

    @property
    def media(self) -> Path:
        return self.raw / "ppt" / "media"

    @property
    def assets(self) -> Path:
        return self.out / "assets"

    def slide_xml(self, filename: str) -> Path:
        return self.raw / "ppt" / "slides" / filename

    def rels_for(self, n: int) -> Path:
        return self.raw / "ppt" / "slides" / "_rels" / f"slide{n}.xml.rels"
