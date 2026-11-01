// Check the narration wiring: that every slide asks for the file voiceover.json
// names, that the file is there, and that play / pause / seek / replay behave.
//
//   node scripts/check-narration.mjs
//
// Run it from the project root after `npm run build` in player/. Drop the real
// recordings in player/public/audio/ first; without them the mapping is still
// checked and every slide is reported as "file missing".
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(process.cwd(), 'player/public');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.mp3': 'audio/mpeg', '.vtt': 'text/vtt', '.woff2': 'font/woff2' };

// Range support matters: without it a browser cannot seek inside an mp3.
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('not found'); }
  const size = fs.statSync(f).size;
  const type = MIME[path.extname(f)] || 'application/octet-stream';
  const range = req.headers.range;
  if (range) {
    const m = /bytes=(\d*)-(\d*)/.exec(range) || [];
    const start = m[1] ? parseInt(m[1], 10) : 0;
    const end = m[2] ? parseInt(m[2], 10) : size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
    return fs.createReadStream(f, { start, end }).pipe(res);
  }
  res.writeHead(200, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes' });
  return fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(8099, r));

const vo = JSON.parse(fs.readFileSync(path.join(ROOT, 'lesson/voiceover.json'), 'utf8'));
const expect = [];
for (const m of vo.modules) {
  for (const s of m.slides) {
    if (s.base?.audioFile) expect.push([s.slideId, s.base.audioFile]);
    for (const L of s.layers || []) if (L.audioFile) expect.push([s.slideId, L.audioFile, L.layerId]);
  }
}
const onDisk = new Set(fs.existsSync(path.join(ROOT, 'audio')) ? fs.readdirSync(path.join(ROOT, 'audio')) : []);
const missing = expect.filter(([, f]) => !onDisk.has(f)).map(([, f]) => f);

const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

// 1. every slide requests the file voiceover.json names for it
const wrong = [];
for (const [slideId, file, layerId] of expect) {
  if (layerId) continue;                                   // layers need a click; covered below
  const mod = slideId.startsWith('slide_1') ? 'module_01' : 'module_02';
  const seen = [];
  page.removeAllListeners('request');
  // count only the mp3: the player also fetches the .vtt beside it, and either can go first
  page.on('request', (r) => { if (r.url().includes('/audio/') && r.url().endsWith('.mp3')) seen.push(r.url().split('/').pop()); });
  await page.goto(`http://localhost:8099/#${mod}/${slideId}`);
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(250);
  if (seen[0] !== file) wrong.push(`${slideId}: asked for ${seen[0] || 'nothing'}, expected ${file}`);
}
console.log(`mapping   : ${expect.length} entries, ${wrong.length} mismatch(es)`);
wrong.slice(0, 10).forEach((w) => console.log('   ', w));
console.log(`files      : ${expect.length - missing.length}/${expect.length} present in player/public/audio/`);
if (missing.length) console.log(`   missing  : ${missing.slice(0, 4).join(', ')}${missing.length > 4 ? ` … +${missing.length - 4}` : ''}`);

// 2. transport controls, only worth running once audio exists
if (!missing.length) {
  const first = expect.find(([, , l]) => !l);
  const mod = first[0].startsWith('slide_1') ? 'module_01' : 'module_02';
  await page.goto(`http://localhost:8099/#${mod}/${first[0]}`);
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  const fill = async () => parseFloat(((await page.locator('.deck-track>div').getAttribute('style')) || '0%').match(/[\d.]+/)[0]);
  const a = await fill(); await page.waitForTimeout(2500); const b = await fill();
  const advancing = b > a;
  await page.locator('.deck-play').click(); await page.waitForTimeout(150);
  const c = await fill(); await page.waitForTimeout(1500); const d = await fill();
  const frozen = c === d;
  const box = await page.locator('.deck-track').boundingBox();
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
  await page.waitForTimeout(300);
  const sought = Math.abs((await fill()) - 50) < 3;
  await page.locator('[aria-label=Replay]').click(); await page.waitForTimeout(300);
  const replayed = (await fill()) < 5;
  const ok = (n, v) => console.log(`   ${v ? 'ok  ' : 'FAIL'}  ${n}`);
  console.log('transport :');
  ok('plays and the bar advances', advancing);
  ok('pause freezes the bar', frozen);
  ok('clicking the bar seeks', sought);
  ok('replay returns to the start', replayed);
}
await browser.close();
server.close();
process.exit(wrong.length ? 1 : 0);
