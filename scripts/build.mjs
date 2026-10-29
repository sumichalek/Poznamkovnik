import { readFile, writeFile } from 'node:fs/promises';
import { build } from 'esbuild';

const version = (await readFile(new URL('../VERSION', import.meta.url), 'utf8')).trim();
if (!/^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(version)) throw new Error('Neplatný súbor VERSION.');
await build({
  entryPoints: ['js/main.js'], bundle: true, format: 'esm', target: 'es2022', minify: true,
  loader: { '.woff2': 'file', '.woff': 'file', '.ttf': 'file' }, outfile: 'assets/app.js',
  define: { __APP_VERSION__: JSON.stringify(version) }, logLevel: 'info',
});
const indexPath = new URL('../index.html', import.meta.url);
const html = await readFile(indexPath, 'utf8');
const updated = html
  .replace(/data-app-version="[^"]*"/, `data-app-version="${version}"`)
  .replace(/(<p id="app-version" class="app-version">)Verzia [^<]*/, `$1Verzia ${version}`)
  .replace(/((?:style\.css|assets\/app\.(?:css|js))\?v=)[^"\s]+/g, `$1${version}`);
if (updated !== html) await writeFile(indexPath, updated);
