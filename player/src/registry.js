// Component registry: components.json `type` -> React component.
// To add a type: write the component, add one line here, add a builder in
// src/generators/components_generator.py and (optionally) a default in layout_generator.py.
import { Heading, Paragraph, Instruction } from './components/Text.jsx';
import {
  Image, Callout, BulletList, ObjectivesList, IconGrid, CardGrid, Definition,
  Comparison, DataTable, Summary, References, Results,
} from './components/Content.jsx';
import { Process } from './components/Interactive.jsx';
import { MultipleChoice, TrueFalse, MultiSelect, Matching, Sequence } from './components/Quiz.jsx';

export const registry = {
  heading: Heading,
  paragraph: Paragraph,
  instruction: Instruction,
  image: Image,
  callout: Callout,
  bulletList: BulletList,
  objectivesList: ObjectivesList,
  iconGrid: IconGrid,
  cardGrid: CardGrid,
  definition: Definition,
  comparison: Comparison,
  table: DataTable,
  summary: Summary,
  references: References,
  results: Results,
  process: Process,
  multipleChoice: MultipleChoice,
  trueFalse: TrueFalse,
  multiSelect: MultiSelect,
  matching: Matching,
  sequence: Sequence,
};

// Deck-faithful renderers, used when the layout entry was measured from an authored deck.
import {
  MText, MImage, MCallout, MCards, MIcons, MList, MTable, MProcess, MMultipleChoice, MSequence,
} from './components/Measured.jsx';

export const measuredRegistry = {
  heading: MText, paragraph: MText, instruction: MText,
  image: MImage, callout: MCallout,
  cardGrid: MCards, comparison: MCards, iconGrid: MIcons,
  definition: MList, bulletList: MList, objectivesList: MList, summary: MList, references: MList, results: MList,
  table: MTable, process: MProcess,
  multipleChoice: MMultipleChoice, trueFalse: MMultipleChoice, multiSelect: MMultipleChoice,
  matching: MMultipleChoice, sequence: MSequence,
};
