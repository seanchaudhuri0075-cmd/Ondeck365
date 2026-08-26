# Deck Editor v14 — vendored copy

## Why this is here

Until 2026-08-26 the Deck Editor lived only at `~/Downloads/Deck_Editor_v14.html`
— in no repository, with no history, and no way to roll back an edit. It is the
**highest-risk control in the pipeline**: it owns the R2 folder prefix (NOTES
2026-08-25, the Old Spice / Olay collision), it owns the publish flow that
LEARNINGS rule 37 bans for external-media decks, and it decides which assets
reach the CDN at all (rule 36).

Nothing edits the editor until there is a copy here with history. This is that
copy.

## Provenance

| | |
|---|---|
| source | `~/Downloads/Deck_Editor_v14.html` |
| vendored | 2026-08-26 |
| original size | 119,451 bytes |
| original sha256 | `bd3bc6bee4d20b6edb8f92d12f6525fdc10f57f6ffc1ac0a8a5c437ebf0dd404` |
| vendored size | 119,436 bytes |
| vendored sha256 | `ae7f3ec562cb3f0a7d38d92f24e6fb424703432716ff263df40dbc2194d83465` |

## The one change — the scrub

**This repo is public.** Exactly one substantive value was redacted, in one
place, the same way `NOTES.md` already declines to record it:

```
- <input type="text" id="r2Url" placeholder="https://deck-media-worker.<...>.workers.dev" />
+ <input type="text" id="r2Url" placeholder="https://YOUR-WORKER.workers.dev" />
```

That is a **`placeholder` attribute only** — grey helper text in the R2
Configuration panel. It is not the value the editor uses. The live value comes
from `localStorage['deckR2'].url`, is typed once per browser profile, and is
unaffected by this substitution. The scrub therefore changes nothing about how
the editor behaves.

Everything else in the file was already a dummy and is committed verbatim:
`pub-xxx.r2.dev`, `ghp_xxxxxxxxxxxx`, `clientname-deck`, and `AUTH_TOKEN`
(a label, not a secret).

**Any future vendoring must re-apply the scrub, and must verify it against the
committed blob rather than the working copy.**

## This copy is not the one you run

Sean's working editor is still `~/Downloads/Deck_Editor_v14.html`. This is the
versioned base to edit *from*, so a change can be reviewed and reverted. When a
change is agreed:

1. edit the copy here,
2. commit it,
3. copy it over the Downloads file,
4. re-enter the Worker URL if the placeholder was ever mistaken for a value
   (it is not one, but check the field reads the real endpoint before uploading).

## Known defects in this version, all recorded elsewhere

- **`doR2Silent()` has no `needsFile` branch** and `doPublish`'s catch does not
  rethrow, so one-click Publish ships a deck of 404s for external media —
  LEARNINGS rule 37. Use the `Upload to R2` modal.
- **`url(data:...)` inside `<style>` is never externalised** — LEARNINGS rule 36.
- **The Deck Name field persists across decks** via `saveR2`/`loadR2` — NOTES
  2026-08-25. This is what put Old Spice's packaging on Olay's slides.
- **~20 full `DOMParser` re-parses of the whole document**, and an undo stack
  holding up to 30 complete copies of it, which is what sets the embed ceiling
  between 180 and 240 MB — `DECK9_HANDOFF.md` section 8.
