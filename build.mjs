/* Frontend build — bundles app.jsx into app.js, minifies CSS, and copies
   everything into ./dist/ for the runtime image to consume. */

import { build } from 'esbuild';
import { mkdir, copyFile, readdir, rm, writeFile, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';

const hashOf = async (file) => {
  const h = createHash('sha256');
  h.update(await readFile(file));
  return h.digest('hex').slice(0, 8);
};

const DIST = 'dist';
if (existsSync(DIST)) await rm(DIST, { recursive: true });
await mkdir(DIST, { recursive: true });

// Bundle the JS app
await build({
  entryPoints: ['app.jsx'],
  bundle: true,
  minify: true,
  format: 'esm',
  target: ['es2020'],
  jsx: 'automatic',
  loader: { '.js': 'jsx', '.jsx': 'jsx' },
  define: { 'process.env.NODE_ENV': '"production"' },
  outfile: path.join(DIST, 'app.js'),
  legalComments: 'none',
  sourcemap: false,
});

// Minify each CSS file in place into dist/
const cssFiles = ['styles.css', 'styles-components.css', 'styles-tasting.css', 'styles-cork.css', 'styles-mobile.css'];
for (const f of cssFiles) {
  await build({
    entryPoints: [f],
    bundle: false,
    minify: true,
    loader: { '.css': 'css' },
    outfile: path.join(DIST, f),
  });
}

// Compute content hashes for cache-busting query strings
const hashedAssets = ['app.js', ...cssFiles];
const hashes = {};
for (const f of hashedAssets) {
  hashes[f] = await hashOf(path.join(DIST, f));
}

// Read HTML, inject ?v=HASH on each asset reference, write to dist
let html = await readFile('Quantum Sommelier.html', 'utf8');
for (const [name, h] of Object.entries(hashes)) {
  // Match: href="<name>" or src="<name>"  (no existing query string)
  const re = new RegExp(`(href|src)="${name.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}"`, 'g');
  html = html.replace(re, `$1="${name}?v=${h}"`);
}
await writeFile(path.join(DIST, 'Quantum Sommelier.html'), html);

// Copy static assets the bundler doesn't touch
const staticAssets = ['favicon.svg'];
for (const a of staticAssets) {
  if (existsSync(a)) await copyFile(a, path.join(DIST, a));
}

// Write a robots.txt + sitemap.xml as static fallbacks (FastAPI will also serve them)
await writeFile(
  path.join(DIST, 'robots.txt'),
  'User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: https://quantum-sommelier.charlesmorris.dev/sitemap.xml\n',
);

await writeFile(
  path.join(DIST, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://quantum-sommelier.charlesmorris.dev/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
`,
);

console.log('Build complete. Files in', DIST + '/:');
for (const f of await readdir(DIST)) console.log('  ' + f);
