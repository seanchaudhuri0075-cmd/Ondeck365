"""Asset stage: extract, content-address, transcode. Shared by every deck.

Rules (LEARNINGS.md):
  6 — every asset is EXTRACTED from ppt/media via its resolved rId. Nothing is
      recreated, traced or approximated.
  7 — output filenames are content hashes, so an asset referenced from N
      slides is one file and one URL.
  8 — video encodes SEQUENTIALLY, one at a time, to a `.__partial.` name that
      is only renamed on success. A partial left in the output set is a hard
      failure, not a warning.

srcRect crops are deliberately NOT baked into pixels: the crop travels to CSS
so it stays reversible in the editor. An asset shown as a narrow strip still
ships whole — the cost of reversibility.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .paths import DeckPaths

Image.MAX_IMAGE_PIXELS = None

MAX_DIM = 2000        # a 960x540pt canvas at 2x is 1920px; beyond that is waste
WEBP_Q = 80
VIDEO_CRF = 23
VIDEO_PRESET = "medium"
AUDIO_BITRATE = "160k"

# The two canvases of the crop-window rule -- see `_window_scale`.
WINDOW_FLOOR_CANVAS = 1920     # MAX_DIM's own standard: one 1920-px canvas
WINDOW_TARGET_CANVAS = 3840    # what a starved image is lifted TO: 2x of it


def _out_hash(path: Path) -> dict:
    """{"out_bytes", "out_sha256"} of a FINISHED output file.

    `sha` in the manifest is the SOURCE hash: it names the asset, and it does
    not move when the encoder settings do. So until this existed the manifest
    could not say whether two builds produced the same bytes -- only committed
    blobs could, which is how Secret's regeneration was proven. Deck 11's
    ~500 MB of video cannot live in git, so its byte-for-byte gate has to run
    against the manifest instead, and that needs the OUTPUT's hash.

    Read from disk after the atomic rename (rule 8), never from the encoder's
    buffer: the claim is about the file that ships.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"out_bytes": path.stat().st_size, "out_sha256": h.hexdigest()}


def image_needs(deck: dict) -> dict:
    """{media name: (need_w, need_h)} -- the FULL image size each picture needs,
    in units of canvas widths, so that its largest displayed window is sharp.

    A shape shows the window `srcRect` leaves (rule: crops travel to CSS and
    are never baked), stretched over the shape's box. If the window is a
    fraction `fw` of the source width and the box is `bw` canvas-widths wide,
    the whole image has to be `bw / fw` canvas-widths wide for the window to
    get one source pixel per canvas pixel. Same on the other axis; the larger
    demand over every use of the image on every slide wins. Posters of videos
    and `<p:bg>` images count as uses.
    """
    W, H = deck["w_pt"], deck["h_pt"]
    needs: dict = {}

    def use(name, w_pt, h_pt, crop):
        c = crop or {}
        fw = 1.0 - (c.get("l", 0.0) + c.get("r", 0.0))
        fh = 1.0 - (c.get("t", 0.0) + c.get("b", 0.0))
        if not name or fw <= 0 or fh <= 0:
            return
        nw, nh = abs(w_pt) / W / fw, abs(h_pt) / W / fh
        pw, ph = needs.get(name, (0.0, 0.0))
        needs[name] = (max(pw, nw), max(ph, nh))

    for sl in deck["slides"]:
        if sl.get("bg_image"):
            use(sl["bg_image"].get("src"), W, H, None)
        for s in sl["shapes"]:
            if s.get("poster"):
                use(s["poster"], s["w"], s["h"], s.get("crop"))
    return needs


def _window_scale(w0: int, h0: int, need, max_dim_scale: float):
    """The scale to use INSTEAD of MAX_DIM's, or None to leave MAX_DIM alone.

    MAX_DIM caps the LONG EDGE OF THE FILE, on the assumption that the file is
    what the viewer sees. Deck 11 slide 30 breaks the assumption: a 1920x9419
    page capture shown three times through `srcRect` windows ~400pt wide.
    MAX_DIM ships it as 408x2000 -- 408 px across a box that is ~800 px wide
    on a 1920-px canvas -- because the 2000 went to an edge nobody sees whole.

    Two canvases, deliberately different:

      FLOOR  1920 px. The question "is MAX_DIM failing this image?" is asked
             against the standard MAX_DIM was chosen to meet (its own comment:
             a canvas at 2x is 1920 px). An image whose windows get at least
             one source pixel per pixel of a 1920-px canvas is SERVED, and is
             left exactly as it was: same code path, same bytes.
      TARGET 3840 px. An image that fails the floor is lifted to 2x a 1920-px
             canvas -- never past its own source resolution.

    They differ because asking the floor question at 3840 would also re-size
    every large photo that MAX_DIM trims today (7 of Secret's 65 measure
    below 2x-at-1920). That may well be worth doing, but it is a deliberate
    re-baselining of shipped decks, not a side effect of fixing a crushed one.
    """
    nw, nh = need
    floor = min(1.0, max(nw * WINDOW_FLOOR_CANVAS / w0, nh * WINDOW_FLOOR_CANVAS / h0))
    if max_dim_scale >= floor:
        return None
    return min(1.0, max(nw * WINDOW_TARGET_CANVAS / w0, nh * WINDOW_TARGET_CANVAS / h0))


def image_mattes(deck: dict) -> dict:
    """{media name: "#RRGGBB"} -- the opaque colour directly BEHIND each
    animated-GIF picture, read from the model (i.e. from the slide XML), for
    flattening a transparent GIF into H.264, which has no alpha.

    Paint order is shape order (rule 21), so "behind" is: the nearest earlier
    shape that is an opaque solid fill covering the picture's whole box; failing
    that the slide's own resolved background; failing that the master's. A
    picture that sits over a photograph, a gradient, a translucent fill, or a
    layout that paints nothing (`bg_from == "none"`) has no single colour behind
    it, and gets NO entry rather than a guess. Two uses that disagree get no
    entry either.
    """
    out, clash = {}, set()
    for sl in deck["slides"]:
        shapes = sl["shapes"]
        for i, s in enumerate(shapes):
            if not s.get("animated_gif"):
                continue
            colour = None
            for under in reversed(shapes[:i]):
                overlaps = not (under["x"] + under["w"] <= s["x"] or s["x"] + s["w"] <= under["x"]
                                or under["y"] + under["h"] <= s["y"] or s["y"] + s["h"] <= under["y"])
                if not overlaps:
                    continue
                covers = (under["x"] <= s["x"] + 1 and under["y"] <= s["y"] + 1
                          and under["x"] + under["w"] >= s["x"] + s["w"] - 1
                          and under["y"] + under["h"] >= s["y"] + s["h"] - 1)
                opaque = (under["type"] in ("rect", "text") and under.get("fill")
                          and not under.get("grad") and under.get("fill_alpha") in (None, 1.0)
                          and under.get("prst") in (None, "rect") and not under.get("rot"))
                colour = under["fill"] if (covers and opaque) else False
                break
            if colour is None:
                if sl.get("bg_image") or sl.get("bg_from") == "none":
                    colour = False
                elif sl.get("bg") and sl.get("bg_alpha") in (None, 1.0):
                    colour = sl["bg"]
                else:
                    colour = deck.get("master_bg") or False
            name = s["poster"]
            if name in out and out[name] != colour:
                clash.add(name)
            out[name] = colour
    return {k: v for k, v in out.items() if v and k not in clash}


def _gif_to_mp4(src: Path, dst: Path, size, crf: int, preset: str,
                matte: str | None = None) -> None:
    """Animated GIF -> silent H.264. `size` is the poster's (w, h), so the clip
    and its frame-0 poster register; yuv420p needs even dimensions, and the odd
    row/column is CROPPED (at most one pixel) rather than resampled or padded.
    Frame delays come through the gif demuxer; nothing is retimed.

    `matte` is what transparent pixels become. Left to itself ffmpeg drops the
    alpha channel and transparent pixels come out WHITE -- measured, and pinned
    by a test, because the first version of this docstring said black and was
    wrong. White is right for a white slide by luck and wrong for every other
    one (Secret's ground is #A7C6ED), and luck is not a rule, so the colour is
    made explicit. With a matte, each frame is composited over a copy of
    ITSELF painted solid -- same frames, same timestamps -- rather than over a
    `color` source, which has its own clock and would retime the clip."""
    w, h = size
    fit = f"scale={w}:{h}:flags=lanczos,crop={w - w % 2}:{h - h % 2}:0:0"
    if matte:
        fit = (f"format=rgba,split[m][g];[m]drawbox=x=0:y=0:w=iw:h=ih:"
               f"color=0x{matte.lstrip('#')}@1.0:t=fill:replace=1[m];"
               f"[m][g]overlay=format=auto,{fit}")
    partial = dst.with_name(dst.name.replace(".mp4", ".__partial.mp4"))
    partial.unlink(missing_ok=True)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src),
         "-vf", fit,
         "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(partial)],
        check=True)
    partial.replace(dst)


def build_images(paths: DeckPaths, used: set[str], max_dim: int = MAX_DIM,
                 quality: int = WEBP_Q, needs: dict | None = None,
                 mattes: dict | None = None,
                 gif_crf: int = VIDEO_CRF, gif_preset: str = VIDEO_PRESET) -> dict:
    """`needs` (from `image_needs(deck)`) switches on the crop-window rule; without
    it every image is capped by `max_dim` alone, exactly as before.

    An ANIMATED GIF keeps its ordinary entry -- the frame-0 WebP, which is what
    this stage has always made of it and is now its poster -- and gains an
    "animated" block naming a silent H.264 clip of all frames. A renderer that
    has never heard of the block still gets a correct still. `mattes` (from
    `image_mattes(deck)`) is the colour a GIF that DECLARES transparency is
    flattened onto; the block records it, or null when none was known."""
    paths.assets.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in sorted(used):
        src = paths.media / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]

        if src.suffix.lower() == ".svg":
            # rule 6: SVG-only pictures embed the actual vector. Nothing to
            # transcode — copy the bytes and keep the content address.
            out_name = f"img_{digest}.svg"
            shutil.copyfile(src, paths.assets / out_name)
            manifest[name] = {"out": out_name, "sha": digest, "svg": True,
                              "src_w": None, "src_h": None,
                              "out_w": None, "out_h": None, "alpha": True,
                              "src_bytes": src.stat().st_size,
                              **_out_hash(paths.assets / out_name)}
            continue

        im = Image.open(src)
        w0, h0 = im.size
        frames = getattr(im, "n_frames", 1) if src.suffix.lower() == ".gif" else 1
        gif_loops = im.info.get("loop") == 0       # NETSCAPE2.0 loop count 0 = forever
        has_alpha = im.mode in ("RGBA", "LA", "P") and (
            im.mode != "P" or "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        scale = min(1.0, max_dim / max(im.size))
        lifted_from = None
        if needs and name in needs:
            lifted = _window_scale(w0, h0, needs[name], scale)
            if lifted is not None:
                lifted_from = [max(1, round(w0 * scale)), max(1, round(h0 * scale))]
                scale = lifted
        if scale < 1.0:
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                           Image.LANCZOS)
        out_name = f"img_{digest}.webp"
        dst = paths.assets / out_name
        partial = paths.assets / f"img_{digest}.__partial.webp"
        im.save(partial, "WEBP", quality=quality, method=6)
        partial.replace(dst)
        manifest[name] = {"out": out_name, "sha": digest, "svg": False,
                          "src_w": w0, "src_h": h0, "out_w": im.width, "out_h": im.height,
                          "alpha": has_alpha,
                          "src_bytes": src.stat().st_size, **_out_hash(dst)}
        if lifted_from:
            # what MAX_DIM alone would have shipped -- the record of WHY this
            # file is bigger than max_dim says it should be
            manifest[name]["lifted_from"] = lifted_from
        if frames > 1:
            clip = paths.assets / f"vid_{digest}.mp4"
            matte = (mattes or {}).get(name) if has_alpha else None
            if not clip.exists():
                _gif_to_mp4(src, clip, (im.width, im.height), gif_crf, gif_preset, matte)
            manifest[name]["animated"] = {"out": clip.name, "frames": frames,
                                          "loop": gif_loops, "matte": matte,
                                          **_probe(clip), **_out_hash(clip)}
    return manifest


def _probe(path: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)])
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    g = math.gcd(w, h)
    return {"width": w, "height": h, "aspect": f"{w // g}/{h // g}"}


def _audio_codec(path: Path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "json", str(path)])
    streams = json.loads(out).get("streams") or []
    return streams[0].get("codec_name") if streams else None


def _file_mode(name, modes, copy, crf, preset, bitrate) -> dict:
    """The call's single mode, overridden for `name` by the per-file map."""
    base = {"copy": copy, "crf": crf, "preset": preset, "bitrate": bitrate}
    m = (modes or {}).get(name)
    if m is None:
        return base
    if m == "copy":
        return {**base, "copy": True, "bitrate": None}
    if m == "encode":
        return {**base, "copy": False}
    if isinstance(m, dict) and set(m) <= set(base):
        return {**base, "copy": False, **m}
    raise ValueError(f"video mode for {name!r} must be 'copy', 'encode' or a dict of "
                     f"{sorted(base)}; got {m!r}")


def build_videos(paths: DeckPaths, used: set[str], crf: int = VIDEO_CRF,
                 preset: str = VIDEO_PRESET, bitrate: str | None = None,
                 copy: bool = False, progress: bool = False,
                 modes: dict | None = None, audio: str = "strip") -> dict:
    """Sequential + atomic (rule 8). Aspect is PROBED, never assumed — deck 8
    is the first with mixed aspects (1:1 and 9:16, no 16:9 anywhere), so a
    hardcoded container ratio would crop or letterbox most of them.

    `bitrate` switches from quality-targeted (CRF) to rate-capped ABR, e.g.
    "5M". Deck 9 needs this: its source is 845 MB for 4.7 minutes — a 24 Mbps
    average — and the decision there was made by comparing encodes at a fixed
    RATE, not a fixed quality, because the deliverable is bounded by what can
    be shipped rather than by a quality target. 5 Mbps was chosen over 3 Mbps
    on the 1080x1080 clip, whose fine bottle-label type softens first.
    `-maxrate`/`-bufsize` cap the peak so a busy frame cannot blow the budget.

    `copy` stream-copies instead of re-encoding, for a source that is ALREADY
    web-rate. Deck 10 (Secret) is the first: 7 clips, H.264, 0.97-2.73 Mbps,
    15.5 MB total. Re-encoding those at CRF 23 is generation loss bought with
    CPU -- a second lossy pass over frames that were already compressed once,
    for no size win worth having. The container is still rewritten, so
    `+faststart` (moov atom first, which is what makes `preload="none"` +
    range requests stream rather than stall) and `-an` still apply.

    The two switches now bracket the decision: `bitrate` when the source is far
    too heavy for the web (deck 9, 24 Mbps), `copy` when it already is not
    (deck 10). Neither is a default, because "what should happen to this deck's
    video" is a measured per-deck call and should read as one at the call
    site.

    `modes` makes that call PER FILE, for a deck that is both cases at once.
    Deck 11 (Unilever) has 22 clips at 0.76-2.82 Mbps and 27 at 3.99-45 Mbps,
    with nothing in between. {name: "copy" | "encode" | {copy, crf, preset,
    bitrate}}; a file not named takes the call's own mode, so a map of only the
    exceptions is enough, and no map at all is the old behaviour exactly. A name
    that is not in `used` is an error, not a no-op: a typo there would silently
    re-encode a clip that was measured as copy.

    `audio`: "strip" is `-an`, as every deck so far has shipped -- silent
    ambient loops. "keep" preserves the track: copied as-is when it is already
    AAC (or when the video is being re-encoded it is re-encoded to AAC too), so
    a stream-copied clip stays a pure remux wherever the container allows.
    Deck 11's click-to-play films are spoken. Whether a clip PLAYS muted is the
    page's business (model.json's `muted`); what is stripped here cannot be
    given back there. A keep-build records "mode" and "audio" (does the output
    carry a track) per file; the default path writes neither, so existing
    manifests do not move."""
    assert audio in ("strip", "keep"), f"audio must be 'strip' or 'keep', got {audio!r}"
    unknown = sorted(set(modes or {}) - set(used))
    assert not unknown, f"video modes name files this deck does not use: {unknown}"
    opted_in = modes is not None or audio != "strip"
    paths.assets.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in sorted(used):
        src = paths.media / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        out_name = f"vid_{digest}.mp4"
        dst = paths.assets / out_name
        partial = paths.assets / f"vid_{digest}.__partial.mp4"
        fm = _file_mode(name, modes, copy, crf, preset, bitrate)
        if not dst.exists():
            partial.unlink(missing_ok=True)
            if fm["copy"]:
                assert not fm["bitrate"], "copy and bitrate are mutually exclusive"
                vcodec = ["-c:v", "copy"]
            else:
                rate = (["-b:v", fm["bitrate"], "-maxrate", fm["bitrate"],
                         "-bufsize", f"{int(fm['bitrate'].rstrip('Mm')) * 2}M"]
                        if fm["bitrate"] else ["-crf", str(fm["crf"])])
                vcodec = ["-c:v", "libx264", *rate, "-preset", fm["preset"],
                          "-pix_fmt", "yuv420p"]
            if audio == "strip":
                acodec = ["-an"]
            elif fm["copy"] and _audio_codec(src) == "aac":
                acodec = ["-c:a", "copy"]
            else:
                acodec = ["-c:a", "aac", "-b:a", AUDIO_BITRATE]
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src),
                 *vcodec, "-movflags", "+faststart", *acodec, str(partial)],
                check=True)
            partial.replace(dst)
        if progress:
            print(f"  {len(manifest) + 1:>3}/{len(used)}  {name:16} "
                  f"{src.stat().st_size / 1e6:7.2f} -> {dst.stat().st_size / 1e6:6.2f} MB",
                  flush=True)
        info = _probe(dst)
        manifest[name] = {"out": out_name, "sha": digest, **info,
                          "src_bytes": src.stat().st_size, **_out_hash(dst)}
        if opted_in:
            manifest[name]["mode"] = "copy" if fm["copy"] else "encode"
            manifest[name]["audio"] = _audio_codec(dst) is not None
    return manifest


def build_all(paths: DeckPaths, used_images: set[str], used_videos: set[str],
              video_kw: dict | None = None, deck: dict | None = None, **kw) -> dict:
    """`deck` (the model) switches on the crop-window image rule (see
    `_window_scale`) and supplies the colour behind each animated GIF (see
    `image_mattes`). Without it, images are capped by MAX_DIM alone and a
    transparent GIF flattens onto ffmpeg's default, white."""
    if deck is not None:
        kw.setdefault("needs", image_needs(deck))
        kw.setdefault("mattes", image_mattes(deck))
    imgs = build_images(paths, used_images, **kw)
    vids = build_videos(paths, used_videos, **(video_kw or {}))
    leftovers = sorted(p.name for p in paths.assets.glob("*.__partial.*"))
    assert not leftovers, f"partial files left in outputs (rule 8): {leftovers}"
    m = {"images": imgs, "videos": vids}
    (paths.out / "asset_manifest.json").write_text(json.dumps(m, indent=1))
    return m
