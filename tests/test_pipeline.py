"""Run with:  python -m pytest -q   (from the project root)"""
import json
import os

from src.lesson_builder import build_lesson
from src.processors.box_normalizer import _chip_text_width

ROOT = os.path.dirname(os.path.dirname(__file__))
SB = os.path.join(ROOT, "input", "storyboard.json")
IX = os.path.join(ROOT, "input", "interactions.json")
R = build_lesson(SB, IX)
C, L, V = R["components"], R["layout"], R["voiceover"]
blob_c = json.dumps(C, ensure_ascii=False)
blob_v = json.dumps(V, ensure_ascii=False)


def test_validation_passes():
    assert R["errors"] == []


def test_player_slide_count_and_embedded_state():
    slides = [s["sourceSlideId"] for m in C["modules"] for s in m["slides"]]
    assert len(slides) == 42
    assert "2.04" not in slides                       # embedded in 2.03
    s203 = next(s for m in C["modules"] for s in m["slides"] if s["sourceSlideId"] == "2.03")
    assert s203["navigation"]["next"] == "slide_2_05"


def test_every_narration_line_is_kept():
    sb = json.load(open(SB, encoding="utf-8"))
    for m in sb["modules"]:
        for s in m["slides"]:
            for line in s["vo"]:
                assert json.dumps(line, ensure_ascii=False) in blob_v, (s["id"], line[:40])


def test_every_content_string_is_kept():
    sb = json.load(open(SB, encoding="utf-8"))
    for m in sb["modules"]:
        for s in m["slides"]:
            texts = [s["heading"]] + [c["label"] for c in s.get("chunks", [])] \
                + [c["body"] for c in s.get("chunks", []) if c.get("body") and s["layout"] != "sequence"] \
                + [c["text"] for c in s.get("callouts", [])] + [o["text"] for o in s.get("options", [])]
            if s.get("table"):
                texts += s["table"]["headers"] + [cell for r in s["table"]["rows"] for cell in r]
            for t in texts:
                assert json.dumps(t, ensure_ascii=False) in blob_c, (s["id"], t[:40])


def test_every_audio_file_is_mapped():
    ix = json.load(open(IX, encoding="utf-8"))
    for a in ix["audio_manifest"]:
        assert f'"{a["file"]}"' in blob_v, a["file"]


def test_no_invented_image_urls():
    for m in C["modules"]:
        for s in m["slides"]:
            for c in s["components"]:
                if c["type"] == "image":
                    assert c["props"]["src"] is None and c["props"]["status"] == "unresolved"


# ---------- with the authored decks ----------
DECKS = [os.path.join(ROOT, "input", "decks", f) for f in ("section_1.pptx", "section_2.pptx")]


def test_every_component_measured_from_deck(tmp_path):
    if not all(os.path.exists(d) for d in DECKS):
        return
    r = build_lesson(SB, IX, DECKS, str(tmp_path))
    assert r["errors"] == []
    assert r["components"]["review"]["deckMatching"] == []          # nothing unmatched
    items = [it for s in r["layout"]["slides"] for it in s["items"]]
    assert all(it["source"].startswith("authored deck") for it in items)
    assert os.path.exists(tmp_path / "assets" / "brand" / "logo.png")


def _deck_layout(tmp_path):
    r = build_lesson(SB, IX, DECKS, str(tmp_path))
    _deck_layout.components = r["components"]
    return r["layout"]


def _titles(layout, slide_id, component_id):
    for m in _deck_layout.components["modules"]:
        for s in m["slides"]:
            if s["slideId"] != slide_id:
                continue
            for c in s["components"]:
                if c["id"] == component_id:
                    return [k["title"] for k in (c["props"].get("cards") or c["props"].get("columns") or [])]
    return []


def test_boxed_text_is_not_left_on_the_powerpoint_inset(tmp_path):
    """Chips, slots, verdict strips and rationale panels get a readable inset."""
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    checked = 0
    for s in layout["slides"]:
        for it in s["items"]:
            for role, spec in list((it.get("parts") or {}).items()) \
                    + [("header", e.get("header")) for e in (it.get("items") or []) if isinstance(e, dict)] \
                    + [("slot", e) for e in (it.get("slots") or [])]:
                if not isinstance(spec, dict) or role not in (
                        "header", "slot", "typeBadge", "rationale", "verdictCorrect", "verdictIncorrect"):
                    continue
                shape = spec.get("shape") or {}
                pad = (spec.get("text") or {}).get("padding")
                if not (shape.get("fill") or shape.get("border")) or not pad:
                    continue
                checked += 1
                assert pad[0] >= 8 and pad[1] >= 14, (s["slideId"], role, pad)
    assert checked >= 40


def test_icons_in_one_grid_share_a_size_and_a_baseline(tmp_path):
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    grids = 0
    for s in layout["slides"]:
        for it in s["items"]:
            icons = [e["icon"]["frame"] for e in (it.get("items") or [])
                     if isinstance(e, dict) and isinstance((e.get("icon") or {}).get("frame"), dict)]
            if len(icons) < 2:
                continue
            grids += 1
            assert len({(f["w"], f["h"]) for f in icons}) == 1, (s["slideId"], icons)
            # one baseline per row, not one per icon
            rows = {round(((e.get("label") or {}).get("frame") or {}).get("y", 0) / 12)
                    for e in it["items"] if isinstance(e, dict)}
            assert len({f["y"] + f["h"] for f in icons}) <= len(rows), (s["slideId"], icons)
    assert grids >= 7


def test_tables_carry_a_cell_inset(tmp_path):
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    tables = [it["table"] for s in layout["slides"] for it in s["items"] if "table" in it]
    assert tables and all(t["cellPadding"][1] >= 12 for t in tables)


def test_responsive_rule_is_complete():
    r = L["responsive"]
    assert r["stackBelowPx"] >= 820 and 0 < r["minScale"] < r["maxScale"]


def test_one_left_margin_for_headings_and_content(tmp_path):
    """The deck keeps its title placeholder at x=17 and content at x=48."""
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    covers = {s["slideId"] for s in layout["slides"] if s.get("cover")}
    lefts = {it["frame"]["x"] for s in layout["slides"] if s["slideId"] not in covers
             for it in s["items"] if it["frame"]["x"] < 300}
    assert lefts == {48}, lefts


def test_header_and_player_bar_are_closed_up(tmp_path):
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    f, h = layout["furniture"], layout["canvas"]["height"]
    band, plate, bar = f["headerBand"]["frame"], f["logoPlate"]["frame"], f["playerBar"]["frame"]
    assert (plate["y"], plate["y"] + plate["h"]) == (band["y"], band["y"] + band["h"])  # no step
    assert bar["y"] + bar["h"] == h                                                    # no strip below
    for part in ("logo", "breadcrumb", "topLinks"):
        p = f[part]["frame"]
        assert band["y"] <= p["y"] and p["y"] + p["h"] <= band["y"] + band["h"], part


def test_nothing_is_hidden_by_the_header_or_the_player_bar(tmp_path):
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    f = layout["furniture"]
    top = f["headerBand"]["frame"]["y"] + f["headerBand"]["frame"]["h"]
    bar = f["playerBar"]["frame"]["y"]
    for s in layout["slides"]:
        for it in s["items"]:
            fr = it["frame"]
            assert fr["y"] >= top, (s["slideId"], it["componentId"], "under the header")
            assert fr["y"] + fr["h"] <= bar, (s["slideId"], it["componentId"], "under the player bar")
        cover = s.get("cover") or {}
        for part in ("logo", "logoPlate"):
            if part in cover:
                fr = cover[part]["frame"]
                assert fr["y"] + fr["h"] <= bar, (s["slideId"], part, "behind the player bar")


def test_a_chip_is_never_a_stub_over_a_column(tmp_path):
    """Over a column the chip shares the column's width; over a full-width body it
    only has to be wide enough for its own label."""
    if not all(os.path.exists(d) for d in DECKS):
        return
    layout = _deck_layout(tmp_path)
    checked = 0
    for s in layout["slides"]:
        for it in s["items"]:
            entries = [e for e in (it.get("items") or []) if isinstance(e, dict) and e.get("header") and e.get("body")]
            if not entries:
                continue
            chip = max(e["header"]["frame"]["w"] for e in entries)
            body = max(e["body"]["frame"]["w"] for e in entries)
            checked += 1
            assert len({e["header"]["frame"]["w"] for e in entries}) == 1, s["slideId"]
            if body <= 700:
                assert chip >= body, (s["slideId"], chip, body)
            else:
                # wide enough for its own longest label, by the same estimate the
                # normalizer uses (no font metrics are available at build time)
                need = max(_chip_text_width(t, (e["header"].get("text") or {}).get("style"),
                                            (e["header"].get("text") or {}).get("padding"))
                           for t, e in zip(_titles(layout, s["slideId"], it["componentId"]), entries))
                assert chip + 1 >= min(need, body), (s["slideId"], chip, need)
    assert checked >= 7


def test_every_manifest_recording_is_mapped_to_a_slide():
    man = json.load(open(IX, encoding="utf-8"))["audio_manifest"]
    mapped = {}
    for m in V["modules"]:
        for s in m["slides"]:
            if s["base"] and s["base"]["audioFile"]:
                mapped[s["base"]["audioFile"]] = (s["slideId"], s["base"]["approxSeconds"])
            for layer in s["layers"]:
                if layer["audioFile"]:
                    mapped[layer["audioFile"]] = (s["slideId"], layer["approxSeconds"])
    assert len(mapped) == len(man)
    for e in man:
        assert e["file"] in mapped, e["file"]
        assert mapped[e["file"]][1] == e["approx_seconds"], e["file"]
