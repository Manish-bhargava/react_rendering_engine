"""Build components.json: WHAT appears on every player slide.

One builder per storyboard layout. Each builder returns a list of components
({id, type, props}). Text is copied from the source unchanged.
Returns (components_doc, context); `context` tells the other generators which
component receives reveal cues and which component owns each interaction layer.
"""
from src.processors.slide_mapper import slide_key


# ---------- small component constructors ----------

def comp(cid, ctype, **props):
    return {"id": cid, "type": ctype, "props": props}


def image_comp(cid, img):
    return comp(cid, "image",
                src=img["chosen_url"],              # null until a developer picks one
                status=img["status"],               # "unresolved" when src is null
                alt=img["purpose"],
                searchTerms=img["search_terms"],
                candidates=img["candidates"],
                placement=img["placement"],
                sizeIn=img["size_in"],
                sourceStatus=img["source_status"])


def callout_comps(sid, rec):
    return [comp(f"{sid}_callout_{i}", "callout", kind=c.get("kind"), text=c.get("text"),
                 placement=c.get("placement"))
            for i, c in enumerate(rec["callouts"], 1)]


def image_comps(sid, rec):
    return [image_comp(f"{sid}_image_{i}", img) for i, img in enumerate(rec["images"], 1)]


# ---------- per-layout builders: return (components, reveal_target_id) ----------

def build_title(sid, rec, ctx):
    # House-style cover: course title, "Module N: <module title>", byline.
    # The storyboard heading stays on the slide record (`title`).
    c = [comp(f"{sid}_heading", "heading", text=ctx["course_title"], level=1, sourceField="course.title"),
         comp(f"{sid}_subtitle", "paragraph", text=f"Module {ctx['module_number']}: {ctx['module_title']}",
              role="subtitle", sourceField="module.number + module.title"),
         comp(f"{sid}_byline", "paragraph", text=f"Prepared by {ctx['producer']}", role="byline",
              sourceField="course.producer")]
    return c + image_comps(sid, rec), None


def build_objectives(sid, rec, ctx):
    lst = comp(f"{sid}_objectives", "objectivesList",
               intro=None,
               items=[{"id": o["id"], "text": o["text"], "level": o.get("level")} for o in ctx["objectives"]],
               sourceField="module.objectives")
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1), lst] + image_comps(sid, rec), lst["id"]


def build_icon_row(sid, rec, ctx):
    items = [{"label": ch["label"], "icon": {"name": ch["icon"], "assetStatus": rec["icon_status"]}}
             for ch in rec["chunks"]]
    props = {"items": items}
    if rec.get("dev_notes") and "hotspot" in rec["dev_notes"].lower():
        # The menu on 1.03: chips are hotspots, but the source names no target slide per topic.
        props["interaction"] = {"type": "menu", "trigger": "click", "visitedState": True,
                                "targets": [None] * len(items), "targetStatus": "unresolved",
                                "note": rec["dev_notes"]}
    grid = comp(f"{sid}_icons", "iconGrid", **props)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if rec.get("instruction"):
        head.append(comp(f"{sid}_instruction", "instruction", text=rec["instruction"]))
    return head + [grid] + image_comps(sid, rec) + callout_comps(sid, rec), grid["id"]


def build_chip_detail(sid, rec, ctx):
    grid = comp(f"{sid}_cards", "cardGrid",
                cards=[{"title": ch["label"], "body": ch["body"]} for ch in rec["chunks"]])
    return ([comp(f"{sid}_heading", "heading", text=rec["title"], level=1), grid]
            + image_comps(sid, rec) + callout_comps(sid, rec)), grid["id"]


def build_definition(sid, rec, ctx):
    d = comp(f"{sid}_definition", "definition",
             terms=[{"term": ch["label"], "description": ch["body"]} for ch in rec["chunks"]])
    return ([comp(f"{sid}_heading", "heading", text=rec["title"], level=1), d]
            + image_comps(sid, rec) + callout_comps(sid, rec)), d["id"]


def build_image_focus(sid, rec, ctx):
    lst = comp(f"{sid}_points", "bulletList", items=[ch["label"] for ch in rec["chunks"]], style="checklist")
    return ([comp(f"{sid}_heading", "heading", text=rec["title"], level=1), lst]
            + image_comps(sid, rec) + callout_comps(sid, rec)), lst["id"]


def build_table(sid, rec, ctx):
    t = rec["table"]
    tbl = comp(f"{sid}_table", "table", headers=t["headers"], rows=t["rows"], colWidthsIn=t.get("col_widths"),
               revealItems="index 0 = header row, 1..n = body rows")
    return ([comp(f"{sid}_heading", "heading", text=rec["title"], level=1), tbl]
            + image_comps(sid, rec) + callout_comps(sid, rec)), tbl["id"]


def build_comparison(sid, rec, ctx):
    cmp_ = comp(f"{sid}_comparison", "comparison",
                columns=[{"title": ch["label"], "body": ch["body"]} for ch in rec["chunks"]])
    return ([comp(f"{sid}_heading", "heading", text=rec["title"], level=1), cmp_]
            + image_comps(sid, rec) + callout_comps(sid, rec)), cmp_["id"]


def build_process(sid, rec, ctx):
    steps = [{"label": ch["label"]} for ch in rec["chunks"]]
    props = {"steps": steps, "numbered": True}
    ix = rec.get("interaction")
    layer_map = {}
    if ix and ix.get("layers"):
        layers = []
        for L in ix["layers"]:
            lid = f"{sid}_layer_{L['index']}"
            layer_map[L["index"]] = lid
            layers.append({"layerId": lid, "index": L["index"], "stepIndex": L["index"] - 1,
                           "label": L.get("tab_label"), "lines": L.get("lines", []),
                           "responsible": L.get("responsible", []), "fromSlide": L.get("from_slide")})
        props["interaction"] = {"type": "layers", "trigger": "click",
                                "sourceType": ix.get("type"),
                                "instruction": ix.get("instruction"),
                                "buildAs": ix.get("build_as"),
                                "layers": layers}
        emb = ctx["embedded"]
        if emb:
            props["embeddedStates"] = [{"sourceSlideId": e["id"], "heading": e["title"], "layout": e["layout"],
                                        "designRationale": e["design_rationale"],
                                        "sourceSlides": e["source_slides"],
                                        "objectiveRefs": e["objective_refs"]} for e in emb]
    p = comp(f"{sid}_process", "process", **props)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if rec.get("instruction"):
        head.append(comp(f"{sid}_instruction", "instruction", text=rec["instruction"]))
    ctx["layer_map"] = (p["id"], layer_map)
    return head + [p] + image_comps(sid, rec) + callout_comps(sid, rec), p["id"]


def _feedback(sid, q):
    return [{"layerId": f"{sid}_feedback_{f['layer']}", "kind": f["layer"], "shownWhen": f.get("shown_when"),
             "heading": f.get("heading"), "body": f.get("body"), "button": f.get("button"),
             "onClick": f.get("on_click", [])} for f in q["feedback_layers"]]


def build_knowledge_check(sid, rec, ctx):
    q = rec["question"]
    mc = comp(f"{sid}_question", "multipleChoice",
              questionType=q["type"], stem=q["stem"],
              options=[{"key": o["key"], "text": o["text"], "correct": o["correct"]} for o in q["options"]],
              correctKeys=[o["key"] for o in q["options"] if o["correct"]],
              attempts=q["attempts"], scored=q["scored"],
              feedback=_feedback(sid, q),
              onSubmitWithNoSelection=q["on_submit_with_no_selection"])
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1),
            comp(f"{sid}_instruction", "instruction", text=q["instruction"]), mc], mc["id"]


def build_sequence(sid, rec, ctx):
    q = rec["question"]
    items = q["drag_items"] or [{"label": ch["label"], "answer_key": ch["body"]} for ch in rec["chunks"]]
    seq = comp(f"{sid}_question", "sequence",
               questionType=q["type"], stem=q["stem"],
               items=[{"id": f"item_{i}", "label": it["label"], "correctPosition": int(it["answer_key"])}
                      for i, it in enumerate(items, 1)],
               attempts=q["attempts"], scored=q["scored"],
               feedback=_feedback(sid, q),
               onSubmitWithNoSelection=q["on_submit_with_no_selection"])
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1),
            comp(f"{sid}_instruction", "instruction", text=q["instruction"]), seq], seq["id"]


def build_match(sid, rec, ctx):
    q = rec["question"]
    if q and q.get("drag_items"):
        items = q["drag_items"]
    else:
        # Code Red format: chunks with label=left side, body=right side
        items = [{"label": ch["label"], "answer_key": ch["body"]} for ch in rec["chunks"]]
    stem = q["stem"] if q else rec.get("title")
    instruction = (q.get("instruction") if q else None) or rec.get("instruction")
    m = comp(f"{sid}_question", "matching",
             questionType=q["type"] if q else "Match the following",
             stem=stem,
             items=[{"id": f"item_{i}", "label": it["label"], "matchText": it.get("answer_key") or it.get("body", "")}
                    for i, it in enumerate(items, 1)],
             attempts=q["attempts"] if q else 1, scored=q["scored"] if q else False,
             feedback=_feedback(sid, q) if q and q.get("feedback_layers") else [],
             onSubmitWithNoSelection=q["on_submit_with_no_selection"] if q else None)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if instruction:
        head.append(comp(f"{sid}_instruction", "instruction", text=instruction))
    return head + [m], m["id"]


def build_true_false(sid, rec, ctx):
    """True/False quiz: same as multiple choice but only two options."""
    q = rec["question"]
    if q:
        stem = q["stem"]
        options = q["options"]
        instruction = q.get("instruction") or rec.get("instruction")
        attempts = q["attempts"]
        scored = q["scored"]
        feedback = _feedback(sid, q) if q.get("feedback_layers") else []
        on_submit = q["on_submit_with_no_selection"]
    else:
        stem = rec.get("question") or rec.get("title")
        options = rec.get("options", [])
        instruction = rec.get("instruction")
        attempts = 1
        scored = False
        feedback = []
        on_submit = None
    tf = comp(f"{sid}_question", "trueFalse",
              questionType="True or False", stem=stem,
              options=[{"key": o["key"], "text": o["text"], "correct": o["correct"]} for o in options],
              correctKeys=[o["key"] for o in options if o["correct"]],
              rationale=rec.get("rationale") or (q.get("rationale") if q else None),
              attempts=attempts, scored=scored,
              feedback=feedback,
              onSubmitWithNoSelection=on_submit)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if instruction:
        head.append(comp(f"{sid}_instruction", "instruction", text=instruction))
    return head + [tf], tf["id"]


def build_multi_select(sid, rec, ctx):
    """Multiple response question: learner selects multiple correct answers."""
    q = rec["question"]
    if q:
        stem = q["stem"]
        options = q["options"]
        instruction = q.get("instruction") or rec.get("instruction")
        attempts = q["attempts"]
        scored = q["scored"]
        feedback = _feedback(sid, q) if q.get("feedback_layers") else []
        on_submit = q["on_submit_with_no_selection"]
    else:
        stem = rec.get("question") or rec.get("title")
        options = rec.get("options", [])
        instruction = rec.get("instruction")
        attempts = 1
        scored = False
        feedback = []
        on_submit = None
    ms = comp(f"{sid}_question", "multiSelect",
              questionType="Multiple Response", stem=stem,
              options=[{"key": o["key"], "text": o["text"], "correct": o["correct"]} for o in options],
              correctKeys=[o["key"] for o in options if o["correct"]],
              rationale=rec.get("rationale") or (q.get("rationale") if q else None),
              attempts=attempts, scored=scored,
              feedback=feedback,
              onSubmitWithNoSelection=on_submit)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if instruction:
        head.append(comp(f"{sid}_instruction", "instruction", text=instruction))
    return head + [ms], ms["id"]


def build_stepper_detail(sid, rec, ctx):
    """Stepper detail: content cards with step-by-step navigation."""
    cards = [{"title": ch["label"], "body": ch["body"]} for ch in rec["chunks"]]
    grid = comp(f"{sid}_cards", "cardGrid", cards=cards)
    head = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)]
    if rec.get("instruction"):
        head.append(comp(f"{sid}_instruction", "instruction", text=rec["instruction"]))
    return head + [grid] + image_comps(sid, rec) + callout_comps(sid, rec), grid["id"]


def build_summary(sid, rec, ctx):
    s = comp(f"{sid}_summary", "summary", points=[ch["label"] for ch in rec["chunks"]])
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1), s], s["id"]


def build_references(sid, rec, ctx):
    r = comp(f"{sid}_references", "references", style="Vancouver", items=[ch["label"] for ch in rec["chunks"]])
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1), r], r["id"]


def build_results(sid, rec, ctx):
    r = comp(f"{sid}_results", "results", lines=[ch["label"] for ch in rec["chunks"]],
             actions=["review", "close"])
    return [comp(f"{sid}_heading", "heading", text=rec["title"], level=1), r], r["id"]


BUILDERS = {
    "title": build_title, "objectives": build_objectives, "icon-row": build_icon_row,
    "chip-detail": build_chip_detail, "definition": build_definition, "image-focus": build_image_focus,
    "table": build_table, "comparison": build_comparison, "process": build_process,
    "knowledge-check": build_knowledge_check, "sequence": build_sequence, "match": build_match,
    "true-false": build_true_false, "multi-select": build_multi_select,
    "stepper-detail": build_stepper_detail,
    "summary": build_summary, "references": build_references, "results": build_results,
}


def _cross_check_layers(rec, embedded, issues):
    """The parent's layers and the embedded slide's chunks must say the same thing."""
    layers = (rec.get("interaction") or {}).get("layers", [])
    for e in embedded:
        for i, ch in enumerate(e["chunks"]):
            L = layers[i] if i < len(layers) else None
            if L is None or L.get("tab_label") != ch["label"] or (L.get("lines") or [None])[0] != ch["body"]:
                issues.append({"slide": rec["id"], "field": f"layer {i + 1}",
                               "problem": f"embedded slide {e['id']} chunk {i + 1} does not match interaction layer"})
        if [L.get("narration") for L in layers] != [[v] for v in e["narration"]]:
            issues.append({"slide": rec["id"], "field": "layer narration",
                           "problem": f"layer narration differs from embedded slide {e['id']} vo"})


def generate_components(mapped, storyboard, interactions, normalize_issues):
    issues = list(normalize_issues) + list(mapped["issues"])
    context = {}
    modules = []
    sme = storyboard["sme_queries"]

    for m in mapped["modules"]:
        src, pkg = m["source"], m["package"] or {}
        slides = []
        for ps in m["player_slides"]:
            rec, sid = ps["record"], ps["slide_id"]
            builder = BUILDERS.get(rec["layout"])
            ctx = {"module_title": src["title"], "module_number": src["number"],
                   "course_title": storyboard["meta"]["course"], "producer": storyboard["meta"]["producer"], "objectives": src["objectives"], "embedded": ps["embedded"]}
            if builder is None:
                issues.append({"slide": rec["id"], "problem": f"no builder for layout '{rec['layout']}'"})
                comps, target = [comp(f"{sid}_heading", "heading", text=rec["title"], level=1)], None
            else:
                comps, target = builder(sid, rec, ctx)
            if ps["embedded"]:
                _cross_check_layers(rec, ps["embedded"], issues)

            src_set = set(rec["source_slides"])
            slide = {
                "slideId": sid,
                "sourceSlideId": rec["id"],
                "order": ps["order"],
                "layout": rec["layout"],
                "title": rec["title"],
                "breadcrumb": rec["breadcrumb"],
                "sourceSlides": rec["source_slides"],
                "objectiveRefs": rec["objective_refs"],
                "designRationale": rec["design_rationale"],
                "devNotes": rec["dev_notes"],
                "navigation": ps["navigation"],
                "smeQueryRefs": [q["id"] for q in sme if src_set & set(q.get("source_slides", []))],
                "embeddedSourceSlides": [e["id"] for e in ps["embedded"]],
                "components": comps,
            }
            if ps["source_navigation"]:
                slide["sourceNavigation"] = ps["source_navigation"]
            slides.append(slide)
            context[sid] = {"reveal_target": target, "layers": ctx.get("layer_map"), "record": rec}

        modules.append({
            "moduleId": m["module_id"],
            "number": src["number"],
            "title": src["title"],
            "scopingSentence": src["scoping_sentence"],
            "objectives": src["objectives"],
            "learningTime": src["learning_time"],
            "scorm": pkg.get("scorm"),
            "player": pkg.get("player"),
            "slideFurniture": pkg.get("slide_furniture"),
            "playerSlideCount": len(slides),
            "embeddedSourceSlides": m["embedded_ids"],
            "slides": slides,
        })

    sb = storyboard["meta"]
    ix = interactions["meta"] if interactions else {}
    doc = {
        "specVersion": "v1",
        "course": {
            "title": sb["course"],
            "producer": sb["producer"],
            "sourceFile": sb["source_file"],
            "sourceSlideCount": sb["source_slide_count"],
            "splitRationale": sb["split_rationale"],
            "learningTimeTotalMin": sb["learning_time_total_min"],
            "learningTimeNote": sb["learning_time_note"],
            "authoringTool": ix.get("authoring_tool"),
            "interactionsSpecVersion": ix.get("spec_version"),
            "interactionsReference": ix.get("reference"),
            "buildChecklist": interactions.get("build_checklist", []) if interactions else [],
        },
        "review": {
            "smeQueries": sme,
            "sourceConflicts": issues,
        },
        "modules": modules,
    }
    return doc, context
