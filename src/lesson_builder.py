"""Runs the pipeline end to end: parse -> normalize -> map -> generate x3 -> validate -> write."""
import json
import logging
import os

from src.parsers.storyboard_parser import parse_storyboard
from src.parsers.interactions_parser import parse_interactions
from src.processors.normalizer import normalize
from src.processors.slide_mapper import map_slides
from src.generators.components_generator import generate_components
from src.generators.layout_generator import generate_layout
from src.generators.voiceover_generator import generate_voiceover
from src.validators.basic_validator import validate
from src.parsers.pptx_parser import parse_deck
from src.processors.deck_matcher import match_decks
from src.processors.box_normalizer import normalize as normalize_boxes

log = logging.getLogger("lesson_builder")


def build_lesson(storyboard_path, interactions_path=None, deck_paths=(), out_dir="output"):
    # ---- Stage 1: Input loading ----
    log.info("STAGE 1: Loading input files")
    sb_abs = os.path.abspath(storyboard_path)
    log.info("  storyboard: %s", sb_abs)

    storyboard = parse_storyboard(storyboard_path)
    sb_modules = len(storyboard["modules"])
    sb_slides = sum(len(m["slides"]) for m in storyboard["modules"])
    log.info("  storyboard loaded: %d module(s), %d slide(s)", sb_modules, sb_slides)

    ix_abs = os.path.abspath(interactions_path) if interactions_path and os.path.isfile(interactions_path) else None
    if ix_abs:
        log.info("  interactions: %s", ix_abs)
    else:
        log.info("  interactions: not provided — running with storyboard only")
    interactions = parse_interactions(interactions_path)
    ix_packages = len(interactions["packages"])
    ix_audio = len(interactions["audio_manifest"])
    log.info("  interactions loaded: %d package(s), %d audio manifest entries", ix_packages, ix_audio)

    # ---- Stage 2: Parsing / Normalization ----
    log.info("STAGE 2: Normalizing and mapping slides")
    normalized = normalize(storyboard, interactions)
    norm_issues = len(normalized["issues"])
    if norm_issues:
        log.warning("  normalization produced %d issue(s)", norm_issues)
        for issue in normalized["issues"]:
            log.warning("    %s", issue)
    else:
        log.info("  normalization: 0 issues")

    mapped = map_slides(normalized)
    player_slides = sum(len(m["player_slides"]) for m in mapped["modules"])
    embedded = sum(len(m["embedded_ids"]) for m in mapped["modules"])
    log.info("  mapped: %d player slide(s), %d embedded state(s)", player_slides, embedded)
    if mapped["issues"]:
        log.warning("  mapping produced %d issue(s)", len(mapped["issues"]))

    # ---- Stage 3: Component generation ----
    log.info("STAGE 3: Generating components")
    components, context = generate_components(mapped, storyboard, interactions, normalized["issues"])
    comp_count = sum(len(c) for m in components["modules"] for s in m["slides"] for c in [s["components"]])
    log.info("  generated %d component(s) across %d slide(s)", comp_count, player_slides)

    deck = None
    if deck_paths:
        log.info("  processing %d deck(s)", len(deck_paths))
        for dp in deck_paths:
            log.info("    deck: %s", os.path.abspath(dp))
        decks = {m["number"]: parse_deck(p) for m, p in zip(components["modules"], deck_paths)}
        deck = match_decks(components, decks, out_dir)
        deck["normalized"] = normalize_boxes(deck["measured"], components, deck["furniture"],
                                             deck.get("cover"))
        components["review"]["deckMatching"] = deck["issues"]
        log.info("  deck matching: %d issue(s)", len(deck["issues"]))

    # ---- Stage 4: Layout generation ----
    log.info("STAGE 4: Generating layout")
    layout = generate_layout(components, deck)
    layout_slides = len(layout["slides"])
    log.info("  layout generated for %d slide(s)", layout_slides)

    # ---- Stage 5: Voiceover generation ----
    log.info("STAGE 5: Generating voiceover")
    voiceover = generate_voiceover(components, context, interactions, components["review"]["sourceConflicts"])
    vo_base = sum(1 for m in voiceover["modules"] for s in m["slides"] if s["base"])
    vo_layers = sum(len(s["layers"]) for m in voiceover["modules"] for s in m["slides"])
    log.info("  voiceover: %d base narration(s), %d layer narration(s)", vo_base, vo_layers)

    # ---- Stage 6: Validation ----
    log.info("STAGE 6: Validating output")
    embedded_ids = [sid for m in mapped["modules"] for sid in m["embedded_ids"]]
    errors = validate(components, layout, voiceover, embedded_ids)
    if errors:
        log.warning("  validation: %d error(s)", len(errors))
        for e in errors:
            log.warning("    %s", e)
    else:
        log.info("  validation: PASSED (0 errors)")

    return {"components": components, "layout": layout, "voiceover": voiceover,
            "errors": errors, "stats": stats(components, voiceover),
            "input_paths": {"storyboard": sb_abs, "interactions": ix_abs or "(none)",
                            "decks": [os.path.abspath(d) for d in (deck_paths or [])]}}


def write_outputs(result, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name in ("components", "layout", "voiceover"):
        p = os.path.join(out_dir, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(result[name], f, ensure_ascii=False, indent=2)
        paths.append(p)
    return paths


def stats(components, voiceover):
    slides = [s for m in components["modules"] for s in m["slides"]]
    comps = [c for s in slides for c in s["components"]]
    content_layers = [L for c in comps for L in c["props"].get("interaction", {}).get("layers", [])]
    feedback_layers = [f for c in comps for f in c["props"].get("feedback", [])]
    vslides = [s for m in voiceover["modules"] for s in m["slides"]]
    base = [s for s in vslides if s["base"]]
    vlayers = [L for s in vslides for L in s["layers"]]
    images = [c for c in comps if c["type"] == "image"]
    types = {}
    for c in comps:
        types[c["type"]] = types.get(c["type"], 0) + 1
    return {
        "modules": len(components["modules"]),
        "player_slides": len(slides),
        "components": len(comps),
        "component_types": dict(sorted(types.items())),
        "interaction_layers": len(content_layers),
        "quiz_feedback_layers": len(feedback_layers),
        "narration_entries_base": len(base),
        "narration_entries_layer": len(vlayers),
        "narration_lines": sum(len(s["base"]["lines"]) for s in base) + sum(len(L["lines"]) for L in vlayers),
        "slides_without_narration": [s["sourceSlideId"] for s in vslides if not s["base"] and not s["layers"]],
        "audio_files_referenced": len({s["base"]["audioFile"] for s in base if s["base"]["audioFile"]}
                                      | {L["audioFile"] for L in vlayers if L["audioFile"]}),
        "images": len(images),
        "images_unresolved": sum(1 for c in images if c["props"]["status"] == "unresolved"),
        "menu_targets_unresolved": sum(len(c["props"]["interaction"]["targets"]) for c in comps
                                       if c["props"].get("interaction", {}).get("type") == "menu"),
        "review_items": len(components["review"]["sourceConflicts"]),
        "sme_queries": len(components["review"]["smeQueries"]),
        "deck_review_items": len(components["review"].get("deckMatching", [])),
    }
