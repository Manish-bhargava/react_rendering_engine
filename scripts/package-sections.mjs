// Write one self-contained player per section.
//
//   node scripts/package-sections.mjs            (run after `npm run build` in player/)
//
// Each section is its own module and is launched on its own, so each gets a complete
// copy of the player carrying only its own module: app.js, index.html, styles.css, the
// brand and icon assets, the audio folder, and the three lesson files filtered to that
// module. The three files keep their existing structure — `modules` still holds a list,
// it just holds one entry — so the same player code reads them unchanged.
//
// player/public/ itself is left as it is: a build holding both sections, which opens at
// whichever one the URL hash names.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// resolved from this file, so it works from the project root or from player/
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PUBLIC = path.join(ROOT, 'player/public');
const LESSON = path.join(PUBLIC, 'lesson');

const read = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const components = read(path.join(LESSON, 'components.json'));
const layout = read(path.join(LESSON, 'layout.json'));
const voiceover = read(path.join(LESSON, 'voiceover.json'));

const slug = (m, i) => `section-${m.number ?? i + 1}`;

// everything a player needs, minus the per-section lesson files and the sections themselves
const SHARED = ['index.html', 'app.js', 'styles.css', 'assets', 'audio'];

let made = 0;
components.modules.forEach((mod, i) => {
  const dir = path.join(PUBLIC, slug(mod, i));
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(path.join(dir, 'lesson'), { recursive: true });

  for (const name of SHARED) {
    const from = path.join(PUBLIC, name);
    if (fs.existsSync(from)) fs.cpSync(from, path.join(dir, name), { recursive: true });
  }

  const ids = new Set(mod.slides.map((s) => s.slideId));
  const write = (name, doc) => fs.writeFileSync(path.join(dir, 'lesson', name), `${JSON.stringify(doc, null, 2)}\n`);

  write('components.json', { ...components, modules: [mod] });
  write('layout.json', { ...layout, slides: layout.slides.filter((s) => ids.has(s.slideId)) });
  write('voiceover.json', {
    ...voiceover,
    manifestEntries: voiceover.modules
      .filter((m) => m.moduleId === mod.moduleId)
      .reduce((n, m) => n + m.slides.reduce((k, s) => k + (s.base?.audioFile ? 1 : 0)
        + (s.layers || []).filter((L) => L.audioFile).length, 0), 0),
    modules: voiceover.modules.filter((m) => m.moduleId === mod.moduleId),
  });

  // open on this section's first slide without needing a hash
  const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8')
    .replace('<div id="root"></div>',
      `<div id="root"></div>\n  <script>if(!location.hash)location.replace('#${mod.moduleId}/${mod.slides[0].slideId}');</script>`);
  fs.writeFileSync(path.join(dir, 'index.html'), html);

  // the filtered files must still be shaped like the originals
  const out = read(path.join(dir, 'lesson', 'components.json'));
  if (out.modules.length !== 1 || out.modules[0].slides.length !== mod.slides.length
      || read(path.join(dir, 'lesson', 'layout.json')).slides.length !== mod.slides.length) {
    throw new Error(`${slug(mod, i)}: filtered lesson files do not match the module`);
  }

  const audio = fs.existsSync(path.join(dir, 'audio')) ? fs.readdirSync(path.join(dir, 'audio')).filter((f) => f.endsWith('.mp3')).length : 0;
  console.log(`${slug(mod, i).padEnd(10)} ${String(mod.slides.length).padStart(2)} slides  ${audio} audio files  ->  player/public/${slug(mod, i)}/`);
  made += 1;
});
console.log(`${made} self-contained section player(s) written.`);
