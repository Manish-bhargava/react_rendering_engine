"""Merge each storyboard slide with its interactions slide into one normalized record.

The storyboard is the source of truth for teaching content; interactions.json is the
source of truth for build behaviour (reveal cues, layers, quiz feedback, audio, media
status, navigation). Where both carry the same field and disagree, the storyboard value
is used and the disagreement is recorded in `issues` - never silently resolved.
"""


def _images(sb_slide, ix_slide):
    """Combine storyboard image specs with the media status from interactions."""
    media = [m for m in (ix_slide or {}).get("media", []) if m.get("kind") != "icon"]
    out = []
    for i, img in enumerate(sb_slide.get("images", [])):
        m = media[i] if i < len(media) else {}
        chosen = img.get("chosen") or m.get("chosen_url")
        out.append({
            "purpose": img.get("purpose"),
            "search_terms": img.get("search_terms"),
            "candidates": [{"url": c.get("url"), "note": c.get("shows")} for c in img.get("candidates", [])],
            "chosen_url": chosen,
            "placement": img.get("placement"),
            "size_in": img.get("size_in"),
            "status": "resolved" if chosen else "unresolved",
            "source_status": m.get("status"),
        })
    return out


def _icon_status(ix_slide):
    st = {m.get("status") for m in (ix_slide or {}).get("media", []) if m.get("kind") == "icon"}
    return st.pop() if len(st) == 1 else (sorted(st) if st else None)


def normalize_slide(module_no, sb, ix, issues):
    sid = sb["id"]

    def check(field, a, b):
        if ix is not None and a != b:
            issues.append({"slide": sid, "field": field, "storyboard": a, "interactions": b,
                           "resolution": "storyboard value used"})

    base = (ix or {}).get("base_layer", {})
    if ix is not None:
        check("heading/title", sb.get("heading"), ix.get("title"))
        check("layout", sb.get("layout"), ix.get("layout"))
        check("breadcrumb", sb.get("breadcrumb"), ix.get("breadcrumb"))
        check("source_slides", sb.get("source_slides"), ix.get("source_slides"))
        check("narration", sb.get("vo", []), base.get("narration", []))

    rec = {
        "id": sid,
        "module": module_no,
        "layout": sb["layout"],
        "title": sb["heading"],
        "breadcrumb": sb.get("breadcrumb"),
        "source_slides": sb.get("source_slides", []),
        "design_rationale": sb.get("design_rationale"),
        "dev_notes": sb.get("dev_notes") or (ix or {}).get("dev_notes"),
        "objective_refs": sb.get("objective_refs", []),
        "instruction": sb.get("instruction"),
        "chunks": [{"label": c.get("label"), "body": c.get("body"), "icon": c.get("icon")}
                   for c in sb.get("chunks", [])],
        "callouts": sb.get("callouts", []),
        "table": sb.get("table"),
        "images": _images(sb, ix),
        "icon_status": _icon_status(ix),
        "narration": sb.get("vo", []),
        "audio_file": base.get("audio_file"),
        "reveal": base.get("reveal", []),
        "reveal_mode": base.get("reveal_mode"),
        "reveal_note": base.get("reveal_note"),
        "storyboard_interaction": sb.get("interaction"),
        "interaction": (ix or {}).get("interaction"),
        "navigation": (ix or {}).get("navigation"),
        "in_interactions": ix is not None,
        "question": None,
    }

    # Knowledge checks: interactions.json carries the full build (attempts + feedback layers)
    if sb.get("qtype") or (ix or {}).get("assessment"):
        a = (ix or {}).get("assessment") or {}
        if a:
            check("question.stem", sb.get("question"), a.get("stem"))
            check("question.options", sb.get("options", []), a.get("options", []))
            check("question.type", sb.get("qtype"), a.get("question_type"))
            correct_fb = next((f for f in a.get("feedback_layers", []) if f.get("layer") == "correct"), {})
            check("question.rationale", sb.get("rationale"), correct_fb.get("body"))
        rec["question"] = {
            "type": sb.get("qtype") or a.get("question_type"),
            "stem": sb.get("question"),
            "instruction": sb.get("instruction") or a.get("instruction"),
            "options": sb.get("options", []),
            "drag_items": a.get("drag_items", []),
            "rationale": sb.get("rationale"),
            "attempts": a.get("attempts"),
            "feedback_layers": a.get("feedback_layers", []),
            "on_submit_with_no_selection": a.get("on_submit_with_no_selection"),
            "on_submit_audio": a.get("on_submit_audio"),
            "scored": a.get("scored"),
        }
    return rec


def normalize(storyboard, interactions):
    issues = []
    modules = []
    for m in storyboard["modules"]:
        pkg = interactions["packages"].get(m["number"])
        if pkg is None:
            issues.append({"module": m["number"], "field": "package",
                           "problem": "no interactions package for this module"})
        slides = {}
        for sid in m["slide_order"]:
            ix = pkg["slides"].get(sid) if pkg else None
            slides[sid] = normalize_slide(m["number"], m["slides"][sid], ix, issues)
        # Interaction slides with no storyboard counterpart would be lost - report them.
        for sid in (pkg["slide_order"] if pkg else []):
            if sid not in slides:
                issues.append({"slide": sid, "field": "slide",
                               "problem": "present in interactions.json but not in storyboard.json"})
        modules.append({"source": m, "package": pkg, "slides": slides})
    return {"modules": modules, "issues": issues}
