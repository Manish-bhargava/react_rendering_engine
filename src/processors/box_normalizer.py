"""Make deck-measured boxes readable and uniform.

Two problems come straight out of PowerPoint and have to be corrected before the
measurements are usable as a layout:

1. **Text insets.** Every text frame carries PowerPoint's default inset of
   0.05 in top/bottom and 0.1 in left/right (4.8 px and 9.6 px at 96 dpi). Inside a
   filled chip, a bordered rationale panel or a sequence slot that puts the text hard
   against the edge. Each *boxed* role gets a readable minimum instead, capped as a
   share of the box's own size so a short box can never be squeezed shut. Bare text
   frames keep the deck inset: their padding is what aligns them with everything else
   on the slide, so raising it would pull them out of line.

2. **Icon tiles.** A deck draws each icon at whatever size the author dropped it in, so
   one icon row can hold tiles from 40 px to 110 px sitting on five different
   baselines. Every icon in a grid is squared to one size and sits on one baseline,
   centred over its label.

Numbers only: this pass adds, removes and renames nothing.
"""
from collections import Counter

# Minimum internal padding, per boxed role: (top, right, bottom, left) in px.
# Roles not listed keep whatever the deck gave them.
BOX_PADDING = {
    "header": (8, 16, 8, 16),             # chips above a card / comparison column
    "slot": (12, 24, 12, 24),             # sequence slots (the index sits in the left gutter)
    "typeBadge": (10, 18, 10, 18),
    "verdictCorrect": (10, 18, 10, 18),
    "verdictIncorrect": (10, 18, 10, 18),
    "rationale": (14, 20, 14, 20),
    "prevButton": (6, 14, 6, 14),
    "nextButton": (6, 14, 6, 14),
    "layerHeader": (8, 16, 8, 16),        # parts.layerStyle.header
}

# A box never gives up more than this share of its own height/width to padding per side.
V_CAP = 0.25
H_CAP = 0.15

# Table cells are drawn by the player, not by a text frame, so their inset lives here.
CELL_PADDING = (8, 16, 8, 16)

MIN_ICON_GAP = 8          # px between an icon's baseline and its label
DEFAULT_ICON_SIDE = 88    # px, used only when a grid gives no usable sizes

# One left margin for the whole course. The deck keeps its title placeholder at x=17
# and everything else at x=48, so headings sit ~31 px left of the content under them.
LEFT_MARGIN = 48

# A chip whose body is a column of this width or less is widened to match that column;
# a chip over a full-width body is only widened as far as its own label needs.
COLUMN_MAX = 700
# Rough advance width of Montserrat Bold as a fraction of the em, used to tell whether
# a chip label would wrap. Deliberately generous: a chip that is too wide costs nothing.
CHAR_EM = 0.58
CHIP_SLACK = 14

COVER_LOGO_GAP = 12       # px of clear space between the cover logo and the player bar


def _visible_shape(spec):
    sh = spec.get("shape") or {}
    return bool(sh.get("fill") or sh.get("border"))


def _pad_target(role, frame, want):
    """Clamp the wanted padding so it can never eat the box."""
    h = (frame or {}).get("h") or 0
    w = (frame or {}).get("w") or 0
    vmax = h * V_CAP if h else want[0]
    hmax = w * H_CAP if w else want[1]
    return [
        round(min(want[0], vmax), 1), round(min(want[1], hmax), 1),
        round(min(want[2], vmax), 1), round(min(want[3], hmax), 1),
    ]


def _apply_padding(role, spec, stats):
    """Raise one boxed spec's text inset to the role minimum."""
    if not isinstance(spec, dict) or role not in BOX_PADDING or not _visible_shape(spec):
        return
    text = spec.get("text")
    if not isinstance(text, dict) or not isinstance(text.get("padding"), list):
        return
    want = _pad_target(role, spec.get("frame"), BOX_PADDING[role])
    have = [round(float(v), 1) for v in text["padding"]]
    if want != have and any(a > b for a, b in zip(want, have)):
        text["padding"] = [max(a, b) for a, b in zip(want, have)]
        stats["padded"] += 1


def _walk_padding(spec, stats):
    """Visit every named sub-spec of one component's measurements."""
    for key in ("parts", "items", "slots"):
        node = spec.get(key)
        if isinstance(node, dict):
            for role, sub in node.items():
                if role == "layerStyle" and isinstance(sub, dict):
                    _apply_padding("layerHeader", sub.get("header"), stats)
                    continue
                _apply_padding(role, sub, stats)
        elif isinstance(node, list):
            for entry in node:
                if not isinstance(entry, dict):
                    continue
                if key == "slots":
                    _apply_padding("slot", entry, stats)
                else:
                    for role, sub in entry.items():
                        _apply_padding(role, sub, stats)
    if isinstance(spec.get("table"), dict):
        spec["table"]["cellPadding"] = list(CELL_PADDING)
        stats["tables"] += 1


def _rows(items):
    """Group icon items into visual rows by the top edge of their labels."""
    rows, order = {}, []
    for i, it in enumerate(items):
        label = (it or {}).get("label") or {}
        y = round(((label.get("frame") or {}).get("y", 0)) / 12) * 12
        if y not in rows:
            rows[y] = []
            order.append(y)
        rows[y].append(i)
    return [rows[y] for y in order]


def _uniform_icons(spec, stats):
    """Square every icon in one grid to a single size on a single baseline."""
    items = spec.get("items")
    if not isinstance(items, list):
        return
    sized = [it for it in items if isinstance(it, dict) and isinstance((it.get("icon") or {}).get("frame"), dict)]
    if len(sized) < 2:
        return

    longest = [max(it["icon"]["frame"]["w"], it["icon"]["frame"]["h"]) for it in sized]
    common = Counter(round(v) for v in longest).most_common(1)
    side = common[0][0] if common and common[0][1] > 1 else round(sorted(longest)[len(longest) // 2])
    side = side or DEFAULT_ICON_SIDE
    if all(round(it["icon"]["frame"]["w"]) == side and round(it["icon"]["frame"]["h"]) == side for it in sized):
        return

    for row in _rows(items):
        entries = [items[i] for i in row
                   if isinstance(items[i], dict) and isinstance((items[i].get("icon") or {}).get("frame"), dict)]
        if not entries:
            continue
        gaps = []
        for it in entries:
            label = (it.get("label") or {}).get("frame")
            icon = it["icon"]["frame"]
            if label:
                gaps.append(label["y"] - (icon["y"] + icon["h"]))
        gap = max(MIN_ICON_GAP, round(sorted(gaps)[len(gaps) // 2])) if gaps else MIN_ICON_GAP
        tops = [((it.get("label") or {}).get("frame") or {}).get("y") for it in entries]
        tops = [t for t in tops if t is not None]
        baseline = (min(tops) - gap) if tops else None

        for it in entries:
            icon = it["icon"]["frame"]
            label = (it.get("label") or {}).get("frame")
            centre = (label["x"] + label["w"] / 2) if label else (icon["x"] + icon["w"] / 2)
            bottom = baseline if baseline is not None else icon["y"] + icon["h"]
            icon["w"] = icon["h"] = side
            icon["x"] = int(round(centre - side / 2))
            icon["y"] = int(round(bottom - side))
        stats["icons"] += len(entries)


# ---------------------------------------------------------------- left margin
def _align_left_margin(measured, components, cover_slides, stats):
    """Put every heading on the same left margin as the content under it.

    The deck's title placeholder starts at x=17 and its content at x=48, so on all
    forty content slides the heading text sits about 31 px to the left of the chips,
    body text and callouts below it. Cover slides are left alone: their heading is
    part of the cover artwork, not a column.
    """
    for mod in components["modules"]:
        for slide in mod["slides"]:
            if slide["slideId"] in cover_slides:
                continue
            for c in slide["components"]:
                spec = measured.get(c["id"])
                frame = (spec or {}).get("frame")
                if not frame or frame["x"] >= LEFT_MARGIN:
                    continue
                shift = LEFT_MARGIN - frame["x"]
                frame["x"] = LEFT_MARGIN
                frame["w"] = max(40, frame["w"] - shift)
                _shift_parts(spec, shift)
                stats["aligned"] += 1


def _shift_parts(spec, shift):
    """Move a component's sub-frames with it, so nothing comes adrift."""
    def walk(node):
        if isinstance(node, dict):
            f = node.get("frame")
            if isinstance(f, dict) and "x" in f:
                f["x"] += shift
            for k, v in node.items():
                if k != "frame":
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for key in ("parts", "items", "slots"):
        walk(spec.get(key))


# ---------------------------------------------------------------- chips
def _chip_text_width(title, style, pad):
    size = (style or {}).get("fontSize") or 16
    return len(title) * CHAR_EM * size + (pad[1] + pad[3] if pad else 32) + CHIP_SLACK


def _fit_chips(measured, components, stats):
    """Stop a card's chip reading as a stub above a much wider body.

    Over a column the chip takes the column's width, so chip and body share an edge
    on both sides. Over a full-width body a full-width chip would be a heavy green
    band, so it only grows as far as its longest label needs.
    """
    for mod in components["modules"]:
        for slide in mod["slides"]:
            for c in slide["components"]:
                if c["type"] not in ("cardGrid", "comparison"):
                    continue
                spec = measured.get(c["id"])
                entries = (spec or {}).get("items")
                if not isinstance(entries, list):
                    continue
                titles = [k["title"] for k in (c["props"].get("cards") or c["props"].get("columns") or [])]
                headers = [e.get("header") for e in entries if isinstance(e, dict) and isinstance(e.get("header"), dict)]
                bodies = [e.get("body") for e in entries if isinstance(e, dict) and isinstance(e.get("body"), dict)]
                if not headers or not bodies:
                    continue
                chip_w = max(h["frame"]["w"] for h in headers)
                col_w = max(b["frame"]["w"] for b in bodies)
                if col_w <= COLUMN_MAX:
                    target = max(chip_w, col_w)
                else:
                    need = max((_chip_text_width(t, (h.get("text") or {}).get("style"),
                                                 (h.get("text") or {}).get("padding"))
                                for t, h in zip(titles, headers)), default=chip_w)
                    target = min(col_w, max(chip_w, need))
                target = int(round(target))
                if target == chip_w:
                    continue
                for h in headers:
                    h["frame"]["w"] = target
                stats["chips"] += len(headers)


# ---------------------------------------------------------------- chrome
def _centre_children(parent, children):
    """Re-centre a band's contents on the band after the band has been resized."""
    mid = parent["frame"]["y"] + parent["frame"]["h"] / 2
    for ch in children:
        f = (ch or {}).get("frame")
        if f:
            f["y"] = int(round(mid - f["h"] / 2))


def _fit_chrome(furniture, canvas_h, stats):
    """Close the seam under the header and the strip under the player bar.

    The deck's logo plate is taller than its header band, so the white plate hangs
    below the teal and leaves a step; the band grows to meet it and the plate is
    squared to the band. The player bar stops 7 px short of the bottom of the canvas,
    which shows as a sliver of slide background under the footer; it is extended to
    the edge and its controls re-centred on the taller bar.
    """
    band, plate, logo = furniture.get("headerBand"), furniture.get("logoPlate"), furniture.get("logo")
    if band and plate:
        bottom = max(band["frame"]["y"] + band["frame"]["h"], plate["frame"]["y"] + plate["frame"]["h"])
        band["frame"]["y"] = 0
        band["frame"]["h"] = int(round(bottom))
        plate["frame"]["y"] = 0
        plate["frame"]["h"] = band["frame"]["h"]
        _centre_children(band, [logo, furniture.get("breadcrumb"), furniture.get("topLinks")])
        stats["chrome"] += 1

    bar = furniture.get("playerBar")
    if bar and canvas_h:
        bar["frame"]["h"] = int(round(canvas_h - bar["frame"]["y"]))
        _centre_children(bar, [furniture.get(k) for k in
                               ("playButton", "progressTrack", "progressFill", "prevButton", "nextButton")])
        stats["chrome"] += 1


def _lift_cover_logo(cover, furniture, stats):
    """Lift the cover logo clear of the player bar.

    The authored cover has no player bar, so it puts the logo in the bottom-right
    corner, exactly where the player's footer now sits: the bar covered the lower
    third of the mark. The logo keeps its size and corner and moves up.
    """
    bar = (furniture or {}).get("playerBar")
    plate, logo = (cover or {}).get("logoPlate"), (cover or {}).get("logo")
    if not (bar and plate and logo):
        return
    limit = bar["frame"]["y"] - COVER_LOGO_GAP
    overlap = (plate["frame"]["y"] + plate["frame"]["h"]) - limit
    if overlap <= 0:
        return
    for part in (plate, logo):
        part["frame"]["y"] = int(round(part["frame"]["y"] - overlap))
    stats["cover"] += 1


def normalize(measured, components=None, furniture=None, cover=None, canvas_h=720):
    """Correct every measured component in place. Returns a small stats dict."""
    stats = Counter()
    for spec in (measured or {}).values():
        if not isinstance(spec, dict):
            continue
        _walk_padding(spec, stats)
        _uniform_icons(spec, stats)
    if components:
        cover_slides = {s["slideId"] for m in components["modules"]
                        for s in m["slides"] if s.get("layout") == "title"}
        _align_left_margin(measured, components, cover_slides, stats)
        _fit_chips(measured, components, stats)
    if isinstance(furniture, dict):
        for role in ("prevButton", "nextButton"):
            _apply_padding(role, furniture.get(role), stats)
        _fit_chrome(furniture, canvas_h, stats)
        _lift_cover_logo(cover, furniture, stats)
    return {"paddedBoxes": stats["padded"], "uniformIcons": stats["icons"], "tables": stats["tables"],
            "alignedLeft": stats["aligned"], "widenedChips": stats["chips"],
            "chromeFixes": stats["chrome"], "coverLogoLifted": bool(stats["cover"])}
