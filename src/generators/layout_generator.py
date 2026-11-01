"""Build layout.json: HOW and WHERE each component appears.

Coordinates are pixels on a 1280 x 720 canvas, origin top-left, x right, y down.
All positions are INFERRED from the storyboard's layout type, image placement and
image size - they are not measurements from the original PowerPoint.
Image frames use the storyboard `size_in` at 96 px per inch (13.333 in slide = 1280 px).

Each slide lists its components with a `frame` (the box the component occupies) and,
where the component has inner structure, an `arrange` block (CSS grid / flex) that the
player applies inside that box.
"""

W, H = 1280, 720
M = 64                       # side margin
CONTENT_W = W - 2 * M        # 1152
HEADING_Y, HEADING_H = 76, 56
INSTR_Y, INSTR_H = 136, 32
BODY_Y = 184
CALLOUT_Y, CALLOUT_H = 568, 72
BODY_BOTTOM_WITH_CALLOUT = 548
BODY_BOTTOM = 640
GAP = 32
PX_PER_IN = 96

TOKENS = {
    # Palette from the client house style (elearning-authoring/references/house-style.md)
    "colors": {
        "primary": "#62C7DD",          # header band / cover field (teal)
        "primaryDark": "#1F9BD8",      # player bar controls
        "primaryTint": "#EBFFFF",      # player bar
        "secondary": "#6EA536",        # heading green
        "accent": "#92D050",           # chips, badges, table header
        "learner": "#FF6600",          # instructions, scoping sentence (learner orange)
        "background": "#FFFFFF",
        "surface": "#F2F7EB",          # panel tint
        "border": "#C8E0AE",           # panel rule
        "text": "#000000",
        "textMuted": "#7F7F7F",
        "textOnPrimary": "#FFFFFF",
        "warning": "#C00000", "warningBg": "#FFFFFF",
        "note": "#7F7F7F", "noteBg": "#FFFFFF",
        "tip": "#6EA536", "tipBg": "#FFFFFF",
        "correct": "#6EA536", "incorrect": "#C00000",
    },
    "font": {
        "family": "Montserrat, Calibri, Carlito, 'Segoe UI', Arial, sans-serif",
        "sizes": {"display": 37, "h1": 28, "h2": 19, "body": 16, "small": 14, "caption": 11},
        "weights": {"regular": 400, "semibold": 600, "bold": 700},
        "lineHeight": 1.2,
    },
    "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 48},
    "radius": {"sm": 6, "md": 10, "lg": 16, "xl": 48, "pill": 999},
    "shadows": {
        "card": "none",
        "raised": "0 6px 18px rgba(0, 0, 0, 0.14)",
    },
}

# Default look of each component type; slide entries only carry overrides.
COMPONENT_STYLES = {
    "heading": {"fontSize": "h1", "fontWeight": "bold", "color": "secondary"},
    "paragraph": {"fontSize": "body", "color": "text"},
    "instruction": {"fontSize": "small", "fontWeight": "semibold", "color": "primaryDark"},
    "image": {"radius": "md", "objectFit": "cover", "placeholderBackground": "surface", "border": "border"},
    "callout": {"padding": "md", "radius": "md", "fontSize": "body", "borderLeftWidth": 6,
                "kinds": {"warning": ["warning", "warningBg"], "note": ["note", "noteBg"], "tip": ["tip", "tipBg"]}},
    "bulletList": {"fontSize": "body", "marker": "check", "markerColor": "primary", "itemGap": "md"},
    "objectivesList": {"fontSize": "body", "marker": "number", "markerColor": "primary", "itemGap": "md"},
    "iconGrid": {"itemBackground": "background", "itemBorder": "border", "radius": "md", "shadow": "card",
                 "iconSize": 40, "iconColor": "primaryDark", "fontSize": "body", "padding": "md"},
    "cardGrid": {"cardBackground": "background", "cardBorder": "border", "accentTop": "primary",
                 "radius": "md", "shadow": "card", "padding": "lg", "titleSize": "h2", "bodySize": "body"},
    "definition": {"termSize": "h2", "termColor": "primaryDark", "bodySize": "body", "divider": "border"},
    "process": {"badgeColor": "primary", "badgeText": "textOnPrimary", "connector": "arrow",
                "stepBackground": "surface", "radius": "md"},
    "comparison": {"columnBackground": "surface", "headerBackground": "primaryDark", "headerText": "textOnPrimary",
                   "radius": "md", "divider": "vs"},
    "table": {"headerBackground": "primaryDark", "headerText": "textOnPrimary", "stripe": "surface",
              "border": "border", "fontSize": "body", "cellPadding": "md", "radius": "md"},
    "multipleChoice": {"optionBackground": "background", "optionBorder": "border", "selectedBorder": "primary",
                       "radius": "md", "fontSize": "body", "stemSize": "h2"},
    "sequence": {"itemBackground": "background", "itemBorder": "border", "radius": "md", "fontSize": "body"},
    "matching": {"itemBackground": "background", "itemBorder": "border", "radius": "md", "fontSize": "body"},
    "trueFalse": {"optionBackground": "background", "optionBorder": "border", "selectedBorder": "primary",
                  "radius": "md", "fontSize": "body", "stemSize": "h2"},
    "multiSelect": {"optionBackground": "background", "optionBorder": "border", "selectedBorder": "primary",
                    "radius": "md", "fontSize": "body", "stemSize": "h2"},
    "summary": {"marker": "check", "markerColor": "primary", "fontSize": "body", "cardBackground": "surface"},
    "references": {"fontSize": "small", "color": "text", "itemGap": "md", "hangingIndent": 24},
    "results": {"fontSize": "h2", "align": "center"},
}

BACKGROUNDS = {
    "title": {"color": "secondary"},
    "knowledge-check": {"color": "primaryTint"},
    "sequence": {"color": "primaryTint"},
    "match": {"color": "primaryTint"},
    "true-false": {"color": "primaryTint"},
    "multi-select": {"color": "primaryTint"},
    "results": {"color": "primaryTint"},
}


def frame(x, y, w, h):
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}


def img_px(size_in):
    return [round(size_in[0] * PX_PER_IN), round(size_in[1] * PX_PER_IN)] if size_in else [384, 288]


def by_type(comps, t):
    return [c for c in comps if c["type"] == t]


def grid_cols(n, max_cols=4):
    if n <= max_cols:
        return n
    return 4 if n in (7, 8) else (5 if n in (9, 10) else max_cols)


def layout_slide(slide, measured=None):
    comps = slide["components"]
    lay = slide["layout"]
    items = []

    def add(c, fr, arrange=None, style=None):
        e = {"componentId": c["id"], "order": len(items) + 1, "frame": fr}
        if arrange:
            e["arrange"] = arrange
        if style:
            e["style"] = style
        items.append(e)

    heading = by_type(comps, "heading")
    instr = by_type(comps, "instruction")
    images = by_type(comps, "image")
    callouts = by_type(comps, "callout")
    main = [c for c in comps if c["type"] not in ("heading", "instruction", "image", "callout", "paragraph")]

    # ----- title: house cover (DEFAULT_COVER). The image sits inside the white disc on
    # the left, the title block on the teal field to the right, the logo plate bottom right.
    if lay == "title":
        img = images[0] if images else None
        if img:
            add(img, frame(*COVER_IMAGE), style={"radius": "xl"})
        tx, tw = COVER_TEXT_X, W - COVER_TEXT_X - M
        add(heading[0], frame(tx, 186, tw, 80),
            style={"fontSize": "display", "color": "textOnPrimary"})
        # all paragraphs on the teal field are white; the last one (the byline) sits at y≈423
        paras = by_type(comps, "paragraph")
        for i, p in enumerate(paras):
            y = 395 if i == len(paras) - 1 else 282 + i * 48
            add(p, frame(tx, y, tw, 56), style={"fontSize": "h2", "color": "textOnPrimary"})
        return apply_measured(slide, items, measured)

    # ----- common header -----
    if heading:
        add(heading[0], frame(M, HEADING_Y, CONTENT_W, HEADING_H))
    body_y = BODY_Y if instr else INSTR_Y + 8
    if instr:
        add(instr[0], frame(M, INSTR_Y, CONTENT_W, INSTR_H))
    bottom = BODY_BOTTOM_WITH_CALLOUT if callouts else BODY_BOTTOM

    # image beside the main content (storyboard placement: right / left)
    body_x, body_w = M, CONTENT_W
    pending_image = None
    if images and lay != "title":
        img = images[0]
        iw, ih = img_px(img["props"]["sizeIn"])
        ih = min(ih, bottom - body_y)
        # added after the main content so stacked (mobile) order reads content first
        if img["props"]["placement"] == "left":
            pending_image = (img, frame(M, body_y, iw, ih))
            body_x, body_w = M + iw + GAP, CONTENT_W - iw - GAP
        else:
            pending_image = (img, frame(W - M - iw, body_y, iw, ih))
            body_w = CONTENT_W - iw - GAP
    body_h = bottom - body_y

    for c in main:
        t = c["type"]
        fr = frame(body_x, body_y, body_w, body_h)
        arrange, style = None, None
        if t == "iconGrid":
            n = len(c["props"]["items"])
            cols = grid_cols(n, 4 if body_w > 900 else 3)
            arrange = {"display": "grid", "columns": cols, "gap": 16, "alignContent": "center"}
            if "interaction" in c["props"]:
                style = {"hoverBorder": "primary", "visitedMarker": True}
        elif t == "cardGrid":
            n = len(c["props"]["cards"])
            cols = 2 if n == 4 else min(n, 3)
            arrange = {"display": "grid", "columns": cols, "gap": 20, "alignContent": "center"}
        elif t == "definition":
            arrange = {"display": "flex", "direction": "column", "gap": 24, "justify": "center"}
        elif t == "bulletList":
            arrange = {"display": "flex", "direction": "column", "gap": 16, "justify": "center"}
        elif t == "objectivesList":
            arrange = {"display": "flex", "direction": "column", "gap": 14, "justify": "center"}
        elif t == "process":
            n = len(c["props"]["steps"])
            if "interaction" in c["props"]:
                # stage tabs on the left, the open layer's panel beside them
                arrange = {"display": "grid", "columns": "300px 1fr", "gap": 24,
                           "tabs": {"direction": "column", "gap": 10},
                           "layerPanel": {"background": "background", "border": "primary",
                                          "shadow": "raised", "radius": "md", "padding": "lg"}}
            else:
                fr = frame(body_x, body_y + 70, body_w, 240)
                arrange = {"display": "grid", "columns": n, "gap": 40, "connector": "arrow"}
        elif t == "comparison":
            arrange = {"display": "grid", "columns": len(c["props"]["columns"]), "gap": 48, "divider": "vs"}
        elif t == "table":
            widths = c["props"].get("colWidthsIn")
            cols = " ".join(f"{w}fr" for w in widths) if widths else None
            arrange = {"display": "table", "columnTemplate": cols, "align": "start"}
            fr = frame(body_x, body_y + 8, body_w, body_h - 8)
        elif t in ("multipleChoice", "sequence", "matching", "trueFalse", "multiSelect"):
            fr = frame(160, body_y, 960, BODY_BOTTOM - body_y)
            arrange = {"display": "flex", "direction": "column", "gap": 12,
                       "feedbackOverlay": {"position": "absolute", "frame": frame(320, 200, 640, 320),
                                           "background": "background", "shadow": "raised", "radius": "lg",
                                           "scrim": "rgba(16,42,67,0.45)"}}
        elif t == "summary":
            arrange = {"display": "grid", "columns": 2, "gap": 16, "alignContent": "center"}
        elif t == "references":
            arrange = {"display": "flex", "direction": "column", "gap": 16, "justify": "start"}
        elif t == "results":
            fr = frame(240, 260, 800, 200)
            arrange = {"display": "flex", "direction": "column", "gap": 16, "align": "center", "justify": "center"}
        add(c, fr, arrange, style)

    if pending_image:
        add(*pending_image)
    for i, c in enumerate(callouts):
        add(c, frame(M, CALLOUT_Y + i * (CALLOUT_H + 8), CONTENT_W, CALLOUT_H))
    return apply_measured(slide, items, measured)


def apply_measured(slide, items, measured):
    """Replace inferred entries with deck measurements where a component was matched."""
    if not measured:
        for e in items:
            e["source"] = "inferred"
        return items
    by_id = {e["componentId"]: e for e in items}
    out = []
    for n, c in enumerate(slide["components"], 1):
        m = measured.get(c["id"])
        if m:
            e = {"componentId": c["id"], "order": n, **{k: v for k, v in m.items()}}
        else:
            e = dict(by_id.get(c["id"]) or {"componentId": c["id"], "frame": frame(M, BODY_Y, CONTENT_W, 80)})
            e["order"] = n
            e["source"] = "inferred"
        out.append(e)
    return out


def generate_layout(components_doc, deck=None):
    deck = deck or {}
    measured = deck.get("measured") or {}
    slides = []
    for m in components_doc["modules"]:
        for s in m["slides"]:
            meta = (deck.get("slides") or {}).get(s["slideId"])
            entry = {
                "slideId": s["slideId"],
                "moduleId": m["moduleId"],
                "template": s["layout"],
                # with a deck, every content slide is white, as authored
                "background": {"color": "background"} if meta else BACKGROUNDS.get(s["layout"], {"color": "background"}),
                "showHeaderBand": s["layout"] != "title",
                "positionSource": f"{meta['deck']} slide {meta['deckSlide']}" if meta else "inferred",
                "items": layout_slide(s, measured if meta else None),
            }
            if s["layout"] == "title":
                cover = deck.get("cover") or DEFAULT_COVER
                entry["background"] = {"color": cover.get("background")}
                entry["cover"] = cover
            slides.append(entry)
    furniture = deck.get("furniture") or DEFAULT_FURNITURE
    return {
        "specVersion": "v1",
        "canvas": {"width": W, "height": H, "unit": "px", "origin": "top-left",
                   "xAxis": "right", "yAxis": "down"},
        "positionSource": ("Measured from the authored decks wherever a component matched a deck shape "
                           "(each item carries `source`). Anything else is inferred from the storyboard layout type, "
                           "image placement and size_in at 96 px per inch."
                           if measured else
                           "Inferred from storyboard layout type, image placement and image size_in "
                           "(96 px per inch). Not original PowerPoint measurements."),
        "tokens": TOKENS,
        "componentStyles": COMPONENT_STYLES,
        "furniture": furniture,
        "assets": deck.get("assets", []),
        "responsive": {
            "mode": "scale-to-fit",
            "description": ("Above the breakpoint the 1280x720 stage is scaled uniformly to fit the space "
                            "left under the toolbar, between minScale and maxScale."),
            # below ~900 px a scaled stage puts body text under 12 px, so the column takes over
            "stackBelowPx": 900,
            "minScale": 0.5,
            "maxScale": 1.6,
            "stackedBehaviour": "Frames are ignored; components flow in a single column in `order`, full width.",
        },
        "slides": slides,
    }


# ---------------------------------------------------------------------------------
# House chrome used when no authored deck is supplied. Same shape as the deck matcher's
# `furniture` / `cover` (deck_matcher.chrome_from / cover_from), so the player draws it
# with the same DeckChrome / DeckPlayerBar renderers. Frames are taken from the house
# reference screenshot (1572 px wide, scaled by 1280/1572 onto the canvas).
# ---------------------------------------------------------------------------------
_C = TOKENS["colors"]
BRAND_LOGO = "assets/brand/logo.png"      # extracted to output/assets/, synced to player/public/assets/
WHITE = "#FFFFFF"
TRACK = "#D6E3E8"                         # unplayed part of the seek track

COVER_IMAGE = (50, 132, 490, 380)         # image panel inside the disc
COVER_TEXT_X = 636                        # title block on the teal field

DEFAULT_COVER = {
    "background": _C["primary"],
    # white disc bleeding off the left edge; its right edge peaks at x≈583
    "disc": {"frame": frame(-435, -151, 1018, 1018),
             "shape": {"geometry": "oval", "fill": WHITE, "border": None, "radius": "50%"}},
    "logoPlate": {"frame": frame(1092, 581, 159, 78),
                  "shape": {"geometry": "roundRect", "fill": WHITE, "border": None, "radius": 12}},
    "logo": {"frame": frame(1100, 588, 143, 64), "src": BRAND_LOGO},
}

_BTN = {"fontSize": 13, "bold": True, "color": WHITE, "align": "center"}
DEFAULT_FURNITURE = {
    "headerBand": {"frame": frame(0, 0, W, 60), "shape": {"fill": _C["primary"]}},
    "breadcrumb": {"frame": frame(54, 6, 900, 48), "style": {"fontSize": 18.7, "bold": True, "color": WHITE}},
    "topLinks": {"frame": frame(1010, 6, 120, 48), "style": {"fontSize": 15, "bold": True, "color": WHITE},
                 "value": "Menu | Exit"},
    "logoPlate": {"frame": frame(1146, 6, 116, 48), "shape": {"fill": WHITE, "radius": 8}},
    "logo": {"frame": frame(1154, 10, 100, 40), "src": BRAND_LOGO},
    # player bar: play | seek track | n / total | replay, time, mute, volume, CC, full screen | PREV NEXT
    "playerBar": {"frame": frame(0, 670, W, 50), "shape": {"fill": _C["primaryTint"]}},
    "playButton": {"frame": frame(15, 681, 27, 27), "shape": {"fill": _C["primaryDark"], "radius": 4}},
    "progressTrack": {"frame": frame(57, 693, 212, 4), "shape": {"fill": TRACK, "radius": 2}},
    "progressFill": {"shape": {"fill": _C["primaryDark"]}},
    "prevButton": {"frame": frame(1028, 681, 100, 29), "shape": {"fill": _C["primaryDark"], "radius": 3},
                   "text": {"style": _BTN}, "value": "‹ PREV"},
    "nextButton": {"frame": frame(1138, 681, 100, 29), "shape": {"fill": _C["primaryDark"], "radius": 3},
                   "text": {"style": _BTN}, "value": "NEXT ›"},
}
