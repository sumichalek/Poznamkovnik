import { apiRequest } from './api.js';
import { dom } from './dom.js';
import { fitDialogResizableSection, installDialogBackdropClose } from './dialogs.js';
import {
  addSourceAssets,
  createAssetCollector,
  downloadMarkdownArchive
} from './markdown-archive.js';
import { importedSourceSnapshot, readImportEntries } from './markdown-import.js';
import {
  copyImportedSources,
  resolvedImportedSourceId
} from './imported-sources.js';
import { sourceSnapshotManifest } from './markdown-export.js';
import {
  loadCompleteSource,
  parseSourcePackageRelations,
  restoreImportedSourceRelations,
  sourcePackageRelations
} from './source-transfer.js';

const COLLECTION_PACKAGE_PATH = '.poznamkovnik-source-collection.json';
const MAX_MANIFEST_BYTES = 4 * 1024 * 1024;
const MAX_COLLECTIONS = 500;
const MAX_SOURCES = 500;

let pendingImport = null;
let beforeImport = async () => true;
let importedCallback = async () => {};

function text(value, maximum = 300) {
  return String(value || '').trim().slice(0, maximum);
}

function filename(value, fallback = 'zbierka-zdrojov') {
  return text(value, 120)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLocaleLowerCase('sk') || fallback;
}

function uniqueById(items) {
  const seen = new Set();
  return items.filter((item) => {
    if (!item?.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

async function loadCollectionSubtree(rootId) {
  const collections = [];
  const memberships = [];
  const sourceIds = new Set();
  const visited = new Set();

  async function visit(collectionId) {
    if (!collectionId || visited.has(collectionId)) return;
    visited.add(collectionId);
    const detail = await apiRequest(`/source-collections/${encodeURIComponent(collectionId)}`);
    const collection = detail.collection;
    if (!collection?.id) throw new Error('Zbierku sa nepodarilo načítať.');
    collections.push({
      id: collection.id,
      parentId: collection.parentId || '',
      title: collection.title || 'Bez názvu'
    });
    (detail.sources || []).forEach((source) => {
      if (!source?.id) return;
      sourceIds.add(source.id);
      memberships.push({ collectionId: collection.id, sourceId: source.id });
    });
    for (const child of detail.children || []) await visit(child.id);
  }

  await visit(rootId);
  return { collections, memberships, sourceIds: [...sourceIds] };
}

async function exportSourceCollection(collection) {
  if (!collection?.id) return;
  const subtree = await loadCollectionSubtree(collection.id);
  const sources = await Promise.all(subtree.sourceIds.map((sourceId) => loadCompleteSource(sourceId)));
  const collector = createAssetCollector();
  const assets = await addSourceAssets(sources, collector);
  const manifest = {
    format: 'poznamkovnik-source-collection-package',
    version: 1,
    rootCollectionId: collection.id,
    collections: subtree.collections,
    collectionSources: subtree.memberships,
    sources: sourceSnapshotManifest(sources),
    sourceRelations: sources.map((source) => ({ sourceId: source.id, relations: sourcePackageRelations(source) }))
  };
  const readme = [
    `# ${collection.title}`,
    '',
    'Prenosový balík zbierky zdrojov pre Poznámkovník.',
    '',
    'Obsahuje celú vnorenú vetvu zbierok, zdroje, ich prílohy a údaje na obnovenie väzieb.'
  ].join('\n').concat('\n');
  await downloadMarkdownArchive(
    `${filename(collection.title)}-zbierka-zdrojov-poznamkovnik.zip`,
    [
      { name: 'README.md', content: readme },
      { name: COLLECTION_PACKAGE_PATH, content: JSON.stringify(manifest, null, 2).concat('\n') }
    ],
    collector,
    assets
  );
}

export function exportSourceCollectionPackage(collection) {
  return exportSourceCollection(collection).catch((error) => {
    window.alert(error?.message || 'Zbierku zdrojov sa nepodarilo vyexportovať.');
  });
}

function validateCollections(manifest) {
  const rawCollections = Array.isArray(manifest?.collections) ? manifest.collections.slice(0, MAX_COLLECTIONS) : [];
  const collectionMap = new Map();
  rawCollections.forEach((item) => {
    const id = text(item?.id, 160);
    const title = text(item?.title, 160);
    if (id && title && !collectionMap.has(id)) collectionMap.set(id, { id, title, parentId: text(item?.parentId, 160) });
  });
  const rootId = text(manifest?.rootCollectionId, 160);
  if (!rootId || !collectionMap.has(rootId)) throw new Error('Balík neobsahuje platnú koreňovú zbierku.');

  const childMap = new Map();
  collectionMap.forEach((collection) => {
    if (!collection.parentId || !collectionMap.has(collection.parentId) || collection.parentId === collection.id) return;
    const children = childMap.get(collection.parentId) || [];
    children.push(collection);
    childMap.set(collection.parentId, children);
  });
  childMap.forEach((children) => children.sort((left, right) => left.title.localeCompare(right.title, 'sk')));

  const ordered = [];
  const visited = new Set();
  function visit(collectionId, depth = 0) {
    if (visited.has(collectionId)) return;
    visited.add(collectionId);
    const collection = collectionMap.get(collectionId);
    if (!collection) return;
    ordered.push({ ...collection, depth, parentId: collectionId === rootId ? '' : collection.parentId });
    (childMap.get(collectionId) || []).forEach((child) => visit(child.id, depth + 1));
  }
  visit(rootId);
  if (!ordered.length) throw new Error('Balík obsahuje neplatnú štruktúru zbierok.');
  return { rootId, collections: ordered, collectionIds: new Set(ordered.map((item) => item.id)) };
}

function packageAssets(entries) {
  return new Map(entries
    .filter((entry) => entry.path !== COLLECTION_PACKAGE_PATH && entry.path.toLocaleLowerCase('sk') !== 'readme.md')
    .map((entry) => [entry.path, { ...entry }]));
}

async function prepareCollectionImport(file) {
  const entries = await readImportEntries(file);
  const manifestEntry = entries.find((entry) => entry.path === COLLECTION_PACKAGE_PATH);
  if (!manifestEntry) throw new Error('ZIP neobsahuje prenosový balík zbierky zdrojov.');
  if (manifestEntry.blob.size > MAX_MANIFEST_BYTES) throw new Error('Prenosový balík má príliš veľký popis obsahu.');
  let manifest;
  try {
    manifest = JSON.parse(await manifestEntry.blob.text());
  } catch {
    throw new Error('Prenosový balík má neplatný popis obsahu.');
  }
  if (manifest?.format !== 'poznamkovnik-source-collection-package') {
    throw new Error('ZIP neobsahuje podporovaný prenosový balík zbierky zdrojov.');
  }

  const tree = validateCollections(manifest);
  const snapshots = uniqueById((Array.isArray(manifest.sources) ? manifest.sources : [])
    .slice(0, MAX_SOURCES)
    .map(importedSourceSnapshot)
    .filter(Boolean));
  const snapshotMap = new Map(snapshots.map((source) => [source.id, source]));
  const memberships = [];
  const pairSet = new Set();
  (Array.isArray(manifest.collectionSources) ? manifest.collectionSources : []).slice(0, MAX_SOURCES * 8).forEach((item) => {
    const collectionId = text(item?.collectionId, 160);
    const sourceId = text(item?.sourceId, 160);
    const pair = `${collectionId}\u0000${sourceId}`;
    if (!tree.collectionIds.has(collectionId) || !snapshotMap.has(sourceId) || pairSet.has(pair)) return;
    pairSet.add(pair);
    memberships.push({ collectionId, sourceId });
  });
  const relationMap = new Map();
  (Array.isArray(manifest.sourceRelations) ? manifest.sourceRelations : []).slice(0, MAX_SOURCES).forEach((item) => {
    const sourceId = text(item?.sourceId, 160);
    if (snapshotMap.has(sourceId) && !relationMap.has(sourceId)) relationMap.set(sourceId, parseSourcePackageRelations(item?.relations));
  });
  const existingResult = await apiRequest('/sources');
  const existingIds = new Set((existingResult.sources || []).map((source) => source.id));
  const sourceLinks = snapshots.map((source) => ({
    sourceId: source.id,
    title: source.title,
    importAvailability: existingIds.has(source.id) ? 'available' : 'missing-source'
  }));
  const sourceActions = Object.fromEntries(sourceLinks.map((link) => [link.sourceId, 'copy']));
  return {
    fileName: file.name,
    tree,
    snapshots,
    snapshotMap,
    memberships,
    relationMap,
    sourceLinks,
    sourceActions,
    assets: packageAssets(entries)
  };
}

function importSummary(preview) {
  const collections = preview.tree.collections.length;
  const sources = preview.snapshots.length;
  const files = preview.snapshots.reduce((count, source) => count + (source.files?.length || 0), 0);
  return [
    `${collections} ${collections === 1 ? 'zbierka' : collections < 5 ? 'zbierky' : 'zbierok'}`,
    `${sources} ${sources === 1 ? 'zdroj' : sources < 5 ? 'zdroje' : 'zdrojov'}`,
    files ? `${files} ${files === 1 ? 'súbor' : files < 5 ? 'súbory' : 'súborov'}` : ''
  ].filter(Boolean).join(' · ');
}

function createCollectionTreeItem(collection) {
  const row = document.createElement('div');
  row.className = 'source-collection-transfer-tree-item';
  row.style.setProperty('--source-collection-import-depth', String(collection.depth));
  const marker = document.createElement('span');
  marker.textContent = collection.depth ? 'Podzbierka' : 'Koreň';
  const title = document.createElement('strong');
  title.textContent = collection.title;
  row.append(marker, title);
  return row;
}

function sourceUsageLabel(preview, sourceId) {
  const count = preview.memberships.filter((item) => item.sourceId === sourceId).length;
  return `${count || 0} ${count === 1 ? 'zbierka' : count < 5 ? 'zbierky' : 'zbierok'}`;
}

function relationCount(preview, sourceId) {
  const relations = preview.relationMap.get(sourceId) || {};
  return Object.values(relations).reduce((count, entries) => count + (Array.isArray(entries) ? entries.length : 0), 0);
}

function renderSourceRows(preview) {
  dom.sourceCollectionTransferImportSources.replaceChildren();
  preview.sourceLinks.forEach((link) => {
    const source = preview.snapshotMap.get(link.sourceId);
    const row = document.createElement('div');
    row.className = 'source-collection-transfer-source';
    const usage = document.createElement('span');
    usage.textContent = sourceUsageLabel(preview, link.sourceId);
    const details = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = source.title;
    const detail = document.createElement('small');
    const files = source.files?.length || 0;
    const relations = relationCount(preview, link.sourceId);
    detail.textContent = [source.kind, files ? `${files} príloh` : '', relations ? `${relations} väzieb` : ''].filter(Boolean).join(' · ') || 'Zdroj';
    details.append(title, detail);
    const action = document.createElement('select');
    action.className = 'markdown-import-source-action';
    action.dataset.sourceCollectionTransferAction = link.sourceId;
    const copy = new Option('Vytvoriť kópiu zdroja', 'copy');
    action.append(copy);
    if (link.importAvailability === 'available') action.append(new Option('Použiť existujúci zdroj', 'existing'));
    action.append(new Option('Vynechať zo zbierky', 'skip'));
    action.value = preview.sourceActions[link.sourceId] || 'copy';
    row.append(usage, details, action);
    dom.sourceCollectionTransferImportSources.append(row);
  });
}

function renderCollectionImport(preview) {
  const summary = importSummary(preview);
  dom.sourceCollectionTransferImportDescription.textContent = `Nič ešte nebolo uložené. Pridá sa ${summary}.`;
  dom.sourceCollectionTransferImportSummary.textContent = summary;
  dom.sourceCollectionTransferImportTree.replaceChildren(...preview.tree.collections.map(createCollectionTreeItem));
  renderSourceRows(preview);
  dom.sourceCollectionTransferImportStatus.textContent = 'Vytvorí sa nová koreňová zbierka. Existujúce zbierky ani zdroje sa nezmenia.';
  dom.sourceCollectionTransferImportConfirm.disabled = false;
  fitDialogResizableSection(dom.sourceCollectionTransferImportTree);
  fitDialogResizableSection(dom.sourceCollectionTransferImportSourcesSection);
}

function closeImportDialog() {
  if (dom.sourceCollectionTransferImportDialog.open) dom.sourceCollectionTransferImportDialog.close();
  else pendingImport = null;
}

function requestImport() {
  dom.sourceCollectionTransferInput.value = '';
  dom.sourceCollectionTransferInput.click();
}

async function handleImportFile() {
  const file = dom.sourceCollectionTransferInput.files?.[0];
  if (!file) return;
  pendingImport = null;
  dom.sourceCollectionTransferImportConfirm.disabled = true;
  dom.sourceCollectionTransferImportDescription.textContent = 'Kontrolujem štruktúru zbierok a pripravujem náhľad...';
  dom.sourceCollectionTransferImportSummary.textContent = '';
  dom.sourceCollectionTransferImportTree.replaceChildren();
  dom.sourceCollectionTransferImportSources.replaceChildren();
  dom.sourceCollectionTransferImportStatus.textContent = '';
  dom.sourceCollectionTransferImportStatus.classList.remove('is-error');
  if (!dom.sourceCollectionTransferImportDialog.open) dom.sourceCollectionTransferImportDialog.showModal();
  try {
    pendingImport = await prepareCollectionImport(file);
    renderCollectionImport(pendingImport);
  } catch (error) {
    dom.sourceCollectionTransferImportStatus.textContent = error?.message || 'Balík zbierky sa nepodarilo spracovať.';
    dom.sourceCollectionTransferImportStatus.classList.add('is-error');
  }
}

function selectSourceAction(event) {
  const sourceId = event.target.dataset.sourceCollectionTransferAction;
  if (!pendingImport || !sourceId) return;
  pendingImport.sourceActions[sourceId] = event.target.value;
}

function warningForCollection(title) {
  return `Zdroj sa nepodarilo zaradiť do zbierky „${title}“.`;
}

async function confirmImport() {
  if (!pendingImport) return;
  dom.sourceCollectionTransferImportConfirm.disabled = true;
  dom.sourceCollectionTransferImportStatus.textContent = 'Vytváram zbierky, prenášam zdroje a prílohy...';
  try {
    if (!(await beforeImport())) throw new Error('Rozpracovaný zdroj sa nepodarilo uložiť.');
    const copyResult = await copyImportedSources({
      links: pendingImport.sourceLinks,
      sourceSnapshots: pendingImport.snapshots,
      sourceAssets: pendingImport.assets,
      sourceActions: pendingImport.sourceActions
    });
    const warnings = [...copyResult.warnings];
    const collectionIds = new Map();
    for (const collection of pendingImport.tree.collections) {
      const parentId = collection.parentId ? collectionIds.get(collection.parentId) || '' : '';
      const result = await apiRequest('/source-collections', {
        method: 'POST',
        body: { id: crypto.randomUUID(), title: collection.title, parentId }
      });
      collectionIds.set(collection.id, result.collection.id);
    }
    for (const membership of pendingImport.memberships) {
      const collectionId = collectionIds.get(membership.collectionId);
      const link = pendingImport.sourceLinks.find((item) => item.sourceId === membership.sourceId);
      const sourceId = resolvedImportedSourceId(link, pendingImport.sourceActions, copyResult);
      if (!collectionId || !sourceId) continue;
      try {
        await apiRequest(`/source-collections/${encodeURIComponent(collectionId)}/sources/${encodeURIComponent(sourceId)}`, { method: 'PUT', body: {} });
      } catch {
        warnings.push(warningForCollection(pendingImport.tree.collections.find((item) => item.id === membership.collectionId)?.title || 'bez názvu'));
      }
    }
    for (const source of pendingImport.snapshots) {
      if (pendingImport.sourceActions[source.id] !== 'copy') continue;
      const sourceId = resolvedImportedSourceId({ sourceId: source.id }, pendingImport.sourceActions, copyResult);
      if (!sourceId) continue;
      const relations = pendingImport.relationMap.get(source.id);
      if (!relations) continue;
      warnings.push(...await restoreImportedSourceRelations(sourceId, {
        source,
        relations: { ...relations, collections: [] }
      }, copyResult));
    }
    const rootCollectionId = collectionIds.get(pendingImport.tree.rootId);
    closeImportDialog();
    await importedCallback(rootCollectionId, [...new Set(warnings)]);
    if (warnings.length) window.alert(`Zbierka bola importovaná, ale niektoré väzby sa nepodarilo obnoviť:\n\n${warnings.slice(0, 10).join('\n')}${warnings.length > 10 ? '\n…' : ''}`);
  } catch (error) {
    dom.sourceCollectionTransferImportStatus.textContent = error?.message || 'Zbierku zdrojov sa nepodarilo importovať.';
    dom.sourceCollectionTransferImportStatus.classList.add('is-error');
    dom.sourceCollectionTransferImportConfirm.disabled = false;
  }
}

export function initializeSourceCollectionTransfer({ saveCurrent = async () => true, onImported = async () => {} } = {}) {
  beforeImport = saveCurrent;
  importedCallback = onImported;
  dom.sourceCollectionTransferImportButton.addEventListener('click', requestImport);
  dom.sourceCollectionTransferInput.addEventListener('change', () => void handleImportFile());
  dom.sourceCollectionTransferImportCancel.addEventListener('click', closeImportDialog);
  dom.sourceCollectionTransferImportConfirm.addEventListener('click', () => void confirmImport());
  dom.sourceCollectionTransferImportSources.addEventListener('change', selectSourceAction);
  dom.sourceCollectionTransferImportDialog.addEventListener('close', () => {
    pendingImport = null;
    dom.sourceCollectionTransferInput.value = '';
  });
  installDialogBackdropClose(dom.sourceCollectionTransferImportDialog, closeImportDialog);
}
