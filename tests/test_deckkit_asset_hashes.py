"""deckkit.assets: every manifest entry carries the OUTPUT file's hash.

DECK11_HANDOFF.md section 7 item 8. `sha` is the SOURCE hash -- it names the
asset and does not move when encoder settings do -- so the manifest alone could
not say whether two builds produced the same bytes. Deck 11's video cannot live
in git, so its byte-for-byte gate has to run against the manifest.

Covers all three writers: WebP, SVG pass-through, and video. The video case
needs ffmpeg and skips without it.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase_1c.deckkit import assets as dkassets
from phase_1c.deckkit.paths import DeckPaths

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4">'
       '<rect width="4" height="4" fill="#A7C6ED"/></svg>')


def _paths(tmp_path):
    p = DeckPaths(slug="synthetic", raw=tmp_path / "raw", out=tmp_path / "out",
                  shots=tmp_path / "shots")
    p.media.mkdir(parents=True)
    p.out.mkdir(parents=True)
    return p


def _assert_entry_matches_disk(paths, entry):
    data = (paths.assets / entry["out"]).read_bytes()
    assert entry["out_bytes"] == len(data), "out_bytes must survive alongside the hash"
    assert entry["out_sha256"] == hashlib.sha256(data).hexdigest()
    assert len(entry["out_sha256"]) == 64


def test_images_and_svg_carry_output_hash(tmp_path):
    paths = _paths(tmp_path)
    Image.new("RGB", (64, 48), "#1665BA").save(paths.media / "image1.png")
    Image.new("RGBA", (32, 32), (255, 255, 255, 128)).save(paths.media / "image2.png")
    (paths.media / "image3.svg").write_text(SVG)

    man = dkassets.build_all(paths, {"image1.png", "image2.png", "image3.svg"}, set())

    assert set(man["images"]) == {"image1.png", "image2.png", "image3.svg"}
    for entry in man["images"].values():
        _assert_entry_matches_disk(paths, entry)
    # The output hash is NOT the source hash: `sha` still names the asset by
    # its source, which is what keeps filenames stable across encoder changes.
    e = man["images"]["image1.png"]
    assert e["out"] == f"img_{e['sha']}.webp"
    assert e["sha"] == hashlib.sha256((paths.media / "image1.png").read_bytes()).hexdigest()[:12]
    assert e["out_sha256"][:12] != e["sha"]
    # SVG is copied verbatim, so there the two DO agree -- a useful cross-check
    # that the hash really is of the written file.
    s = man["images"]["image3.svg"]
    assert s["out_sha256"][:12] == s["sha"]
    # and the manifest on disk is the manifest returned
    assert json.loads((paths.out / "asset_manifest.json").read_text()) == man


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="needs ffmpeg + ffprobe")
@pytest.mark.parametrize("video_kw", [{"copy": True}, {}], ids=["copy", "crf"])
def test_videos_carry_output_hash(tmp_path, video_kw):
    paths = _paths(tmp_path)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=64x64:rate=10:duration=1", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(paths.media / "media1.mp4")], check=True)

    man = dkassets.build_all(paths, set(), {"media1.mp4"}, video_kw=video_kw)

    entry = man["videos"]["media1.mp4"]
    _assert_entry_matches_disk(paths, entry)
    assert (entry["width"], entry["height"]) == (64, 64)
