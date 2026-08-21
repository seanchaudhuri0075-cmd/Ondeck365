"""Slide archetype classification — shape-signature based, not per-slide manual tagging.

Phase 1B's LEARNINGS.md flagged auto-classification as deliberately deferred
until the pipeline had seen enough deck variety to know what "typical" looks
like ("Open gaps" section). That variety now exists (P&G's curated templates,
this deck's freeform patterns). This module is the first cut: classify a
slide by the *shapes it actually contains*, not by guessing from its
position in the deck or requiring an operator to hand-tag it.

The payoff isn't cosmetic categorization — it's routing. Two consumers read
these labels: (1) which desktop template a slide should use (existing,
manifest-driven work this module doesn't replace, only informs), and (2)
which *mobile* treatment a slide gets. Naive reflow (stack everything in
z-order) is the wrong mobile answer for several of these archetypes — a
decorative bleed-text acrostic doesn't reflow into anything meaningful, a
full-bleed photo with a caption wants the caption overlaid not stacked
below. Classify first, design the mobile treatment per archetype second.

Operates on the same `items` list freeform.py already builds (shape +
parsed text frame, where applicable) — no separate parse pass.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Archetype:
    label: str
    # Human-readable reason, useful in logs/manifests when a classification
    # looks wrong and someone needs to see why the classifier picked it.
    reason: str


def classify_slide(items: list, slide_w_pt: float) -> Archetype:
    """Classify a slide from freeform.py's `items` list (shape + parsed frame).

    Each item is a dict with at least `"type"` ("text" | "image" | "rect")
    and `"shape"` (a FlatShape); text items also carry `"frame"` (a parsed
    TextFrame with `.paragraphs`).
    """
    text_items = [it for it in items if it["type"] == "text"]
    image_items = [it for it in items if it["type"] == "image"]

    off_canvas_text = [
        it for it in text_items if it["shape"].x_pt is not None and it["shape"].x_pt < 0
    ]
    off_canvas_ids = {id(it) for it in off_canvas_text}
    on_canvas_text = [it for it in text_items if id(it) not in off_canvas_ids]

    has_bullets = any(
        p.bullet_char for it in on_canvas_text for p in it["frame"].paragraphs
    )
    full_bleed_images = [
        it for it in image_items
        if it["shape"].w_pt and it["shape"].h_pt and it["shape"].w_pt >= slide_w_pt * 0.5
    ]

    # A short on-canvas text shape (a handful of words, no bullets) paired
    # with a large image and nothing else of substance is a caption-over-
    # photo pattern — the caption should overlay the photo on mobile, not
    # stack below it as a separate block (that's the "naive reflow is the
    # wrong answer" case this module exists for).
    body_word_counts = [
        sum(len(r.text.split()) for p in it["frame"].paragraphs for r in p.runs)
        for it in on_canvas_text
    ]
    is_caption_length = bool(body_word_counts) and max(body_word_counts, default=0) <= 12

    if off_canvas_text:
        label = "acrostic_bleed_bulleted" if has_bullets else "acrostic_bleed_plain"
        reason = (
            f"{len(off_canvas_text)} text shape(s) bleed off the left canvas edge "
            f"(decorative brand-word column)"
            + (", with bulleted body content" if has_bullets else "")
        )
    elif full_bleed_images and on_canvas_text and is_caption_length and not has_bullets:
        label = "photo_with_caption"
        reason = f"{len(full_bleed_images)} full-bleed image(s) with short caption text, no bullets"
    elif full_bleed_images and not on_canvas_text:
        label = "photo_only"
        reason = f"{len(full_bleed_images)} full-bleed image(s), no on-canvas text"
    elif on_canvas_text and has_bullets:
        label = "bulleted_list"
        reason = "on-canvas text with bulleted paragraphs, no decorative bleed column"
    elif on_canvas_text and len(on_canvas_text) <= 2 and not image_items:
        label = "title_or_cover"
        reason = "one or two short text shapes, no images"
    else:
        label = "generic"
        reason = "no shape signature matched a known archetype"

    return Archetype(label=label, reason=reason)
