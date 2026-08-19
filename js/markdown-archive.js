const MAX_BUNDLED_ASSET_BYTES = 512 * 1024 * 1024;
const ZIP_STORE_LIMIT = 0xffffffff;
const textEncoder = new TextEncoder();

const relationLabels = {
  reference: 'Odkaz na zdroj',
  citation: 'Citácia',
  quote: 'Citát',
  annotation: 'Anotácia'
};

const crc32Table = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < table.length; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    table[index] = value >>> 0;
  }
  return table;
})();

function safeFilename(value, fallback) {
  const normalized = String(value || fallback)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
  return normalized.slice(0, 160) || fallback;
}

function extensionForMimeType(mimeType) {
  const extensions = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'text/markdown': '.md'
  };
  return extensions[String(mimeType || '').toLowerCase()] || '';
}

function dataUrlBlob(value) {
  const match = String(value || '').match(/^data:([^;,]+)?(?:;charset=[^;,]+)?(;base64)?,([\s\S]*)$/i);
  if (!match) return null;
  try {
    if (match[2]) {
      const binary = atob(match[3]);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      return new Blob([bytes], { type: match[1] || 'application/octet-stream' });
    }
    return new Blob([decodeURIComponent(match[3])], { type: match[1] || 'application/octet-stream' });
  } catch {
    return null;
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function writeUint16(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
}

function writeUint32(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  target[offset + 2] = (value >>> 16) & 0xff;
  target[offset + 3] = (value >>> 24) & 0xff;
}

function dosTimestamp(date) {
  const safeYear = Math.max(1980, Math.min(2107, date.getFullYear()));
  return {
    date: ((safeYear - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    time: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2)
  };
}

async function crc32(blob) {
  let checksum = 0xffffffff;
  const reader = blob.stream().getReader();
  try {
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      result.value.forEach((byte) => {
        checksum = crc32Table[(checksum ^ byte) & 0xff] ^ (checksum >>> 8);
      });
    }
  } finally {
    reader.releaseLock();
  }
  return (checksum ^ 0xffffffff) >>> 0;
}

async function createStoredZip(files) {
  const entries = [];
  const dataParts = [];
  const centralParts = [];
  const timestamp = dosTimestamp(new Date());
  let offset = 0;

  for (const file of files) {
    const name = String(file.name || 'subor').replace(/^\/+/, '');
    const nameBytes = textEncoder.encode(name);
    const blob = file.blob instanceof Blob ? file.blob : new Blob([file.blob]);
    if (blob.size > ZIP_STORE_LIMIT || nameBytes.length > 0xffff || offset + 30 + nameBytes.length + blob.size > ZIP_STORE_LIMIT) {
      throw new Error('Export s prílohami je príliš veľký pre prenosný ZIP súbor.');
    }
    const checksum = await crc32(blob);
    const header = new Uint8Array(30 + nameBytes.length);
    writeUint32(header, 0, 0x04034b50);
    writeUint16(header, 4, 20);
    writeUint16(header, 6, 0x0800);
    writeUint16(header, 8, 0);
    writeUint16(header, 10, timestamp.time);
    writeUint16(header, 12, timestamp.date);
    writeUint32(header, 14, checksum);
    writeUint32(header, 18, blob.size);
    writeUint32(header, 22, blob.size);
    writeUint16(header, 26, nameBytes.length);
    writeUint16(header, 28, 0);
    header.set(nameBytes, 30);
    entries.push({ nameBytes, blob, checksum, offset });
    dataParts.push(header, blob);
    offset += header.length + blob.size;
  }

  let centralSize = 0;
  entries.forEach((entry) => {
    const header = new Uint8Array(46 + entry.nameBytes.length);
    writeUint32(header, 0, 0x02014b50);
    writeUint16(header, 4, 20);
    writeUint16(header, 6, 20);
    writeUint16(header, 8, 0x0800);
    writeUint16(header, 10, 0);
    writeUint16(header, 12, timestamp.time);
    writeUint16(header, 14, timestamp.date);
    writeUint32(header, 16, entry.checksum);
    writeUint32(header, 20, entry.blob.size);
    writeUint32(header, 24, entry.blob.size);
    writeUint16(header, 28, entry.nameBytes.length);
    writeUint16(header, 30, 0);
    writeUint16(header, 32, 0);
    writeUint16(header, 34, 0);
    writeUint16(header, 36, 0);
    writeUint32(header, 38, 0);
    writeUint32(header, 42, entry.offset);
    header.set(entry.nameBytes, 46);
    centralParts.push(header);
    centralSize += header.length;
  });
  if (entries.length > 0xffff || offset + centralSize > ZIP_STORE_LIMIT) {
    throw new Error('Export obsahuje príliš veľa údajov pre prenosný ZIP súbor.');
  }
  const end = new Uint8Array(22);
  writeUint32(end, 0, 0x06054b50);
  writeUint16(end, 4, 0);
  writeUint16(end, 6, 0);
  writeUint16(end, 8, entries.length);
  writeUint16(end, 10, entries.length);
  writeUint32(end, 12, centralSize);
  writeUint32(end, 16, offset);
  writeUint16(end, 20, 0);
  return new Blob([...dataParts, ...centralParts, end], { type: 'application/zip' });
}

function sourceUrl(source) {
  const metadata = source && typeof source.metadata === 'object' ? source.metadata : {};
  const direct = String(metadata.url || '').trim();
  if (direct) return direct;
  const doi = String(metadata.doi || '').trim();
  if (doi) return doi.startsWith('http') ? doi : 'https://doi.org/' + doi;
  return '';
}

function sourceDescription(source) {
  const title = String(source.title || 'Zdroj');
  const kind = String(source.kind || '').trim();
  const url = sourceUrl(source);
  const label = url ? '[' + title + '](' + url + ')' : title;
  return '- ' + label + (kind ? ' (' + kind + ')' : '');
}

function sourceContext(source) {
  const contexts = Array.isArray(source.exportContexts) ? source.exportContexts : [];
  if (contexts.length) return contexts.join('; ');
  return [
    relationLabels[source.relationType] || source.relationType,
    source.locator,
    source.sourceFileName,
    source.note
  ].filter(Boolean).join(' · ');
}

function uniqueSources(sources) {
  const sourceMap = new Map();
  sources.filter(Boolean).forEach((source) => {
    const key = String(source.id || source.title || source.locator || Math.random());
    const context = [
      relationLabels[source.relationType] || source.relationType,
      source.locator,
      source.sourceFileName,
      source.note
    ].filter(Boolean).join(' · ');
    const current = sourceMap.get(key);
    if (!current) {
      sourceMap.set(key, { ...source, exportContexts: context ? [context] : [] });
      return;
    }
    if (context && !current.exportContexts.includes(context)) current.exportContexts.push(context);
  });
  return [...sourceMap.values()];
}

export function createAssetCollector() {
  const assets = [];
  const usedNames = new Set();
  const pathsByKey = new Map();
  return {
    add(blob, name, key = '') {
      if (!(blob instanceof Blob) || !blob.size) return '';
      const normalizedKey = String(key || '');
      if (normalizedKey && pathsByKey.has(normalizedKey)) return pathsByKey.get(normalizedKey);
      const extension = extensionForMimeType(blob.type);
      const baseName = safeFilename(name, 'priloha' + extension);
      const fullName = /\.[a-z0-9]{1,12}$/i.test(baseName) || !extension ? baseName : baseName + extension;
      const stem = fullName.replace(/(\.[^.]+)?$/, '');
      const suffix = fullName.match(/(\.[^.]+)$/)?.[1] || '';
      let candidate = fullName;
      let index = 2;
      while (usedNames.has(candidate.toLowerCase())) {
        candidate = stem + '-' + index + suffix;
        index += 1;
      }
      usedNames.add(candidate.toLowerCase());
      const path = 'assets/' + candidate;
      assets.push({ name: path, blob });
      if (normalizedKey) pathsByKey.set(normalizedKey, path);
      return path;
    },
    pathForKey(key) {
      return pathsByKey.get(String(key || '')) || '';
    },
    values() {
      return assets;
    },
    totalBytes() {
      return assets.reduce((sum, asset) => sum + asset.blob.size, 0);
    }
  };
}

export function extractEmbeddedAssets(html, collector) {
  const document = new DOMParser().parseFromString(String(html || ''), 'text/html');
  document.querySelectorAll('img[src^="data:"], a[href^="data:"]').forEach((node, index) => {
    const attribute = node.tagName.toLowerCase() === 'img' ? 'src' : 'href';
    const blob = dataUrlBlob(node.getAttribute(attribute));
    const hint = node.getAttribute('alt') || node.getAttribute('title') || node.textContent || 'vlozena-priloha-' + (index + 1);
    const path = blob ? collector.add(blob, hint) : '';
    if (path) node.setAttribute(attribute, path);
  });
  return document.body.innerHTML;
}

async function fetchSourceDetails(sources, { preserveLinks = false } = {}) {
  const items = preserveLinks ? (Array.isArray(sources) ? sources : []) : uniqueSources(sources);
  return Promise.all(items.map(async (source) => {
    if (!source.id) return source;
    try {
      const response = await fetch('/api/sources/' + encodeURIComponent(source.id), { credentials: 'same-origin' });
      if (!response.ok) return source;
      const payload = await response.json();
      return { ...source, ...payload.source, files: payload.source && Array.isArray(payload.source.files) ? payload.source.files : [] };
    } catch {
      return source;
    }
  }));
}

export async function loadElementSources(elementId, { preserveLinks = false } = {}) {
  if (!elementId) return [];
  try {
    const response = await fetch('/api/elements/' + encodeURIComponent(elementId) + '/sources', { credentials: 'same-origin' });
    if (!response.ok) return [];
    const payload = await response.json();
    return fetchSourceDetails(Array.isArray(payload.sources) ? payload.sources : [], { preserveLinks });
  } catch {
    return [];
  }
}

export async function loadLibrarySources(libraryId) {
  if (!libraryId) return [];
  try {
    const response = await fetch('/api/libraries/' + encodeURIComponent(libraryId) + '/sources', { credentials: 'same-origin' });
    if (!response.ok) return [];
    const payload = await response.json();
    return fetchSourceDetails(Array.isArray(payload.sources) ? payload.sources : []);
  } catch {
    return [];
  }
}

export async function loadTaskSources(links) {
  const sourceLinks = (Array.isArray(links) ? links : [])
    .filter((link) => link && link.targetType === 'source')
    .map((link) => ({ id: link.targetId, title: link.title, kind: link.subtitle || 'source' }));
  return fetchSourceDetails(sourceLinks);
}

export async function addSourceAssets(sources, collector) {
  const missing = [];
  const skipped = [];
  for (const source of sources) {
    for (const file of Array.isArray(source.files) ? source.files : []) {
      const assetKey = file.id ? 'source-file:' + file.id : '';
      const existingPath = collector.pathForKey(assetKey);
      if (existingPath) {
        file.exportPath = existingPath;
        continue;
      }
      const declaredSize = Number(file.sizeBytes);
      if (Number.isFinite(declaredSize) && declaredSize > 0 && collector.totalBytes() + declaredSize > MAX_BUNDLED_ASSET_BYTES) {
        skipped.push(file.originalName || 'príloha');
        continue;
      }
      try {
        const response = await fetch('/api/files/' + encodeURIComponent(file.id) + '?download=1', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Súbor nie je dostupný.');
        const path = collector.add(await response.blob(), file.originalName, assetKey);
        if (!path) missing.push(file.originalName || 'príloha');
        else file.exportPath = path;
      } catch {
        missing.push(file.originalName || 'príloha');
      }
    }
  }
  return { missing, skipped };
}

export function sourceMarkdown(sources) {
  const unique = uniqueSources(sources);
  if (!unique.length) return '';
  const rows = unique.map((source) => {
    const context = sourceContext(source);
    const files = (Array.isArray(source.files) ? source.files : []).map((file) => {
      const label = String(file.originalName || 'príloha');
      return '  - Súbor: ' + (file.exportPath ? '[' + label + '](' + file.exportPath + ')' : label);
    });
    const contextLine = context ? '> ' + context : '';
    return [sourceDescription(source), contextLine, ...files].filter(Boolean).join('\n');
  });
  return '## Zdroje\n\n' + rows.join('\n');
}

export function rebaseAssetLinks(markdown, documentPath = '') {
  const directoryParts = String(documentPath || '').split('/').slice(0, -1).filter(Boolean);
  if (!directoryParts.length) return String(markdown || '');
  const prefix = '../'.repeat(directoryParts.length);
  return String(markdown || '').replace(/\]\(assets\//g, `](${prefix}assets/`);
}

export async function downloadMarkdownArchive(archiveFilename, files, collector, assetStatus) {
  const status = assetStatus || { missing: [], skipped: [] };
  const markdownFiles = (Array.isArray(files) ? files : []).map((file) => ({
    name: String(file?.name || 'README.md').replace(/^\/+/, ''),
    blob: file?.blob instanceof Blob ? file.blob : new Blob([String(file?.content || '')], { type: 'text/markdown;charset=utf-8' })
  }));
  const assets = collector?.values?.() || [];
  const totalSize = assets.reduce((sum, asset) => sum + asset.blob.size, 0);
  if (totalSize > MAX_BUNDLED_ASSET_BYTES) {
    throw new Error('Prílohy exportu presahujú 512 MB. Export celej štruktúry sa nevytvoril.');
  }
  const names = new Set();
  for (const file of [...markdownFiles, ...assets]) {
    const key = file.name.toLocaleLowerCase('sk');
    if (names.has(key)) throw new Error('Export obsahuje dve položky s rovnakým názvom: ' + file.name);
    names.add(key);
  }
  const archive = await createStoredZip([...markdownFiles, ...assets]);
  const safeName = safeFilename(archiveFilename, 'poznamkovnik-export.zip').replace(/\.zip$/i, '') + '.zip';
  downloadBlob(archive, safeName);
  return { bundled: true, missingFiles: status.missing || [], skippedFiles: status.skipped || [] };
}

export async function downloadMarkdownBundle(markdownFilename, markdown, collector, assetStatus) {
  const status = assetStatus || { missing: [], skipped: [] };
  const assets = collector.values();
  if (!assets.length) {
    downloadBlob(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), markdownFilename);
    return { bundled: false, missingFiles: status.missing, skippedFiles: status.skipped };
  }
  const totalSize = assets.reduce((sum, asset) => sum + asset.blob.size, 0);
  if (totalSize > MAX_BUNDLED_ASSET_BYTES) {
    downloadBlob(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), markdownFilename);
    return { bundled: false, tooLarge: true, missingFiles: status.missing, skippedFiles: status.skipped };
  }
  const archive = await createStoredZip([
    { name: markdownFilename, blob: new Blob([markdown], { type: 'text/markdown;charset=utf-8' }) },
    ...assets
  ]);
  const zipName = markdownFilename.replace(/\.md$/i, '') + '-export.zip';
  downloadBlob(archive, zipName);
  return { bundled: true, missingFiles: status.missing, skippedFiles: status.skipped };
}
