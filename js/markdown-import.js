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

async function readImportEntries(file) {
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

function parseFrontmatter(markdown) {
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

function documentTitle(markdown, fallback) {
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
  return { folders: new Map(), librarySources: [], documentSources: new Map(), isOwnExport: false };
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
      return { folders, librarySources, documentSources, isOwnExport: true };
    } catch {
      return emptyExportManifest();
    }
  });
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
  const manifest = await parseManifest(entries);
  const manifestFolders = manifest.folders;
  const warnings = [];
  const assets = new Map();
  entries.filter((entry) => (
    entry.path !== '.poznamkovnik-export.json'
    && (!isMarkdownPath(entry.path) || isInternalAssetPath(entry.path, manifestFolders))
  )).forEach((entry) => {
    assets.set(entry.path, { ...entry, available: false, dataUrl: '' });
  });
  let markdownEntries = entries.filter((entry) => (
    entry.path !== '.poznamkovnik-export.json'
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
  return {
    sourceName: String(file.name || 'Markdown'),
    documents,
    folders: [...folderMap.entries()].map(([path, title]) => ({ path, title })),
    warnings: [...new Set(warnings)],
    attachments,
    librarySourceLinks: manifest.librarySources,
    sourceManifest: manifest.isOwnExport
  };
}

export function importedLibraryPlan(preview, parentId = '') {
  const timestamp = new Date().toISOString();
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
    sourceManifest: Boolean(preview?.sourceManifest)
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

function sourceLinkRows(preview) {
  const rows = [];
  (preview.librarySourceLinks || []).forEach((link) => {
    rows.push({
      type: 'Knižnici',
      title: link.title || 'Zdroj z archívu',
      context: link.note ? `Spoločný zdroj knižnice · ${link.note}` : 'Spoločný zdroj knižnice',
      availability: link.importAvailability || 'unchecked'
    });
  });
  (preview.documents || []).forEach((document) => {
    (document.sourceLinks || []).forEach((link) => {
      const detail = [
        document.title,
        link.label || relationLabel(link.relationType),
        link.locator
      ].filter(Boolean).join(' · ');
      rows.push({
        type: 'Textu',
        title: link.title || 'Zdroj z archívu',
        context: detail ? `${document.type === 'article' ? 'Článok' : 'Poznámka'}: ${detail}` : 'Väzba na text',
        availability: link.importAvailability || 'unchecked'
      });
    });
  });
  return rows;
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

function sourceAvailabilitySummary(rows) {
  const counts = rows.reduce((result, row) => {
    result[row.availability] = (result[row.availability] || 0) + 1;
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
  const rows = sourceLinkRows(preview);
  const libraryCount = (preview.librarySourceLinks || []).length;
  const documentCount = rows.length - libraryCount;
  dom.markdownImportSourceItems.replaceChildren();
  dom.markdownImportSourceLinks.hidden = !rows.length;
  if (!rows.length) return;

  const parts = [];
  if (libraryCount) parts.push(`${libraryCount} ku knižnici`);
  if (documentCount) parts.push(`${documentCount} k textom`);
  dom.markdownImportSourceSummary.textContent = `Obnoví sa ${parts.join(' · ')} · ${sourceAvailabilitySummary(rows)}.`;
  rows.forEach((link) => {
    const row = document.createElement('div');
    row.className = `markdown-import-source-item is-${link.availability}`;
    const type = document.createElement('span');
    type.textContent = link.type;
    const title = document.createElement('strong');
    title.textContent = link.title;
    const context = document.createElement('small');
    context.textContent = link.context;
    const availability = document.createElement('em');
    availability.textContent = sourceAvailabilityLabel(link.availability);
    row.append(type, title, context, availability);
    dom.markdownImportSourceItems.append(row);
  });
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
  const sourceLinkRowsPreview = sourceLinkRows(preview);
  const sourceLinks = sourceLinkRowsPreview.length;
  const unavailableSourceLinks = sourceLinkRowsPreview.filter((link) => link.availability !== 'available').length;
  dom.markdownImportItems.hidden = !view.items.length;
  dom.markdownImportItemsResizer.hidden = !view.items.length || !sourceLinks.length;
  fitDialogResizableSection(dom.markdownImportItems);
  fitDialogResizableSection(dom.markdownImportSourceItems);
  const warnings = [...new Set([...(preview.warnings || []), ...(view.warnings || [])])];
  const readyMessage = sourceLinks
    ? unavailableSourceLinks
      ? `Import vytvorí iba nové položky. ${unavailableSourceLinks} väzieb zdrojov sa neobnoví alebo ich nebolo možné overiť.`
      : `Import vytvorí iba nové položky a obnoví ${sourceLinks} väzieb zdrojov; existujúce texty nemení.`
    : 'Import vytvorí iba nové položky; existujúce texty nemení.';
  setPreviewStatus(warnings.length ? warnings.join(' ') : readyMessage, Boolean(warnings.length));
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
    pendingImport = await prepareMarkdownImport(file);
    await checkImportSourceAvailability(pendingImport);
    renderPreview(pendingImport);
  } catch (error) {
    setPreviewStatus(error?.message || 'Markdown sa nepodarilo spracovať.', true);
  }
}

async function confirmImport() {
  if (!pendingImport || !importTarget) return;
  dom.markdownImportConfirm.disabled = true;
  setPreviewStatus(sourceLinkRows(pendingImport).length ? 'Pridávam nové položky a obnovujem väzby zdrojov...' : 'Pridávam nové položky...');
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

export function requestMarkdownImport({ libraryName = '', parentId = '', destinationLabel = 'knižnice', previewAdapter = null, onConfirm }) {
  importTarget = { parentId, destinationLabel, previewAdapter, onConfirm };
  pendingImport = null;
  dom.markdownImportInput.value = '';
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
