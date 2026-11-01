# Lesson Builder V4

Converts an educational PowerPoint's **storyboard JSON** and **interactions JSON** (plus, optionally, the **authored .pptx decks**) into three files that a React lesson player renders:

| File | Answers | Holds |
|---|---|---|
| `output/components.json` | **What** is on each slide | course/module metadata, slides, ordered components with typed props, interaction layers, quiz feedback, SME queries, recorded source issues |
| `output/layout.json` | **How and where** it appears | 1280×720 canvas, house-style tokens, a frame (x, y, w, h) per component plus measured part/item frames, shape styles and typography, header/cover/player-bar chrome, responsive rule |
| `output/voiceover.json` | **What is heard and when** | base narration lines, audio file, words, approximate seconds, reveal cues, layer narration, playback rules |

Every layout entry and every voice-over cue or layer points at a component ID in `components.json`. Nothing is duplicated across the three files.
`output/assets/` holds the logo and icon images taken from the decks; it holds media files only, no JSON.

---

## Quick start

```bash
# 1. Generate (Python 3.9+)
pip install -r requirements.txt          # python-pptx, Pillow (pytest for tests)
python -m src.main                       # reads input/ (+ input/decks/*.pptx), writes output/
python -m src.main --storyboard a.json --interactions b.json \
                   --deck s1.pptx --deck s2.pptx --out out/   # one --deck per module, in order

# 2. Test (needs pytest)
python -m pytest -q

# 3. Run the player (Node 18+)
cd player
npm install
npm run dev                              # copies output/*.json, serves http://localhost:5173
# or: npm run build, then serve player/public/ with any static server

# The build also emits two self-contained section folders:
#   player/public/section-1/   (module_01, slides 1_01–1_20)
#   player/public/section-2/   (module_02, slides 2_01–2_23)
# Each carries its own index.html, app.js, styles.css, JSON and assets,
# and can be served standalone from any static server.

# 4. Check the layout at every screen size (after npm run build; needs playwright)
node scripts/check-responsive.mjs                          # 1920 / 1440 / 1180 / 900 / 768 / 390
node scripts/check-responsive.mjs 1440x900,390x844         # or pick the widths

# 5. Check the narration wiring (mapping always; transport once the audio is in place)
node scripts/check-narration.mjs
```

LibreOffice (`soffice`) is optional. When it is installed, icons drawn as PowerPoint shapes are rendered and cropped to PNG. Without it, those icons are reported as not extracted; picture icons and the logo are extracted either way. Without any decks, the pipeline falls back to inferred positions and a default look.

Put recorded narration in `player/public/audio/` using the filenames in `voiceover.json`; `player/public/audio/README.md` lists all 44 with their slide and estimated length. The player works without the audio files: it shows all content and labels the missing narration.

---

## Architecture

```
storyboard.json ─┐
                 ├─ Parse ─ Normalize ─ Map slides ─ components ─┬─ [match decks] ─ layout ─┐
interactions.json┘                                               └─ voiceover ──────────────┼─ Validate ─ write 3 files
authored decks (optional) ─ Parse ───────────────────────────────────┘                      │
                                                    source + deck issues → components.review ┘
```

| Stage | File | Responsibility |
|---|---|---|
| Parse | `src/parsers/storyboard_parser.py` | Load the storyboard, check the required keys, and index slides by ID. No content changes. |
|  | `src/parsers/interactions_parser.py` | Load packages, slides (in player order) and the audio manifest keyed by (slide, layer). |
|  | `src/parsers/pptx_parser.py` | Optional. Reads an authored deck into shape records (frame in px, geometry, fill, border, per-paragraph font and colour, tables, picture bytes). |
| Normalize | `src/processors/normalizer.py` | Merge each storyboard slide with its interaction slide into one record. The storyboard wins on teaching content and the interactions file wins on build behaviour (cues, layers, feedback, audio, media status). Disagreements go into `review.sourceConflicts` and are never silently resolved. |
| Map | `src/processors/slide_mapper.py` | Set the real player sequence and attach embedded states (`interaction.state_of`, or a layer's `from_slide`) to their parent as layers. Rebuild prev/next/home and report any source navigation that pointed at an embedded slide. |
| Match decks | `src/processors/deck_matcher.py` | Optional. Pairs every component with its deck shapes **by text, never by position**: chips, badges, rails, panels, verdict strips, rationale panels and table styling. Saves the logo and icons to `output/assets/`. Deck text that no component claims becomes a `paragraph` component, so nothing on the deck is lost. Mismatches go into `components.review.deckMatching`. |
| Normalize boxes | `src/processors/box_normalizer.py` | Corrects what a deck gets wrong once it has to be a player. **Insets:** every PowerPoint text frame arrives with the default 4.8 px / 9.6 px inset, which puts text hard against the edge of a chip, a rationale panel or a sequence slot; each boxed role gets a readable minimum instead, capped as a share of the box's own size so a short box can never be squeezed shut. Bare text frames keep the deck inset, because that is what aligns them with the rest of the slide. **Icon tiles:** a grid whose icons were dropped in at 40–110 px on five baselines is squared to one size on one baseline, centred over each label. **Left margin:** the deck keeps its title placeholder at x=17 and everything else at x=48, so every heading sat ~31 px left of its own content; headings move to the content margin and their sub-frames move with them. **Chips:** a card chip measured at 326 px over a 575 px body reads as a stub and wraps its label, so over a column the chip takes the column's width, and over a full-width body it grows only as far as its longest label needs. **Chrome:** the deck's logo plate is taller than its header band and its player bar stops 7 px short of the canvas, so the band grows to meet the plate, the bar runs to the bottom edge, both bands' contents are re-centred, and the cover logo — which the deck puts exactly where the player's footer goes — is lifted clear of it. Numbers only — no key is added, removed or renamed. |
| Generate | `src/generators/components_generator.py` | Run one small builder per storyboard layout to turn a record into typed components. Text is copied verbatim. |
|  | `src/generators/layout_generator.py` | Set the house-style tokens. Uses the deck measurements for every matched component (`source: "authored deck … slide N"`) and infers the rest (`source: "inferred"`) from the layout type, image placement and `size_in`. |
|  | `src/generators/voiceover_generator.py` | Copy narration lines and manifest data, and map each reveal cue to `componentId + itemIndex + lineIndex`. Builds the layer narration and playback rules. |
| Validate | `src/validators/basic_validator.py` | Checks valid JSON, unique slide, component and layer IDs, layout and voice-over references, required props, frames on the canvas, nav targets, and that no embedded slide is also a player slide. |
| Orchestrate | `src/lesson_builder.py`, `src/main.py` | Run the stages, write the outputs, and print the stats and any source issues. |

**Player** (`player/`, React 19, bundled with esbuild):

| File | Responsibility |
|---|---|
| `src/App.jsx` | Loads the three files, handles slide navigation (`#module_01/slide_1_04`), picks the responsive mode and stage scale, draws the header band, caption band with CC toggle and player bar, and renders components by registry lookup. Each section is launched as its own self-contained player; there is no module tab bar. |
| `src/vtt.js` | Reads a WebVTT file into cues and finds the cue for a given time. The narration plays through a bare `Audio` object, so there is no `<track>` to read cues from. |
| `src/registry.js` | Maps component `type` to a React component. This is the only place types are wired up. |
| `src/components/Measured.jsx` | Deck-faithful renderers, used when a layout entry was measured. They draw each part at its measured frame, with its shape style and typography. |
| `src/components/*.jsx` (others) | Fallback renderers for inferred layouts: `Text`, `Content`, `Interactive`, `Quiz`. |
| `src/useNarration.js` | One hook for base audio, layer audio, pause/resume and reveal timing. |
| `src/theme.js` | Turns `layout.json` tokens into CSS variables. |
| `public/styles.css` | All styling, which reads only the token variables. |
| `scripts/package-sections.mjs` | Post-build script that emits `section-1/` and `section-2/` self-contained player folders, each carrying only its own module's JSON and assets. |

---

## Key rules in the data

**Base slides vs layers.** Storyboard 2.04 is the expanded state of 2.03 (`state_of: "2.03"`). It is not a player slide. Its five panels are `process.props.interaction.layers` on `slide_2_03` (`slide_2_03_layer_1…5`), its own metadata sits in `embeddedStates`, and each layer's narration is in `voiceover.json` under the same layer ID.

**Quiz feedback layers.** The three Storyline feedback layers per question (`try_again`, `incorrect`, `correct`) are kept with their `shownWhen`, button and `onClick` actions. The player gives 2 attempts, as the source specifies.

**Reveal cues.** `voiceover.json` holds `{order, componentId, itemIndex, lineIndex}` for each cue. A table's item 0 is the header row. Line start time = audio duration × (words before the line ÷ total words). An item whose `lineIndex` is null takes the previous cue. Without audio, everything shows at once.

**Unresolved assets are kept, not invented.** Images have `src: null`, `status: "unresolved"` and keep their purpose, search terms and candidate search URLs. Icons carry their name with status "supplied in the authored deck". Menu hotspot targets on 1.03 are `null` (`targetStatus: "unresolved"`) because the source does not name them.

**Positions are measured from the decks.** A 13.333 in deck at 96 px/in is exactly 1280 × 720, so deck coordinates map 1:1. Each layout entry carries `source`. Two things are still inferred and labelled: the open-layer panel on 2.03 (the deck shows 2.04 as a separate state, and the player draws the layer under the stage track using 2.04's chip and body styling), and the player's own audio controls inside the measured player bar.

---

## Responsive behaviour

`layout.json → responsive` holds the whole rule; the player reads it and never hard-codes a breakpoint.

```json
{ "mode": "scale-to-fit", "stackBelowPx": 900, "minScale": 0.5, "maxScale": 1.6 }
```

**Stage mode — 900 px and wider.** The 1280 × 720 canvas is scaled as one piece, so every measured frame stays exactly where the deck put it. The scale is the smaller of the width and height that are actually available: `App.jsx` measures the wrapper and the space left under it rather than subtracting a guessed toolbar height, and re-measures on resize, rotate and any layout change (`ResizeObserver`). `minScale`/`maxScale` stop a very short window from shrinking the slide to nothing and a very large one from blowing it up past legibility.

**Flow mode — below 900 px.** Below that width a scaled stage would put body text under 12 px, so frames are dropped and the slide becomes one scrolling column in `order`. Spacing comes from three variables (`--flow-pad`, `--flow-gap`, `--flow-tight`) that tighten once more under 520 px, so every slide has the same rhythm whatever it contains. Per component type:

| Type | In the column |
|---|---|
| header / player bar | Wrap to two rows; Prev and Next become equal half-width targets at least 42 px tall |
| chips + bodies | Chip full width above its body, one block per card |
| icon grids | Icon beside its label, every tile the same height, 52 px artwork |
| tables | Scroll sideways inside the column, edge to edge, with a fade on the right to say so |
| process stages | A vertical numbered list; the rail is dropped |
| quiz options / sequence slots | Full-width rows on an equal-height grid, so they stay one set however differently they wrap |
| quiz feedback | A fixed, centred modal |
| images | Keep a 16:10 shape instead of a canvas height |

**Uniform boxes.** Sibling boxes that should read as one family are the same size by construction: icon tiles are squared in `box_normalizer.py` before they reach `layout.json`, and option rows and sequence slots sit on a CSS grid with equal rows so wrapping cannot make one taller than the next. Runs of text use `min-height` rather than a fixed height, so a fallback font pushes the box down instead of spilling out of it.

**One left margin.** Every heading and every piece of content on a content slide starts at x=48. Nothing sits under the header band or the player bar: the deepest frame on any slide ends at 655 against a bar that starts at 670, and the cover logo is lifted clear of it.

`scripts/check-responsive.mjs` walks every slide at six widths and reports sideways page overflow, text clipped by its own box, anything outside the column, and sibling boxes that rendered at different sizes.

> **A caveat on text width.** The build machine has no Montserrat and cannot reach Google Fonts, so wrapping was verified against rendered screenshots from a machine that does have it, and chip widths are sized with a deliberately generous character-width estimate rather than measured metrics. Self-hosting the font under `player/public/fonts/` would remove the guesswork and make the player render identically offline.

---

## Narration

`voiceover.json` carries the whole mapping: the source `audio_manifest`'s 44 entries become 39 `slides[].base.audioFile` and 5 `slides[].layers[].audioFile`, each with the manifest's word count and its 140 wpm `approxSeconds`. The player requests `audio/<file>` for the slide it is showing, pauses the base track when an interaction layer opens and resumes it on close, and drives the footer's progress bar, pause, seek and replay from that one element.

The manifest holds filenames only — no audio — so the recordings are dropped into `player/public/audio/` separately; that folder's `README.md` lists all 44 with their slide and estimated length. Nothing else needs changing when they arrive. Until then the player shows every slide and the CC button is disabled.

**Closed captions.** The player bar has a CC toggle that defaults from `modules[].player.closed_captions`. Captions use `.vtt` files named to match their `.mp3` (e.g. `m1_1_02_base.mp3` → `m1_1_02_base.vtt`), placed in the same `player/public/audio/` folder. The player fetches and parses the VTT itself since narration runs through a bare `Audio` object with no `<track>`. When a VTT is missing or empty the CC button stays visible but disabled for that slide. Layer narration on slide 2.03 has its own VTTs and its own caption stream, which takes over the caption band while the layer is open.

Two things to know when serving it:

- **HTTP Range matters.** A static server that does not answer range requests will still play a track from the start but will not let the learner seek inside it.
- **Autoplay.** `voiceover.json → playback.autoplayBase` asks the browser to start the narration on slide load. A browser that blocks autoplay reports `blocked` and the learner presses play; nothing else is affected.

`node scripts/check-narration.mjs` checks that every slide requests the file `voiceover.json` names for it, reports which recordings are missing, and — once they are all present — that the bar advances on play, freezes on pause, seeks when clicked and returns to the start on replay.

**Knowledge checks follow the house style.** Feedback appears in the deck's verdict strip and rationale panel, not in a pop-up. The final incorrect strip names the right answer, as the deck does ("That's incorrect! The correct answer is B.").

---

## Adding a component type

1. **Generator:** emit `{id, type: "myType", props: {...}}` from a builder in `components_generator.py` (add to `BUILDERS` if it is a new storyboard layout).
2. **Layout:** add an `arrange` branch for it in `layout_generator.py` if it has inner structure, and an entry in `COMPONENT_STYLES`.
3. **Validator:** add its required props to `REQUIRED_PROPS` in `basic_validator.py`.
4. **Player:** write the React component (props: `c, arrange, frame, narr, nav`) and add one line to `src/registry.js`.

An unknown type renders a visible "Unknown component type" box instead of crashing.

---

## Section packaging

`npm run build` emits two self-contained section folders alongside the main player:

```
player/public/
  section-1/          ← module_01 only (slides 1_01–1_20)
  section-2/          ← module_02 only (slides 2_01–2_23)
```

Each folder contains its own `index.html`, `app.js`, `styles.css`, filtered `components.json`, `layout.json`, `voiceover.json`, and copies of `assets/` and `audio/`. Each opens standalone at its root URL and navigates within its own section only.

The packaging script is `scripts/package-sections.mjs`. It filters the three JSON files to keep only the entries belonging to each module, injects a hash redirect into `index.html` so the section opens at its first slide, and validates that every slide referenced by the module is present in the filtered output.

---

## V4 limits (deliberate)

- Narration timing is word-proportional, not true per-line timestamps.
- No SCORM export, LMS reporting or score tracking. SCORM settings are carried in `components.json → modules[].scorm` for a future version.
- Photos and audio are unresolved until supplied. Icons and the logo come from the decks.
- Montserrat loads from Google Fonts in the player (falls back to Calibri or Carlito offline).
