"""The minimum checks V1 needs. Returns a list of error strings (empty = pass)."""
import json

REQUIRED_PROPS = {
    "heading": ["text"], "paragraph": ["text"], "instruction": ["text"],
    "image": ["alt", "status"], "callout": ["kind", "text"],
    "bulletList": ["items"], "objectivesList": ["items"], "iconGrid": ["items"],
    "cardGrid": ["cards"], "definition": ["terms"], "process": ["steps"],
    "comparison": ["columns"], "table": ["headers", "rows"],
    "multipleChoice": ["stem", "options", "correctKeys", "feedback"],
    "trueFalse": ["stem", "options", "correctKeys"],
    "multiSelect": ["stem", "options", "correctKeys"],
    "sequence": ["items", "feedback"], "matching": ["items", "feedback"], "summary": ["points"],
    "references": ["items"], "results": ["lines"],
}


def validate(components, layout, voiceover, embedded_source_ids=()):
    errors = []

    # 1. valid JSON (round-trip what will be written)
    for name, doc in [("components.json", components), ("layout.json", layout), ("voiceover.json", voiceover)]:
        try:
            json.loads(json.dumps(doc))
        except (TypeError, ValueError) as e:
            errors.append(f"{name}: not serialisable as JSON ({e})")

    # 2. unique slide ids, unique component ids, required props
    slide_ids, comp_ids, layer_ids, source_ids = [], [], [], []
    for m in components["modules"]:
        for s in m["slides"]:
            slide_ids.append(s["slideId"])
            source_ids.append(s["sourceSlideId"])
            for c in s["components"]:
                comp_ids.append(c["id"])
                for p in REQUIRED_PROPS.get(c["type"], []):
                    if c["props"].get(p) in (None, "", []):
                        errors.append(f"{c['id']}: required prop '{p}' missing for type {c['type']}")
                for L in c["props"].get("interaction", {}).get("layers", []):
                    layer_ids.append(L["layerId"])
                for f in c["props"].get("feedback", []):
                    layer_ids.append(f["layerId"])
            for k in ("prev", "next", "home"):
                tgt = s["navigation"].get(k)
                if tgt is not None and tgt not in [x["slideId"] for x in m["slides"]]:
                    errors.append(f"{s['slideId']}: navigation.{k} -> {tgt} is not a slide in {m['moduleId']}")

    def dupes(xs):
        return sorted({x for x in xs if xs.count(x) > 1})

    for label, xs in [("slide id", slide_ids), ("component id", comp_ids), ("layer id", layer_ids)]:
        for d in dupes(xs):
            errors.append(f"duplicate {label}: {d}")

    slide_set, comp_set, layer_set = set(slide_ids), set(comp_ids), set(layer_ids)

    # 3. layout references
    laid_out = set()
    for ls in layout["slides"]:
        if ls["slideId"] not in slide_set:
            errors.append(f"layout.json: unknown slide {ls['slideId']}")
        for it in ls["items"]:
            if it["componentId"] not in comp_set:
                errors.append(f"layout.json {ls['slideId']}: unknown component {it['componentId']}")
            laid_out.add(it["componentId"])
            f = it["frame"]
            if f["x"] < 0 or f["y"] < 0 or f["x"] + f["w"] > layout["canvas"]["width"] \
                    or f["y"] + f["h"] > layout["canvas"]["height"]:
                errors.append(f"layout.json {it['componentId']}: frame outside the canvas {f}")
    for c in sorted(comp_set - laid_out):
        errors.append(f"layout.json: component {c} has no layout entry")
    if {s["slideId"] for s in layout["slides"]} != slide_set:
        errors.append("layout.json: slide set differs from components.json")

    # 4. voice-over references
    for m in voiceover["modules"]:
        for vs in m["slides"]:
            if vs["slideId"] not in slide_set:
                errors.append(f"voiceover.json: unknown slide {vs['slideId']}")
            for L in vs["layers"]:
                if L["layerId"] not in layer_set:
                    errors.append(f"voiceover.json {vs['slideId']}: unknown layer {L['layerId']}")
                if L["componentId"] not in comp_set:
                    errors.append(f"voiceover.json {vs['slideId']}: unknown component {L['componentId']}")
            for cue in (vs["base"] or {}).get("reveal", {}).get("cues", []):
                if cue["componentId"] is not None and cue["componentId"] not in comp_set:
                    errors.append(f"voiceover.json {vs['slideId']}: cue -> unknown component {cue['componentId']}")
                if cue["componentId"] is None:
                    errors.append(f"voiceover.json {vs['slideId']}: reveal cue {cue['order']} has no target component")

    # 5. embedded interaction layers must not also be player slides
    for sid in embedded_source_ids:
        if sid in source_ids:
            errors.append(f"embedded slide {sid} also appears as a player slide")

    return errors
