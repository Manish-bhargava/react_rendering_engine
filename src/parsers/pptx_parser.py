"""Read an authored .pptx deck into plain shape records (optional third input).

Every measurement is converted to pixels on the 1280 x 720 canvas: a 13.333 in slide at
96 px per inch is exactly 1280 px wide. Font sizes become px (pt x 96/72).
Embedded pictures (logo, icons) are returned as bytes so the builder can save them.
"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

EMU_PER_PX = 914400 / 96          # 9525
PT_TO_PX = 96 / 72


def px(emu):
    return round(emu / EMU_PER_PX, 1)


def _color(getter):
    try:
        c = getter()
        return "#" + str(c) if c is not None else None
    except Exception:
        return None


def _fill(shape):
    try:
        if shape.fill.type == 1:                       # solid
            return "#" + str(shape.fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _line(shape):
    try:
        ln = shape.line
        if ln.fill.type == 1:
            return {"color": "#" + str(ln.color.rgb), "width": round(ln.width / EMU_PER_PX, 1) if ln.width else 1}
    except Exception:
        pass
    return None


def _font(run, para=None):
    f = run.font
    color = None
    try:
        if f.color is not None and f.color.type is not None:
            color = "#" + str(f.color.rgb)
    except Exception:
        pass
    return {
        "family": f.name,
        "sizePx": round(f.size.pt * PT_TO_PX, 1) if f.size else None,
        "bold": bool(f.bold),
        "color": color,
    }


def _paragraphs(tf):
    out = []
    for p in tf.paragraphs:
        run = p.runs[0] if p.runs else None
        align = {1: "left", 2: "center", 3: "right", 4: "justify"}.get(int(p.alignment) if p.alignment else 1, "left")
        out.append({"text": p.text, "align": align, "font": _font(run) if run else None})
    return out


def _text_frame(tf):
    anchor = {1: "top", 3: "middle", 4: "bottom"}.get(int(tf.vertical_anchor) if tf.vertical_anchor else 1, "top")
    return {
        "paragraphs": _paragraphs(tf),
        "anchor": anchor,
        "padding": [px(tf.margin_top or 0), px(tf.margin_right or 0), px(tf.margin_bottom or 0), px(tf.margin_left or 0)],
    }


def _shape_record(sh, dx=0, dy=0):
    rec = {
        "name": sh.name,
        "frame": {"x": px(sh.left + dx), "y": px(sh.top + dy), "w": px(sh.width), "h": px(sh.height)},
        "kind": "shape",
        "geometry": None,
        "fill": None, "line": None, "text": None,
    }
    st = sh.shape_type
    if st == MSO_SHAPE_TYPE.PICTURE:
        rec["kind"] = "picture"
        rec["image"] = {"blob": sh.image.blob, "ext": sh.image.ext, "sha1": sh.image.sha1}
        return rec
    if st == MSO_SHAPE_TYPE.TABLE:
        rec["kind"] = "table"
        t = sh.table
        rec["table"] = {
            "colWidths": [px(c.width) for c in t.columns],
            "rowHeights": [px(r.height) for r in t.rows],
            "cells": [[{
                "text": c.text,
                "fill": _color(lambda c=c: c.fill.fore_color.rgb if c.fill.type == 1 else None),
                "font": _font(c.text_frame.paragraphs[0].runs[0]) if c.text_frame.paragraphs[0].runs else None,
                "padding": [px(c.margin_top or 0), px(c.margin_right or 0), px(c.margin_bottom or 0), px(c.margin_left or 0)],
            } for c in r.cells] for r in t.rows],
        }
        return rec
    if st == MSO_SHAPE_TYPE.TEXT_BOX:
        rec["kind"] = "text"
    elif st == MSO_SHAPE_TYPE.AUTO_SHAPE:
        try:
            rec["geometry"] = str(sh.auto_shape_type).split(".")[-1].split(" ")[0].lower()
        except Exception:
            rec["geometry"] = "custom"
        rec["fill"], rec["line"] = _fill(sh), _line(sh)
        try:
            rec["cornerRatio"] = round(float(sh.adjustments[0]), 3) if rec["geometry"].startswith("rounded") and len(sh.adjustments) else None
        except Exception:
            rec["cornerRatio"] = None
    if getattr(sh, "has_text_frame", False) and sh.has_text_frame and sh.text_frame.text.strip():
        rec["text"] = _text_frame(sh.text_frame)
    return rec


def _walk(shapes, dx=0, dy=0):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(sh.shapes, dx, dy)
        else:
            yield _shape_record(sh, dx, dy)


def parse_deck(path):
    prs = Presentation(path)
    slides = []
    for i, s in enumerate(prs.slides, 1):
        notes = s.notes_slide.notes_text_frame.text if s.has_notes_slide else None
        slides.append({"index": i, "shapes": list(_walk(s.shapes)), "notes": notes})
    return {
        "path": path,
        "widthPx": px(prs.slide_width), "heightPx": px(prs.slide_height),
        "slides": slides,
    }


def plain(rec):
    """All text of a shape record as one string."""
    if not rec.get("text"):
        return ""
    return "\n".join(p["text"] for p in rec["text"]["paragraphs"])
