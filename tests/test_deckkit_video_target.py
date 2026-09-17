"""deckkit.model: which media part a video <p:pic> plays.

Found on deck 11 (Unilever SHPC), slide 16 -- see DECK11_HANDOFF.md section 7
item 1. PowerPoint names a video's payload twice: `<a:videoFile r:link>` and
`<p14:media r:embed>`. One clip there has a videoFile rel of
`Target="NULL" TargetMode="External"` while p14:media embeds the real file.
The parser read videoFile only, so the model carried a video called "NULL",
`used_videos` contained "NULL", and the asset stage printed `MISSING NULL`
and carried on: a silently missing video rather than an error.

The fixture is a minimal synthetic package (one master, one layout, one slide)
built in tmp_path, run through the real `build_model`, so the assertion is on
what a deck build would actually consume.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase_1c.deckkit import model as dkmodel
from phase_1c.deckkit.paths import DeckPaths

FIXTURES = Path(__file__).resolve().parents[1] / "phase_1c" / "fixtures"

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
MS_MEDIA = "http://schemas.microsoft.com/office/2007/relationships/media"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"

EMPTY_TREE = ('<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
              '<p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>{shapes}</p:spTree></p:cSld>')


def _rels(*rows):
    body = "".join(
        f'<Relationship Id="{i}" Type="{t}" Target="{tgt}"'
        + (' TargetMode="External"' if ext else "") + "/>"
        for i, t, tgt, ext in rows)
    return f'<Relationships xmlns="{PKG}">{body}</Relationships>'


def _video_pic(name, x, link_rid, media_rid, poster_rid):
    """A video <p:pic> exactly as PowerPoint writes one: videoFile by r:link,
    p14:media by r:embed inside the nvPr extLst, poster on the blip."""
    media = (f'<p:extLst><p:ext uri="{{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}}">'
             f'<p14:media xmlns:p14="{P14}" r:embed="{media_rid}"/></p:ext></p:extLst>'
             if media_rid else "")
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{x}" name="{name}"/><p:cNvPicPr/>'
            f'<p:nvPr><a:videoFile r:link="{link_rid}"/>{media}</p:nvPr></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{poster_rid}"/><a:stretch><a:fillRect/></a:stretch>'
            f'</p:blipFill><p:spPr><a:xfrm><a:off x="{x * 1000000}" y="0"/>'
            f'<a:ext cx="900000" cy="1600000"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


def _package(tmp_path, shapes, slide_rels, timing=""):
    raw = tmp_path / "raw"
    ppt = raw / "ppt"
    for d in ("_rels", "slides/_rels", "slideLayouts/_rels", "slideMasters/_rels",
              "theme", "media"):
        (ppt / d).mkdir(parents=True)
    shutil.copyfile(FIXTURES / "theme_demert_default_office.xml", ppt / "theme" / "theme1.xml")

    (ppt / "presentation.xml").write_text(
        f'<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        f'</p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
        f'<p:sldSz cx="12192000" cy="6858000"/></p:presentation>')
    (ppt / "_rels" / "presentation.xml.rels").write_text(_rels(
        ("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml", False),
        ("rId2", f"{REL}/slide", "slides/slide1.xml", False)))

    (ppt / "slideMasters" / "slideMaster1.xml").write_text(
        f'<p:sldMaster {NS}>{EMPTY_TREE.format(shapes="")}</p:sldMaster>')
    (ppt / "slideMasters" / "_rels" / "slideMaster1.xml.rels").write_text(_rels(
        ("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml", False),
        ("rId2", f"{REL}/theme", "../theme/theme1.xml", False)))

    (ppt / "slideLayouts" / "slideLayout1.xml").write_text(
        f'<p:sldLayout {NS} type="blank">'
        + EMPTY_TREE.format(shapes="").replace("<p:cSld>", '<p:cSld name="Blank">')
        + '</p:sldLayout>')
    (ppt / "slideLayouts" / "_rels" / "slideLayout1.xml.rels").write_text(_rels(
        ("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml", False)))

    (ppt / "slides" / "slide1.xml").write_text(
        f'<p:sld {NS}>{EMPTY_TREE.format(shapes=shapes)}{timing}</p:sld>')
    (ppt / "slides" / "_rels" / "slide1.xml.rels").write_text(_rels(
        ("rId99", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml", False),
        *slide_rels))
    return DeckPaths(slug="synthetic", raw=raw, out=tmp_path / "out", shots=tmp_path / "shots")


def _build(tmp_path, shapes, slide_rels):
    deck, imgs, vids = dkmodel.build_model(_package(tmp_path, shapes, slide_rels))
    videos = [s for s in deck["slides"][0]["shapes"] if s["type"] == "video"]
    return deck, vids, videos


# ---------------------------------------------------------------------------
# The deck-11 slide-16 case, reduced: videoFile -> External "NULL",
# p14:media -> the real embedded part.
# ---------------------------------------------------------------------------
def test_external_null_videofile_falls_through_to_p14_media(tmp_path):
    deck, used_videos, videos = _build(
        tmp_path,
        _video_pic("broken-link clip", 1, "rId3", "rId4", "rId5"),
        [("rId3", f"{REL}/video", "NULL", True),
         ("rId4", MS_MEDIA, "../media/media12.mp4", False),
         ("rId5", f"{REL}/image", "../media/image13.png", False)])

    assert [v["video"] for v in videos] == ["media12.mp4"], (
        "the embedded p14:media part must be the video, not the External "
        "videoFile target")
    assert used_videos == {"media12.mp4"}
    assert "NULL" not in used_videos
    assert "NULL" not in str(deck["slides"]) and "NULL" not in str(deck["coverage"]), (
        "the External rel names no part of this package: it must not surface "
        "as a video, nor as an unbound rel")
    assert deck["coverage"][0]["unbound_rels"] == [], (
        "media12.mp4 is bound through p14:media and must not read as unbound")
    assert deck["coverage"][0]["skipped"] == []


# ---------------------------------------------------------------------------
# The ordinary case must not move: videoFile and p14:media name the same part
# (every Secret clip, 48 of deck 11's 49). Both on one slide with the broken
# one, as slide 16 has them.
# ---------------------------------------------------------------------------
def test_ordinary_video_beside_a_broken_one(tmp_path):
    _, used_videos, videos = _build(
        tmp_path,
        _video_pic("ordinary clip", 1, "rId2", "rId1", "rId5")
        + _video_pic("broken-link clip", 2, "rId3", "rId4", "rId6"),
        [("rId1", MS_MEDIA, "../media/media11.mp4", False),
         ("rId2", f"{REL}/video", "../media/media11.mp4", False),
         ("rId3", f"{REL}/video", "NULL", True),
         ("rId4", MS_MEDIA, "../media/media12.mp4", False),
         ("rId5", f"{REL}/image", "../media/image12.png", False),
         ("rId6", f"{REL}/image", "../media/image13.png", False)])

    assert [v["video"] for v in videos] == ["media11.mp4", "media12.mp4"]
    assert used_videos == {"media11.mp4", "media12.mp4"}


# ---------------------------------------------------------------------------
# A 2007-style pic with no p14:media still resolves through videoFile.
# ---------------------------------------------------------------------------
def test_videofile_alone_still_resolves(tmp_path):
    _, used_videos, videos = _build(
        tmp_path,
        _video_pic("legacy clip", 1, "rId2", None, "rId5"),
        [("rId2", f"{REL}/video", "../media/media1.mp4", False),
         ("rId5", f"{REL}/image", "../media/image1.png", False)])

    assert [v["video"] for v in videos] == ["media1.mp4"]
    assert used_videos == {"media1.mp4"}


# ---------------------------------------------------------------------------
# Nothing resolvable at all -> recorded in `skipped` (rule 3: emitted or
# accounted for), never emitted as a video with a made-up filename.
# ---------------------------------------------------------------------------
def test_unresolvable_video_is_skipped_and_recorded(tmp_path):
    deck, used_videos, videos = _build(
        tmp_path,
        _video_pic("dead clip", 1, "rId3", None, "rId5")          # External only
        + _video_pic("dangling clip", 2, "rId77", None, "rId6"),  # rId not in rels
        [("rId3", f"{REL}/video", "NULL", True),
         ("rId5", f"{REL}/image", "../media/image1.png", False),
         ("rId6", f"{REL}/image", "../media/image2.png", False)])

    assert videos == [] and used_videos == set()
    skipped = deck["coverage"][0]["skipped"]
    assert [(s["name"], s["why"]) for s in skipped] == [
        ("dead clip", "video rId unresolved"),
        ("dangling clip", "video rId unresolved")]
