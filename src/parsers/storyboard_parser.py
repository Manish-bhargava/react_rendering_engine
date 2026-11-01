"""Read storyboard.json and index it. No content is changed here."""
import json

REQUIRED_TOP = ["course", "modules"]
REQUIRED_SLIDE = ["id", "layout", "heading"]


def parse_storyboard(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    missing = [k for k in REQUIRED_TOP if k not in data]
    if missing:
        raise ValueError(f"storyboard.json is missing top-level keys: {missing}")

    modules = []
    for m in data["modules"]:
        slides = {}
        for s in m.get("slides", []):
            gaps = [k for k in REQUIRED_SLIDE if k not in s]
            if gaps:
                raise ValueError(f"storyboard slide {s.get('id')} is missing {gaps}")
            slides[s["id"]] = s
        modules.append({
            "number": m["number"],
            "title": m.get("title"),
            "objectives": m.get("objectives", []),
            "scoping_sentence": m.get("scoping_sentence"),
            "learning_time": m.get("learning_time"),
            "slides": slides,                      # keyed by storyboard id, e.g. "1.04"
            "slide_order": [s["id"] for s in m.get("slides", [])],
        })

    return {
        "meta": {k: data.get(k) for k in [
            "course", "producer", "source_file", "source_slide_count",
            "split_rationale", "learning_time_total_min", "learning_time_note"]},
        "sme_queries": data.get("sme_queries", []),
        "modules": modules,
    }
