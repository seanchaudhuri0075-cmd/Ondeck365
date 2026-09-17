"""deckkit.model: a video's authored playback intent, from <p:timing>.

DECK11_HANDOFF.md section 7 item 6. Deck 11 (Unilever SHPC) is the first deck
whose clips differ in how they start -- a TV commercial that waits for a click
beside walls of clips that start on slide entry -- and the model had no field
for it. `playback` / `loop` / `muted` are ADVISORY: no renderer reads them.

Fixtures are synthetic timing trees shaped exactly like PowerPoint's: a main
sequence of steps, the interactive "click the clip to toggle pause" sequence
PowerPoint attaches to every video, and one <p:cMediaNode> per clip. Timing
targets a shape by <p:spTgt spid> == the shape's <p:cNvPr id>; `_video_pic`
uses its `x` argument as that id.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase_1c.deckkit import model as dkmodel
from tests.test_deckkit_video_target import MS_MEDIA, REL, _package, _video_pic

_ids = iter(range(100, 100000))


def _mediacall(spid, node_type, cmd="playFrom(0.0)", preset=1):
    return (f'<p:par><p:cTn id="{next(_ids)}" presetID="{preset}" presetClass="mediacall" '
            f'presetSubtype="0" fill="hold" nodeType="{node_type}">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            f'<p:cmd type="call" cmd="{cmd}"><p:cBhvr><p:cTn id="{next(_ids)}" dur="8000" fill="hold"/>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>'
            f'</p:childTnLst></p:cTn></p:par>')


def _step(effects, on_entry):
    """One top-level step of the main sequence. PowerPoint gives the FIRST
    step an `onBegin` condition when it starts by itself; a step that waits
    for a click has only `delay="indefinite"` and opens with a clickEffect."""
    cond = ('<p:cond delay="indefinite"/>'
            + ('<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>' if on_entry else ""))
    inner = "".join(f'<p:par><p:cTn id="{next(_ids)}" fill="hold"><p:stCondLst>'
                    f'<p:cond delay="0"/></p:stCondLst><p:childTnLst>{e}</p:childTnLst>'
                    f'</p:cTn></p:par>' for e in effects)
    return (f'<p:par><p:cTn id="{next(_ids)}" fill="hold"><p:stCondLst>{cond}</p:stCondLst>'
            f'<p:childTnLst>{inner}</p:childTnLst></p:cTn></p:par>')


def _interactive(spid):
    """The toggle-pause sequence PowerPoint attaches to a video: fires on a
    click ON the clip. Present on auto clips too."""
    return (f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="{next(_ids)}" restart="whenNotActive" '
            f'fill="hold" evtFilter="cancelBubble" nodeType="interactiveSeq"><p:stCondLst>'
            f'<p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cond>'
            f'</p:stCondLst><p:childTnLst>'
            f'{_step([_mediacall(spid, "clickEffect", "togglePause", preset=2)], on_entry=False)}'
            f'</p:childTnLst></p:cTn></p:seq>')


def _media_node(spid, attrs="", ctn_attrs=""):
    return (f'<p:video><p:cMediaNode {attrs}><p:cTn id="{next(_ids)}" {ctn_attrs} fill="hold" '
            f'display="0"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>')


def _timing(steps, extras):
    main = (f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
            f'<p:childTnLst>{"".join(steps)}</p:childTnLst></p:cTn></p:seq>' if steps else "")
    return (f'<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" '
            f'nodeType="tmRoot"><p:childTnLst>{main}{"".join(extras)}</p:childTnLst></p:cTn>'
            f'</p:par></p:tnLst></p:timing>')


def _videos(tmp_path, spids, timing):
    shapes, rels = "", []
    for n, spid in enumerate(spids, 1):
        shapes += _video_pic(f"clip {spid}", spid, f"rIdV{n}", f"rIdM{n}", f"rIdP{n}")
        rels += [(f"rIdV{n}", f"{REL}/video", f"../media/media{n}.mp4", False),
                 (f"rIdM{n}", MS_MEDIA, f"../media/media{n}.mp4", False),
                 (f"rIdP{n}", f"{REL}/image", f"../media/image{n}.png", False)]
    deck, _, _ = dkmodel.build_model(_package(tmp_path, shapes, rels, timing))
    return {int(s["name"].split()[-1]): s
            for s in deck["slides"][0]["shapes"] if s["type"] == "video"}


# ---------------------------------------------------------------------------
# auto: a play command in a main-sequence step that starts on slide entry.
# Both spellings -- "With Previous" and "After Previous" -- and each carries
# the interactive toggle-pause too, which must NOT demote it to "click".
# ---------------------------------------------------------------------------
def test_auto_with_and_after_effect(tmp_path):
    v = _videos(tmp_path, [4, 5], _timing(
        [_step([_mediacall(4, "withEffect"), _mediacall(5, "afterEffect")], on_entry=True)],
        [_media_node(4), _media_node(5), _interactive(4), _interactive(5)]))
    assert v[4]["playback"] == "auto"
    assert v[5]["playback"] == "auto"


# ---------------------------------------------------------------------------
# click: both ways PowerPoint writes it.
#   7 -- "In Click Sequence": a clickEffect play command in the main sequence
#   8 -- "When Clicked On":   only the interactive sequence
# ---------------------------------------------------------------------------
def test_click_in_sequence_and_when_clicked_on(tmp_path):
    v = _videos(tmp_path, [7, 8], _timing(
        [_step([_mediacall(7, "clickEffect")], on_entry=False)],
        [_media_node(7), _media_node(8), _interactive(7), _interactive(8)]))
    assert v[7]["playback"] == "click"
    assert v[8]["playback"] == "click"


# ---------------------------------------------------------------------------
# none: nothing targets the clip. Three shapes of "nothing": no <p:timing> at
# all, a timing tree about some OTHER shape, and a bare media node (which
# declares the clip but starts nothing).
# ---------------------------------------------------------------------------
def test_none_without_timing(tmp_path):
    v = _videos(tmp_path, [4], "")
    assert v[4]["playback"] == "none"
    assert "loop" not in v[4] and "muted" not in v[4]


def test_none_when_timing_targets_other_shapes(tmp_path):
    v = _videos(tmp_path, [4, 5], _timing(
        [_step([_mediacall(5, "withEffect")], on_entry=True)],
        [_media_node(4), _media_node(5)]))
    assert v[4]["playback"] == "none", "a media node declares a clip; it does not start it"
    assert v[5]["playback"] == "auto"


# ---------------------------------------------------------------------------
# One slide mixing auto and click -- deck 11's actual situation.
# 6 is the trap: a withEffect play command riding along in a step that WAITS
# FOR A CLICK. Its nodeType says "with previous"; the previous thing is a
# click, so it does not start on slide entry.
# ---------------------------------------------------------------------------
def test_mixed_auto_and_click_on_one_slide(tmp_path):
    v = _videos(tmp_path, [4, 5, 6, 9], _timing(
        [_step([_mediacall(4, "withEffect")], on_entry=True),
         _step([_mediacall(5, "clickEffect"), _mediacall(6, "withEffect")], on_entry=False)],
        [_media_node(s) for s in (4, 5, 6, 9)] + [_interactive(s) for s in (4, 5, 6)]))
    assert {k: s["playback"] for k, s in v.items()} == {
        4: "auto", 5: "click", 6: "click", 9: "none"}


# ---------------------------------------------------------------------------
# loop / muted: recorded only when the XML states them, with the value it
# states. Absent attribute -> absent key.
# ---------------------------------------------------------------------------
def test_loop_and_muted_only_when_stated(tmp_path):
    v = _videos(tmp_path, [4, 5, 6, 7], _timing(
        [_step([_mediacall(s, "withEffect") for s in (4, 5, 6, 7)], on_entry=True)],
        [_media_node(4, 'vol="80000" mute="1"', 'repeatCount="indefinite"'),
         _media_node(5, 'vol="80000"'),
         _media_node(6, 'mute="0"', 'repeatCount="2000"'),
         _media_node(7, 'mute="1"')]))
    assert (v[4]["loop"], v[4]["muted"]) == (True, True)
    assert "loop" not in v[5] and "muted" not in v[5], "vol alone states neither"
    assert (v[6]["loop"], v[6]["muted"]) == (False, False), (
        "a stated finite repeatCount is stated-and-not-looping; mute=0 is stated-and-audible")
    assert v[7]["muted"] is True and "loop" not in v[7]


# ---------------------------------------------------------------------------
# Only a command that can START a clip counts. A stop on slide entry is not
# autoplay, and it is not click-to-play either.
# ---------------------------------------------------------------------------
def test_stop_command_starts_nothing(tmp_path):
    v = _videos(tmp_path, [4], _timing(
        [_step([_mediacall(4, "withEffect", cmd="stop")], on_entry=True)], [_media_node(4)]))
    assert v[4]["playback"] == "none"
