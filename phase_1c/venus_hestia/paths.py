"""Where deck 9's bytes live. The only file that knows a path."""
from __future__ import annotations

from phase_1c.deckkit.paths import DeckPaths

SCRATCH = ("/private/tmp/claude-501/-Users-gif025-Downloads-ondeck-pipeline"
           "/52eb2c50-b0ad-400e-a904-2240d65e39d6/scratchpad")

# Canonical source, settled in DECK9_HANDOFF.md section 1. The _OSR is a strict
# superset of the R4 and RENUMBERS the media by one, so the choice of file fixes
# the asset key space for the life of the deck. Never build from the R4.
SOURCE_PPTX = "~/Downloads/Venus_Hestia_Photoshoot_GenAI_CreativeAds_OSR.pptx"
SOURCE_SHA256 = "32689c7c0d8e84793f8c91a44fc41bc6689b25566f5f76c3ae505c90f09d1162"

PATHS = DeckPaths.for_deck(
    slug="venus-hestia",
    raw=f"{SCRATCH}/venus_raw",
    shots=f"{SCRATCH}/venus_shots",
)
