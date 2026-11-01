"""Read interactions.json and index packages, slides and the audio manifest.

When no interactions file is available, `parse_interactions(None)` returns an
empty but structurally valid dict so the rest of the pipeline can run.
"""
import json
import os

REQUIRED_TOP = ["course", "packages"]


def _empty_interactions():
    """Return a valid interactions dict with no data."""
    return {
        "meta": {"spec_version": None, "course": None, "producer": None,
                 "source_file": None, "authoring_tool": None,
                 "generated_from": None, "reference": None},
        "build_checklist": [],
        "packages": {},
        "audio": {},
        "audio_manifest": [],
    }


def parse_interactions(path):
    if path is None or not os.path.isfile(path):
        return _empty_interactions()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    missing = [k for k in REQUIRED_TOP if k not in data]
    if missing:
        raise ValueError(f"interactions.json is missing top-level keys: {missing}")

    packages = {}
    for p in data["packages"]:
        packages[p["module"]] = {
            "module": p["module"],
            "title": p.get("title"),
            "slide_count": p.get("slide_count"),
            "learning_time": p.get("learning_time"),
            "scorm": p.get("scorm"),
            "player": p.get("player"),
            "slide_furniture": p.get("slide_furniture"),
            "slides": {s["id"]: s for s in p.get("slides", [])},
            "slide_order": [s["id"] for s in p.get("slides", [])],   # this IS the player order
        }

    # Audio manifest keyed by (slide id, layer index or None)
    audio = {}
    for a in data.get("audio_manifest", []):
        audio[(a["slide"], a.get("layer"))] = a

    return {
        "meta": {k: data.get(k) for k in [
            "spec_version", "course", "producer", "source_file",
            "authoring_tool", "generated_from", "reference"]},
        "build_checklist": data.get("build_checklist", []),
        "packages": packages,
        "audio": audio,
        "audio_manifest": data.get("audio_manifest", []),
    }
