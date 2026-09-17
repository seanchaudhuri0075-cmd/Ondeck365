"""deckkit.assets / deckkit.model: DECK11_HANDOFF.md section 7 items 2, 4, 5.

  2  per-file video mode + kept audio
  4  animated GIF -> H.264 clip + frame-0 poster
  5  the crop-window image rule (MAX_DIM starves a tall image shown cropped)

Every fixture is synthetic and generated here. The video and GIF cases need
ffmpeg/ffprobe and skip without them.
"""
import hashlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase_1c.deckkit import assets as dkassets
from phase_1c.deckkit import model as dkmodel
from phase_1c.deckkit.paths import DeckPaths
from tests.test_deckkit_video_target import REL, _package

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg + ffprobe")


def _paths(tmp_path, tag="a"):
    p = DeckPaths(slug="synthetic", raw=tmp_path / f"raw_{tag}", out=tmp_path / f"out_{tag}",
                  shots=tmp_path / "shots")
    p.media.mkdir(parents=True)
    p.out.mkdir(parents=True)
    return p


def _streams(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,codec_name", "-of", "json", str(path)])
    return {s["codec_type"]: s["codec_name"] for s in json.loads(out)["streams"]}


def _clip(path, with_audio=True, acodec="aac", pattern="testsrc"):
    """`pattern` matters: outputs are content-addressed by SOURCE hash, so two
    identical fixtures would be one asset and the second would never be built."""
    a_in = ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"] if with_audio else []
    a_out = ["-c:a", acodec] if with_audio else []
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"{pattern}=size=64x64:rate=10:duration=1", *a_in, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", *a_out, "-shortest", str(path)], check=True)


def _video_packets(path):
    """md5 of the video stream's packets as stored: equal iff it was not re-encoded."""
    return subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                    "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"])


# ===========================================================================
# item 2 -- per-file video mode, audio kept
# ===========================================================================
@needs_ffmpeg
def test_mixed_mode_map_copies_one_and_reencodes_the_other_keeping_audio(tmp_path):
    paths = _paths(tmp_path)
    _clip(paths.media / "media1.mp4")
    _clip(paths.media / "media2.mp4", pattern="testsrc2")

    man = dkassets.build_videos(paths, {"media1.mp4", "media2.mp4"},
                                modes={"media1.mp4": "copy", "media2.mp4": "encode"},
                                audio="keep")

    one, two = man["media1.mp4"], man["media2.mp4"]
    assert (one["mode"], two["mode"]) == ("copy", "encode")
    assert one["audio"] is True and two["audio"] is True
    for e in (one, two):
        assert _streams(paths.assets / e["out"]) == {"video": "h264", "audio": "aac"}
    # the proof that "copy" copied and "encode" did not: the stored video
    # packets are the source's own in one and are not in the other
    assert _video_packets(paths.assets / one["out"]) == _video_packets(paths.media / "media1.mp4")
    assert _video_packets(paths.assets / two["out"]) != _video_packets(paths.media / "media2.mp4")


@needs_ffmpeg
def test_unnamed_file_takes_the_calls_own_mode(tmp_path):
    paths = _paths(tmp_path)
    _clip(paths.media / "media1.mp4")
    _clip(paths.media / "media2.mp4", pattern="testsrc2")
    man = dkassets.build_videos(paths, {"media1.mp4", "media2.mp4"}, copy=True,
                                modes={"media2.mp4": {"crf": 30}})
    assert (man["media1.mp4"]["mode"], man["media2.mp4"]["mode"]) == ("copy", "encode")
    assert man["media1.mp4"]["audio"] is False, "audio defaults to strip even with a map"


@needs_ffmpeg
def test_keep_audio_on_silent_source_and_non_aac_source(tmp_path):
    paths = _paths(tmp_path)
    _clip(paths.media / "media1.mp4", with_audio=False)
    _clip(paths.media / "media2.mov", acodec="pcm_s16le")   # mp4 cannot carry PCM
    man = dkassets.build_videos(paths, {"media1.mp4", "media2.mov"}, copy=True, audio="keep")
    assert man["media1.mp4"]["audio"] is False, "no track in, no track out -- and no failure"
    assert _streams(paths.assets / man["media2.mov"]["out"]) == {"video": "h264", "audio": "aac"}
    assert (_video_packets(paths.assets / man["media2.mov"]["out"])
            == _video_packets(paths.media / "media2.mov")), "video still stream-copied"


@needs_ffmpeg
@pytest.mark.parametrize("kw", [{"copy": True}, {}], ids=["copy", "crf"])
def test_default_path_is_unchanged(tmp_path, kw):
    """No map, no audio argument: `-an`, and not one new manifest key. Built
    twice -- once as the old call, once spelling out the new defaults -- and
    the outputs must be the same bytes."""
    a, b = _paths(tmp_path, "a"), _paths(tmp_path, "b")
    _clip(a.media / "media1.mp4")
    shutil.copyfile(a.media / "media1.mp4", b.media / "media1.mp4")

    old = dkassets.build_videos(a, {"media1.mp4"}, **kw)["media1.mp4"]
    new = dkassets.build_videos(b, {"media1.mp4"}, **kw, modes=None, audio="strip")["media1.mp4"]

    assert set(old) == {"out", "sha", "width", "height", "aspect", "src_bytes",
                        "out_bytes", "out_sha256"}
    assert old == new
    assert _streams(a.assets / old["out"]) == {"video": "h264"}, "audio stripped, as always"


def test_mode_map_rejects_unknown_files_and_bad_values(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(AssertionError, match="does not use"):
        dkassets.build_videos(paths, {"media1.mp4"}, modes={"media9.mp4": "copy"})
    with pytest.raises(ValueError, match="must be"):
        dkassets._file_mode("media1.mp4", {"media1.mp4": "fast"}, False, 23, "medium", None)
    with pytest.raises(AssertionError, match="audio must be"):
        dkassets.build_videos(paths, set(), audio="mute")


# ===========================================================================
# item 4 -- animated GIF
# ===========================================================================
def _gif(path, n_frames, size=(33, 21)):          # ODD on both axes, like deck 11's 1000x571
    frames = [Image.new("RGB", size, c) for c in ("#ff0000", "#00ff00", "#0000ff")[:n_frames]]
    frames[0].save(path, save_all=n_frames > 1, append_images=frames[1:], duration=100, loop=0)


@needs_ffmpeg
def test_three_frame_gif_emits_clip_and_poster(tmp_path):
    paths = _paths(tmp_path)
    _gif(paths.media / "image1.gif", 3)
    man = dkassets.build_all(paths, {"image1.gif"}, set())
    e = man["images"]["image1.gif"]

    # the ordinary entry is the frame-0 poster, exactly what this stage made before
    assert e["out"].endswith(".webp") and (e["out_w"], e["out_h"]) == (33, 21)
    poster = Image.open(paths.assets / e["out"]).convert("RGB")
    assert poster.getpixel((5, 5))[0] > 200 and poster.getpixel((5, 5))[2] < 60, "frame 0 is red"

    a = e["animated"]
    clip = paths.assets / a["out"]
    assert a["out"] == f"vid_{e['sha']}.mp4" and clip.exists()
    assert a["frames"] == 3 and a["loop"] is True
    assert a["matte"] is None, "this GIF declares no transparency: nothing to flatten"
    assert (a["width"], a["height"]) == (32, 20), "odd edges cropped to even for yuv420p"
    assert _streams(clip) == {"video": "h264"}, "silent"
    assert a["out_bytes"] == clip.stat().st_size
    assert a["out_sha256"] == hashlib.sha256(clip.read_bytes()).hexdigest()
    n = subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams",
                                 "v:0", "-show_entries", "stream=nb_read_frames", "-of",
                                 "csv=p=0", str(clip)]).decode().strip()
    assert int(n) == 3, "every GIF frame is in the clip"


def _transparent_gif(path):
    """3 frames, 32x20; the LEFT HALF is genuinely transparent in every frame."""
    frames = []
    for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        f = Image.new("RGBA", (32, 20), (0, 0, 0, 0))
        f.paste(c + (255,), (16, 0, 32, 20))
        frames.append(f)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0,
                   disposal=2)


def _clip_pixel(clip, xy, frame=1):
    raw = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-i", str(clip), "-vf",
                                   f"select=eq(n\\,{frame})", "-frames:v", "1", "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-"])
    i = (xy[1] * 32 + xy[0]) * 3
    return tuple(raw[i:i + 3])


@needs_ffmpeg
def test_transparent_gif_flattens_onto_the_matte_not_onto_ffmpegs_white(tmp_path):
    """Pins both halves of the claim: what ffmpeg does when left alone (WHITE --
    this test was first written expecting black, and failed), and that a matte
    replaces it. Colour is read from the DECODED CLIP."""
    a, b = _paths(tmp_path, "a"), _paths(tmp_path, "b")
    _transparent_gif(a.media / "image1.gif")
    shutil.copyfile(a.media / "image1.gif", b.media / "image1.gif")

    plain = dkassets.build_images(a, {"image1.gif"})["image1.gif"]
    assert plain["alpha"] is True and plain["animated"]["matte"] is None
    assert min(_clip_pixel(a.assets / plain["animated"]["out"], (4, 10))) > 225, "default: WHITE"

    matted = dkassets.build_images(b, {"image1.gif"}, mattes={"image1.gif": "#A7C6ED"})["image1.gif"]
    assert matted["animated"]["matte"] == "#A7C6ED"
    r, g, bl = _clip_pixel(b.assets / matted["animated"]["out"], (4, 10))
    assert abs(r - 0xA7) < 12 and abs(g - 0xC6) < 12 and abs(bl - 0xED) < 12, (r, g, bl)
    r, g, bl = _clip_pixel(b.assets / matted["animated"]["out"], (24, 10))
    assert g > 180 and r < 80 and bl < 80, "opaque half untouched: frame 1 is green"
    n = subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams",
                                 "v:0", "-show_entries", "stream=nb_read_frames", "-of",
                                 "csv=p=0", str(b.assets / matted["animated"]["out"])])
    assert int(n.decode().strip()) == 3, "matting must not add, drop or retime frames"


def test_matte_is_the_colour_behind_the_gif_in_the_model(tmp_path):
    fill = ('<p:sp><p:nvSpPr><p:cNvPr id="9" name="panel"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="6858000"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="A7C6ED"/></a:solidFill></p:spPr></p:sp>')
    rels = [("rId1", f"{REL}/image", "../media/image1.gif", False)]

    over_panel = _package(tmp_path / "p", fill + _pic("moving", 2, "rId1"), rels)
    _gif(over_panel.media / "image1.gif", 3)
    deck, _, _ = dkmodel.build_model(over_panel)
    assert dkassets.image_mattes(deck) == {"image1.gif": "#A7C6ED"}

    on_master = _package(tmp_path / "m", _pic("moving", 2, "rId1"), rels)
    _gif(on_master.media / "image1.gif", 3)
    deck, _, _ = dkmodel.build_model(on_master)
    assert deck["slides"][0]["bg_from"] == "master"
    assert dkassets.image_mattes(deck) == {"image1.gif": deck["master_bg"]}


def test_one_frame_gif_keeps_the_webp_path(tmp_path):
    paths = _paths(tmp_path)
    _gif(paths.media / "image1.gif", 1)
    e = dkassets.build_all(paths, {"image1.gif"}, set())["images"]["image1.gif"]
    assert "animated" not in e and e["out"].endswith(".webp")
    assert sorted(p.name for p in paths.assets.iterdir()) == [e["out"]], "no clip written"


def _pic(name, shape_id, rid, crop=""):
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvPicPr/><p:nvPr/>'
            f'</p:nvPicPr><p:blipFill><a:blip r:embed="{rid}"/>{crop}<a:stretch><a:fillRect/>'
            f'</a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="4876800" cy="6858000"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


def test_model_flags_the_animated_gif_picture_only(tmp_path):
    paths = _package(tmp_path, _pic("moving", 2, "rId1") + _pic("still", 3, "rId2"),
                     [("rId1", f"{REL}/image", "../media/image1.gif", False),
                      ("rId2", f"{REL}/image", "../media/image2.gif", False)])
    _gif(paths.media / "image1.gif", 3)
    _gif(paths.media / "image2.gif", 1)
    deck, imgs, _ = dkmodel.build_model(paths)
    by = {s["name"]: s for s in deck["slides"][0]["shapes"]}
    assert by["moving"]["type"] == "image" and by["moving"]["animated_gif"] is True
    assert "animated_gif" not in by["still"]
    assert imgs == {"image1.gif", "image2.gif"}


# ===========================================================================
# item 5 -- the crop-window rule
# ===========================================================================
TALL = (400, 4000)


def _tall_png(path):
    im = Image.new("RGB", TALL)
    px = im.load()
    for y in range(TALL[1]):
        for x in range(0, TALL[0], 7):
            px[x, y] = ((x * 5) % 256, (y // 3) % 256, (x + y) % 256)
    im.save(path)


def _today(src, max_dim=dkassets.MAX_DIM):
    """The bytes this stage produced BEFORE the rule existed."""
    im = Image.open(src).convert("RGB")
    s = min(1.0, max_dim / max(im.size))
    if s < 1.0:
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "WEBP", quality=dkassets.WEBP_Q, method=6)
    return im.size, b.getvalue()


def _deck_showing(tmp_path, crop_xml, source=None):
    """A 960x540pt deck with one picture, 384pt wide x 540pt tall (the fixture
    `_pic` box: 4876800 x 6858000 EMU), showing image1.png through `crop_xml`."""
    paths = _package(tmp_path, _pic("page", 2, "rId1", crop_xml),
                     [("rId1", f"{REL}/image", "../media/image1.png", False)])
    if source is None:
        _tall_png(paths.media / "image1.png")
    else:
        source.save(paths.media / "image1.png")
    deck, imgs, _ = dkmodel.build_model(paths)
    return paths, deck, imgs


def test_tall_image_shown_through_a_crop_is_lifted_and_never_baked(tmp_path):
    # a window 30% of the height: t=40%, b=30%
    paths, deck, imgs = _deck_showing(tmp_path, '<a:srcRect t="40000" b="30000"/>')
    assert deck["slides"][0]["shapes"][0]["crop"] == {"l": 0.0, "t": 0.4, "r": 0.0, "b": 0.3}
    (today_w, today_h), _ = _today(paths.media / "image1.png")
    assert (today_w, today_h) == (200, 2000), "MAX_DIM alone: 200 px across a 384pt box"

    e = dkassets.build_all(paths, imgs, set(), deck=deck)["images"]["image1.png"]

    # need: the box is 384/960 = 0.4 canvas wide -> 0.4 x 3840 = 1536 px, but the
    # source is only 400 wide: capped at source resolution, the whole file ships.
    assert (e["out_w"], e["out_h"]) == TALL
    assert e["lifted_from"] == [200, 2000]
    out = Image.open(paths.assets / e["out"])
    assert out.size == TALL, "the FULL image ships: the crop stays in CSS, never baked"


def test_lift_stops_at_the_target_not_at_the_source(tmp_path):
    """Same picture, but make the source huge relative to its window so the
    2x-of-1920 target binds before the source does."""
    paths, deck, imgs = _deck_showing(tmp_path, '<a:srcRect t="40000" b="30000"/>')
    big = Image.open(paths.media / "image1.png").resize((4000, 40000), Image.NEAREST)
    big.save(paths.media / "image1.png")
    e = dkassets.build_all(paths, imgs, set(), deck=deck)["images"]["image1.png"]
    # width need 0.4 x 3840 = 1536; height need (540/960 x 3840) / 0.3 = 7200
    # -> scale max(1536/4000, 7200/40000) = 0.384 -> 1536 x 15360
    assert (e["out_w"], e["out_h"]) == (1536, 15360)
    assert e["lifted_from"] == [200, 2000]


def test_served_image_is_byte_identical_to_today(tmp_path):
    """A 2400x3375 photo filling the same 384x540pt box, uncropped. MAX_DIM
    trims it to 1422x2000. One 1920-px canvas asks for 768x1080, so it is
    SERVED and must come out as today's bytes exactly -- even though 2x of that
    canvas (1536x2160) is more than it gets. This is Secret's situation (7 of
    its 65 images), and it is why the floor and the target are two numbers."""
    photo = Image.radial_gradient("L").resize((2400, 3375)).convert("RGB")
    paths, deck, imgs = _deck_showing(tmp_path, "", source=photo)
    today_size, today_bytes = _today(paths.media / "image1.png")
    e = dkassets.build_all(paths, imgs, set(), deck=deck)["images"]["image1.png"]
    assert "lifted_from" not in e
    assert (e["out_w"], e["out_h"]) == today_size == (1422, 2000)
    assert (paths.assets / e["out"]).read_bytes() == today_bytes


def test_without_a_deck_the_rule_is_off(tmp_path):
    paths, deck, imgs = _deck_showing(tmp_path, '<a:srcRect t="40000" b="30000"/>')
    _, today_bytes = _today(paths.media / "image1.png")
    e = dkassets.build_all(paths, imgs, set())["images"]["image1.png"]
    assert "lifted_from" not in e
    assert (paths.assets / e["out"]).read_bytes() == today_bytes
