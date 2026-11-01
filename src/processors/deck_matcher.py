"""Match authored-deck shapes to generated components (optional stage).

Input: the components document, the slide mapping, and one parsed deck per module.
Output: `measured[componentId]` = frames, shape styles and typography taken from the deck,
`furniture` = header/footer chrome, extracted assets, and a list of deck text that was
not matched (added to components.json as `deckText` paragraphs so nothing on the deck is lost).

Matching is by text, never by position, so a deck whose shapes are re-ordered still matches.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

from src.parsers.pptx_parser import plain

HEADER_BOTTOM = 70        # px: shapes ending above this are header chrome
FOOT_TOP = 668            # px: shapes starting below this are player bar / dev notes
PANEL_FILL = "#F2F7EB"


# ---------------------------------------------------------------- helpers
def norm(s):
    s = (s or "").replace(" ", " ")
    s = re.sub(r"^\s*(•|[A-Z]\.|\d+\.)\s+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip().lower()


def rframe(f):
    return {k: int(round(v)) for k, v in f.items()}


def contains(outer, inner, slack=4):
    o, i = outer["frame"], inner["frame"]
    cx, cy = i["x"] + i["w"] / 2, i["y"] + i["h"] / 2
    return o["x"] - slack <= cx <= o["x"] + o["w"] + slack and o["y"] - slack <= cy <= o["y"] + o["h"] + slack


def union(frames):
    xs = [f["x"] for f in frames]; ys = [f["y"] for f in frames]
    x2 = [f["x"] + f["w"] for f in frames]; y2 = [f["y"] + f["h"] for f in frames]
    return {"x": min(xs), "y": min(ys), "w": max(x2) - min(xs), "h": max(y2) - min(ys)}


def text_style(p_font, align="left"):
    f = p_font or {}
    return {"fontSize": f.get("sizePx"), "bold": f.get("bold"), "color": f.get("color"),
            "fontFamily": f.get("family"), "align": align}


def text_spec(rec):
    t = rec["text"]
    paras = t["paragraphs"]
    first = next((p for p in paras if p["font"]), {"font": None, "align": "left"})
    spec = {"frame": rframe(rec["frame"]), "anchor": t["anchor"], "padding": t["padding"],
            "style": text_style(first["font"], first["align"])}
    styles = [text_style(p["font"], p["align"]) for p in paras]
    if any(s != spec["style"] for s in styles):
        spec["paragraphStyles"] = styles
    return spec


def box_spec(rec):
    f = rec["frame"]
    spec = {"frame": rframe(f), "shape": {
        "geometry": rec.get("geometry"),
        "fill": rec.get("fill"),
        "border": rec.get("line"),
    }}
    g = rec.get("geometry") or ""
    if g.startswith("rounded"):
        spec["shape"]["radius"] = round((rec.get("cornerRatio") or 0.16667) * min(f["w"], f["h"]), 1)
    elif g == "oval":
        spec["shape"]["radius"] = "50%"
    if rec.get("text"):
        spec["text"] = text_spec(rec)
        spec["text"].pop("frame")
    return spec


class Slide:
    """Shapes of one deck slide, with 'used' tracking so each shape matches once."""

    def __init__(self, deck_slide):
        self.all = deck_slide["shapes"]
        self.body = [s for s in self.all
                     if not (s["frame"]["y"] + s["frame"]["h"] <= HEADER_BOTTOM) and s["frame"]["y"] < FOOT_TOP]
        self.used = set()

    def texts(self):
        return [s for s in self.body if s.get("text") and id(s) not in self.used]

    def take(self, rec):
        if rec is not None:
            self.used.add(id(rec))
        return rec

    def find_text(self, text, mode="eq", kinds=("text", "shape")):
        n = norm(text)
        if not n:
            return None
        for s in self.texts():
            if s["kind"] not in kinds:
                continue
            t = norm(plain(s))
            whole = norm(" ".join(norm(p["text"]) for p in s["text"]["paragraphs"]))
            if (mode == "eq" and (t == n or whole == n)) or (mode == "in" and n in whole) or \
                    (mode == "start" and whole.startswith(n)):
                return self.take(s)
        return None

    def enclosing(self, inner, pred):
        best = None
        for s in self.body:
            if s is inner or s["kind"] != "shape" or id(s) in self.used or not pred(s):
                continue
            if contains(s, inner) and (best is None or s["frame"]["w"] * s["frame"]["h"] < best["frame"]["w"] * best["frame"]["h"]):
                best = s
        return self.take(best)

    def inside(self, outer, pred=lambda s: True):
        return [self.take(s) for s in self.body
                if s is not outer and id(s) not in self.used and contains(outer, s) and pred(s)]


# ---------------------------------------------------------------- assets
class Assets:
    def __init__(self, out_dir, renders):
        self.dir = out_dir
        self.renders = renders            # module -> list of PIL images (or None)
        self.saved = {}

    def save_blob(self, blob, ext, sub, stem):
        key = hashlib.sha1(blob).hexdigest()[:10]
        if key in self.saved:
            return self.saved[key]
        rel = f"assets/{sub}/{stem}.{ext}"
        os.makedirs(os.path.join(self.dir, "assets", sub), exist_ok=True)
        with open(os.path.join(self.dir, rel), "wb") as f:
            f.write(blob)
        self.saved[key] = rel
        return rel

    def crop(self, module, slide_index, frame, stem):
        imgs = self.renders.get(module)
        if not imgs or slide_index - 1 >= len(imgs):
            return None
        im = imgs[slide_index - 1]
        k = im.width / 1280
        pad = 12
        box = (int((frame["x"] - pad) * k), int((frame["y"] - pad) * k),
               int((frame["x"] + frame["w"] + pad) * k), int((frame["y"] + frame["h"] + pad) * k))
        rel = f"assets/icons/{stem}.png"
        os.makedirs(os.path.join(self.dir, "assets", "icons"), exist_ok=True)
        im.crop(box).save(os.path.join(self.dir, rel))
        return rel


def render_deck(path, dpi=192):
    """Render a deck to images with LibreOffice (used only to capture drawn icons)."""
    if not shutil.which("soffice"):
        return None
    try:
        from PIL import Image
        tmp = tempfile.mkdtemp()
        shutil.copy(path, os.path.join(tmp, "deck.pptx"))
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, os.path.join(tmp, "deck.pptx")],
                       check=True, capture_output=True, timeout=300)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", os.path.join(tmp, "deck.pdf"), os.path.join(tmp, "p")],
                       check=True, capture_output=True, timeout=300)
        files = sorted(f for f in os.listdir(tmp) if f.startswith("p") and f.endswith(".png"))
        return [Image.open(os.path.join(tmp, f)).convert("RGBA") for f in files]
    except Exception:
        return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


# ---------------------------------------------------------------- per-type matchers
def m_text(S, c, text, mode="eq"):
    r = S.find_text(text, mode)
    return {"frame": rframe(r["frame"]), "text": text_spec(r)} if r else None


def m_image(S, c):
    label = S.find_text(c["props"]["alt"], "in")
    if not label:
        return None
    panel = S.enclosing(label, lambda s: s.get("fill") == PANEL_FILL)
    if not panel:
        return None
    spec = box_spec(panel)
    spec["parts"] = {"label": text_spec(label)}
    cap = next((s for s in S.texts() if plain(s).startswith("https://")
                and abs(s["frame"]["y"] - (panel["frame"]["y"] + panel["frame"]["h"])) < 20
                and abs(s["frame"]["x"] - panel["frame"]["x"]) < 20), None)
    if cap:
        S.take(cap)
        spec["parts"]["caption"] = text_spec(cap)
    return spec


def m_callout(S, c):
    body = S.find_text(c["props"]["text"])
    if not body:
        return None
    box = S.enclosing(body, lambda s: s.get("line") and not s.get("fill"))
    if not box:
        return {"frame": rframe(body["frame"]), "parts": {"body": text_spec(body)}}
    spec = box_spec(box)
    tag = next((s for s in S.inside(box, lambda s: s.get("text") and s is not body)), None)
    spec["parts"] = {"body": text_spec(body)}
    if tag:
        spec["parts"]["tag"] = text_spec(tag)
        spec["parts"]["tag"]["value"] = plain(tag)
    return spec


def m_list(S, items, intro_key=None):
    """A single text box holding all items as paragraphs."""
    if not items:
        return None, None
    rec = S.find_text(items[0], "in")
    if not rec:
        return None, None
    paras = rec["text"]["paragraphs"]
    intro = None
    if norm(paras[0]["text"]) != norm(items[0]):
        intro = paras[0]["text"]
    marker = None
    first_item = paras[1 if intro else 0]["text"].strip()
    if first_item.startswith("•"):
        marker = "bullet"
    elif re.match(r"^\d+\.", first_item):
        marker = "number"
    spec = {"frame": rframe(rec["frame"]), "text": text_spec(rec), "marker": marker}
    return spec, intro


def m_cards(S, c, title_key, body_key, list_key):
    items, frames = [], []
    for card in c["props"][list_key]:
        chip = S.find_text(card[title_key], kinds=("shape",)) or S.find_text(card[title_key])
        body = S.find_text(card[body_key]) if card.get(body_key) else None
        it = {}
        if chip:
            it["header"] = box_spec(chip) if chip["kind"] == "shape" else {"frame": rframe(chip["frame"]), "text": text_spec(chip)}
            frames.append(chip["frame"])
        if body:
            panel = S.enclosing(body, lambda s: s.get("line") and not s.get("fill"))
            if panel:
                it["panel"] = box_spec(panel)
                frames.append(panel["frame"])
            it["body"] = text_spec(body)
            frames.append(body["frame"])
        items.append(it or None)
    if not frames:
        return None
    return {"frame": rframe(union(frames)), "items": items}


def m_icons(S, c, assets, module, slide_index):
    items, frames = [], []
    for k, it in enumerate(c["props"]["items"]):
        label = S.find_text(it["label"])
        if not label:
            items.append(None)
            continue
        lf = label["frame"]
        cand = [s for s in S.body if id(s) not in S.used and not s.get("text")
                and s["kind"] in ("picture", "shape")
                and lf["x"] <= s["frame"]["x"] + s["frame"]["w"] / 2 <= lf["x"] + lf["w"]
                and lf["y"] - 170 <= s["frame"]["y"] and s["frame"]["y"] + s["frame"]["h"] <= lf["y"] + 4]
        spec = {"label": text_spec(label)}
        frames.append(lf)
        if cand:
            for s in cand:
                S.take(s)
            f = union([s["frame"] for s in cand])
            frames.append(f)
            pics = [s for s in cand if s["kind"] == "picture"]
            stem = slug(it["icon"]["name"])
            if len(cand) == 1 and pics:
                src = assets.save_blob(pics[0]["image"]["blob"], pics[0]["image"]["ext"], "icons", stem)
                how = "embedded picture in deck"
            else:
                src = assets.crop(module, slide_index, f, stem)
                how = "drawn shapes in deck, cropped from a render" if src else "drawn shapes in deck (not extracted: no renderer)"
            spec["icon"] = {"frame": rframe(f), "src": src, "source": how}
        items.append(spec)
    if not frames:
        return None
    return {"frame": rframe(union(frames)), "items": items}


def m_process(S, c, embedded_deck_slide=None):
    items, frames = [], []
    for k, st in enumerate(c["props"]["steps"]):
        label = S.find_text(st["label"])
        it = {}
        if label:
            it["label"] = text_spec(label)
            frames.append(label["frame"])
            lf = label["frame"]
            badge = next((s for s in S.body if id(s) not in S.used and s.get("geometry") == "oval"
                          and norm(plain(s)) == str(k + 1) and s["frame"]["y"] < lf["y"]
                          and abs((s["frame"]["x"] + s["frame"]["w"] / 2) - (lf["x"] + lf["w"] / 2)) < lf["w"]), None)
            if badge:
                S.take(badge)
                it["badge"] = box_spec(badge)
                frames.append(badge["frame"])
        items.append(it or None)
    if not frames:
        return None
    spec = {"frame": rframe(union(frames)), "items": items, "parts": {}}
    rail = next((s for s in S.body if id(s) not in S.used and s.get("geometry") == "rectangle"
                 and s["frame"]["h"] <= 6 and s["frame"]["w"] > 200 and s.get("fill")), None)
    if rail:
        S.take(rail)
        spec["parts"]["rail"] = box_spec(rail)
    # interaction layers: style from the embedded deck slide, panel placed under the track
    ix = c["props"].get("interaction")
    if ix and ix.get("layers"):
        layer_style = None
        if embedded_deck_slide is not None:
            E = Slide(embedded_deck_slide)
            L0 = ix["layers"][0]
            chip = E.find_text(L0["label"], kinds=("shape",))
            body = E.find_text(L0["lines"][0]) if L0["lines"] else None
            if chip and body:
                layer_style = {"header": box_spec(chip), "body": text_spec(body),
                               "source": "measured from authored deck slide " + ix["layers"][0].get("fromSlide", "")}
        label_bottom = max(it["badge"]["frame"]["y"] for it in items if it and "badge" in it) + 110 \
            if any(it and "badge" in it for it in items) else spec["frame"]["y"] + 120
        x0 = spec["frame"]["x"]
        x1 = spec["frame"]["x"] + spec["frame"]["w"]
        panel = {"x": x0, "y": int(label_bottom), "w": int(x1 - x0), "h": int(655 - label_bottom)}
        spec["parts"]["layerPanel"] = {"frame": panel, "source": "inferred: below the stage track, above the player bar"}
        if layer_style:
            spec["parts"]["layerStyle"] = layer_style
        spec["frame"] = rframe(union([spec["frame"], panel]))
    return spec


def m_table(S, c):
    rec = next((s for s in S.body if s["kind"] == "table" and id(s) not in S.used), None)
    if not rec:
        return None
    S.take(rec)
    t = rec["table"]
    cells = t["cells"]
    return {"frame": rframe(rec["frame"]), "table": {
        "colWidths": t["colWidths"], "rowHeights": t["rowHeights"],
        "header": {"fill": cells[0][0]["fill"], "style": text_style(cells[0][0]["font"])},
        "rows": [{"fill": r[0]["fill"], "firstColStyle": text_style(r[0]["font"]),
                  "style": text_style(r[1]["font"] if len(r) > 1 else r[0]["font"])} for r in cells[1:]],
        "cellPadding": cells[0][0]["padding"],
    }}


def m_quiz_common(S, c, spec):
    p = c["props"]
    badge = S.find_text(p["questionType"], kinds=("shape",))
    if badge:
        spec["parts"]["typeBadge"] = box_spec(badge)
    for kind, starts in (("verdictCorrect", "that's correct"), ("verdictIncorrect", "that's incorrect")):
        t = next((s for s in S.texts() if norm(plain(s)).startswith(starts)), None)
        if t:
            S.take(t)
            box = S.enclosing(t, lambda s: s.get("line"))
            spec["parts"][kind] = box_spec(box) if box else {"frame": rframe(t["frame"])}
            spec["parts"][kind]["text"] = text_spec(t)
            spec["parts"][kind]["deckText"] = plain(t)
    fb = next((f for f in p["feedback"] if f["kind"] == "correct"), None)
    if fb:
        r = S.find_text(fb["body"])
        if r:
            panel = S.enclosing(r, lambda s: s.get("fill") == PANEL_FILL)
            spec["parts"]["rationale"] = box_spec(panel) if panel else {"frame": rframe(r["frame"])}
            spec["parts"]["rationale"]["text"] = text_spec(r)
    frames = [v["frame"] for v in spec["parts"].values() if isinstance(v, dict) and "frame" in v]
    spec["frame"] = rframe(union(frames)) if frames else None
    return spec


def m_mc(S, c):
    p = c["props"]
    spec = {"parts": {}}
    stem = S.find_text(p["stem"])
    if stem:
        spec["parts"]["stem"] = text_spec(stem)
    opts = S.find_text(p["options"][0]["text"], "in")
    if opts:
        spec["parts"]["options"] = text_spec(opts)
    return m_quiz_common(S, c, spec)


def m_sequence(S, c):
    spec = {"parts": {}, "items": []}
    slots = []
    for it in c["props"]["items"]:
        chip = S.find_text(it["label"], kinds=("shape",))
        slots.append(box_spec(chip) if chip else None)
    spec["slots"] = slots
    spec = m_quiz_common(S, c, spec)
    frames = [s["frame"] for s in slots if s] + ([spec["frame"]] if spec["frame"] else [])
    spec["frame"] = rframe(union(frames)) if frames else None
    spec.pop("items")
    return spec


# ---------------------------------------------------------------- chrome
def chrome_from(deck_slide, assets):
    sh = deck_slide["shapes"]
    out = {}
    band = next((s for s in sh if s["kind"] == "shape" and s["frame"]["y"] <= 1 and s["frame"]["w"] >= 1270 and s["frame"]["h"] < 80), None)
    if band:
        out["headerBand"] = box_spec(band)
    crumb = next((s for s in sh if s.get("text") and s["frame"]["y"] < 20 and s["frame"]["x"] < 40), None)
    if crumb:
        out["breadcrumb"] = text_spec(crumb)
    links = next((s for s in sh if s.get("text") and "exit" in plain(s).lower() and s["frame"]["y"] < 20), None)
    if links:
        out["topLinks"] = text_spec(links)
        out["topLinks"]["value"] = plain(links)
    logo = next((s for s in sh if s["kind"] == "picture" and s["frame"]["y"] < 20), None)
    if logo:
        out["logo"] = {"frame": rframe(logo["frame"]), "src": assets.save_blob(logo["image"]["blob"], logo["image"]["ext"], "brand", "logo")}
        plate = next((s for s in sh if s["kind"] == "shape" and s.get("fill") == "#FFFFFF" and contains(s, logo)), None)
        if plate:
            out["logoPlate"] = box_spec(plate)
    bar = next((s for s in sh if s["kind"] == "shape" and s["frame"]["y"] >= FOOT_TOP - 5 and s["frame"]["w"] >= 1270), None)
    if bar:
        out["playerBar"] = box_spec(bar)
        foot = [s for s in sh if s["frame"]["y"] >= bar["frame"]["y"] and s is not bar]
        play = next((s for s in foot if (s.get("geometry") or "").startswith("rounded") and s["frame"]["w"] < 40), None)
        if play:
            out["playButton"] = box_spec(play)
        rails = sorted([s for s in foot if s.get("geometry") == "rectangle" and s["frame"]["h"] <= 6], key=lambda s: -s["frame"]["w"])
        if rails:
            out["progressTrack"] = box_spec(rails[0])
            if len(rails) > 1:
                out["progressFill"] = box_spec(rails[1])
        pills = [s for s in foot if (s.get("geometry") or "").startswith("rounded") and s["frame"]["w"] > 60]
        labels = [s for s in foot if s.get("text") and ("PREV" in plain(s) or "NEXT" in plain(s))]
        for name, key in (("prevButton", "PREV"), ("nextButton", "NEXT")):
            lab = next((s for s in labels if key in plain(s)), None)
            pill = next((s for s in pills if lab and contains(s, lab)), None)
            if pill:
                out[name] = box_spec(pill)
                out[name]["text"] = text_spec(lab)
                out[name]["text"].pop("frame")
                out[name]["value"] = plain(lab)
    return out


def cover_from(deck_slide, assets):
    sh = deck_slide["shapes"]
    out = {}
    bg = next((s for s in sh if s["kind"] == "shape" and s["frame"]["w"] >= 1270 and s["frame"]["h"] >= 700), None)
    if bg:
        out["background"] = bg.get("fill")
    disc = next((s for s in sh if s.get("geometry") == "oval" and s["frame"]["h"] > 700), None)
    if disc:
        out["disc"] = box_spec(disc)
    logo = next((s for s in sh if s["kind"] == "picture"), None)
    if logo:
        out["logo"] = {"frame": rframe(logo["frame"]), "src": assets.save_blob(logo["image"]["blob"], logo["image"]["ext"], "brand", "logo")}
        plate = next((s for s in sh if s["kind"] == "shape" and s.get("fill") == "#FFFFFF" and contains(s, logo) and s is not disc), None)
        if plate:
            out["logoPlate"] = box_spec(plate)
    return out


# ---------------------------------------------------------------- driver
def match_decks(components, decks, out_dir):
    """decks: {module_number: parsed_deck}. Returns measurement bundle; may add deckText components."""
    renders = {m: render_deck(d["path"]) for m, d in decks.items()}
    assets = Assets(out_dir, renders)
    measured, slide_meta, issues = {}, {}, []
    furniture, cover = None, None

    for mod in components["modules"]:
        deck = decks.get(mod["number"])
        if not deck:
            continue
        src_order = [s["sourceSlideId"] for s in mod["slides"]]
        embedded = mod["embeddedSourceSlides"]
        # deck slides follow the storyboard order, which includes embedded states
        sb_order = sorted(src_order + embedded, key=lambda x: [int(p) for p in x.split(".")])
        if len(sb_order) != len(deck["slides"]):
            issues.append({"module": mod["number"], "problem":
                           f"deck has {len(deck['slides'])} slides, storyboard order has {len(sb_order)}; matched by heading"})
        by_id = {sid: deck["slides"][i] for i, sid in enumerate(sb_order) if i < len(deck["slides"])}

        for s in mod["slides"]:
            ds = by_id.get(s["sourceSlideId"])
            if ds is None:
                continue
            S = Slide(ds)
            if not S.find_text(s["title"]) and s["layout"] != "title":
                issues.append({"slide": s["sourceSlideId"], "problem": "deck slide heading does not match; slide not measured"})
                continue
            S.used.clear()
            if s["layout"] == "title":
                cover = cover or cover_from(ds, assets)
            elif furniture is None:
                furniture = chrome_from(ds, assets)
            emb_ds = by_id.get(s["embeddedSourceSlides"][0]) if s["embeddedSourceSlides"] else None
            module_ctx = mod

            for c in s["components"]:
                t, p = c["type"], c["props"]
                spec = None
                if t in ("heading", "paragraph", "instruction"):
                    spec = m_text(S, c, p["text"])
                elif t == "image":
                    spec = m_image(S, c)
                elif t == "callout":
                    spec = m_callout(S, c)
                elif t == "cardGrid":
                    spec = m_cards(S, c, "title", "body", "cards")
                elif t == "comparison":
                    spec = m_cards(S, c, "title", "body", "columns")
                elif t == "iconGrid":
                    spec = m_icons(S, c, assets, mod["number"], ds["index"])
                elif t == "definition":
                    spec, _ = m_list(S, [p["terms"][0]["term"]])
                elif t in ("bulletList", "references"):
                    spec, _ = m_list(S, p["items"])
                elif t == "summary":
                    spec, _ = m_list(S, p["points"])
                elif t == "results":
                    spec, _ = m_list(S, p["lines"])
                elif t == "objectivesList":
                    spec, intro = m_list(S, [o["text"] for o in p["items"]])
                    if intro:
                        p["intro"] = intro
                        p["introSource"] = "authored deck"
                elif t == "process":
                    spec = m_process(S, c, emb_ds)
                elif t == "table":
                    spec = m_table(S, c)
                elif t == "multipleChoice":
                    spec = m_mc(S, c)
                elif t == "sequence":
                    spec = m_sequence(S, c)
                if spec and spec.get("frame"):
                    spec["source"] = f"authored deck {os.path.basename(deck['path'])} slide {ds['index']}"
                    measured[c["id"]] = spec
                else:
                    issues.append({"slide": s["sourceSlideId"], "component": c["id"], "problem": "no matching deck shape; layout inferred"})

            # deck text that no component claimed -> keep it as a component
            n = 0
            for r in S.texts():
                txt = plain(r)
                if txt.startswith("https://") or txt.startswith("DEV:") or txt.strip() in ("!", "Note", "Tip"):
                    continue
                n += 1
                cid = f"{s['slideId']}_decktext_{n}"
                role = "scope" if norm(txt) == norm(module_ctx.get("scopingSentence")) else "deckText"
                comp = {"id": cid, "type": "paragraph",
                        "props": {"text": txt, "role": role,
                                  "source": "module.scopingSentence" if role == "scope" else "authored deck"}}
                s["components"].append(comp)
                measured[cid] = {"frame": rframe(r["frame"]), "text": text_spec(r),
                                 "source": f"authored deck {os.path.basename(deck['path'])} slide {ds['index']}"}
                if role == "deckText":
                    issues.append({"slide": s["sourceSlideId"], "component": cid,
                                   "problem": f"on-screen text found only in the authored deck: {txt[:60]!r}"})
            slide_meta[s["slideId"]] = {"deckSlide": ds["index"], "deck": os.path.basename(deck["path"])}

    return {"measured": measured, "slides": slide_meta, "furniture": furniture, "cover": cover,
            "issues": issues, "assets": sorted(set(assets.saved.values()) | {
                m["icon"]["src"] for v in measured.values() for m in (v.get("items") or []) if m and m.get("icon", {}).get("src")})}
