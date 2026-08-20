import { apiRequest } from './api.js';
import { dom } from './dom.js';
import { installDialogBackdropClose } from './dialogs.js';
import {
  addSourceAssets,
  createAssetCollector,
  downloadMarkdownArchive,
  downloadMarkdownBundle
} from './markdown-archive.js';
import {
  documentTitle,
  importedSourceSnapshot,
  parseFrontmatter,
  readImportEntries
} from './markdown-import.js';
import {
  copyImportedSources,
  resolvedImportedSourceFileId,
  resolvedImportedSourceId
} from './imported-sources.js';
import { sourceSnapshotManifest } from './markdown-export.js';

const SOURCE_PACKAGE_PATH = '.poznamkovnik-source.json';
const MAX_MANIFEST_BYTES = 2 * 1024 * 1024;
const sourceKinds = new Set(['source', 'article', 'book', 'web', 'dataset', 'attachment']);

let exportSourceId = '';
let pendingImport = null;
let beforeImport = async () => true;
let importedCallback = async () => {};

function text(value, maximum = 300) {
  return String(value || '').trim().slice(0, maximum);
}

function sourceFilename(value, fallback = 'zdroj') {
  return text(value, 120)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLocaleLowerCase('sk') || fallback;
}

export function sourcePackageRelations(source) {
  return {
    collections: (source.collections || []).map((item) => ({ id: text(item.id, 160), title: text(item.title, 160) })).filter((item) => item.id),
    libraries: (source.libraries || []).map((item) => ({ id: text(item.id, 160), title: text(item.name, 160), note: text(item.note, 2_000) })).filter((item) => item.id),
    elements: (source.elements || []).map((item) => ({
      id: text(item.id, 160),
      title: text(item.title, 240),
      libraryName: text(item.libraryName, 160),
      relationType: text(item.relationType, 40) || 'reference',
      sourceFileId: text(item.sourceFileId, 160),
      locator: text(item.locator, 300),
      label: text(item.label, 300),
      note: text(item.note, 2_000)
    })).filter((item) => item.id),
    annotations: (source.annotations || []).map((item) => ({
      sourceFileId: text(item.sourceFileId, 160),
      elementId: text(item.elementId, 160),
      elementTitle: text(item.elementTitle, 240),
      quote: text(item.quote, 10_000),
      locator: text(item.locator, 300),
      note: text(item.note, 5_000)
    })).filter((item) => item.sourceFileId && (item.quote || item.note)),
    tasks: (source.tasks || []).map((item) => ({ id: text(item.id, 160), title: text(item.title, 240) })).filter((item) => item.id),
    calendarEvents: (source.calendarEvents || []).map((item) => ({ id: text(item.id, 160), title: text(item.title, 240) })).filter((item) => item.id)
  };
}

function sourceRelationRows(relations) {
  const rows = [];
  (relations.collections || []).forEach((item) => rows.push({ type: 'Zbierka', title: item.title || 'Zbierka', detail: 'Zaradenie zdroja' }));
  (relations.libraries || []).forEach((item) => rows.push({ type: 'Knižnica', title: item.title || 'Knižnica', detail: item.note || 'Spoločný zdroj knižnice' }));
  (relations.elements || []).forEach((item) => rows.push({ type: 'Text', title: item.title || 'Článok alebo poznámka', detail: [item.libraryName, item.locator].filter(Boolean).join(' · ') || item.relationType }));
  (relations.annotations || []).forEach((item) => rows.push({ type: 'Anotácia', title: item.elementTitle || 'Anotácia prílohy', detail: item.locator || item.note || item.quote }));
  (relations.tasks || []).forEach((item) => rows.push({ type: 'Úloha', title: item.title || 'Úloha', detail: 'Väzba na zdroj' }));
  (relations.calendarEvents || []).forEach((item) => rows.push({ type: 'Kalendár', title: item.title || 'Udalosť', detail: 'Väzba na zdroj' }));
  return rows;
}

function markdownEscape(value) {
  return JSON.stringify(String(value || ''));
}

function sourceMarkdown(source) {
  const metadata = source.metadata || {};
  const files = source.files || [];
  const lines = [
    '---',
    'type: source',
    `title: ${markdownEscape(source.title)}`,
    `kind: ${markdownEscape(source.kind || 'source')}`,
    `author: ${markdownEscape(metadata.author || '')}`,
    `year: ${markdownEscape(metadata.year || '')}`,
    `url: ${markdownEscape(metadata.url || '')}`,
    `tags: ${JSON.stringify(Array.isArray(source.tags) ? source.tags : [])}`,
    '---',
    '',
    `# ${source.title}`
  ];
  if (source.description) lines.push('', source.description);
  if (files.length) {
    lines.push('', '## Prílohy', '');
    files.forEach((file) => lines.push(`- ${file.originalName}`));
  }
  return lines.join('\n').concat('\n');
}

export async function loadCompleteSource(sourceId) {
  const result = await apiRequest(`/sources/${encodeURIComponent(sourceId)}`);
  return result.source;
}

async function downloadSourcePackage(sourceId) {
  const source = await loadCompleteSource(sourceId);
  const collector = createAssetCollector();
  const assetStatus = await addSourceAssets([source], collector);
  const snapshot = sourceSnapshotManifest([source])[0];
  if (!snapshot) throw new Error('Zdroj nemá platné údaje na export.');
  const manifest = JSON.stringify({
    format: 'poznamkovnik-source-package',
    version: 1,
    source: snapshot,
    relations: sourcePackageRelations(source)
  }, null, 2).concat('\n');
  const readme = [
    `# ${source.title}`,
    '',
    'Prenosový balík zdroja pre Poznámkovník.',
    '',
    'Balík obsahuje metadáta, priložené súbory, anotácie a údaje na obnovenie väzieb v Poznámkovníku.'
  ].join('\n').concat('\n');
  await downloadMarkdownArchive(
    `${sourceFilename(source.title)}-zdroj-poznamkovnik.zip`,
    [
      { name: 'README.md', content: readme },
      { name: SOURCE_PACKAGE_PATH, content: manifest }
    ],
    collector,
    assetStatus
  );
}

async function downloadSourceMarkdown(sourceId) {
  const source = await loadCompleteSource(sourceId);
  await downloadMarkdownBundle(`${sourceFilename(source.title)}-zdroj.md`, sourceMarkdown(source), createAssetCollector(), { missing: [], skipped: [] });
}

function setExportBusy(busy) {
  dom.sourcePackageExport.disabled = busy;
  dom.sourceMarkdownExport.disabled = busy;
  dom.sourceExportCancel.disabled = busy;
}

function closeSourceExportDialog() {
  if (dom.sourceExportDialog.open) dom.sourceExportDialog.close();
  else exportSourceId = '';
}

export function openSourceExportDialog(source) {
  if (!source?.id) return;
  exportSourceId = source.id;
  dom.sourceExportDescription.textContent = `Zdroj „${source.title || 'Zdroj'}“ sa vyexportuje až po zvolení formátu.`;
  if (!dom.sourceExportDialog.open) dom.sourceExportDialog.showModal();
}

async function exportSource(format) {
  if (!exportSourceId) return;
  setExportBusy(true);
  try {
    if (format === 'package') await downloadSourcePackage(exportSourceId);
    else await downloadSourceMarkdown(exportSourceId);
    closeSourceExportDialog();
  } catch (error) {
    window.alert(error?.message || 'Zdroj sa nepodarilo vyexportovať.');
  } finally {
    setExportBusy(false);
  }
}

export function parseSourcePackageRelations(value) {
  const relations = value && typeof value === 'object' ? value : {};
  const normalize = (items, map) => (Array.isArray(items) ? items : []).slice(0, 500).map(map).filter(Boolean);
  return {
    collections: normalize(relations.collections, (item) => {
      const id = text(item?.id, 160);
      return id ? { id, title: text(item?.title, 160) } : null;
    }),
    libraries: normalize(relations.libraries, (item) => {
      const id = text(item?.id, 160);
      return id ? { id, title: text(item?.title, 160), note: text(item?.note, 2_000) } : null;
    }),
    elements: normalize(relations.elements, (item) => {
      const id = text(item?.id, 160);
      return id ? {
        id,
        title: text(item?.title, 240),
        libraryName: text(item?.libraryName, 160),
        relationType: ['reference', 'citation', 'attachment', 'evidence', 'counterargument', 'derived'].includes(item?.relationType) ? item.relationType : 'reference',
        sourceFileId: text(item?.sourceFileId, 160),
        locator: text(item?.locator, 300),
        label: text(item?.label, 300),
        note: text(item?.note, 2_000)
      } : null;
    }),
    annotations: normalize(relations.annotations, (item) => {
      const sourceFileId = text(item?.sourceFileId, 160);
      const quote = text(item?.quote, 10_000);
      const note = text(item?.note, 5_000);
      return sourceFileId && (quote || note) ? {
        sourceFileId,
        elementId: text(item?.elementId, 160),
        elementTitle: text(item?.elementTitle, 240),
        quote,
        locator: text(item?.locator, 300),
        note
      } : null;
    }),
    tasks: normalize(relations.tasks, (item) => {
      const id = text(item?.id, 160);
      return id ? { id, title: text(item?.title, 240) } : null;
    }),
    calendarEvents: normalize(relations.calendarEvents, (item) => {
      const id = text(item?.id, 160);
      return id ? { id, title: text(item?.title, 240) } : null;
    })
  };
}

function withoutTitle(markdown, title) {
  const lines = String(markdown || '').replace(/\r\n?/g, '\n').split('\n');
  const index = lines.findIndex((line) => line.trim());
  if (index !== -1 && lines[index].replace(/^#\s+/, '').trim() === title) lines.splice(index, 1);
  const attachments = lines.findIndex((line) => /^##\s+Prílohy\s*$/i.test(line));
  if (attachments !== -1) lines.splice(attachments);
  return lines.join('\n').trim().slice(0, 10_000);
}

async function prepareSourceImport(file) {
  const entries = await readImportEntries(file);
  const manifestEntry = entries.find((entry) => entry.path === SOURCE_PACKAGE_PATH);
  if (manifestEntry) {
    if (manifestEntry.blob.size > MAX_MANIFEST_BYTES) throw new Error('Prenosový balík zdroja má príliš veľký popis obsahu.');
    let manifest;
    try {
      manifest = JSON.parse(await manifestEntry.blob.text());
    } catch {
      throw new Error('Prenosový balík zdroja má neplatný popis obsahu.');
    }
    if (manifest?.format !== 'poznamkovnik-source-package') throw new Error('ZIP neobsahuje podporovaný prenosový balík zdroja.');
    const source = importedSourceSnapshot(manifest.source);
    if (!source) throw new Error('Prenosový balík neobsahuje platný zdroj.');
    const assets = new Map(entries
      // README is documentation for people. Every other file can be a real
      // attachment, including a Markdown attachment with a .md extension.
      .filter((entry) => entry.path !== SOURCE_PACKAGE_PATH && entry.path.toLocaleLowerCase('sk') !== 'readme.md')
      .map((entry) => [entry.path, { ...entry }]));
    return { source, relations: parseSourcePackageRelations(manifest.relations), assets, sourceManifest: true, sourceName: file.name };
  }

  const markdownEntries = entries.filter((entry) => /\.(?:md|markdown|mdown|mkdn)$/i.test(entry.path) && entry.path.toLocaleLowerCase('sk') !== 'readme.md');
  if (markdownEntries.length !== 1) throw new Error('Pre import zdroja vyber jeden Markdown súbor alebo prenosový ZIP balík.');
  const entry = markdownEntries[0];
  const { metadata, body } = parseFrontmatter(await entry.blob.text());
  if (metadata.type && metadata.type !== 'source') throw new Error('Vybraný Markdown neoznačuje zdroj.');
  const fallback = entry.path.split('/').at(-1).replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
  const title = text(metadata.title || documentTitle(body, fallback), 240) || 'Importovaný zdroj';
  const source = importedSourceSnapshot({
    id: crypto.randomUUID(),
    title,
    kind: sourceKinds.has(metadata.kind) ? metadata.kind : 'source',
    description: withoutTitle(body, title),
    metadata: { author: text(metadata.author, 240), year: text(metadata.year, 12), url: text(metadata.url, 500) },
    tags: Array.isArray(metadata.tags) ? metadata.tags : [],
    files: []
  });
  if (!source) throw new Error('Markdown zdroja nemá platný názov.');
  return { source, relations: parseSourcePackageRelations(), assets: new Map(), sourceManifest: false, sourceName: file.name };
}

function sourceImportSummary(preview) {
  const files = preview.source.files.length;
  const relations = sourceRelationRows(preview.relations).length;
  return [`1 zdroj`, files ? `${files} ${files === 1 ? 'súbor' : 'súbory'}` : '', relations ? `${relations} väzieb` : ''].filter(Boolean).join(' · ');
}

function renderSourceImport(preview) {
  const snapshot = preview.source;
  const metadata = snapshot.metadata || {};
  dom.sourceTransferImportDescription.textContent = `Nič ešte nebolo uložené. Pridá sa ${sourceImportSummary(preview)}.`;
  dom.sourceTransferImportSummary.textContent = sourceImportSummary(preview);
  dom.sourceTransferImportItem.replaceChildren();
  const type = document.createElement('span');
  type.textContent = 'Zdroj';
  const copy = document.createElement('span');
  const title = document.createElement('strong');
  title.textContent = snapshot.title;
  const detail = document.createElement('small');
  detail.textContent = [snapshot.kind, metadata.author, metadata.year, metadata.url].filter(Boolean).join(' · ') || 'Metadáta zdroja';
  copy.append(title, detail);
  dom.sourceTransferImportItem.append(type, copy);
  dom.sourceTransferImportRelations.replaceChildren();
  const rows = sourceRelationRows(preview.relations);
  dom.sourceTransferImportRelationsSection.hidden = !rows.length;
  rows.slice(0, 120).forEach((relation) => {
    const row = document.createElement('div');
    row.className = 'source-transfer-relation';
    const typeCell = document.createElement('span');
    typeCell.textContent = relation.type;
    const target = document.createElement('strong');
    target.textContent = relation.title;
    const detailCell = document.createElement('small');
    detailCell.textContent = relation.detail || 'Väzba sa obnoví, ak cieľ existuje.';
    const action = document.createElement('em');
    action.textContent = 'Obnoviť, ak existuje';
    row.append(typeCell, target, detailCell, action);
    dom.sourceTransferImportRelations.append(row);
  });
  if (rows.length > 120) {
    const more = document.createElement('p');
    more.className = 'source-transfer-more';
    more.textContent = `A ďalších ${rows.length - 120} väzieb.`;
    dom.sourceTransferImportRelations.append(more);
  }
  dom.sourceTransferImportStatus.textContent = preview.sourceManifest
    ? 'Vytvorí sa nový zdroj. Prílohy sa skopírujú a väzby sa obnovia iba ku dostupným prvkom.'
    : 'Vytvorí sa nový zdroj bez príloh a väzieb.';
  dom.sourceTransferImportConfirm.disabled = false;
}

function closeSourceImportDialog() {
  if (dom.sourceTransferImportDialog.open) dom.sourceTransferImportDialog.close();
  else pendingImport = null;
}

function relationWarning(type, title) {
  return `Väzba ${type.toLocaleLowerCase('sk')} „${title || 'bez názvu'}“ nebola obnovená, pretože cieľ v tomto Poznámkovníku neexistuje.`;
}

export async function restoreImportedSourceRelations(sourceId, preview, copyResult) {
  const warnings = [];
  const relations = preview.relations;
  for (const collection of relations.collections) {
    try {
      await apiRequest(`/source-collections/${encodeURIComponent(collection.id)}/sources/${encodeURIComponent(sourceId)}`, { method: 'PUT', body: {} });
    } catch {
      warnings.push(relationWarning('zbierky', collection.title));
    }
  }
  for (const library of relations.libraries) {
    try {
      await apiRequest(`/sources/${encodeURIComponent(sourceId)}/libraries/${encodeURIComponent(library.id)}`, { method: 'PUT', body: { note: library.note } });
    } catch {
      warnings.push(relationWarning('knižnice', library.title));
    }
  }
  for (const element of relations.elements) {
    const sourceFileId = element.sourceFileId
      ? resolvedImportedSourceFileId({ sourceId: preview.source.id, sourceFileId: element.sourceFileId }, { [preview.source.id]: 'copy' }, copyResult)
      : '';
    if (element.sourceFileId && !sourceFileId) {
      warnings.push(`Väzba na text „${element.title || 'bez názvu'}“ vyžaduje prílohu, ktorá sa nepodarilo preniesť.`);
      continue;
    }
    try {
      await apiRequest(`/sources/${encodeURIComponent(sourceId)}/element-links`, {
        method: 'POST',
        body: { id: crypto.randomUUID(), elementId: element.id, sourceFileId, relationType: element.relationType, locator: element.locator, label: element.label, note: element.note }
      });
    } catch {
      warnings.push(relationWarning('textu', element.title));
    }
  }
  for (const annotation of relations.annotations) {
    const sourceFileId = resolvedImportedSourceFileId({ sourceId: preview.source.id, sourceFileId: annotation.sourceFileId }, { [preview.source.id]: 'copy' }, copyResult);
    if (!sourceFileId) {
      warnings.push('Anotácia sa neobnovila, pretože jej príloha sa nepodarilo preniesť.');
      continue;
    }
    const body = { id: crypto.randomUUID(), quote: annotation.quote, locator: annotation.locator, note: annotation.note };
    if (annotation.elementId) body.elementId = annotation.elementId;
    try {
      await apiRequest(`/sources/${encodeURIComponent(sourceId)}/files/${encodeURIComponent(sourceFileId)}/annotations`, { method: 'POST', body });
    } catch {
      if (!annotation.elementId) {
        warnings.push('Anotáciu sa nepodarilo obnoviť.');
        continue;
      }
      try {
        await apiRequest(`/sources/${encodeURIComponent(sourceId)}/files/${encodeURIComponent(sourceFileId)}/annotations`, {
          method: 'POST',
          body: { id: crypto.randomUUID(), quote: annotation.quote, locator: annotation.locator, note: annotation.note }
        });
        warnings.push(`Anotácia sa obnovila bez väzby na chýbajúci text „${annotation.elementTitle || 'bez názvu'}“.`);
      } catch {
        warnings.push('Anotáciu sa nepodarilo obnoviť.');
      }
    }
  }
  for (const task of relations.tasks) {
    try {
      await apiRequest(`/tasks/${encodeURIComponent(task.id)}/links`, { method: 'POST', body: { id: crypto.randomUUID(), targetType: 'source', targetId: sourceId } });
    } catch {
      warnings.push(relationWarning('úlohy', task.title));
    }
  }
  for (const event of relations.calendarEvents) {
    try {
      await apiRequest(`/calendar-events/${encodeURIComponent(event.id)}/links`, { method: 'POST', body: { id: crypto.randomUUID(), targetType: 'source', targetId: sourceId } });
    } catch {
      warnings.push(relationWarning('udalosti', event.title));
    }
  }
  return warnings;
}

async function confirmSourceImport() {
  if (!pendingImport) return;
  dom.sourceTransferImportConfirm.disabled = true;
  dom.sourceTransferImportStatus.textContent = 'Vytváram zdroj, prenášam súbory a obnovujem väzby...';
  try {
    if (!(await beforeImport())) throw new Error('Rozpracovaný zdroj sa nepodarilo uložiť.');
    const copyResult = await copyImportedSources({
      links: [{ sourceId: pendingImport.source.id, title: pendingImport.source.title, importAvailability: 'missing-source' }],
      sourceSnapshots: [pendingImport.source],
      sourceAssets: pendingImport.assets,
      sourceActions: { [pendingImport.source.id]: 'copy' }
    });
    const sourceId = resolvedImportedSourceId({ sourceId: pendingImport.source.id }, { [pendingImport.source.id]: 'copy' }, copyResult);
    if (!sourceId) throw new Error(copyResult.warnings[0] || 'Zdroj sa nepodarilo vytvoriť.');
    const warnings = [...copyResult.warnings, ...(await restoreImportedSourceRelations(sourceId, pendingImport, copyResult))];
    closeSourceImportDialog();
    await importedCallback(sourceId, [...new Set(warnings)]);
    if (warnings.length) window.alert(`Zdroj bol importovaný, ale niektoré väzby sa nepodarilo obnoviť:\n\n${warnings.slice(0, 10).join('\n')}${warnings.length > 10 ? '\n…' : ''}`);
  } catch (error) {
    dom.sourceTransferImportStatus.textContent = error?.message || 'Zdroj sa nepodarilo importovať.';
    dom.sourceTransferImportStatus.classList.add('is-error');
    dom.sourceTransferImportConfirm.disabled = false;
  }
}

async function handleSourceImportFile() {
  const file = dom.sourceTransferInput.files?.[0];
  if (!file) return;
  pendingImport = null;
  dom.sourceTransferImportConfirm.disabled = true;
  dom.sourceTransferImportRelations.replaceChildren();
  dom.sourceTransferImportRelationsSection.hidden = true;
  dom.sourceTransferImportDescription.textContent = 'Kontrolujem štruktúru a pripravujem náhľad...';
  dom.sourceTransferImportSummary.textContent = '';
  dom.sourceTransferImportStatus.textContent = '';
  dom.sourceTransferImportStatus.classList.remove('is-error');
  if (!dom.sourceTransferImportDialog.open) dom.sourceTransferImportDialog.showModal();
  try {
    pendingImport = await prepareSourceImport(file);
    renderSourceImport(pendingImport);
  } catch (error) {
    dom.sourceTransferImportStatus.textContent = error?.message || 'Súbor sa nepodarilo spracovať.';
    dom.sourceTransferImportStatus.classList.add('is-error');
  }
}

function requestSourceImport() {
  dom.sourceTransferInput.value = '';
  dom.sourceTransferInput.click();
}

export function initializeSourceTransfer({ saveCurrent = async () => true, onImported = async () => {} } = {}) {
  beforeImport = saveCurrent;
  importedCallback = onImported;
  dom.sourceTransferImportButton.addEventListener('click', requestSourceImport);
  dom.sourceTransferInput.addEventListener('change', () => void handleSourceImportFile());
  dom.sourceTransferImportCancel.addEventListener('click', closeSourceImportDialog);
  dom.sourceTransferImportConfirm.addEventListener('click', () => void confirmSourceImport());
  dom.sourceTransferImportDialog.addEventListener('close', () => {
    pendingImport = null;
    dom.sourceTransferInput.value = '';
  });
  installDialogBackdropClose(dom.sourceTransferImportDialog, closeSourceImportDialog);
  dom.sourceExportCancel.addEventListener('click', closeSourceExportDialog);
  dom.sourcePackageExport.addEventListener('click', () => void exportSource('package'));
  dom.sourceMarkdownExport.addEventListener('click', () => void exportSource('markdown'));
  dom.sourceExportDialog.addEventListener('close', () => {
    exportSourceId = '';
    setExportBusy(false);
  });
  installDialogBackdropClose(dom.sourceExportDialog, closeSourceExportDialog);
}
