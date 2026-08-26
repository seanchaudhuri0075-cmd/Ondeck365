# Deck 9 (Venus / Hestia) — video encode samples

Evidence behind the **5 Mbps** bitrate decision recorded in
`DECK9_HANDOFF.md` §4. Captured 2026-08-26, before any building.

## What these are

One representative clip from each of deck 9's three aspect families, encoded
at 3 and 5 Mbps and frame-grabbed at the clip midpoint alongside the source.

| file | what |
|---|---|
| `CMP_<family>.png` | side-by-side strip: SRC \| 5Mbps \| 3Mbps, downscaled |
| `<family>_SRC.png` | full-resolution frame from the untouched source |
| `<family>_5Mbps.png` | full-resolution frame from the 5 Mbps encode |
| `<family>_3Mbps.png` | full-resolution frame from the 3 Mbps encode |

The `CMP_` strips are for a quick side-by-side read. **The full-resolution
frames are the ones that support the decision** — the difference between 3 and
5 Mbps shows in fine label type, which the downscaled strips lose.

## Measured sizes

| family | source clip | source | 5 Mbps | 3 Mbps |
|---|---|---|---|---|
| square 1080×1080 (4.7 s) | `ppt/media/media50.mp4` | 25.31 MB | **2.89 MB** | 1.70 MB |
| vertical 1080×1920 (8.0 s) | `ppt/media/media21.mp4` | 24.77 MB | **5.20 MB** | 3.06 MB |
| landscape 1920×1080 (8.0 s) | `ppt/media/media19.mp4` | 33.29 MB | **4.88 MB** | 2.81 MB |

Deck-wide at 5 Mbps: **~176 MB** against 845.55 MB of source (~4.8×).

## Why 5 Mbps

The square 1080×1080 clip is the hardest case — the busiest frame, with fine
type on the bottle labels ("Sheo Butter", "Pro-Vitamin B5") and water droplets.
That is where 3 Mbps softens first. The vertical and landscape clips are
largely flat mint backgrounds and hold up at 3 Mbps. Since one number covers
all three families and these are client ad boards, 5 Mbps is the safe choice.

## Regenerating

The `.mp4` encodes are **not** committed — ~104 MB including sources, and
reproducible. To recreate:

```bash
# extract from the canonical source
python3 - <<'PY'
import zipfile, shutil
F="~/Downloads/Venus_Hestia_Photoshoot_GenAI_CreativeAds_OSR.pptx"
z=zipfile.ZipFile(F)
for label,n in {"square_1080x1080":"ppt/media/media50.mp4",
                "vertical_1080x1920":"ppt/media/media21.mp4",
                "landscape_1920x1080":"ppt/media/media19.mp4"}.items():
    with z.open(n) as s, open(f"{label}_SRC.mp4","wb") as d:
        shutil.copyfileobj(s,d)
PY

# encode (matches ondeck/transform/video.py's encoder family: libx264, preset medium)
for f in square_1080x1080 vertical_1080x1920 landscape_1920x1080; do
  for br in 3 5; do
    ffmpeg -y -v error -i ${f}_SRC.mp4 \
      -c:v libx264 -b:v ${br}M -maxrate $((br*115/100))M -bufsize $((br*2))M \
      -preset medium -pix_fmt yuv420p -movflags +faststart -an \
      ${f}_${br}Mbps.mp4
  done
done
```

Source clip identity is by **OSR media ordinal**. If the source file is ever
changed, re-derive — R4's media are renumbered by one relative to OSR (see
`DECK9_HANDOFF.md` §1).
