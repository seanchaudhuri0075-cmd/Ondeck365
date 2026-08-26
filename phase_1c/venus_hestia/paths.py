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

# ---------------------------------------------------------------------------
# CLIENT INSTRUCTION, 2026-08-26 (Sean, at desktop review).
#
# Source slide 1 ("Hestia Pre-Pro Deck") is DROPPED from the deliverable.
#
# The deck ships with two cover slides. Identified by reading the slides, not by
# assuming from the OSR/R4 diff:
#     source slide 1 -> "Hestia Pre-Pro Deck"            <- dropped
#     source slide 2 -> "Hestia Deck for Revised Labels" <- retained
# Both carry the same two assets (the Venus/Gillette lockup and the corner mark)
# at identical geometry. Sean updated the revised-labels cover and the older
# pre-pro one should not have shipped.
#
# This is a CONTENT decision by the client, not a conversion defect. It is
# applied at model-build time so a re-render cannot bring the slide back, and so
# the dropped slide contributes nothing to used_assets. Neither of its two
# assets is orphaned -- both are still used by the retained cover and by the
# closing slide.
#
# Rule 14 ("reproduce source content faithfully, including its mistakes") is not
# in tension here: that rule forbids the PIPELINE editorialising. This is the
# author telling us what the deliverable is, which is the same distinction
# rule 23 draws for review stickers.
DROP_SLIDES = frozenset({1})
