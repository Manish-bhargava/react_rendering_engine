# CLAUDE.md



## What this is

A Python pipeline that turns an e-learning storyboard (`input/storyboard.json`), a Storyline-style interactions file (`input/interactions.json`) and, optionally, the authored PowerPoint decks (`input/decks/*.pptx`) into three JSON files in `output/`. A React player in `player/` renders those files. README.md is the detailed spec. Read it before changing data rules, layout normalization or responsive behaviour.

## Commands

Run everything from the repo root. Imports are `from src.…`, and `conftest.py` puts the root on `sys.path`.

```bash
pip install -r requirements.txt                 # python-pptx, Pillow, pytest
python -m src.main                              # input/ (+ input/decks/*.pptx) -> output/
python -m src.main --storyboard a.json --interactions b.json --deck s1.pptx --deck s2.pptx --out out/
python -m src.main --interactions none          # storyboard only

python -m pytest -q                             # all tests
python -m pytest -q tests/test_pipeline.py::test_validation_passes   # a single test

cd player && npm install
npm run dev        # bundles with esbuild, serves player/public on :5173, serves /lesson/*.json straight from ../output/
npm run build      # copies output/*.json + assets into player/public, minified bundle, then emits section-1/ and section-2/
node scripts/check-responsive.mjs [1440x900,390x844]   # after build; needs playwright
node scripts/check-narration.mjs
```

- The `venv/` folder in the repo is a Windows venv (`Scripts/`, no `bin/`). It won't work on macOS or Linux, so create a fresh one.
- `src.main` writes the outputs even when validation fails. It exits 1 in that case. The log is appended to `logs/lesson_builder.log`.
- `tests/test_pipeline.py` builds the lesson once when the module is imported. Deck-dependent tests quietly return early if `input/decks/section_1.pptx` and `section_2.pptx` are missing. In this checkout `input/decks/` doesn't exist, so those tests pass without testing anything.
- LibreOffice (`soffice`) is optional. It's used only to render icons that were drawn as PowerPoint shapes into PNGs.

## Pipeline architecture

`src/lesson_builder.py::build_lesson` runs the stages in order, and `write_outputs` writes the files:

1. **Parse** (`src/parsers/`): storyboard, interactions (packages, slides in player order, audio manifest keyed by `(slide, layer)`), and the optional pptx shape records.
2. **Normalize** (`processors/normalizer.py`): merges each storyboard slide with its interaction slide. The storyboard wins on teaching content. The interactions file wins on build behaviour (cues, layers, feedback, audio). Conflicts are recorded in `review.sourceConflicts` and never resolved silently.
3. **Map** (`processors/slide_mapper.py`): builds the real player sequence. Embedded states (`interaction.state_of` or a layer's `from_slide`, e.g. 2.04 → layers on `slide_2_03`) become layers, not player slides. Rebuilds prev/next/home.
4. **Generate components** (`generators/components_generator.py`): one builder per storyboard layout (`BUILDERS`). Text is copied verbatim.
5. **Match decks** (`processors/deck_matcher.py`): pairs components with deck shapes **by text, never by position**. Extracts the logo and icons to `output/assets/`. Unclaimed deck text becomes `paragraph` components. Mismatches are recorded in `review.deckMatching`.
6. **Layout** (`generators/layout_generator.py`): the deck is 13.333 in at 96 px/in, which maps 1:1 onto a 1280×720 canvas. Each entry carries `source`, either `"authored deck … slide N"` or `"inferred"`. Then `processors/box_normalizer.py` adjusts numbers only (insets, icon-grid squaring, x=48 left margin, chip widths, header/player-bar chrome). It must never add, remove or rename keys.
7. **Voiceover** (`generators/voiceover_generator.py`): reveal cues map to `componentId + itemIndex + lineIndex`. Timing is word-proportional.
8. **Validate** (`validators/basic_validator.py`): unique IDs, cross-file references, `REQUIRED_PROPS`, frames on the canvas, nav targets, and no embedded slide that is also a player slide.

The three outputs are split by concern, and nothing is duplicated between them. `components.json` holds what is on each slide. `layout.json` holds where it goes and how it looks. `voiceover.json` holds what is heard and when. Every layout item and voiceover cue or layer references a component ID.

Invariants the tests enforce: every narration line and every content string from the inputs survives, and every manifest audio file is mapped. Unresolved images keep `src: null` / `status: "unresolved"`, so never invent URLs or asset targets.

## Player

React 19 is bundled by esbuild (no Vite). `player/src/App.jsx` loads the three JSON files, routes on hash (`#module_01/slide_1_04`), and switches between scale-to-fit stage mode and flow mode (below `layout.json → responsive.stackBelowPx`). Breakpoints come from `layout.json` and are never hard-coded. `src/registry.js` is the only place component types are wired to renderers. `components/Measured.jsx` renders deck-measured layouts, and `Text/Content/Interactive/Quiz.jsx` are fallbacks for inferred ones. `useNarration.js` handles base and layer audio and reveal timing, with captions from `vtt.js`. `public/styles.css` reads only the token CSS variables set by `theme.js`.

`player/public/app.js`, `player/public/lesson/`, `player/public/assets/` and `player/public/section-*/` are build outputs. Edit `player/src/` and regenerate them, not the outputs themselves. `scripts/package-sections.mjs` filters the JSON per module into self-contained `section-1/` (module_01) and `section-2/` (module_02) folders.

## Adding a component type

Touch all four places: a builder in `components_generator.py`, an `arrange` branch plus a `COMPONENT_STYLES` entry in `layout_generator.py`, `REQUIRED_PROPS` in `basic_validator.py`, and a React component (props `c, arrange, frame, narr, nav`) registered in `player/src/registry.js`.



