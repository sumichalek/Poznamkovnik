import { dom } from './dom.js';
import { fitDialogResizableSection, installDialogBackdropClose } from './dialogs.js';
import { apiRequest } from './api.js';

const MAX_ARCHIVE_BYTES = 50 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES = 1_000;
const MAX_MARKDOWN_BYTES = 2 * 1024 * 1024;
const MAX_EMBEDDED_FILE_BYTES = 1_500_000;
const MAX_EMBEDDED_TOTAL_BYTES = 20 * 1024 * 1024;
const MAX_DOCUMENT_CONTENT_LENGTH = 4_500_000;
const MAX_EXPORT_MANIFEST_BYTES = 2 * 1024 * 1024;
const MAX_LIBRARY_PACKAGE_MANIFEST_BYTES = 20 * 1024 * 1024;
const libraryPackageManifestPath = '.poznamkovnik-library.json';
const taskPackageManifestPath = '.poznamkovnik-task.json';
const markdownExtensions = new Set(['md', 'markdown', 'mdown', 'mkdn']);

let pendingImport = null;
let importTarget = null;

function extensionFor(path) {
  const name = String(path || '').split('/').at(-1) || '';
  return name.includes('.') ? name.split('.').at(-1).toLocaleLowerCase('sk') : '';
}

function isMarkdownPath(path) {
  return markdownExtensions.has(extensionFor(path));
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function mimeForPath(path) {
  const mimeTypes = {
    pdf: 'application/pdf',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    gif: 'image/gif',
    webp: 'image/webp',
    svg: 'image/svg+xml',
    txt: 'text/plain',
    csv: 'text/csv',
    json: 'application/json',
    mp3: 'audio/mpeg',
    mp4: 'video/mp4'
  };
  return mimeTypes[extensionFor(path)] || 'application/octet-stream';
}

function normalizeArchivePath(value) {
  const parts = String(value || '').replace(/\\/g, '/').split('/');
  const normalized = [];
  for (const part of parts) {
    if (!part || part === '.') continue;
    if (part === '..' || part.includes('\0')) return '';
    normalized.push(part);
  }
  const path = normalized.join('/');
  return path.length <= 320 ? path : '';
}

function findEndOfCentralDirectory(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let offset = bytes.byteLength - 22; offset >= Math.max(0, bytes.byteLength - 65_557); offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) return offset;
  }
  return -1;
}

async function inflateDeflateRaw(bytes) {
  if (typeof DecompressionStream !== 'function') {
    throw new Error('Tento prehliadač nevie bezpečne rozbaliť komprimovaný ZIP. Použi ZIP bez kompresie alebo novší prehliadač.');
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function readZipEntries(file) {
  if (file.size > MAX_ARCHIVE_BYTES) throw new Error('ZIP môže mať najviac 50 MB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const endOffset = findEndOfCentralDirectory(bytes);
  if (endOffset === -1) throw new Error('Súbor nie je platný ZIP archív.');
  const entriesCount = view.getUint16(endOffset + 10, true);
  const directorySize = view.getUint32(endOffset + 12, true);
  const directoryOffset = view.getUint32(endOffset + 16, true);
  if (entriesCount > MAX_ARCHIVE_ENTRIES) throw new Error('ZIP obsahuje príliš veľa položiek.');
  if (directoryOffset + directorySize > bytes.byteLength) throw new Error('ZIP má neplatný centrálny adresár.');

  const decoder = new TextDecoder('utf-8', { fatal: false });
  const entries = [];
  const names = new Set();
  let offset = directoryOffset;
  let totalUncompressed = 0;
  for (let index = 0; index < entriesCount; index += 1) {
    if (offset + 46 > bytes.byteLength || view.getUint32(offset, true) !== 0x02014b50) {
      throw new Error('ZIP má neplatnú položku.');
    }
    const flags = view.getUint16(offset + 8, true);
    const compression = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const uncompressedSize = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    const nextOffset = offset + 46 + nameLength + extraLength + commentLength;
    if (nextOffset > bytes.byteLength || flags & 1 || compressedSize === 0xffffffff || uncompressedSize === 0xffffffff) {
      throw new Error('ZIP používa nepodporovaný alebo šifrovaný formát.');
    }
    const path = normalizeArchivePath(decoder.decode(bytes.slice(offset + 46, offset + 46 + nameLength)));
    offset = nextOffset;
    if (!path || path.startsWith('__MACOSX/') || path.endsWith('.DS_Store')) continue;
    const lowered = path.toLocaleLowerCase('sk');
    if (names.has(lowered)) throw new Error('ZIP obsahuje dve položky s rovnakou cestou.');
    names.add(lowered);
    if (uncompressedSize > MAX_ARCHIVE_BYTES || totalUncompressed + uncompressedSize > MAX_ARCHIVE_BYTES) {
      throw new Error('Rozbalený ZIP by bol príliš veľký.');
    }
    totalUncompressed += uncompressedSize;
    if (path.endsWith('/')) continue;
    if (localOffset + 30 > bytes.byteLength || view.getUint32(localOffset, true) !== 0x04034b50) {
      throw new Error('ZIP odkazuje na neplatný súbor.');
    }
    const localNameLength = view.getUint16(localOffset + 26, true);
    const localExtraLength = view.getUint16(localOffset + 28, true);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const dataEnd = dataStart + compressedSize;
    if (dataEnd > bytes.byteLength) throw new Error('ZIP obsahuje neúplný súbor.');
    const compressed = bytes.slice(dataStart, dataEnd);
    let content;
    if (compression === 0) content = compressed;
    else if (compression === 8) content = await inflateDeflateRaw(compressed);
    else throw new Error('ZIP používa nepodporovaný spôsob kompresie.');
    if (content.byteLength !== uncompressedSize) throw new Error('ZIP obsahuje neplatne rozbalený súbor.');
    entries.push({ path, blob: new Blob([content], { type: mimeForPath(path) }) });
  }
  return entries;
}

export async function readImportEntries(file) {
  const filename = String(file?.name || 'import.md');
  if (extensionFor(filename) === 'zip') return readZipEntries(file);
  if (!isMarkdownPath(filename)) throw new Error('Vyber Markdown súbor alebo ZIP archív.');
  if (file.size > MAX_MARKDOWN_BYTES) throw new Error('Markdown súbor môže mať najviac 2 MB.');
  return [{ path: normalizeArchivePath(filename) || 'import.md', blob: file.slice(0, file.size, 'text/markdown') }];
}

function parseScalar(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return '';
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed.replace(/^['"]|['"]$/g, '');
  }
}

export function parseFrontmatter(markdown) {
  const value = String(markdown || '').replace(/^\uFEFF/, '');
  if (!value.startsWith('---\n') && !value.startsWith('---\r\n')) return { metadata: {}, body: value };
  const lines = value.replace(/\r\n?/g, '\n').split('\n');
  let end = -1;
  for (let index = 1; index < lines.length; index += 1) {
    if (lines[index].trim() === '---') {
      end = index;
      break;
    }
  }
  if (end === -1) return { metadata: {}, body: value };
  const metadata = {};
  for (let index = 1; index < end; index += 1) {
    const match = lines[index].match(/^([A-Za-z][\w-]*):\s*(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    if (key === 'tags') {
      const tags = [];
      if (rawValue.trim() && rawValue.trim() !== '[]') tags.push(parseScalar(rawValue));
      while (index + 1 < end && /^\s+-\s+/.test(lines[index + 1])) {
        index += 1;
        tags.push(parseScalar(lines[index].replace(/^\s+-\s+/, '')));
      }
      metadata.tags = tags.filter((tag) => typeof tag === 'string' && tag.trim()).map((tag) => tag.trim());
      continue;
    }
    metadata[key] = parseScalar(rawValue);
  }
  return { metadata, body: lines.slice(end + 1).join('\n') };
}

export function documentTitle(markdown, fallback) {
  const heading = String(markdown || '').match(/^\s*#\s+(.+?)\s*$/m)?.[1];
  return String(heading || fallback || 'Importovaná poznámka').replace(/[*_`]/g, '').trim().slice(0, 200) || 'Importovaná poznámka';
}

function stripDuplicateTitle(markdown, title) {
  const lines = String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
  const firstContent = lines.findIndex((line) => line.trim());
  if (firstContent !== -1 && lines[firstContent].match(/^#\s+/)) {
    const heading = lines[firstContent].replace(/^#\s+/, '').trim();
    if (heading === title) lines.splice(firstContent, 1);
  }
  return lines.join('\n').replace(/^\s+/, '');
}

function safeExternalUrl(value) {
  const href = String(value || '').trim();
  if (!href) return '';
  if (href.startsWith('#') || href.startsWith('/')) return href;
  try {
    const url = new URL(href);
    return ['http:', 'https:', 'mailto:'].includes(url.protocol) ? href : '';
  } catch {
    return '';
  }
}

function resolveLocalAsset(value, documentPath, assets) {
  const target = String(value || '').trim().replace(/^<|>$/g, '').split('#', 1)[0];
  if (!target || /^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith('/')) return null;
  const parts = [...String(documentPath || '').split('/').slice(0, -1), ...target.split('/')];
  const normalized = [];
  for (const part of parts) {
    if (!part || part === '.') continue;
    if (part === '..') {
      if (!normalized.length) return null;
      normalized.pop();
      continue;
    }
    normalized.push(part);
  }
  return assets.get(normalized.join('/')) || null;
}

function readBlobAsDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => resolve(String(reader.result || '')));
    reader.addEventListener('error', () => reject(reader.error || new Error('Súbor sa nepodarilo načítať.')));
    reader.readAsDataURL(blob);
  });
}

async function prepareDocumentAssets(markdown, documentPath, assets, budget, warnings) {
  const references = [];
  const pattern = /!?\[[^\]]*\]\(([^)\s]+)(?:\s+['"][^'"]*['"])?\)/g;
  for (const match of String(markdown || '').matchAll(pattern)) references.push(match[1]);
  const referenced = new Set();
  for (const reference of references) {
    const asset = resolveLocalAsset(reference, documentPath, assets);
    if (!asset || referenced.has(asset.path)) continue;
    referenced.add(asset.path);
    if (asset.blob.type === 'image/svg+xml') {
      warnings.push(`${asset.path}: SVG sa z bezpečnostných dôvodov nevkladá.`);
      continue;
    }
    if (asset.blob.size > MAX_EMBEDDED_FILE_BYTES) {
      warnings.push(`${asset.path}: príloha presahuje 1,5 MB a nebude vložená.`);
      continue;
    }
    if (budget.used + asset.blob.size > MAX_EMBEDDED_TOTAL_BYTES) {
      warnings.push(`${asset.path}: prekročený spoločný limit vložených príloh 20 MB.`);
      continue;
    }
    try {
      asset.dataUrl ||= await readBlobAsDataUrl(asset.blob);
      budget.used += asset.blob.size;
      asset.available = true;
    } catch {
      warnings.push(`${asset.path}: prílohu sa nepodarilo načítať.`);
    }
  }
}

function inlineHtml(value, documentPath, assets) {
  const tokens = [];
  const token = (html) => {
    const marker = `\u0000markdown-token-${tokens.length}\u0000`;
    tokens.push(html);
    return marker;
  };
  let output = String(value || '');
  output = output.replace(/`([^`]+)`/g, (_, code) => token(`<code>${escapeHtml(code)}</code>`));
  output = output.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+['"][^'"]*['"])?\)/g, (_, alt, target) => {
    const asset = resolveLocalAsset(target, documentPath, assets);
    if (asset?.available && asset.dataUrl) {
      return token(`<img src="${escapeHtml(asset.dataUrl)}" alt="${escapeHtml(alt)}" title="${escapeHtml(asset.path.split('/').at(-1))}">`);
    }
    const href = safeExternalUrl(target);
    return href ? token(`<img src="${escapeHtml(href)}" alt="${escapeHtml(alt)}">`) : escapeHtml(alt);
  });
  output = output.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+['"][^'"]*['"])?\)/g, (_, label, target) => {
    const asset = resolveLocalAsset(target, documentPath, assets);
    if (asset?.available && asset.dataUrl) {
      const name = asset.path.split('/').at(-1) || label;
      return token(`<a data-attachment="" data-attachment-name="${escapeHtml(name)}" data-attachment-type="${escapeHtml(asset.blob.type)}" href="${escapeHtml(asset.dataUrl)}" download="${escapeHtml(name)}">${escapeHtml(label)}</a>`);
    }
    const href = safeExternalUrl(target);
    return href ? token(`<a href="${escapeHtml(href)}">${escapeHtml(label)}</a>`) : escapeHtml(label);
  });
  output = escapeHtml(output);
  output = output.replace(/\$([^$\n]+)\$/g, (_, latex) => `<span data-type="inline-math" data-latex="${escapeHtml(latex.trim())}"></span>`);
  output = output.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  output = output.replace(/~~([^~]+)~~/g, '<s>$1</s>');
  output = output.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  output = output.replace(/\u0000markdown-token-(\d+)\u0000/g, (_, index) => tokens[Number(index)] || '');
  return output;
}

function tableCells(line) {
  return String(line || '').trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
}

function isTableDivider(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(String(line || ''));
}

function isListLine(line) {
  return /^\s*(?:[-+*]|\d+\.)\s+/.test(String(line || ''));
}

function markdownToHtml(markdown, documentPath, assets) {
  const lines = String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let index = 0;
  const isBlockStart = (line, next = '') => /^```|^\$\$\s*$|^#{1,6}\s+|^>\s?|^\s*(?:[-+*]|\d+\.)\s+|^\s*(?:---+|\*\*\*+)\s*$/.test(line) || (line.includes('|') && isTableDivider(next));

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const codeMatch = line.match(/^```\s*([\w+-]*)\s*$/);
    if (codeMatch) {
      const language = codeMatch[1].replace(/[^\w+-]/g, '');
      const code = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(`<pre><code${language ? ` class="language-${language}"` : ''}>${escapeHtml(code.join('\n'))}</code></pre>`);
      continue;
    }
    if (/^\$\$\s*$/.test(line)) {
      const latex = [];
      index += 1;
      while (index < lines.length && !/^\$\$\s*$/.test(lines[index])) {
        latex.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(`<div data-type="block-math" data-latex="${escapeHtml(latex.join('\n').trim())}"></div>`);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      blocks.push(`<h${level}>${inlineHtml(heading[2], documentPath, assets)}</h${level}>`);
      index += 1;
      continue;
    }
    if (/^\s*(?:---+|\*\*\*+)\s*$/.test(line)) {
      blocks.push('<hr>');
      index += 1;
      continue;
    }
    if (line.startsWith('>')) {
      const quote = [];
      while (index < lines.length && lines[index].startsWith('>')) {
        quote.push(lines[index].replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push(`<blockquote><p>${inlineHtml(quote.join('\n'), documentPath, assets)}</p></blockquote>`);
      continue;
    }
    if (line.includes('|') && isTableDivider(lines[index + 1])) {
      const header = tableCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      const headerRow = `<tr>${header.map((cell) => `<th>${inlineHtml(cell, documentPath, assets)}</th>`).join('')}</tr>`;
      const bodyRows = rows.map((row) => `<tr>${header.map((_, cellIndex) => `<td>${inlineHtml(row[cellIndex] || '', documentPath, assets)}</td>`).join('')}</tr>`).join('');
      blocks.push(`<table><thead>${headerRow}</thead><tbody>${bodyRows}</tbody></table>`);
      continue;
    }
    if (isListLine(line)) {
      const items = [];
      let hasTask = false;
      let ordered = /^\s*\d+\.\s+/.test(line);
      while (index < lines.length && isListLine(lines[index])) {
        const item = lines[index].replace(/^\s*(?:[-+*]|\d+\.)\s+/, '');
        const task = item.match(/^\[([ xX])\]\s*(.*)$/);
        if (task) hasTask = true;
        items.push(task ? { text: task[2], checked: task[1].toLocaleLowerCase('sk') === 'x' } : { text: item, checked: null });
        index += 1;
      }
      if (hasTask) {
        const rows = items.map((item) => `<li data-type="taskItem" data-checked="${Boolean(item.checked)}"><label><input type="checkbox"${item.checked ? ' checked' : ''}><span></span></label><div><p>${inlineHtml(item.text, documentPath, assets)}</p></div></li>`).join('');
        blocks.push(`<ul data-type="taskList">${rows}</ul>`);
      } else {
        const tag = ordered ? 'ol' : 'ul';
        blocks.push(`<${tag}>${items.map((item) => `<li>${inlineHtml(item.text, documentPath, assets)}</li>`).join('')}</${tag}>`);
      }
      continue;
    }
    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index], lines[index + 1])) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(`<p>${inlineHtml(paragraph.join('\n'), documentPath, assets).replace(/\n/g, '<br>')}</p>`);
  }
  return blocks.join('') || '<p></p>';
}

function emptyExportManifest() {
  return {
    library: { name: '', tags: [] },
    folders: new Map(),
    librarySources: [],
    documentSources: new Map(),
    sourceSnapshots: [],
    isOwnExport: false
  };
}

function manifestText(value, maximum) {
  return typeof value === 'string' ? value.trim().slice(0, maximum) : '';
}

function manifestSourceLink(value) {
  const sourceId = manifestText(value?.sourceId, 160);
  if (!sourceId) return null;
  const relationType = manifestText(value?.relationType, 40) || 'reference';
  if (!['reference', 'citation', 'attachment', 'evidence', 'counterargument', 'derived', 'annotation'].includes(relationType)) return null;
  return {
    sourceId,
    title: manifestText(value?.title, 300),
    sourceFileId: manifestText(value?.sourceFileId, 160),
    relationType,
    locator: manifestText(value?.locator, 300),
    label: manifestText(value?.label, 300),
    note: manifestText(value?.note, 2_000)
  };
}

function manifestLibrarySource(value) {
  const sourceId = manifestText(value?.sourceId, 160);
  if (!sourceId) return null;
  return { sourceId, title: manifestText(value?.title, 300), note: manifestText(value?.note, 2_000) };
}

function manifestLibrary(value) {
  const tags = Array.isArray(value?.tags)
    ? value.tags.map((tag) => manifestText(tag, 80)).filter(Boolean).slice(0, 30)
    : [];
  return { name: manifestText(value?.name, 80), tags: [...new Set(tags)] };
}

function manifestSourceMetadata(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const metadata = {};
  Object.entries(value).slice(0, 50).forEach(([key, item]) => {
    const name = manifestText(key, 80);
    if (!name) return;
    if (typeof item === 'string') metadata[name] = manifestText(item, 1_000);
    else if (typeof item === 'number' && Number.isFinite(item)) metadata[name] = item;
    else if (typeof item === 'boolean') metadata[name] = item;
  });
  return metadata;
}

export function importedSourceSnapshot(value) {
  const id = manifestText(value?.id, 160);
  const title = manifestText(value?.title, 240);
  if (!id || !title) return null;
  const files = (Array.isArray(value?.files) ? value.files : []).slice(0, 200).map((file) => {
    const fileId = manifestText(file?.id, 160);
    if (!fileId) return null;
    return {
      id: fileId,
      originalName: manifestText(file?.originalName, 240) || 'priloha',
      mimeType: manifestText(file?.mimeType, 160) || 'application/octet-stream',
      sizeBytes: Math.max(0, Math.min(Number(file?.sizeBytes) || 0, MAX_ARCHIVE_BYTES)),
      archivePath: manifestText(file?.archivePath, 320)
    };
  }).filter(Boolean);
  const tags = Array.isArray(value?.tags)
    ? [...new Set(value.tags.map((tag) => manifestText(tag, 80)).filter(Boolean))].slice(0, 30)
    : [];
  return {
    id,
    title,
    kind: manifestText(value?.kind, 40) || 'source',
    description: manifestText(value?.description, 10_000),
    metadata: manifestSourceMetadata(value?.metadata),
    tags,
    files
  };
}

function stripExportSourceSection(markdown, sourceSection) {
  const body = String(markdown || '').replace(/\r\n?/g, '\n');
  const section = String(sourceSection || '').replace(/\r\n?/g, '\n').trim();
  if (!section) return { body, removed: false };
  const suffix = `\n\n${section}`;
  if (!body.trimEnd().endsWith(suffix)) return { body, removed: false };
  return { body: body.trimEnd().slice(0, -suffix.length).trimEnd(), removed: true };
}

function parseManifest(entries) {
  const manifest = entries.find((entry) => entry.path === '.poznamkovnik-export.json');
  if (!manifest || manifest.blob.size > MAX_EXPORT_MANIFEST_BYTES) return Promise.resolve(emptyExportManifest());
  return manifest.blob.text().then((text) => {
    try {
      const value = JSON.parse(text);
      if (value?.format !== 'poznamkovnik-markdown-export' || !Array.isArray(value.folders)) return emptyExportManifest();
      const folders = new Map(value.folders
        .slice(0, 500)
        .filter((folder) => typeof folder?.path === 'string' && typeof folder?.title === 'string')
        .map((folder) => [normalizeArchivePath(folder.path), folder.title.trim()])
        .filter(([path, title]) => path && title));
      const librarySources = (Array.isArray(value.librarySources) ? value.librarySources : [])
        .map(manifestLibrarySource)
        .filter(Boolean);
      const documentSources = new Map();
      (Array.isArray(value.documents) ? value.documents : []).slice(0, 500).forEach((document) => {
        const path = normalizeArchivePath(document?.path);
        if (!path || !isMarkdownPath(path) || documentSources.has(path)) return;
        documentSources.set(path, {
          sourceSection: manifestText(document?.sourceSection, MAX_DOCUMENT_CONTENT_LENGTH),
          links: (Array.isArray(document?.links) ? document.links : []).map(manifestSourceLink).filter(Boolean)
        });
      });
      const sourceSnapshots = (Array.isArray(value.sources) ? value.sources : [])
        .slice(0, 500)
        .map(importedSourceSnapshot)
        .filter(Boolean);
      return { library: manifestLibrary(value.library), folders, librarySources, documentSources, sourceSnapshots, isOwnExport: true };
    } catch {
      return emptyExportManifest();
    }
  });
}

function packageElement(value) {
  const id = manifestText(value?.id, 160);
  const title = manifestText(value?.title, 200);
  const type = ['folder', 'note', 'article'].includes(value?.type) ? value.type : '';
  if (!id || !title || !type) return null;
  const tags = Array.isArray(value?.tags)
    ? [...new Set(value.tags.map((tag) => manifestText(tag, 80)).filter(Boolean))].slice(0, 30)
    : [];
  const content = type === 'folder' ? '' : String(value?.content || '');
  if (content.length > MAX_DOCUMENT_CONTENT_LENGTH) return null;
  return {
    id,
    type,
    parentId: manifestText(value?.parentId, 160),
    title,
    content,
    tags,
    createdAt: manifestText(value?.createdAt, 80),
    updatedAt: manifestText(value?.updatedAt, 80),
    sourceLinks: []
  };
}

async function parseLibraryPackage(entries) {
  const manifest = entries.find((entry) => entry.path === libraryPackageManifestPath);
  if (!manifest) return null;
  if (manifest.blob.size > MAX_LIBRARY_PACKAGE_MANIFEST_BYTES) {
    throw new Error('Prenosový balík má príliš veľký popis obsahu.');
  }
  let value;
  try {
    value = JSON.parse(await manifest.blob.text());
  } catch {
    throw new Error('Prenosový balík má neplatný popis obsahu.');
  }
  if (value?.format !== 'poznamkovnik-library-package' || !Array.isArray(value.elements)) {
    throw new Error('ZIP neobsahuje podporovaný prenosový balík Poznámkovníka.');
  }
  const elements = value.elements.slice(0, 500).map(packageElement).filter(Boolean);
  const elementIds = new Set(elements.map((element) => element.id));
  const linksByElement = new Map();
  (Array.isArray(value.elementLinks) ? value.elementLinks : []).slice(0, 500).forEach((item) => {
    const elementId = manifestText(item?.elementId, 160);
    if (!elementIds.has(elementId) || linksByElement.has(elementId)) return;
    linksByElement.set(elementId, (Array.isArray(item?.links) ? item.links : []).map(manifestSourceLink).filter(Boolean));
  });
  elements.forEach((element) => {
    element.parentId = elementIds.has(element.parentId) ? element.parentId : '';
    element.sourceLinks = linksByElement.get(element.id) || [];
  });
  const librarySources = (Array.isArray(value.librarySources) ? value.librarySources : [])
    .map(manifestLibrarySource)
    .filter(Boolean);
  const sourceSnapshots = (Array.isArray(value.sources) ? value.sources : [])
    .slice(0, 500)
    .map(importedSourceSnapshot)
    .filter(Boolean);
  return {
    library: manifestLibrary(value.library),
    elements,
    librarySources,
    sourceSnapshots
  };
}

function importedTaskRecord(value) {
  const title = manifestText(value?.title, 240);
  if (!title) return null;
  const status = ['open', 'in_progress', 'done'].includes(value?.status) ? value.status : 'open';
  const priority = ['none', 'low', 'medium', 'high'].includes(value?.priority) ? value.priority : 'none';
  const dueDate = manifestText(value?.dueDate, 32);
  const tags = Array.isArray(value?.tags)
    ? [...new Set(value.tags.map((tag) => manifestText(tag, 80)).filter(Boolean))].slice(0, 30)
    : [];
  return {
    title,
    description: manifestText(value?.description, 10_000),
    status,
    priority,
    dueDate: /^\d{4}-\d{2}-\d{2}$/.test(dueDate) ? dueDate : '',
    tags
  };
}

function importedTaskLink(value) {
  const targetType = ['library', 'element', 'source'].includes(value?.targetType) ? value.targetType : '';
  const targetId = manifestText(value?.targetId, 160);
  if (!targetType || !targetId) return null;
  return {
    targetType,
    targetId,
    title: manifestText(value?.title, 300),
    subtitle: manifestText(value?.subtitle, 300),
    libraryId: manifestText(value?.libraryId, 160),
    elementType: manifestText(value?.elementType, 40)
  };
}

async function parseTaskPackage(entries) {
  const manifest = entries.find((entry) => entry.path === taskPackageManifestPath);
  if (!manifest) return null;
  if (manifest.blob.size > MAX_EXPORT_MANIFEST_BYTES) throw new Error('Prenosový balík úlohy má príliš veľký popis obsahu.');
  let value;
  try {
    value = JSON.parse(await manifest.blob.text());
  } catch {
    throw new Error('Prenosový balík úlohy má neplatný popis obsahu.');
  }
  if (value?.format !== 'poznamkovnik-task-package') {
    throw new Error('ZIP neobsahuje podporovaný prenosový balík úlohy Poznámkovníka.');
  }
  const task = importedTaskRecord(value.task);
  if (!task) throw new Error('Prenosový balík úlohy neobsahuje platný názov.');
  return {
    task,
    links: (Array.isArray(value.links) ? value.links : []).slice(0, 100).map(importedTaskLink).filter(Boolean),
    sourceSnapshots: (Array.isArray(value.sources) ? value.sources : []).slice(0, 200).map(importedSourceSnapshot).filter(Boolean)
  };
}

function importedTaskTitle(body, fallback) {
  return documentTitle(body, fallback)
    .replace(/^\[[ xX]\]\s*/, '')
    .trim()
    .slice(0, 240) || 'Importovaná úloha';
}

function importedTaskDescription(body) {
  const lines = String(body || '').replace(/\r\n?/g, '\n').split('\n');
  const firstContent = lines.findIndex((line) => line.trim());
  if (firstContent !== -1 && /^#\s+/.test(lines[firstContent])) lines.splice(firstContent, 1);
  while (lines.length && !lines[0].trim()) lines.shift();
  while (lines.length && /^\*\*(?:Stav|Priorita|Termín):\*\*/.test(lines[0].trim())) lines.shift();
  while (lines.length && !lines[0].trim()) lines.shift();
  const generatedSection = lines.findIndex((line) => /^##\s+(?:Prepojenia|Zdroje)\s*$/i.test(line.trim()));
  if (generatedSection !== -1) lines.splice(generatedSection);
  return lines.join('\n').trim().slice(0, 10_000);
}

function taskImportPreview({ sourceName, task, links = [], sourceSnapshots = [], sourceAssets = new Map(), sourceManifest = false }) {
  const sourceLinks = links
    .filter((link) => link.targetType === 'source')
    .map((link) => {
      const sourceImportLink = {
        sourceId: link.targetId,
        title: link.title,
        relationType: 'reference',
        locator: '',
        label: '',
        note: ''
      };
      link.sourceImportLink = sourceImportLink;
      return sourceImportLink;
    });
  return {
    sourceName,
    task,
    taskLinks: links,
    documents: [{ title: task.title, type: 'task', sourceLinks }],
    folders: [],
    warnings: [],
    attachments: 0,
    librarySourceLinks: [],
    sourceManifest,
    sourceSnapshots,
    sourceAssets,
    sourceActions: {},
    sourceUsageLabel: 'Úloha',
    sourceDestinationLabel: 'k úlohe'
  };
}

export async function prepareTaskMarkdownImport(file) {
  const entries = await readImportEntries(file);
  const taskPackage = await parseTaskPackage(entries);
  const assets = new Map();
  entries.filter((entry) => (
    entry.path !== '.poznamkovnik-export.json'
    && entry.path !== libraryPackageManifestPath
    && entry.path !== taskPackageManifestPath
    && !isMarkdownPath(entry.path)
  )).forEach((entry) => assets.set(entry.path, { ...entry, available: false, dataUrl: '' }));
  if (taskPackage) {
    return taskImportPreview({
      sourceName: String(file.name || 'Prenosový balík úlohy'),
      task: taskPackage.task,
      links: taskPackage.links,
      sourceSnapshots: taskPackage.sourceSnapshots,
      sourceAssets: assets,
      sourceManifest: true
    });
  }

  const markdownEntries = entries.filter((entry) => isMarkdownPath(entry.path) && entry.path.toLocaleLowerCase('sk') !== 'readme.md');
  if (markdownEntries.length !== 1) {
    throw new Error('Pre import úlohy vyber jeden Markdown súbor alebo ZIP s jedinou úlohou.');
  }
  const entry = markdownEntries[0];
  if (entry.blob.size > MAX_MARKDOWN_BYTES) throw new Error('Markdown súbor môže mať najviac 2 MB.');
  const { metadata, body } = parseFrontmatter(await entry.blob.text());
  if (metadata.type && metadata.type !== 'task') throw new Error('Vybraný Markdown neoznačuje úlohu.');
  const fallback = entry.path.split('/').at(-1).replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
  const task = importedTaskRecord({
    title: metadata.title || importedTaskTitle(body, fallback),
    description: importedTaskDescription(body),
    status: metadata.status,
    priority: metadata.priority,
    dueDate: metadata.due,
    tags: metadata.tags
  });
  if (!task) throw new Error('Markdown úlohy nemá platný názov.');
  return taskImportPreview({ sourceName: String(file.name || 'Markdown úlohy'), task });
}

function isInternalAssetPath(path, manifestFolders) {
  const normalized = normalizeArchivePath(path);
  if (!normalized.startsWith('assets/')) return false;

  // Exporter stores bundled attachments under assets/. A real user folder with
  // this name is retained in the manifest and must remain importable.
  return ![...manifestFolders.keys()].some((folderPath) => folderPath === 'assets' || folderPath.startsWith('assets/'));
}

function summaryText(preview) {
  const kinds = preview.documents.reduce((counts, document) => {
    counts[document.type] = (counts[document.type] || 0) + 1;
    return counts;
  }, {});
  const parts = [
    `${preview.folders.length} ${preview.folders.length === 1 ? 'priečinok' : 'priečinkov'}`,
    `${kinds.note || 0} ${kinds.note === 1 ? 'poznámka' : 'poznámok'}`,
    `${kinds.article || 0} ${kinds.article === 1 ? 'článok' : 'článkov'}`
  ];
  if (preview.attachments) parts.push(`${preview.attachments} ${preview.attachments === 1 ? 'príloha' : 'príloh'}`);
  return parts.join(' · ');
}

export async function prepareMarkdownImport(file) {
  const entries = await readImportEntries(file);
  const libraryPackage = await parseLibraryPackage(entries);
  const manifest = await parseManifest(entries);
  const manifestFolders = manifest.folders;
  const warnings = [];
  const assets = new Map();
  entries.filter((entry) => (
    entry.path !== '.poznamkovnik-export.json'
    && entry.path !== libraryPackageManifestPath
    && (!isMarkdownPath(entry.path) || isInternalAssetPath(entry.path, manifestFolders))
  )).forEach((entry) => {
    assets.set(entry.path, { ...entry, available: false, dataUrl: '' });
  });
  if (libraryPackage) {
    const folders = libraryPackage.elements
      .filter((element) => element.type === 'folder')
      .map((element) => ({ path: element.id, title: element.title }));
    const documents = libraryPackage.elements
      .filter((element) => element.type !== 'folder')
      .map((element) => ({
        path: element.title,
        directory: [],
        title: element.title,
        type: element.type,
        tags: element.tags,
        content: element.content,
        sourceLinks: element.sourceLinks
      }));
    return {
      sourceName: String(file.name || 'Prenosový balík'),
      libraryName: libraryPackage.library.name,
      libraryTags: libraryPackage.library.tags,
      documents,
      folders,
      warnings: [],
      attachments: 0,
      librarySourceLinks: libraryPackage.librarySources,
      sourceManifest: true,
      sourceSnapshots: libraryPackage.sourceSnapshots,
      sourceAssets: assets,
      sourceActions: {},
      nativeElements: libraryPackage.elements
    };
  }
  let markdownEntries = entries.filter((entry) => (
    entry.path !== '.poznamkovnik-export.json'
    && entry.path !== libraryPackageManifestPath
    && isMarkdownPath(entry.path)
    && !isInternalAssetPath(entry.path, manifestFolders)
  ));
  if (manifest.isOwnExport) markdownEntries = markdownEntries.filter((entry) => entry.path !== 'README.md');
  else if (markdownEntries.length > 1) markdownEntries = markdownEntries.filter((entry) => entry.path !== 'README.md');
  if (!markdownEntries.length && !manifest.folders.size && !manifest.librarySources.length) {
    throw new Error('Nenašiel sa žiadny Markdown súbor na import.');
  }
  if (markdownEntries.length > 250) throw new Error('Naraz je možné importovať najviac 250 Markdown súborov.');
  const budget = { used: 0 };
  const documents = [];
  for (const entry of markdownEntries) {
    if (entry.blob.size > MAX_MARKDOWN_BYTES) {
      warnings.push(`${entry.path}: Markdown súbor presahuje 2 MB a nebude importovaný.`);
      continue;
    }
    const { metadata, body } = parseFrontmatter(await entry.blob.text());
    const fallback = entry.path.split('/').at(-1).replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
    const title = String(metadata.title || documentTitle(body, fallback)).trim().slice(0, 200) || 'Importovaná poznámka';
    const type = metadata.type === 'article' ? 'article' : 'note';
    const tags = Array.isArray(metadata.tags) ? metadata.tags.slice(0, 30) : [];
    const sourceInfo = manifest.documentSources.get(entry.path);
    const strippedSource = stripExportSourceSection(body, sourceInfo?.sourceSection);
    if (sourceInfo?.sourceSection && !strippedSource.removed) {
      warnings.push(`${entry.path}: automatickú sekciu Zdroje sa nepodarilo rozpoznať, preto ostala v texte.`);
    }
    const cleanedBody = stripDuplicateTitle(strippedSource.body, title);
    await prepareDocumentAssets(cleanedBody, entry.path, assets, budget, warnings);
    const content = markdownToHtml(cleanedBody, entry.path, assets);
    if (content.length > MAX_DOCUMENT_CONTENT_LENGTH) {
      warnings.push(`${entry.path}: výsledný text je príliš veľký a nebude importovaný.`);
      continue;
    }
    const directory = entry.path.split('/').slice(0, -1);
    documents.push({
      path: entry.path,
      directory,
      title,
      type,
      tags,
      content,
      markdown: cleanedBody,
      metadata,
      sourceLinks: sourceInfo?.links || []
    });
  }
  if (!documents.length && !manifest.folders.size && !manifest.librarySources.length) {
    throw new Error('Žiadny Markdown súbor nevyhovuje limitom importu.');
  }
  const folderMap = new Map();
  manifestFolders.forEach((title, path) => folderMap.set(path, title));
  documents.forEach((document) => {
    document.directory.forEach((segment, index) => {
      const path = document.directory.slice(0, index + 1).join('/');
      folderMap.set(path, manifestFolders.get(path) || segment);
    });
  });
  const attachments = [...assets.values()].filter((asset) => asset.available).length;
  const markdownLibraryName = documents.map((document) => manifestText(document.metadata?.library, 80)).find(Boolean) || '';
  return {
    sourceName: String(file.name || 'Markdown'),
    libraryName: manifest.library.name || markdownLibraryName,
    libraryTags: manifest.library.tags,
    documents,
    folders: [...folderMap.entries()].map(([path, title]) => ({ path, title })),
    warnings: [...new Set(warnings)],
    attachments,
    librarySourceLinks: manifest.librarySources,
    sourceManifest: manifest.isOwnExport,
    sourceSnapshots: manifest.sourceSnapshots,
    sourceAssets: assets,
    sourceActions: {}
  };
}

export function importedLibraryPlan(preview, parentId = '') {
  const timestamp = new Date().toISOString();
  if (Array.isArray(preview?.nativeElements)) {
    const rawElements = preview.nativeElements.filter((item) => item?.id && ['folder', 'note', 'article'].includes(item.type));
    const ids = new Map(rawElements.map((item) => [item.id, crypto.randomUUID()]));
    const items = rawElements.map((item) => ({
      id: ids.get(item.id),
      type: item.type,
      parentId: ids.get(item.parentId) || parentId,
      title: item.title,
      content: item.type === 'folder' ? '' : item.content,
      tags: item.tags,
      createdAt: item.createdAt || timestamp,
      updatedAt: item.updatedAt || timestamp
    }));
    const elementSourceLinks = rawElements.flatMap((item) => (item.sourceLinks || []).map((link) => ({
      ...link,
      elementId: ids.get(item.id)
    })));
    return {
      items,
      librarySourceLinks: Array.isArray(preview?.librarySourceLinks) ? preview.librarySourceLinks : [],
      elementSourceLinks,
      sourceManifest: Boolean(preview?.sourceManifest),
      sourceSnapshots: Array.isArray(preview?.sourceSnapshots) ? preview.sourceSnapshots : [],
      sourceAssets: preview?.sourceAssets instanceof Map ? preview.sourceAssets : new Map(),
      sourceActions: preview?.sourceActions && typeof preview.sourceActions === 'object' ? preview.sourceActions : {}
    };
  }
  const folders = [...(preview?.folders || [])].sort((first, second) => first.path.split('/').length - second.path.split('/').length || first.path.localeCompare(second.path, 'sk'));
  const folderIds = new Map([['', parentId]]);
  const items = [];
  const elementSourceLinks = [];
  folders.forEach((folder) => {
    const parentPath = folder.path.split('/').slice(0, -1).join('/');
    const id = crypto.randomUUID();
    folderIds.set(folder.path, id);
    items.push({ id, type: 'folder', parentId: folderIds.get(parentPath) || parentId, title: folder.title, content: '', tags: [], createdAt: timestamp, updatedAt: timestamp });
  });
  (preview?.documents || []).forEach((document) => {
    const directory = document.directory.join('/');
    const id = crypto.randomUUID();
    items.push({
      id,
      type: document.type,
      parentId: folderIds.get(directory) || parentId,
      title: document.title,
      content: document.content,
      tags: document.tags,
      createdAt: timestamp,
      updatedAt: timestamp
    });
    (document.sourceLinks || []).forEach((link) => elementSourceLinks.push({ ...link, elementId: id }));
  });
  return {
    items,
    librarySourceLinks: Array.isArray(preview?.librarySourceLinks) ? preview.librarySourceLinks : [],
    elementSourceLinks,
    sourceManifest: Boolean(preview?.sourceManifest),
    sourceSnapshots: Array.isArray(preview?.sourceSnapshots) ? preview.sourceSnapshots : [],
    sourceAssets: preview?.sourceAssets instanceof Map ? preview.sourceAssets : new Map(),
    sourceActions: preview?.sourceActions && typeof preview.sourceActions === 'object' ? preview.sourceActions : {}
  };
}

export function importedLibraryItems(preview, parentId = '') {
  return importedLibraryPlan(preview, parentId).items;
}

function setPreviewStatus(message = '', error = false) {
  dom.markdownImportStatus.textContent = message;
  dom.markdownImportStatus.classList.toggle('is-error', error);
}

function previewView(preview) {
  const adapted = importTarget?.previewAdapter?.(preview);
  if (adapted?.summary && Array.isArray(adapted.items)) return adapted;
  return {
    summary: summaryText(preview),
    items: preview.documents.map((document) => ({
      type: document.type === 'article' ? 'Článok' : 'Poznámka',
      title: document.title,
      path: document.path
    }))
  };
}

function sourceAvailabilityLabel(status) {
  const labels = {
    available: 'Pripravené na obnovenie',
    'missing-source': 'Chýba zdroj v katalógu',
    'missing-file': 'Chýba priložený súbor',
    unchecked: 'Nepodarilo sa overiť'
  };
  return labels[status] || labels.unchecked;
}

function sourceSnapshotMap(preview) {
  return new Map((Array.isArray(preview?.sourceSnapshots) ? preview.sourceSnapshots : [])
    .filter((source) => source?.id)
    .map((source) => [source.id, source]));
}

function sourceGroupAvailability(links) {
  const states = new Set(links.map((link) => link.importAvailability || 'unchecked'));
  if (states.size === 1 && states.has('available')) return 'available';
  if (states.has('unchecked')) return 'unchecked';
  if (states.has('missing-source')) return 'missing-source';
  if (states.has('missing-file')) return 'missing-file';
  return 'unchecked';
}

function sourceActionChoices(group) {
  const choices = [];
  if (group.sourceExists) choices.push({ value: 'existing', label: 'Použiť existujúci zdroj' });
  if (group.snapshot) {
    const fileCount = group.snapshot.files.length;
    const bundledFiles = group.snapshot.files.filter((file) => file.archivePath).length;
    const suffix = fileCount ? ` · ${bundledFiles}/${fileCount} súb.` : '';
    choices.push({ value: 'copy', label: `Vytvoriť kópiu${suffix}` });
  }
  choices.push({ value: 'skip', label: 'Vynechať väzby' });
  return choices;
}

function defaultSourceAction(group) {
  if (group.availability === 'available' && group.sourceExists) return 'existing';
  if (group.availability === 'unchecked') return 'skip';
  if (group.snapshot) return 'copy';
  return group.sourceExists ? 'existing' : 'skip';
}

function sourceImportGroups(preview) {
  const snapshots = sourceSnapshotMap(preview);
  const groups = new Map();
  (preview?.librarySourceLinks || []).forEach((link) => {
    const sourceId = String(link?.sourceId || '');
    if (!sourceId) return;
    const group = groups.get(sourceId) || { sourceId, title: link.title || 'Zdroj z archívu', libraryLinks: [], documentLinks: [] };
    group.libraryLinks.push(link);
    groups.set(sourceId, group);
  });
  (preview?.documents || []).forEach((document) => {
    (document.sourceLinks || []).forEach((link) => {
      const sourceId = String(link?.sourceId || '');
      if (!sourceId) return;
      const group = groups.get(sourceId) || { sourceId, title: link.title || 'Zdroj z archívu', libraryLinks: [], documentLinks: [] };
      group.documentLinks.push({ ...link, document });
      groups.set(sourceId, group);
    });
  });
  return [...groups.values()].map((group) => {
    const links = [...group.libraryLinks, ...group.documentLinks];
    const availability = sourceGroupAvailability(links);
    const snapshot = snapshots.get(group.sourceId) || null;
    const sourceExists = availability === 'available' || availability === 'missing-file';
    const result = {
      ...group,
      links,
      snapshot,
      sourceExists,
      availability
    };
    const choices = sourceActionChoices(result);
    const selected = preview.sourceActions?.[group.sourceId];
    result.action = choices.some((choice) => choice.value === selected) ? selected : defaultSourceAction(result);
    return result;
  });
}

function sourceUsageLabel(group, preview) {
  const parts = [];
  if (group.libraryLinks.length) parts.push(`${group.libraryLinks.length} kniž.`);
  if (group.documentLinks.length) {
    parts.push(preview?.sourceUsageLabel || `${group.documentLinks.length} text.`);
  }
  return parts.join(' · ') || 'Bez väzby';
}

function sourceContextLabel(group) {
  const details = group.documentLinks.slice(0, 2).map(({ document, label, relationType, locator }) => (
    [document?.title, label || relationLabel(relationType), locator].filter(Boolean).join(' · ')
  )).filter(Boolean);
  if (group.documentLinks.length > 2) details.push(`a ďalších ${group.documentLinks.length - 2}`);
  if (group.libraryLinks.length && !details.length) {
    const note = group.libraryLinks.find((link) => link.note)?.note;
    return note ? `Spoločný zdroj knižnice · ${note}` : 'Spoločný zdroj knižnice';
  }
  return details.join(' · ') || 'Väzba zo zdroja';
}

function sourceAvailabilitySummary(groups) {
  const counts = groups.reduce((result, group) => {
    result[group.availability] = (result[group.availability] || 0) + 1;
    return result;
  }, {});
  const parts = [];
  if (counts.available) parts.push(`${counts.available} pripravených`);
  if (counts['missing-source']) parts.push(`${counts['missing-source']} chýbajúci zdroj`);
  if (counts['missing-file']) parts.push(`${counts['missing-file']} chýbajúci súbor`);
  if (counts.unchecked) parts.push(`${counts.unchecked} neoverené`);
  return parts.join(' · ');
}

function allSourceLinks(preview) {
  return [
    ...(preview?.librarySourceLinks || []),
    ...(preview?.documents || []).flatMap((document) => document.sourceLinks || [])
  ];
}

async function checkImportSourceAvailability(preview) {
  const links = allSourceLinks(preview);
  if (!preview?.sourceManifest || !links.length) return;

  const ids = [...new Set(links.map((link) => link.sourceId).filter(Boolean))];
  const results = await Promise.allSettled(ids.map(async (sourceId) => {
    const response = await apiRequest(`/sources/${encodeURIComponent(sourceId)}`);
    return [sourceId, response.source];
  }));
  const sources = new Map();
  const unavailableIds = new Set();
  results.forEach((result, index) => {
    const sourceId = ids[index];
    if (result.status === 'fulfilled') sources.set(sourceId, result.value[1]);
    else if (result.reason?.status !== 404) unavailableIds.add(sourceId);
  });
  links.forEach((link) => {
    const source = sources.get(link.sourceId);
    if (!source) {
      link.importAvailability = unavailableIds.has(link.sourceId) ? 'unchecked' : 'missing-source';
      return;
    }
    if (link.sourceFileId && !(source.files || []).some((file) => file.id === link.sourceFileId)) {
      link.importAvailability = 'missing-file';
      return;
    }
    link.importAvailability = 'available';
  });
  sourceImportGroups(preview).forEach((group) => {
    if (!Object.hasOwn(preview.sourceActions, group.sourceId)) {
      preview.sourceActions[group.sourceId] = defaultSourceAction(group);
    }
  });
}

function relationLabel(relationType) {
  const labels = {
    reference: 'Odkaz na zdroj',
    citation: 'Citácia',
    attachment: 'Príloha',
    evidence: 'Dôkaz',
    counterargument: 'Protiargument',
    derived: 'Odvodené',
    annotation: 'Anotácia'
  };
  return labels[relationType] || 'Väzba na zdroj';
}

function renderSourceLinkPreview(preview) {
  const groups = sourceImportGroups(preview);
  const libraryCount = (preview.librarySourceLinks || []).length;
  const documentCount = allSourceLinks(preview).length - libraryCount;
  dom.markdownImportSourceItems.replaceChildren();
  dom.markdownImportSourceLinks.hidden = !groups.length;
  if (!groups.length) return;

  const parts = [];
  if (libraryCount) parts.push(`${libraryCount} ku knižnici`);
  if (documentCount) parts.push(`${documentCount} ${preview?.sourceDestinationLabel || 'k textom'}`);
  dom.markdownImportSourceSummary.textContent = `${groups.length} zdrojov · ${parts.join(' · ')} · ${sourceAvailabilitySummary(groups)}.`;
  groups.forEach((group) => {
    const row = document.createElement('div');
    row.className = `markdown-import-source-item is-${group.availability}`;
    const usage = document.createElement('span');
    usage.textContent = sourceUsageLabel(group, preview);
    const title = document.createElement('strong');
    title.textContent = group.title;
    const context = document.createElement('small');
    context.textContent = sourceContextLabel(group);
    const availability = document.createElement('em');
    availability.textContent = sourceAvailabilityLabel(group.availability);
    const action = document.createElement('select');
    action.className = 'markdown-import-source-action';
    action.setAttribute('aria-label', `Postup importu zdroja ${group.title}`);
    sourceActionChoices(group).forEach((choice) => {
      const option = document.createElement('option');
      option.value = choice.value;
      option.textContent = choice.label;
      action.append(option);
    });
    action.value = group.action;
    action.addEventListener('change', () => {
      preview.sourceActions[group.sourceId] = action.value;
      renderSourceLinkPreview(preview);
      updateImportReadyStatus(preview);
    });
    row.append(usage, title, context, availability, action);
    dom.markdownImportSourceItems.append(row);
  });
}

function updateImportReadyStatus(preview, view = previewView(preview)) {
  const groups = sourceImportGroups(preview);
  const sourceLinks = allSourceLinks(preview).length;
  const copied = groups.filter((group) => group.action === 'copy').length;
  const skippedLinks = groups.filter((group) => group.action === 'skip').reduce((count, group) => count + group.links.length, 0);
  const warnings = [...new Set([...(preview.warnings || []), ...(view.warnings || [])])];
  const sourceMessage = !sourceLinks
    ? 'Import vytvorí iba nové položky; existujúce texty nemení.'
    : [
        'Import vytvorí iba nové položky',
        copied ? `vytvorí kópiu ${copied} ${copied === 1 ? 'zdroja' : 'zdrojov'}` : '',
        skippedLinks ? `vynechá ${skippedLinks} ${skippedLinks === 1 ? 'väzbu' : 'väzieb'}` : '',
        'existujúce texty nemení'
      ].filter(Boolean).join('; ') + '.';
  setPreviewStatus(warnings.length ? warnings.join(' ') : sourceMessage, Boolean(warnings.length));
}

function renderPreview(preview) {
  const view = previewView(preview);
  const destination = importTarget?.destinationLabel || 'knižnice';
  dom.markdownImportDescription.textContent = `Nič ešte nebolo uložené. Do ${destination} sa pridá: ${view.summary}.`;
  dom.markdownImportSummary.textContent = view.summary;
  dom.markdownImportItems.replaceChildren();
  view.items.slice(0, 120).forEach((importedDocument) => {
    const row = document.createElement('div');
    row.className = 'markdown-import-item';
    const type = document.createElement('span');
    type.textContent = importedDocument.type;
    const title = document.createElement('strong');
    title.textContent = importedDocument.title;
    const path = document.createElement('small');
    path.textContent = importedDocument.path;
    row.append(type, title, path);
    dom.markdownImportItems.append(row);
  });
  if (view.items.length > 120) {
    const more = document.createElement('p');
    more.className = 'markdown-import-more';
    more.textContent = `A ďalších ${view.items.length - 120} položiek.`;
    dom.markdownImportItems.append(more);
  }
  renderSourceLinkPreview(preview);
  const sourceLinks = allSourceLinks(preview).length;
  dom.markdownImportItems.hidden = !view.items.length;
  dom.markdownImportItemsResizer.hidden = !view.items.length || !sourceLinks.length;
  fitDialogResizableSection(dom.markdownImportItems);
  updateImportReadyStatus(preview, view);
  dom.markdownImportConfirm.disabled = false;
}

function closeImportDialog() {
  if (dom.markdownImportDialog.open) dom.markdownImportDialog.close();
  else {
    pendingImport = null;
    importTarget = null;
  }
}

async function handleSelectedFile() {
  const file = dom.markdownImportInput.files?.[0];
  if (!file || !importTarget) return;
  pendingImport = null;
  dom.markdownImportConfirm.disabled = true;
  dom.markdownImportItems.replaceChildren();
  dom.markdownImportSourceItems.replaceChildren();
  dom.markdownImportItems.style.removeProperty('height');
  dom.markdownImportSourceItems.style.removeProperty('height');
  dom.markdownImportItems.hidden = false;
  dom.markdownImportItemsResizer.hidden = true;
  dom.markdownImportSourceLinks.hidden = true;
  dom.markdownImportSummary.textContent = '';
  dom.markdownImportDescription.textContent = 'Kontrolujem štruktúru a pripravujem náhľad...';
  setPreviewStatus('');
  if (!dom.markdownImportDialog.open) dom.markdownImportDialog.showModal();
  try {
    pendingImport = importTarget.prepareImport
      ? await importTarget.prepareImport(file)
      : await prepareMarkdownImport(file);
    await checkImportSourceAvailability(pendingImport);
    renderPreview(pendingImport);
  } catch (error) {
    setPreviewStatus(error?.message || 'Markdown sa nepodarilo spracovať.', true);
  }
}

async function confirmImport() {
  if (!pendingImport || !importTarget) return;
  dom.markdownImportConfirm.disabled = true;
  setPreviewStatus(allSourceLinks(pendingImport).length ? 'Pridávam nové položky a obnovujem väzby zdrojov...' : 'Pridávam nové položky...');
  try {
    const result = await importTarget.onConfirm(pendingImport);
    closeImportDialog();
    if (Array.isArray(result?.warnings) && result.warnings.length) {
      const preview = result.warnings.slice(0, 10).join('\n');
      const more = result.warnings.length > 10 ? '\n…' : '';
      window.alert(`Import je dokončený, ale niektoré väzby sa nepodarilo obnoviť:\n\n${preview}${more}`);
    }
  } catch (error) {
    setPreviewStatus(error?.message || 'Import sa nepodarilo uložiť.', true);
    dom.markdownImportConfirm.disabled = false;
  }
}

export function requestMarkdownImport({
  libraryName = '',
  parentId = '',
  destinationLabel = 'knižnice',
  confirmLabel = 'Pridať do knižnice',
  previewAdapter = null,
  prepareImport = null,
  onConfirm
}) {
  importTarget = { parentId, destinationLabel, confirmLabel, previewAdapter, prepareImport, onConfirm };
  pendingImport = null;
  dom.markdownImportInput.value = '';
  dom.markdownImportConfirm.textContent = confirmLabel;
  dom.markdownImportDialog.setAttribute('aria-label', `Import Markdownu do knižnice ${libraryName || ''}`.trim());
  dom.markdownImportInput.click();
}

export function initializeMarkdownImport() {
  dom.markdownImportInput.addEventListener('change', () => void handleSelectedFile());
  dom.markdownImportCancel.addEventListener('click', closeImportDialog);
  dom.markdownImportConfirm.addEventListener('click', () => void confirmImport());
  installDialogBackdropClose(dom.markdownImportDialog, closeImportDialog);
  dom.markdownImportDialog.addEventListener('close', () => {
    pendingImport = null;
    importTarget = null;
    dom.markdownImportInput.value = '';
  });
}
