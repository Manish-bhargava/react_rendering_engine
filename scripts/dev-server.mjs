// Dev server: serves player/public/ for static assets, but routes /lesson/*.json
// directly from output/ so the player always loads the latest generated JSON.
// No sync step needed — run the Python pipeline, refresh the browser.

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const root      = join(__dirname, '..');
const publicDir = join(root, 'player', 'public');
const outputDir = join(root, 'output');

// ── 1. Bundle the React player ──────────────────────────────────────
console.log('Building player bundle …');
try {
  execSync(
    'npx esbuild player/src/main.jsx --bundle --jsx=automatic --loader:.js=jsx --outfile=player/public/app.js',
    { cwd: root, stdio: 'inherit' }
  );
} catch (e) {
  console.error('esbuild failed:', e.message);
  process.exit(1);
}

// ── 2. MIME map ─────────────────────────────────────────────────────
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg':  'image/svg+xml',
  '.mp3':  'audio/mpeg',
  '.ogg':  'audio/ogg',
  '.wav':  'audio/wav',
  '.vtt':  'text/vtt; charset=utf-8',
  '.woff2':'font/woff2',
  '.woff': 'font/woff',
};

// ── 3. Static file server ───────────────────────────────────────────
const server = createServer(async (req, res) => {
  let url = req.url.split('?')[0].split('#')[0];
  if (url === '/') url = '/index.html';

  let filePath;

  if (url.startsWith('/lesson/')) {
    // Serve lesson JSON live from output/ — no copy needed
    const file = url.slice('/lesson/'.length);
    filePath = join(outputDir, file);
  } else if (url.startsWith('/assets/')) {
    // Check output/assets first, then fall back to public/assets
    const fromOutput = join(outputDir, url.slice(1));
    try {
      const data = await readFile(fromOutput);
      const ext = extname(fromOutput);
      res.writeHead(200, {
        'Content-Type': MIME[ext] || 'application/octet-stream',
        'Cache-Control': 'no-cache',
      });
      res.end(data);
      return;
    } catch {
      filePath = join(publicDir, url);
    }
  } else {
    filePath = join(publicDir, url);
  }

  try {
    const data = await readFile(filePath);
    const ext = extname(filePath);
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end(`404 Not Found: ${url}`);
  }
});

// ── 4. Start ────────────────────────────────────────────────────────
const PORT = parseInt(process.env.PORT, 10) || 5173;
server.listen(PORT, () => {
  console.log('');
  console.log(`  Lesson Player running at  http://localhost:${PORT}`);
  console.log(`  JSON served live from:    ${outputDir}`);
  console.log(`  Static files from:        ${publicDir}`);
  console.log('');
  console.log('  Re-run the Python pipeline and refresh the browser — no sync needed.');
  console.log('');
});
