"""Video detection + media-shape rId resolution.

Owns: identifying which <p:pic> shapes are actually videos (not still
images), and resolving the THREE relationship ids that PPTX videos
carry:

  1. <p14:media r:embed="rIdN">   in <p:nvPicPr><p:nvPr><p:extLst>
                                   → the actual video binary (mp4)
  2. <a:videoFile r:link="rIdN">   in <p:nvPicPr><p:cNvPr><a:extLst>
                                   → legacy-compat duplicate, often
                                     points at the same target as #1
  3. <a:blip r:embed="rIdN">       in <p:blipFill>
                                   → the poster image (still frame)

Per NOTES.md entry #2 (handoff correction): videos are NOT
<p:graphicFrame> shapes — they're <p:pic> shapes carrying <p14:media>
media-extension metadata. Detection: presence of <p14:media> in the
shape subtree is the signal. Without this, the pipeline silently drops
every video.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lxml import etree
from pptx.slide import Slide

from .slide import NS

# Relationship namespace (used on r:embed / r:link attributes).
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# <p14:media> — PowerPoint 2010+ media extension marker.
P14_NS = "{http://schemas.microsoft.com/office/powerpoint/2010/main}"

# <a:videoFile> — drawingml legacy video reference.
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


@dataclass
class VideoRef:
    """Resolved video + poster + legacy compat reference.

    Only `video_blob` is load-bearing for downstream encoding; the other
    fields are diagnostic / fallback. None fields mean the source PPTX
    didn't carry that piece (irregular markup; defensive).
    """

    # The actual video binary (rId from <p14:media>).
    video_rid: Optional[str]
    video_blob: Optional[bytes]
    video_part_name: Optional[str]
    video_content_type: Optional[str]

    # Legacy-compat link (rId from <a:videoFile>). Usually duplicates the
    # media target; preserved here for forensic comparison.
    legacy_link_rid: Optional[str]
    legacy_target: Optional[str]

    # Poster image (rId from <a:blip>). Same path as parse/images.py
    # would extract — kept here so video and poster come together.
    poster_rid: Optional[str]
    poster_blob: Optional[bytes]
    poster_content_type: Optional[str]


def is_video_pic(pic_elem: etree._Element) -> bool:
    """True iff this <p:pic> carries <p14:media> media metadata.

    A <p:pic> without <p14:media> is a still image — handle via
    parse/images.py. Use this as a pre-check before calling extract_video.
    """
    return pic_elem.find(f".//{P14_NS}media") is not None


def extract_video(pic_elem: etree._Element, slide: Slide) -> Optional[VideoRef]:
    """Resolve all three video-related rIds for a <p:pic> shape.

    Returns None if the shape is not a video (no <p14:media>). Otherwise
    returns a VideoRef with each field populated where the source PPTX
    provides it.
    """
    if not is_video_pic(pic_elem):
        return None

    rels = slide.part.rels

    # (1) <p14:media r:embed=...> — the load-bearing video binary
    media = pic_elem.find(f".//{P14_NS}media")
    video_rid = media.get(R_NS + "embed") if media is not None else None
    video_blob = video_part_name = video_content_type = None
    if video_rid:
        part = slide.part.related_part(video_rid)
        video_blob = part.blob
        video_part_name = str(part.partname)
        video_content_type = part.content_type or ""

    # (2) <a:videoFile r:link=...> — legacy compat reference
    video_file = pic_elem.find(f".//{A_NS}videoFile")
    legacy_link_rid = video_file.get(R_NS + "link") if video_file is not None else None
    legacy_target = None
    if legacy_link_rid:
        try:
            legacy_target = str(rels[legacy_link_rid].target_ref)
        except (KeyError, AttributeError):
            legacy_target = None

    # (3) <a:blip r:embed=...> — poster still
    blip = pic_elem.find("p:blipFill/a:blip", NS)
    poster_rid = blip.get(R_NS + "embed") if blip is not None else None
    poster_blob = poster_content_type = None
    if poster_rid:
        part = slide.part.related_part(poster_rid)
        poster_blob = part.blob
        poster_content_type = part.content_type or ""

    return VideoRef(
        video_rid=video_rid,
        video_blob=video_blob,
        video_part_name=video_part_name,
        video_content_type=video_content_type,
        legacy_link_rid=legacy_link_rid,
        legacy_target=legacy_target,
        poster_rid=poster_rid,
        poster_blob=poster_blob,
        poster_content_type=poster_content_type,
    )
