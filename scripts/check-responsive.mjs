// Walk every slide at several widths and report layout faults:
// horizontal page overflow, elements outside the stage, clipped text, and
// sibling boxes of the same role whose rendered size differs.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

// run from the project root:  node scripts/check-responsive.mjs [1440x900,390x844]
const ROOT = path.resolve(process.cwd(), 'player/public');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p === '/') p = '/index.html';
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('no'); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(8099, r));

const lesson = JSON.parse(fs.readFileSync(path.join(ROOT, 'lesson/components.json'), 'utf8'));
const slides = lesson.modules.flatMap((m) => m.slides.map((s) => [m.moduleId, s.slideId]));
const sizes = (process.argv[2] || '1920x1080,1440x900,1180x820,900x700,768x1024,390x844').split(',').map((s) => s.split('x').map(Number));

const browser = await chromium.launch();
const faults = [];
for (const [w, h] of sizes) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on('pageerror', (e) => faults.push(`${w} JS ${String(e).slice(0, 120)}`));
  for (const [mod, s] of slides) {
    await page.goto(`http://localhost:8099/#${mod}/${s}`);
    await page.reload({ waitUntil: 'networkidle' });
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const bad = await page.evaluate(() => {
      const out = [];
      const doc = document.documentElement;
      if (doc.scrollWidth > doc.clientWidth + 1) out.push(`page scrolls sideways by ${doc.scrollWidth - doc.clientWidth}px`);
      const stage = document.querySelector('.stage');
      if (!stage) return ['no stage'];
      const flow = stage.classList.contains('stacked');
      const sr = stage.getBoundingClientRect();
      // text clipped by its own box
      for (const el of stage.querySelectorAll('.m-box, .m-text, .m-option, .m-seq, .m-layer, td, th')) {
        if (el.scrollHeight > el.clientHeight + 2 && getComputedStyle(el).overflow !== 'auto') {
          const t = (el.textContent || '').trim().slice(0, 32);
          out.push(`clipped vertically (+${el.scrollHeight - el.clientHeight}px): "${t}"`);
        }
      }
      // in flow mode nothing may stick out of the column
      if (flow) {
        for (const el of stage.querySelectorAll('.c, .m-box, .m-text, .m-table-wrap')) {
          const r = el.getBoundingClientRect();
          if (r.width === 0) continue;
          // tables bleed to the stage edge on purpose so they can scroll sideways
          if (el.closest('.m-table-wrap')) continue;
          if (r.right > sr.right + 2 || r.left < sr.left - 2) {
            out.push(`outside column: "${(el.textContent || '').trim().slice(0, 28)}" [${Math.round(r.left - sr.left)}..${Math.round(r.right - sr.right)}]`);
          }
        }
      }
      // sibling boxes of one role should render the same size
      const groups = {};
      for (const el of stage.querySelectorAll('.m-chip, .m-seq, .m-option, .m-icon-item img, .m-badge')) {
        const key = el.className.toString().split(' ').filter((c) => c.startsWith('m-')).join('.');
        const r = el.getBoundingClientRect();
        (groups[key] ||= []).push([Math.round(r.width), Math.round(r.height)]);
      }
      for (const [k, list] of Object.entries(groups)) {
        if (list.length < 2) continue;
        const ws = new Set(list.map((x) => x[0]));
        const hs = new Set(list.map((x) => x[1]));
        if (ws.size > 1 || hs.size > 1) out.push(`uneven ${k}: w=${[...ws]} h=${[...hs]}`);
      }
      return out;
    });
    for (const b of bad) faults.push(`${w}  ${s}  ${b}`);
  }
  await page.close();
}
await browser.close(); server.close();
const uniq = [...new Set(faults)];
console.log(uniq.length ? uniq.join('\n') : 'no faults');
console.log('---', uniq.length, 'fault lines');
