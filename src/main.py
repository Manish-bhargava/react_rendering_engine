"""CLI: python -m src.main [--storyboard PATH] [--interactions PATH] [--out DIR]"""
import argparse
import json
import logging
import os
import sys
import time

from src.lesson_builder import build_lesson, write_outputs


def setup_logging():
    """Configure logging to both console and file."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "lesson_builder.log")

    root = logging.getLogger("lesson_builder")
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — append mode, full detail
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler — info and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    return log_path


def print_build_report(result, out_dir, log_path, elapsed):
    """Print a final build summary."""
    log = logging.getLogger("lesson_builder")
    st = result["stats"]
    errors = result["errors"]
    paths = result.get("written_paths", [])
    inputs = result.get("input_paths", {})

    log.info("=" * 60)
    log.info("BUILD REPORT")
    log.info("=" * 60)
    log.info("Input files:")
    log.info("  storyboard:   %s", inputs.get("storyboard", "?"))
    log.info("  interactions: %s", inputs.get("interactions", "?"))
    for d in inputs.get("decks", []):
        log.info("  deck:         %s", d)
    log.info("")
    log.info("Counts:")
    log.info("  modules:              %d", st["modules"])
    log.info("  player slides:        %d", st["player_slides"])
    log.info("  components:           %d", st["components"])
    log.info("  interaction layers:   %d", st["interaction_layers"])
    log.info("  quiz feedback layers: %d", st["quiz_feedback_layers"])
    log.info("  base narrations:      %d", st["narration_entries_base"])
    log.info("  layer narrations:     %d", st["narration_entries_layer"])
    log.info("  narration lines:      %d", st["narration_lines"])
    log.info("  audio files:          %d", st["audio_files_referenced"])
    log.info("  images:               %d (%d unresolved)", st["images"], st["images_unresolved"])
    log.info("  review items:         %d", st["review_items"])
    log.info("  SME queries:          %d", st["sme_queries"])
    log.info("")
    log.info("Component types: %s", json.dumps(st["component_types"]))
    if st["slides_without_narration"]:
        log.info("Slides without narration: %s", st["slides_without_narration"])
    log.info("")
    log.info("Generation:  PASSED")
    log.info("Output:      %s (%d file(s) written)", "WRITTEN" if paths else "NOT WRITTEN", len(paths))
    for p in paths:
        log.info("  %s", p)
    log.info("Validation:  %s (%d error(s))", "PASSED" if not errors else "FAILED", len(errors))
    if errors:
        for e in errors:
            log.info("  - %s", e)
    log.info("")
    log.info("Elapsed: %.2f seconds", elapsed)
    log.info("Log file: %s", log_path)
    log.info("=" * 60)


def main(argv=None):
    log_path = setup_logging()
    log = logging.getLogger("lesson_builder")

    ap = argparse.ArgumentParser(description="Convert storyboard + interactions JSON into a V1 lesson.")
    ap.add_argument("--storyboard", default="input/storyboard.json")
    ap.add_argument("--interactions", default="input/interactions.json",
                    help="Path to interactions.json (optional; omit or set to 'none' to skip)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--deck", action="append", default=None,
                    help="authored .pptx, once per module in order (default: input/decks/*.pptx)")
    args = ap.parse_args(argv)

    decks = args.deck
    if decks is None:
        import glob
        decks = sorted(glob.glob("input/decks/*.pptx"))

    log.info("Lesson Builder started")
    log.info("Working directory: %s", os.getcwd())
    start = time.time()

    # ---- Generate ----
    ix_path = args.interactions if args.interactions.lower() != "none" else None
    result = build_lesson(args.storyboard, ix_path, decks, args.out)

    # ---- Stage 7: Always write output files ----
    log.info("STAGE 7: Writing output files")
    written = write_outputs(result, args.out)
    result["written_paths"] = written
    for p in written:
        log.info("  wrote %s", p)

    # ---- Report ----
    elapsed = time.time() - start
    print_build_report(result, args.out, log_path, elapsed)

    # ---- Review items (deck matching, source conflicts) ----
    for i in result["components"]["review"].get("deckMatching", []):
        log.debug("deck issue: %s | %s", i.get("slide", i.get("module")), i["problem"])
    review = result["components"]["review"]["sourceConflicts"]
    if review:
        log.info("%d source issue(s) recorded in components.json -> review.sourceConflicts", len(review))

    # Exit 1 on validation failure, but output files are already written
    if result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
