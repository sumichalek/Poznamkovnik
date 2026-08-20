import { apiRequest, uploadSourceFile } from './api.js';
import { createAppIcon, setAppIcon, sourceFileIcon, sourceKindIcon } from './app-icons.js';
import { dom } from './dom.js';
import { state } from './state.js';
import { flushWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';
import { getSourceFileMaxBytes, sourceFileLimitLabel } from './preferences.js';
import { refreshSourceDetailResizeHandle } from './source-detail-resize.js';
import { refreshSourcePreviewResizeHandle } from './source-preview-resize.js';
import { readTagField, refreshTagSuggestions, setTagField } from './tags.js';
import { openRelationships } from './relationships.js';
import { initializeSourceTransfer, openSourceExportDialog } from './source-transfer.js';
import { exportSourceCollectionPackage, initializeSourceCollectionTransfer } from './source-collection-transfer.js';

const kindLabels = {
  source: 'Zdroj',
  article: 'Článok',
  book: 'Kniha',
  web: 'Web',
  dataset: 'Dáta',
  attachment: 'Príloha'
};

const relationLabels = {
  reference: 'Odkaz',
  citation: 'Citácia',
  attachment: 'Príloha',
  evidence: 'Dôkaz',
  counterargument: 'Protinázor',
  derived: 'Vychádza zo zdroja',
  annotation: 'Anotácia'
};

const TEXT_PREVIEW_MAX_BYTES = 2 * 1024 * 1024;

let sources = [];
let selectedSource = null;
let searchTimer = 0;
let panelPinned = false;
let previewSourceId = '';
let previewFileId = '';
let previewRequestId = 0;
let previewAnnotations = [];
let previewAnnotationsError = '';
let previewSelectedText = '';
let previewFullscreen = false;
let loadedSourcesQuery = null;
let loadingSourcesQuery = null;
let sourcesLoadPromise = null;
let sourcesLoadRequestId = 0;
let editorSourceMenuOpen = false;
let sourceFormBaseline = '';
let sourceOperationCount = 0;
let sourceIdleResolvers = [];
let sourceFileDropDepth = 0;
let sourceCollections = [];
let activeSourceCollectionId = '';
let activeSourceCollectionDetail = null;
let sourceCollectionFormMode = '';
let sourceCollectionFormBaseline = '';
let sourceDraftCollectionId = '';
let sourceBrowserError = '';
let lastSourceBrowserAction = null;
let pointerHandledSourceBrowserItem = null;

function notifySourcesChanged() {
  window.dispatchEvent(new Event('sources-changed'));
}

function activeElementTitle() {
  for (const items of Object.values(state.libraryElements)) {
    const item = items.find((entry) => entry.id === state.activeLibraryElementId);
    if (item) return item.title || (item.type === 'article' ? 'Nový článok' : 'Nová poznámka');
  }
  return '';
}

function syncSourceReturnButton() {
  const target = state.sourceReturnTarget;
  const visible = Boolean(target?.libraryId && target?.title);
  dom.sourceReturnButton.hidden = !visible;
  dom.sourceReturnLabel.textContent = visible ? `Späť na: ${target.title}` : '';
  dom.sourceReturnButton.title = visible ? `Vrátiť sa na ${target.title}` : '';
  dom.sourceReturnButton.setAttribute('aria-label', visible ? `Vrátiť sa na ${target.title}` : '');
}

export function setSourceReturnTarget(target = null) {
  const libraryId = String(target?.libraryId || '');
  const elementId = String(target?.elementId || '');
  const title = String(target?.title || '').trim();
  state.sourceReturnTarget = libraryId && title ? { libraryId, elementId, title } : null;
  syncSourceReturnButton();
}

export function clearSourceReturnTarget() {
  setSourceReturnTarget();
}

function sourceFormSnapshot() {
  return JSON.stringify({
    title: dom.sourceTitle.value.trim(),
    kind: dom.sourceKind.value,
    year: dom.sourceYear.value.trim(),
    author: dom.sourceAuthor.value.trim(),
    url: dom.sourceUrl.value.trim(),
    description: dom.sourceDescription.value.trim(),
    tags: readTagField(dom.sourceTags)
  });
}

function rememberSourceForm() {
  sourceFormBaseline = sourceFormSnapshot();
}

async function runSourceOperation(operation) {
  sourceOperationCount += 1;
  try {
    return await operation();
  } finally {
    sourceOperationCount -= 1;
    if (!sourceOperationCount) {
      sourceIdleResolvers.forEach((resolve) => resolve());
      sourceIdleResolvers = [];
    }
  }
}

export function waitForSourceOperations() {
  if (!sourceOperationCount) return Promise.resolve();
  return new Promise((resolve) => sourceIdleResolvers.push(resolve));
}

export function hasUnsavedSourceChanges() {
  const hasCollectionChanges =
    !dom.sourceCollectionForm.hidden && dom.sourceCollectionName.value.trim() !== sourceCollectionFormBaseline;
  return hasCollectionChanges || (!dom.sourceForm.hidden && sourceFormSnapshot() !== sourceFormBaseline);
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExtension(file) {
  const name = file?.originalName || '';
  const extension = name.split('.').at(-1);
  return extension && extension !== name ? extension.toUpperCase() : '';
}

function fileFormatLabel(file) {
  const extension = fileExtension(file);
  const knownFormats = {
    PDF: 'PDF',
    EPUB: 'EPUB',
    TXT: 'Text',
    MD: 'Markdown',
    DOC: 'Word',
    DOCX: 'Word',
    ODT: 'OpenDocument',
    XLS: 'Excel',
    XLSX: 'Excel',
    CSV: 'CSV',
    ODS: 'OpenDocument',
    JSON: 'JSON',
    HTML: 'HTML',
    HTM: 'HTML'
  };
  if (knownFormats[extension]) return knownFormats[extension];
  if (file?.mimeType?.startsWith('image/')) return 'Obrázok';
  if (file?.mimeType?.startsWith('text/')) return 'Text';
  return extension || 'Súbor';
}

function annotationCountLabel(count) {
  if (count === 1) return '1 anotácia';
  const lastTwo = count % 100;
  if (count % 10 >= 2 && count % 10 <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${count} anotácie`;
  return `${count} anotácií`;
}

function supportsInlinePreview(file) {
  return (
    file.mimeType === 'application/pdf' ||
    (file.mimeType.startsWith('image/') && file.mimeType !== 'image/svg+xml') ||
    file.mimeType.startsWith('text/') ||
    file.mimeType === 'application/json'
  );
}

function previewFallbackMessage(file) {
  const format = fileFormatLabel(file);
  if (file.sizeBytes > TEXT_PREVIEW_MAX_BYTES && file.mimeType.startsWith('text/')) {
    return 'Textový súbor je na vstavaný náhľad príliš veľký. Môžeš ho stiahnuť.';
  }
  if (format === 'EPUB') return 'EPUB si môžeš stiahnuť a otvoriť v čítačke elektronických kníh.';
  if (format === 'Word' || format === 'OpenDocument') return 'Dokument si môžeš stiahnuť a otvoriť v kancelárskom programe.';
  if (format === 'Excel' || format === 'CSV') return 'Tabuľku si môžeš stiahnuť a otvoriť v tabuľkovom programe.';
  return 'Pre tento formát zatiaľ nemáme vstavaný náhľad. Súbor môžeš stiahnuť.';
}

function setSourceFilesStatus(message = '', { error = false } = {}) {
  dom.sourceFilesStatus.textContent = message;
  dom.sourceFilesStatus.classList.toggle('is-error', error);
}

function setSourceFilesBusy(busy) {
  dom.sourceUploadButton.disabled = busy;
  dom.sourceFileDropzone.classList.toggle('is-busy', busy);
  dom.sourceFileDropzone.setAttribute('aria-disabled', String(busy));
}

function sourceFilesAreBusy() {
  return dom.sourceFileDropzone.getAttribute('aria-disabled') === 'true';
}

function sourceFileUrl(file, { download = false } = {}) {
  const suffix = download ? '?download=1' : '';
  return `/api/files/${encodeURIComponent(file.id)}${suffix}`;
}

function sourceAnnotationUrl(fileId = previewFileId, annotationId = '') {
  const path = `/sources/${encodeURIComponent(previewSourceId)}/files/${encodeURIComponent(fileId)}/annotations`;
  return annotationId ? `${path}/${encodeURIComponent(annotationId)}` : path;
}

function setSourcePreviewOpen(open) {
  if (!open) previewFullscreen = false;
  dom.sourcePreviewDock.classList.toggle('is-open', open);
  dom.sourcePreviewDock.setAttribute('aria-hidden', String(!open));
  syncSourcePreviewFullscreen();
  refreshSourcePreviewResizeHandle();
  updateTopbarVisibility();
}

export function isSourcePreviewOpen() {
  return dom.sourcePreviewDock.classList.contains('is-open');
}

export function isSourcePreviewFullscreen() {
  return previewFullscreen && isSourcePreviewOpen();
}

function syncSourcePreviewFullscreen() {
  const fullscreen = isSourcePreviewFullscreen();
  dom.sourcePreviewDock.classList.toggle('is-fullscreen', fullscreen);
  dom.sourcePreviewFullscreen.dataset.mode = fullscreen ? 'restore' : 'maximize';
  dom.sourcePreviewFullscreen.title = fullscreen ? 'Zobraziť vedľa detailu zdroja' : 'Celá plocha';
  dom.sourcePreviewFullscreen.setAttribute(
    'aria-label',
    fullscreen ? 'Zobraziť náhľad vedľa detailu zdroja' : 'Otvoriť náhľad na celej ploche'
  );
  setAppIcon(dom.sourcePreviewFullscreen.querySelector('.app-icon'), fullscreen ? 'minimize' : 'maximize');
}

export function toggleSourcePreviewFullscreen() {
  if (!isSourcePreviewOpen()) return;
  previewFullscreen = !previewFullscreen;
  syncSourcePreviewFullscreen();
  refreshSourcePreviewResizeHandle();
  updateTopbarVisibility();
}

export function exitSourcePreviewFullscreen() {
  if (!isSourcePreviewFullscreen()) return false;
  previewFullscreen = false;
  syncSourcePreviewFullscreen();
  refreshSourcePreviewResizeHandle();
  updateTopbarVisibility();
  return true;
}

function hideSourcePreviewViews() {
  dom.sourcePreviewFrame.hidden = true;
  dom.sourcePreviewFrame.removeAttribute('src');
  dom.sourcePreviewImage.hidden = true;
  dom.sourcePreviewImage.removeAttribute('src');
  dom.sourcePreviewImage.alt = '';
  dom.sourcePreviewText.hidden = true;
  dom.sourcePreviewText.textContent = '';
  dom.sourcePreviewFallback.hidden = true;
  dom.sourcePreviewFallbackMessage.textContent = '';
}

function clearSourcePreviewRelations() {
  dom.sourcePreviewRelations.hidden = true;
  dom.sourcePreviewRelationsCount.textContent = '';
  dom.sourcePreviewRelationsList.replaceChildren();
}

function setSourcePreviewAnnotationStatus(message = '', { error = false } = {}) {
  dom.sourcePreviewAnnotationStatus.textContent = message;
  dom.sourcePreviewAnnotationStatus.classList.toggle('is-error', error);
}

function clearSourcePreviewAnnotationForm() {
  dom.sourcePreviewAnnotationForm.hidden = true;
  dom.sourcePreviewAnnotationQuote.value = '';
  dom.sourcePreviewAnnotationQuote.setCustomValidity('');
  dom.sourcePreviewAnnotationLocator.value = '';
  dom.sourcePreviewAnnotationElement.replaceChildren();
  dom.sourcePreviewAnnotationNote.value = '';
  setSourcePreviewAnnotationStatus('');
}

function sourceAnnotationElements() {
  return Object.entries(state.libraryElements)
    .flatMap(([libraryId, items]) => {
      const library = state.libraries.find((entry) => entry.id === libraryId);
      return items
        .filter((item) => item.type === 'note' || item.type === 'article')
        .map((item) => ({ ...item, libraryId, libraryName: library?.name || 'Knižnica' }));
    })
    .sort((left, right) => {
      const library = left.libraryName.localeCompare(right.libraryName, 'sk');
      return library || left.title.localeCompare(right.title, 'sk');
    });
}

function renderSourceAnnotationElementOptions() {
  dom.sourcePreviewAnnotationElement.replaceChildren();
  const none = document.createElement('option');
  none.value = '';
  none.textContent = 'Bez priameho prepojenia';
  dom.sourcePreviewAnnotationElement.append(none);
  sourceAnnotationElements().forEach((element) => {
    const option = document.createElement('option');
    option.value = element.id;
    option.textContent = `${element.libraryName} / ${element.title}`;
    dom.sourcePreviewAnnotationElement.append(option);
  });
}

function captureSourcePreviewSelection() {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !selection.toString().trim()) return;
  if (!dom.sourcePreviewText.contains(selection.anchorNode) || !dom.sourcePreviewText.contains(selection.focusNode)) return;
  previewSelectedText = selection.toString().trim().slice(0, 10_000);
}

function openSourceAnnotationForm() {
  if (!previewSourceId || !previewFileId) return;
  renderSourceAnnotationElementOptions();
  dom.sourcePreviewAnnotationForm.hidden = false;
  dom.sourcePreviewAnnotationQuote.value = previewSelectedText;
  dom.sourcePreviewAnnotationLocator.value = '';
  dom.sourcePreviewAnnotationNote.value = '';
  dom.sourcePreviewAnnotationQuote.setCustomValidity('');
  setSourcePreviewAnnotationStatus('');
  dom.sourcePreviewAnnotationQuote.focus();
}

function renderSourcePreviewAnnotations() {
  dom.sourcePreviewAnnotationsList.replaceChildren();
  dom.sourcePreviewAnnotationsCount.textContent = previewAnnotations.length ? String(previewAnnotations.length) : '';

  if (previewAnnotationsError) {
    const error = document.createElement('p');
    error.className = 'source-preview-annotation-empty is-error';
    error.textContent = previewAnnotationsError;
    dom.sourcePreviewAnnotationsList.append(error);
    return;
  }

  if (!previewAnnotations.length) {
    const empty = document.createElement('p');
    empty.className = 'source-preview-annotation-empty';
    empty.textContent = 'Táto príloha zatiaľ nemá anotácie.';
    dom.sourcePreviewAnnotationsList.append(empty);
    return;
  }

  previewAnnotations.forEach((annotation) => {
    const row = document.createElement('article');
    row.className = 'source-preview-annotation';
    const copy = document.createElement('div');
    copy.className = 'source-preview-annotation-copy';

    if (annotation.quote) {
      const quote = document.createElement('p');
      quote.className = 'source-preview-annotation-quote';
      quote.textContent = `„${annotation.quote}“`;
      copy.append(quote);
    }
    if (annotation.locator) {
      const locator = document.createElement('p');
      locator.className = 'source-preview-annotation-locator';
      locator.textContent = annotation.locator;
      copy.append(locator);
    }
    if (annotation.note) {
      const note = document.createElement('p');
      note.className = 'source-preview-annotation-note';
      note.textContent = annotation.note;
      copy.append(note);
    }
    if (annotation.elementId && annotation.elementTitle) {
      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'source-preview-annotation-link';
      link.textContent = `${annotation.libraryName} / ${annotation.elementTitle}`;
      link.title = `Otvoriť ${annotation.elementTitle}`;
      link.addEventListener('click', () => {
        openSourceRelation({
          id: annotation.elementId,
          type: annotation.elementType,
          libraryId: annotation.libraryId,
          title: annotation.elementTitle
        });
      });
      copy.append(link);
    }

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'panel-icon-button danger source-preview-annotation-delete';
    remove.title = 'Zmazať anotáciu';
    remove.setAttribute('aria-label', 'Zmazať anotáciu');
    remove.append(createAppIcon('trash'));
    remove.addEventListener('click', () => void deleteSourceAnnotation(annotation));
    row.append(copy, remove);
    dom.sourcePreviewAnnotationsList.append(row);
  });
}

async function loadSourcePreviewAnnotations(file, requestId) {
  previewAnnotations = [];
  previewAnnotationsError = '';
  renderSourcePreviewAnnotations();
  try {
    const result = await apiRequest(sourceAnnotationUrl(file.id));
    if (requestId !== previewRequestId || previewFileId !== file.id || !isSourcePreviewOpen()) return;
    previewAnnotations = result.annotations;
    renderSourcePreviewAnnotations();
  } catch (error) {
    if (requestId !== previewRequestId || previewFileId !== file.id) return;
    previewAnnotationsError = error?.message || 'Anotácie sa nepodarilo načítať.';
    renderSourcePreviewAnnotations();
  }
}

async function saveSourceAnnotation() {
  if (!previewSourceId || !previewFileId) return;
  const quote = dom.sourcePreviewAnnotationQuote.value.trim();
  const note = dom.sourcePreviewAnnotationNote.value.trim();
  if (!quote && !note) {
    dom.sourcePreviewAnnotationQuote.setCustomValidity('Doplň úryvok alebo poznámku.');
    dom.sourcePreviewAnnotationQuote.reportValidity();
    return;
  }
  dom.sourcePreviewAnnotationQuote.setCustomValidity('');
  try {
    await flushWorkspaceSync();
    const result = await apiRequest(sourceAnnotationUrl(), {
      method: 'POST',
      body: {
        id: crypto.randomUUID(),
        quote,
        locator: dom.sourcePreviewAnnotationLocator.value.trim(),
        note,
        elementId: dom.sourcePreviewAnnotationElement.value
      }
    });
    previewAnnotations = [result.annotation, ...previewAnnotations];
    previewAnnotationsError = '';
    previewSelectedText = '';
    clearSourcePreviewAnnotationForm();
    renderSourcePreviewAnnotations();
    await refreshElementSourceLinks();
  } catch (error) {
    setSourcePreviewAnnotationStatus(error?.message || 'Anotáciu sa nepodarilo uložiť.', { error: true });
  }
}

async function deleteSourceAnnotation(annotation) {
  if (!confirm('Zmazať túto anotáciu?')) return;
  try {
    await apiRequest(sourceAnnotationUrl(previewFileId, annotation.id), { method: 'DELETE' });
    previewAnnotations = previewAnnotations.filter((entry) => entry.id !== annotation.id);
    renderSourcePreviewAnnotations();
  } catch (error) {
    previewAnnotationsError = error?.message || 'Anotáciu sa nepodarilo odstrániť.';
    renderSourcePreviewAnnotations();
  }
}

function openSourceRelation(element) {
  window.dispatchEvent(
    new CustomEvent('source-open-element', { detail: { libraryId: element.libraryId, elementId: element.id } })
  );
}

function renderSourcePreviewRelations(file) {
  clearSourcePreviewRelations();
  const linkedElements = (selectedSource?.elements || []).filter((element) => element.sourceFileId === file.id);
  const count = linkedElements.length;
  dom.sourcePreviewRelations.hidden = false;
  dom.sourcePreviewRelationsCount.textContent = count ? String(count) : '';

  if (!count) {
    const empty = document.createElement('p');
    empty.className = 'source-preview-relations-empty';
    empty.textContent = 'Táto príloha zatiaľ nie je pripojená k žiadnemu prvku.';
    dom.sourcePreviewRelationsList.append(empty);
    return;
  }

  linkedElements.forEach((element) => {
    const link = document.createElement('button');
    link.type = 'button';
    link.className = 'source-preview-relation-link';
    link.title = `Otvoriť ${element.title}`;
    link.append(createAppIcon(element.type === 'article' ? 'article' : 'note', 'source-preview-relation-icon'));

    const copy = document.createElement('span');
    copy.className = 'source-preview-relation-copy';
    const title = document.createElement('strong');
    title.textContent = element.title;
    const meta = document.createElement('small');
    const locator = element.locator ? ` · ${element.locator}` : '';
    meta.textContent = `${element.libraryName} · ${relationLabels[element.relationType] || element.relationType}${locator}`;
    copy.append(title, meta);
    link.append(copy);
    link.addEventListener('click', () => openSourceRelation(element));
    dom.sourcePreviewRelationsList.append(link);
  });
}

function showSourcePreviewFallback(message) {
  hideSourcePreviewViews();
  dom.sourcePreviewFallbackMessage.textContent = message;
  dom.sourcePreviewFallback.hidden = false;
}

export function closeSourcePreview() {
  previewRequestId += 1;
  previewSourceId = '';
  previewFileId = '';
  previewAnnotations = [];
  previewAnnotationsError = '';
  previewSelectedText = '';
  hideSourcePreviewViews();
  clearSourcePreviewRelations();
  clearSourcePreviewAnnotationForm();
  renderSourcePreviewAnnotations();
  setSourcePreviewOpen(false);
}

function setEditorSourceMenuOpen(open) {
  const visible = open && !dom.editorSourceLinks.hidden;
  editorSourceMenuOpen = visible;
  dom.editorSourceMenu.hidden = !visible;
  dom.editorSourceToggle.setAttribute('aria-expanded', String(visible));
}

export function isEditorSourceMenuOpen() {
  return editorSourceMenuOpen;
}

export function closeEditorSourceMenu() {
  setEditorSourceMenuOpen(false);
}

async function openSourceFile(file) {
  if (!selectedSource) return;

  const requestId = ++previewRequestId;
  const fileUrl = sourceFileUrl(file);
  previewSourceId = selectedSource.id;
  previewFileId = file.id;
  dom.sourcePreviewSource.textContent = selectedSource.title;
  dom.sourcePreviewTitle.textContent = file.originalName;
  dom.sourcePreviewMeta.textContent = `${fileFormatLabel(file)} · ${formatFileSize(file.sizeBytes)}`;
  dom.sourcePreviewExternal.href = fileUrl;
  dom.sourcePreviewExternal.hidden = !supportsInlinePreview(file);
  dom.sourcePreviewDownload.href = sourceFileUrl(file, { download: true });
  dom.sourcePreviewDownload.download = file.originalName;
  setSourcePreviewOpen(true);
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'sources' } }));
  hideSourcePreviewViews();
  previewSelectedText = '';
  clearSourcePreviewAnnotationForm();
  renderSourcePreviewRelations(file);
  void loadSourcePreviewAnnotations(file, requestId);

  if (file.mimeType === 'application/pdf') {
    dom.sourcePreviewFrame.src = fileUrl;
    dom.sourcePreviewFrame.hidden = false;
    return;
  }

  if (file.mimeType.startsWith('image/') && file.mimeType !== 'image/svg+xml') {
    dom.sourcePreviewImage.src = fileUrl;
    dom.sourcePreviewImage.alt = file.originalName;
    dom.sourcePreviewImage.hidden = false;
    return;
  }

  if ((file.mimeType.startsWith('text/') || file.mimeType === 'application/json') && file.sizeBytes <= TEXT_PREVIEW_MAX_BYTES) {
    dom.sourcePreviewText.textContent = 'Načítavam text...';
    dom.sourcePreviewText.hidden = false;
    try {
      const response = await fetch(fileUrl, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('Súbor sa nepodarilo načítať.');
      const text = await response.text();
      if (requestId !== previewRequestId || !isSourcePreviewOpen()) return;
      dom.sourcePreviewText.textContent = text;
    } catch {
      if (requestId === previewRequestId) {
        showSourcePreviewFallback('Textový náhľad sa nepodarilo načítať. Súbor môžeš otvoriť v novom okne alebo stiahnuť.');
      }
    }
    return;
  }

  showSourcePreviewFallback(previewFallbackMessage(file));
}

function setPanelOpen(open) {
  dom.sourcesPanel.classList.toggle('is-open', open);
  dom.sourcesPanel.setAttribute('aria-hidden', String(!open));
  dom.sourceBrowserPanel.classList.toggle('is-open', open);
  dom.sourceBrowserPanel.setAttribute('aria-hidden', String(!open));
  dom.sourcesButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

function setSourceDetailOpen(open) {
  dom.sourceDetailDock.classList.toggle('is-open', open);
  dom.sourceDetailDock.setAttribute('aria-hidden', String(!open));
  if (open) {
    document.body.dataset.sourceDetailOpen = 'true';
  } else {
    delete document.body.dataset.sourceDetailOpen;
  }
  refreshSourceDetailResizeHandle();
  refreshSourcePreviewResizeHandle();
  updateTopbarVisibility();
}

export function isSourcesPanelOpen() {
  return dom.sourcesPanel.classList.contains('is-open');
}

export function isSourceDetailOpen() {
  return dom.sourceDetailDock.classList.contains('is-open');
}

export function isSourcesPanelPinned() {
  return panelPinned;
}

export function closeSourcesPanel({ force = false } = {}) {
  if (panelPinned && !force) return;
  panelPinned = false;
  clearSourceReturnTarget();
  dom.sourceDetail.hidden = true;
  setSourceDetailOpen(false);
  setPanelOpen(false);
}

export async function openSourcesPanel({ sourceId = '', collectionId = '', pinned = false } = {}) {
  closeEditorSourceMenu();
  if (pinned) panelPinned = true;
  setPanelOpen(true);
  await Promise.all([loadSources(), loadSourceCollections()]);
  if (collectionId) await openSourceCollection(collectionId);
  else if (activeSourceCollectionId) await loadActiveSourceCollection();
  else renderSourceBrowser();
  if (sourceId) await selectSource(sourceId);
}

async function loadSources({ force = false } = {}) {
  const query = dom.sourceSearch.value.trim();
  if (!force && loadedSourcesQuery === query) return;
  if (!force && sourcesLoadPromise && loadingSourcesQuery === query) return sourcesLoadPromise;

  const requestId = ++sourcesLoadRequestId;
  loadingSourcesQuery = query;
  const request = apiRequest(`/sources?q=${encodeURIComponent(query)}`)
    .then((result) => {
      if (requestId !== sourcesLoadRequestId) return;
      sources = result.sources;
      loadedSourcesQuery = query;
      renderSourceBrowser();
    })
    .finally(() => {
      if (sourcesLoadPromise === request) {
        sourcesLoadPromise = null;
        loadingSourcesQuery = null;
      }
    });
  sourcesLoadPromise = request;
  return request;
}

async function loadSourceCollections({ force = false } = {}) {
  if (!force && sourceCollections.length) return;
  const result = await apiRequest('/source-collections');
  sourceCollections = result.collections;
  if (activeSourceCollectionId && !sourceCollections.some((collection) => collection.id === activeSourceCollectionId)) {
    activeSourceCollectionId = '';
    activeSourceCollectionDetail = null;
  }
  renderSourceCatalogTree();
}

function sourceCollectionById(collectionId) {
  return sourceCollections.find((collection) => collection.id === collectionId) || null;
}

function sourceCollectionPath(collectionId) {
  const path = [];
  const seen = new Set();
  let nextId = collectionId;
  while (nextId && !seen.has(nextId)) {
    const collection = sourceCollectionById(nextId);
    if (!collection) break;
    path.unshift(collection);
    seen.add(nextId);
    nextId = collection.parentId || '';
  }
  return path;
}

function sourceCollectionLabel(collectionId) {
  const labels = sourceCollectionPath(collectionId).map((collection) => collection.title);
  return labels.length ? labels.join(' / ') : 'Všetky zdroje';
}

function sourceUsageMeta(source) {
  const usage = [
    source.fileCount ? `${source.fileCount} súb.` : '',
    source.libraryCount ? `${source.libraryCount} kn.` : '',
    source.elementCount ? `${source.elementCount} prv.` : '',
    source.collectionCount ? `${source.collectionCount} zb.` : ''
  ]
    .filter(Boolean)
    .join(' · ');
  return [kindLabels[source.kind] || 'Zdroj', usage].filter(Boolean).join(' · ');
}

function renderSourceCatalogTree() {
  dom.sourceCatalogRoot.classList.toggle('is-active', !activeSourceCollectionId);
  dom.sourceCollectionsTree.replaceChildren();
  const childrenByParent = new Map();
  sourceCollections.forEach((collection) => {
    const parentId = collection.parentId || '';
    const children = childrenByParent.get(parentId) || [];
    children.push(collection);
    childrenByParent.set(parentId, children);
  });

  const addChildren = (parentId, depth = 0) => {
    (childrenByParent.get(parentId) || []).forEach((collection) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'source-catalog-tree-item';
      button.classList.toggle('is-active', collection.id === activeSourceCollectionId);
      button.style.setProperty('--source-collection-indent', `${depth * 14}px`);
      button.title = sourceCollectionLabel(collection.id);
      const title = document.createElement('span');
      title.className = 'source-catalog-tree-title';
      title.textContent = collection.title;
      const count = document.createElement('small');
      count.textContent = `${collection.sourceCount || 0}`;
      button.append(createAppIcon('folder', 'source-catalog-tree-icon'), title, count);
      button.addEventListener('click', () => void openSourceCollection(collection.id));
      dom.sourceCollectionsTree.append(button);
      addChildren(collection.id, depth + 1);
    });
  };

  addChildren('');
  if (!sourceCollections.length) {
    const empty = document.createElement('p');
    empty.className = 'source-catalog-empty';
    empty.textContent = 'Zatiaľ žiadne zbierky.';
    dom.sourceCollectionsTree.append(empty);
  }
}

function renderSourceBrowserItem(source) {
  const card = document.createElement('article');
  card.className = 'source-browser-item source-browser-source';
  card.dataset.sourceId = source.id;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'source-browser-open';
  button.title = `Otvoriť zdroj ${source.title}`;
  button.setAttribute('aria-label', `Otvoriť zdroj ${source.title}`);
  const icon = createAppIcon(sourceKindIcon(source.kind), 'source-browser-item-icon');
  const copy = document.createElement('span');
  copy.className = 'source-browser-item-copy';
  const title = document.createElement('strong');
  title.textContent = source.title;
  const meta = document.createElement('small');
  const tagMeta = (source.tags || []).slice(0, 2).map((tag) => `#${tag}`).join(' ');
  meta.textContent = [sourceUsageMeta(source), tagMeta].filter(Boolean).join(' · ');
  copy.append(title, meta);
  button.append(icon, copy);

  const actions = document.createElement('div');
  actions.className = 'source-browser-item-actions';

  const editButton = document.createElement('button');
  editButton.type = 'button';
  editButton.className = 'source-browser-item-action';
  editButton.dataset.sourceBrowserAction = 'edit';
  editButton.append(createAppIcon('pencil'));
  editButton.title = 'Upraviť zdroj';
  editButton.setAttribute('aria-label', `Upraviť zdroj ${source.title}`);

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.className = 'source-browser-item-action danger';
  deleteButton.dataset.sourceBrowserAction = 'delete';
  deleteButton.append(createAppIcon('trash'));
  deleteButton.title = 'Zmazať zdroj';
  deleteButton.setAttribute('aria-label', `Zmazať zdroj ${source.title}`);

  actions.append(editButton, deleteButton);
  card.append(button, actions);
  return card;
}

function renderSourceCollectionItem(collection) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'source-browser-item source-browser-collection';
  button.dataset.sourceCollectionId = collection.id;
  button.title = `Otvoriť zbierku ${collection.title}`;
  const icon = createAppIcon('folder', 'source-browser-item-icon');
  const copy = document.createElement('span');
  copy.className = 'source-browser-item-copy';
  const title = document.createElement('strong');
  title.textContent = collection.title;
  const meta = document.createElement('small');
  const parts = [collection.childCount ? `${collection.childCount} podzb.` : '', `${collection.sourceCount || 0} zdrojov`].filter(Boolean);
  meta.textContent = parts.join(' · ');
  copy.append(title, meta);
  button.append(icon, copy);
  return button;
}

function runSourceBrowserAction(item, itemAction = 'open') {
  const sourceId = item.dataset.sourceId;
  const collectionId = item.dataset.sourceCollectionId;
  const action = `${sourceId ? 'source' : 'collection'}:${itemAction}`;
  const targetId = sourceId || collectionId;
  if (!targetId) return;

  const now = window.performance.now();
  if (
    lastSourceBrowserAction &&
    lastSourceBrowserAction.action === action &&
    lastSourceBrowserAction.targetId === targetId &&
    now - lastSourceBrowserAction.at < 350
  ) {
    return;
  }

  lastSourceBrowserAction = { action, targetId, at: now };
  sourceBrowserError = '';
  if (sourceId) {
    if (itemAction === 'delete') {
      const sourceTitle = item.querySelector('.source-browser-item-copy strong')?.textContent || 'tento zdroj';
      void deleteSource(sourceId, sourceTitle);
      return;
    }
    void selectSource(sourceId, { focusTitle: itemAction === 'edit' });
    return;
  }
  void openSourceCollection(collectionId);
}

function handleSourceBrowserAction(event) {
  const item = event.target.closest('.source-browser-item');
  if (!item || !dom.sourceBrowserList.contains(item)) return;
  if (event.type === 'click' && pointerHandledSourceBrowserItem === item) {
    pointerHandledSourceBrowserItem = null;
    return;
  }
  event.preventDefault();
  const itemAction = event.target.closest('[data-source-browser-action]')?.dataset.sourceBrowserAction || 'open';
  if (event.type === 'pointerup') pointerHandledSourceBrowserItem = item;
  runSourceBrowserAction(item, itemAction);
  if (event.type === 'pointerup') {
    window.setTimeout(() => {
      if (pointerHandledSourceBrowserItem === item) pointerHandledSourceBrowserItem = null;
    }, 0);
  }
}

function renderSourceBrowser() {
  const query = dom.sourceSearch.value.trim();
  const activeCollection = sourceCollectionById(activeSourceCollectionId);
  const path = activeSourceCollectionId ? sourceCollectionPath(activeSourceCollectionId) : [];
  const title = query ? `Výsledky: ${query}` : path.length ? ['Všetky zdroje', ...path.map((collection) => collection.title)].join(' / ') : 'Všetky zdroje';
  dom.sourceBrowserTitle.textContent = title;
  dom.sourceBrowserTitle.title = title;
  dom.sourceCatalogHomeButton.disabled = !activeSourceCollectionId && !query;
  dom.sourceCatalogUpButton.disabled = !activeSourceCollectionId;
  dom.sourceCollectionTransferExportButton.hidden = !activeCollection;
  dom.sourceCollectionRenameButton.hidden = !activeCollection;
  dom.sourceCollectionDeleteButton.hidden = !activeCollection;
  dom.sourceBrowserList.replaceChildren();

  const children = query
    ? []
    : activeSourceCollectionId
      ? activeSourceCollectionDetail?.children || []
      : sourceCollections.filter((collection) => !collection.parentId);
  const visibleSources = query ? sources : activeSourceCollectionId ? activeSourceCollectionDetail?.sources || [] : sources;

  children.forEach((collection) => dom.sourceBrowserList.append(renderSourceCollectionItem(collection)));
  visibleSources.forEach((source) => dom.sourceBrowserList.append(renderSourceBrowserItem(source)));

  if (sourceBrowserError) {
    const error = document.createElement('p');
    error.className = 'source-browser-message is-error';
    error.textContent = sourceBrowserError;
    dom.sourceBrowserList.prepend(error);
  }

  if (!children.length && !visibleSources.length) {
    const empty = document.createElement('p');
    empty.className = 'sources-empty source-browser-empty';
    empty.textContent = query
      ? 'Nenašli sa žiadne zdroje.'
      : activeCollection
        ? 'Táto zbierka je zatiaľ prázdna.'
        : 'Katalóg zatiaľ neobsahuje zdroje ani zbierky.';
    dom.sourceBrowserList.append(empty);
  }
}

async function loadActiveSourceCollection() {
  if (!activeSourceCollectionId) {
    activeSourceCollectionDetail = null;
    renderSourceBrowser();
    return;
  }
  try {
    activeSourceCollectionDetail = await apiRequest(`/source-collections/${encodeURIComponent(activeSourceCollectionId)}`);
  } catch {
    activeSourceCollectionId = '';
    activeSourceCollectionDetail = null;
  }
  renderSourceCatalogTree();
  renderSourceBrowser();
}

async function refreshSourceCatalog() {
  await Promise.all([loadSources({ force: true }), loadSourceCollections({ force: true })]);
  await loadActiveSourceCollection();
}

function showSourceBrowser() {
  dom.sourceDetail.hidden = true;
  setSourceDetailOpen(false);
  renderSourceBrowser();
}

function showSourceDetail() {
  dom.sourceDetail.hidden = false;
  panelPinned = true;
  setSourceDetailOpen(true);
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'sources' } }));
}

export function closeSourceDetail() {
  closeSourcePreview();
  showSourceBrowser();
}

async function openSourceCatalogRoot() {
  closeSourcePreview();
  if (dom.sourceSearch.value) {
    dom.sourceSearch.value = '';
    await loadSources({ force: true });
  }
  activeSourceCollectionId = '';
  activeSourceCollectionDetail = null;
  showSourceBrowser();
  renderSourceCatalogTree();
}

async function openSourceCollection(collectionId) {
  if (!sourceCollectionById(collectionId)) return;
  closeSourcePreview();
  if (dom.sourceSearch.value) {
    dom.sourceSearch.value = '';
    await loadSources({ force: true });
  }
  activeSourceCollectionId = collectionId;
  showSourceBrowser();
  await loadActiveSourceCollection();
}

async function openParentSourceCollection() {
  const parentId = sourceCollectionById(activeSourceCollectionId)?.parentId || '';
  if (parentId) await openSourceCollection(parentId);
  else await openSourceCatalogRoot();
}

function hideSourceCollectionForm() {
  sourceCollectionFormMode = '';
  sourceCollectionFormBaseline = '';
  dom.sourceCollectionForm.hidden = true;
  dom.sourceCollectionName.value = '';
  dom.sourceCollectionName.setCustomValidity('');
}

function showSourceCollectionForm(mode) {
  if (mode === 'rename' && !activeSourceCollectionId) return;
  sourceCollectionFormMode = mode;
  dom.sourceCollectionForm.hidden = false;
  dom.sourceCollectionName.value = mode === 'rename' ? sourceCollectionById(activeSourceCollectionId)?.title || '' : '';
  sourceCollectionFormBaseline = dom.sourceCollectionName.value.trim();
  dom.sourceCollectionName.setCustomValidity('');
  dom.sourceCollectionName.focus();
  dom.sourceCollectionName.select();
}

async function saveSourceCollectionForm() {
  if (!sourceCollectionFormMode || !dom.sourceCollectionForm.reportValidity()) return;
  const title = dom.sourceCollectionName.value.trim();
  try {
    if (sourceCollectionFormMode === 'rename') {
      activeSourceCollectionDetail = await apiRequest(`/source-collections/${encodeURIComponent(activeSourceCollectionId)}`, {
        method: 'PATCH',
        body: { title }
      });
    } else {
      await apiRequest('/source-collections', {
        method: 'POST',
        body: { id: crypto.randomUUID(), title, parentId: activeSourceCollectionId }
      });
    }
    hideSourceCollectionForm();
    await refreshSourceCatalog();
  } catch (error) {
    dom.sourceCollectionName.setCustomValidity(error?.message || 'Zbierku sa nepodarilo uložiť.');
    dom.sourceCollectionName.reportValidity();
  }
}

async function deleteActiveSourceCollection() {
  const collection = sourceCollectionById(activeSourceCollectionId);
  if (!collection || !confirm(`Zmazať zbierku "${collection.title}"? Zdroje zostanú v katalógu a podzbierky sa posunú o úroveň vyššie.`)) return;
  const result = await apiRequest(`/source-collections/${encodeURIComponent(collection.id)}`, { method: 'DELETE' });
  hideSourceCollectionForm();
  activeSourceCollectionId = result.parentId || '';
  activeSourceCollectionDetail = null;
  await refreshSourceCatalog();
  showSourceBrowser();
}

async function selectSource(sourceId, { focusTitle = false } = {}) {
  if (previewSourceId && previewSourceId !== sourceId) closeSourcePreview();
  try {
    const result = await apiRequest(`/sources/${encodeURIComponent(sourceId)}`);
    selectedSource = result.source;
    setSourceFilesStatus('');
    showSourceDetail();
    renderSourceDetail();
    if (focusTitle) {
      dom.sourceTitle.focus();
      dom.sourceTitle.select();
    }
  } catch (error) {
    sourceBrowserError = error?.message || 'Zdroj sa nepodarilo otvoriť.';
    renderSourceBrowser();
  }
}

async function deleteSource(sourceId, sourceTitle) {
  if (!confirm(`Zmazať zdroj "${sourceTitle}" aj jeho súbory?`)) return;
  try {
    await runSourceOperation(async () => {
      if (previewSourceId === sourceId) closeSourcePreview();
      await apiRequest(`/sources/${encodeURIComponent(sourceId)}`, { method: 'DELETE' });
      if (selectedSource?.id === sourceId) {
        selectedSource = null;
        sourceDraftCollectionId = '';
        showSourceBrowser();
      }
      await refreshSourceCatalog();
      await refreshElementSourceLinks();
      notifySourcesChanged();
    });
  } catch (error) {
    sourceBrowserError = error?.message || 'Zdroj sa nepodarilo zmazať.';
    renderSourceBrowser();
  }
}

function startNewSource() {
  closeSourcePreview();
  sourceDraftCollectionId = activeSourceCollectionId;
  selectedSource = null;
  setSourceFilesStatus('');
  showSourceDetail();
  dom.sourceForm.reset();
  setTagField(dom.sourceTags, dom.sourceTagChips, []);
  dom.sourceKind.value = 'source';
  dom.sourceFormTitle.textContent = 'Nový zdroj';
  dom.sourceDeleteButton.hidden = true;
  dom.sourceRelationshipsButton.hidden = true;
  dom.sourceTransferExportButton.hidden = true;
  dom.sourceDetailEmpty.hidden = true;
  dom.sourceForm.hidden = false;
  hideSourceSections();
  rememberSourceForm();
  dom.sourceTitle.focus();
}

function hideSourceSections() {
  dom.sourceCollectionSection.hidden = true;
  dom.sourceFilesSection.hidden = true;
  dom.sourceLibrarySection.hidden = true;
  dom.sourceElementSection.hidden = true;
  dom.sourceAnnotationSection.hidden = true;
  dom.sourceTaskSection.hidden = true;
  dom.sourceCalendarSection.hidden = true;
}

function renderSourceDetail() {
  if (!selectedSource) {
    dom.sourceDetailEmpty.hidden = false;
    dom.sourceForm.hidden = true;
    hideSourceSections();
    return;
  }
  const metadata = selectedSource.metadata || {};
  dom.sourceDetailEmpty.hidden = true;
  dom.sourceForm.hidden = false;
  dom.sourceFormTitle.textContent = selectedSource.title;
  dom.sourceDeleteButton.hidden = false;
  dom.sourceRelationshipsButton.hidden = false;
  dom.sourceTransferExportButton.hidden = false;
  dom.sourceTitle.value = selectedSource.title;
  dom.sourceKind.value = selectedSource.kind in kindLabels ? selectedSource.kind : 'source';
  dom.sourceYear.value = metadata.year || '';
  dom.sourceAuthor.value = metadata.author || '';
  dom.sourceUrl.value = metadata.url || '';
  dom.sourceDescription.value = selectedSource.description || '';
  setTagField(dom.sourceTags, dom.sourceTagChips, selectedSource.tags || []);
  dom.sourceCollectionSection.hidden = false;
  dom.sourceFilesSection.hidden = false;
  dom.sourceLibrarySection.hidden = false;
  dom.sourceElementSection.hidden = false;
  dom.sourceAnnotationSection.hidden = false;
  dom.sourceTaskSection.hidden = false;
  dom.sourceCalendarSection.hidden = false;
  renderFiles();
  renderSourceCollections();
  renderLibraries();
  renderElements();
  renderSourceAnnotations();
  renderSourceTasks();
  renderSourceCalendarEvents();
  if (previewFileId) {
    const previewedFile = selectedSource.files?.find((file) => file.id === previewFileId);
    if (previewedFile) renderSourcePreviewRelations(previewedFile);
    else closeSourcePreview();
  }
  rememberSourceForm();
}

export function discardSourceDraft() {
  if (!dom.sourceCollectionForm.hidden) {
    hideSourceCollectionForm();
    return;
  }
  if (selectedSource) renderSourceDetail();
  else startNewSource();
}

export async function saveSourceDraft() {
  if (!dom.sourceCollectionForm.hidden && dom.sourceCollectionName.value.trim() !== sourceCollectionFormBaseline) {
    await saveSourceCollectionForm();
    return dom.sourceCollectionForm.hidden;
  }
  if (!hasUnsavedSourceChanges()) return true;
  if (!dom.sourceForm.reportValidity()) return false;

  try {
    await runSourceOperation(async () => {
      const isNewSource = !selectedSource;
      const data = {
        title: dom.sourceTitle.value.trim(),
        kind: dom.sourceKind.value,
        description: dom.sourceDescription.value.trim(),
        tags: readTagField(dom.sourceTags),
        metadata: {
          author: dom.sourceAuthor.value.trim(),
          year: dom.sourceYear.value.trim(),
          url: dom.sourceUrl.value.trim()
        }
      };
      const result = selectedSource
        ? await apiRequest(`/sources/${selectedSource.id}`, { method: 'PATCH', body: data })
        : await apiRequest('/sources', { method: 'POST', body: { ...data, id: crypto.randomUUID() } });
      selectedSource = result.source;
      if (isNewSource && sourceDraftCollectionId) {
        await apiRequest(`/source-collections/${encodeURIComponent(sourceDraftCollectionId)}/sources/${selectedSource.id}`, {
          method: 'PUT',
          body: {}
        });
        const refreshed = await apiRequest(`/sources/${encodeURIComponent(selectedSource.id)}`);
        selectedSource = refreshed.source;
      }
      sourceDraftCollectionId = '';
      renderSourceDetail();
      await refreshSourceCatalog();
      refreshTagSuggestions();
      notifySourcesChanged();
    });
    return true;
  } catch (error) {
    dom.sourceTitle.setCustomValidity(error?.message || 'Zdroj sa nepodarilo uložiť.');
    dom.sourceTitle.reportValidity();
    return false;
  }
}

function renderFiles() {
  const selectedFileId = dom.sourceFileSelect.value;
  dom.sourceFileSelect.replaceChildren();
  const sourceOption = document.createElement('option');
  sourceOption.value = '';
  sourceOption.textContent = 'Celý zdroj';
  dom.sourceFileSelect.append(sourceOption);
  selectedSource.files?.forEach((file) => {
    const option = document.createElement('option');
    option.value = file.id;
    option.textContent = file.originalName;
    dom.sourceFileSelect.append(option);
  });
  dom.sourceFileSelect.value = Array.from(dom.sourceFileSelect.options).some((option) => option.value === selectedFileId)
    ? selectedFileId
    : '';

  dom.sourceFilesList.replaceChildren();
  if (!selectedSource.files?.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Bez priložených súborov.';
    dom.sourceFilesList.append(empty);
    return;
  }
  selectedSource.files.forEach((file) => {
    const row = document.createElement('div');
    row.className = 'source-file-row';
    const name = document.createElement('button');
    name.type = 'button';
    name.className = 'source-file-open';
    name.textContent = file.originalName;
    name.title = `Otvoriť náhľad ${file.originalName}`;
    name.addEventListener('click', () => void openSourceFile(file));
    const fileIcon = createAppIcon(sourceFileIcon(file), 'source-file-icon');
    const meta = document.createElement('span');
    const annotationCount = Number(file.annotationCount) || 0;
    meta.textContent = [fileFormatLabel(file), formatFileSize(file.sizeBytes), annotationCount ? annotationCountLabel(annotationCount) : '']
      .filter(Boolean)
      .join(' · ');
    meta.title = file.mimeType;
    const download = document.createElement('a');
    download.className = 'source-file-download';
    download.href = sourceFileUrl(file, { download: true });
    download.download = file.originalName;
    download.append(createAppIcon('download'));
    download.title = `Stiahnuť ${file.originalName}`;
    download.setAttribute('aria-label', `Stiahnuť ${file.originalName}`);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-file-delete';
    remove.append(createAppIcon('trash'));
    remove.title = `Odstrániť ${file.originalName}`;
    remove.setAttribute('aria-label', `Odstrániť ${file.originalName}`);
    remove.addEventListener('click', () => void deleteSourceFile(file));
    const copy = document.createElement('div');
    copy.className = 'source-file-copy';
    copy.append(name, meta);
    row.append(fileIcon, copy, download, remove);
    dom.sourceFilesList.append(row);
  });
}

function renderSourceCollections() {
  const linkedIds = new Set((selectedSource?.collections || []).map((collection) => collection.id));
  dom.sourceCollectionSelect.replaceChildren();
  sourceCollections
    .filter((collection) => !linkedIds.has(collection.id))
    .forEach((collection) => {
      const option = document.createElement('option');
      option.value = collection.id;
      option.textContent = sourceCollectionLabel(collection.id);
      option.selected = collection.id === activeSourceCollectionId;
      dom.sourceCollectionSelect.append(option);
    });
  dom.sourceCollectionLinkButton.disabled = !dom.sourceCollectionSelect.options.length;

  dom.sourceCollectionsList.replaceChildren();
  if (!selectedSource.collections?.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Nie je zaradený v žiadnej zbierke.';
    dom.sourceCollectionsList.append(empty);
    return;
  }
  selectedSource.collections.forEach((collection) => {
    const row = document.createElement('div');
    row.className = 'source-usage-row';
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'source-usage-link';
    label.textContent = sourceCollectionLabel(collection.id);
    label.title = `Otvoriť zbierku ${collection.title}`;
    label.addEventListener('click', () => void openSourceCollection(collection.id));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Odobrať zo zbierky ${collection.title}`;
    remove.setAttribute('aria-label', `Odobrať zo zbierky ${collection.title}`);
    remove.addEventListener('click', async () => {
      await apiRequest(`/source-collections/${encodeURIComponent(collection.id)}/sources/${selectedSource.id}`, { method: 'DELETE' });
      const refreshed = await apiRequest(`/sources/${encodeURIComponent(selectedSource.id)}`);
      selectedSource = refreshed.source;
      renderSourceDetail();
      await refreshSourceCatalog();
    });
    row.append(label, remove);
    dom.sourceCollectionsList.append(row);
  });
}

async function addSourceFiles(fileList) {
  if (!selectedSource) return;
  const sourceId = selectedSource.id;
  const files = Array.from(fileList || []);
  const fileSizeLimit = getSourceFileMaxBytes();
  const oversized = files.filter((file) => file.size > fileSizeLimit);
  const acceptedFiles = files.filter((file) => file.size <= fileSizeLimit);
  if (!acceptedFiles.length) {
    setSourceFilesStatus(`Vybraný súbor presahuje limit ${sourceFileLimitLabel()}.`, { error: true });
    return;
  }

  await runSourceOperation(async () => {
    setSourceFilesBusy(true);
    const failedFiles = [];
    let uploadedCount = 0;
    try {
      for (const [index, file] of acceptedFiles.entries()) {
        setSourceFilesStatus(`Nahrávam ${index + 1}/${acceptedFiles.length}: ${file.name}`);
        try {
          const result = await uploadSourceFile(sourceId, file);
          if (selectedSource?.id === sourceId) selectedSource = result.source;
          uploadedCount += 1;
        } catch (error) {
          failedFiles.push(error?.message || file.name);
        }
      }
      if (selectedSource?.id === sourceId) renderSourceDetail();
      await refreshSourceCatalog();
      notifySourcesChanged();
      if (selectedSource?.id !== sourceId) return;
      if (failedFiles.length || oversized.length) {
        const rejectedCount = failedFiles.length + oversized.length;
        setSourceFilesStatus(
          `${uploadedCount ? `Pridané: ${uploadedCount}. ` : ''}Nepodarilo sa pridať: ${rejectedCount}.`,
          { error: true }
        );
      } else {
        setSourceFilesStatus(uploadedCount === 1 ? 'Príloha bola pridaná.' : `Pridané prílohy: ${uploadedCount}.`);
      }
    } finally {
      setSourceFilesBusy(false);
    }
  });
}

async function deleteSourceFile(file) {
  if (!selectedSource || !confirm(`Odstrániť prílohu "${file.originalName}"?`)) return;
  const sourceId = selectedSource.id;
  await runSourceOperation(async () => {
    setSourceFilesBusy(true);
    try {
      const result = await apiRequest(`/sources/${sourceId}/files/${file.id}`, { method: 'DELETE' });
      if (previewFileId === file.id) closeSourcePreview();
      if (selectedSource?.id === sourceId) {
        selectedSource = result.source;
        renderSourceDetail();
        setSourceFilesStatus('Príloha bola odstránená.');
      }
      await refreshSourceCatalog();
      await refreshElementSourceLinks();
      notifySourcesChanged();
    } catch (error) {
      setSourceFilesStatus(error?.message || 'Prílohu sa nepodarilo odstrániť.', { error: true });
    } finally {
      setSourceFilesBusy(false);
    }
  });
}

function renderLibraries() {
  const linkedIds = new Set((selectedSource?.libraries || []).map((library) => library.id));
  dom.sourceLibrarySelect.replaceChildren();
  state.libraries
    .filter((library) => !linkedIds.has(library.id))
    .forEach((library) => {
      const option = document.createElement('option');
      option.value = library.id;
      option.textContent = library.name;
      option.selected = library.id === state.activeLibraryId;
      dom.sourceLibrarySelect.append(option);
    });
  dom.sourceLibraryLinkButton.disabled = !dom.sourceLibrarySelect.options.length;

  dom.sourceLibrariesList.replaceChildren();
  if (!selectedSource.libraries?.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Nie je vložený v žiadnej knižnici.';
    dom.sourceLibrariesList.append(empty);
    return;
  }
  selectedSource.libraries.forEach((library) => {
    const row = document.createElement('div');
    row.className = 'source-usage-row';
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'source-usage-link';
    label.textContent = library.note ? `${library.name} — ${library.note}` : library.name;
    label.title = `Otvoriť knižnicu ${library.name}`;
    label.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('source-open-library', { detail: { libraryId: library.id } }));
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Odobrať z knižnice ${library.name}`;
    remove.setAttribute('aria-label', `Odobrať z knižnice ${library.name}`);
    remove.addEventListener('click', async () => {
      const result = await apiRequest(`/sources/${selectedSource.id}/libraries/${library.id}`, { method: 'DELETE' });
      selectedSource = result.source;
      renderSourceDetail();
      await refreshSourceCatalog();
      notifySourcesChanged();
    });
    row.append(label, remove);
    dom.sourceLibrariesList.append(row);
  });
}

function renderElements() {
  const activeTitle = activeElementTitle();
  dom.sourceElementLinkButton.disabled = !state.activeLibraryElementId;
  dom.sourceElementLinkButton.textContent = activeTitle ? `Pripojiť k: ${activeTitle}` : 'Otvor prvok na pripojenie';
  dom.sourceElementsList.replaceChildren();
  if (!selectedSource.elements?.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Zatiaľ nie je pripojený k žiadnemu článku ani poznámke.';
    dom.sourceElementsList.append(empty);
    return;
  }
  selectedSource.elements.forEach((element) => {
    const row = document.createElement('div');
    row.className = 'source-usage-row';
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'source-usage-link';
    const locator = element.locator ? ` · ${element.locator}` : '';
    const fileName = element.sourceFileName ? ` / ${element.sourceFileName}` : '';
    label.textContent = `${element.libraryName} / ${element.title}${fileName} · ${relationLabels[element.relationType] || element.relationType}${locator}`;
    label.title = `Otvoriť ${element.title}`;
    label.addEventListener('click', () => openSourceRelation(element));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.append(createAppIcon('close'));
    remove.title = `Odpojiť od ${element.title}`;
    remove.setAttribute('aria-label', `Odpojiť od ${element.title}`);
    remove.addEventListener('click', async () => {
      const result = await apiRequest(`/sources/${selectedSource.id}/element-links/${element.linkId}`, { method: 'DELETE' });
      selectedSource = result.source;
      renderSourceDetail();
      await refreshElementSourceLinks();
      await refreshSourceCatalog();
    });
    row.append(label, remove);
    dom.sourceElementsList.append(row);
  });
}

function renderSourceAnnotations() {
  const annotations = selectedSource?.annotations || [];
  dom.sourceAnnotationsCount.textContent = annotations.length ? String(annotations.length) : '';
  dom.sourceAnnotationsCount.hidden = !annotations.length;
  dom.sourceAnnotationsList.replaceChildren();
  if (!annotations.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Zatiaľ žiadne anotácie príloh.';
    dom.sourceAnnotationsList.append(empty);
    return;
  }

  annotations.forEach((annotation) => {
    const row = document.createElement('div');
    row.className = 'source-annotation-row';
    const file = selectedSource.files?.find((entry) => entry.id === annotation.sourceFileId);
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'source-annotation-open';
    open.title = `Otvoriť anotáciu v súbore ${annotation.sourceFileName}`;
    open.append(createAppIcon('quote', 'source-annotation-icon'));

    const copy = document.createElement('span');
    copy.className = 'source-annotation-copy';
    const title = document.createElement('strong');
    const excerpt = annotation.quote || annotation.note || 'Anotácia bez textu';
    title.textContent = excerpt.length > 150 ? `${excerpt.slice(0, 147)}...` : excerpt;
    title.title = excerpt;
    const meta = document.createElement('small');
    meta.textContent = [annotation.sourceFileName, annotation.locator].filter(Boolean).join(' · ');
    copy.append(title, meta);
    if (annotation.note && annotation.quote) {
      const note = document.createElement('small');
      note.className = 'source-annotation-note';
      note.textContent = annotation.note.length > 120 ? `${annotation.note.slice(0, 117)}...` : annotation.note;
      note.title = annotation.note;
      copy.append(note);
    }
    open.append(copy);
    open.addEventListener('click', () => {
      if (file) void openSourceFile(file);
    });
    row.append(open);

    if (annotation.elementId && annotation.elementTitle) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'source-annotation-element-link';
      element.title = `Otvoriť ${annotation.elementTitle}`;
      element.setAttribute('aria-label', `Otvoriť ${annotation.libraryName} / ${annotation.elementTitle}`);
      element.append(createAppIcon(annotation.elementType === 'article' ? 'article' : 'note'));
      element.addEventListener('click', () => {
        openSourceRelation({
          id: annotation.elementId,
          type: annotation.elementType,
          libraryId: annotation.libraryId,
          title: annotation.elementTitle
        });
      });
      row.append(element);
    }
    dom.sourceAnnotationsList.append(row);
  });
}

function renderSourceTasks() {
  const tasks = selectedSource?.tasks || [];
  dom.sourceTasksCount.textContent = tasks.length ? String(tasks.length) : '';
  dom.sourceTasksCount.hidden = !tasks.length;
  dom.sourceTasksList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Zatiaľ nie je pripojený k žiadnej úlohe.';
    dom.sourceTasksList.append(empty);
    return;
  }
  tasks.forEach((task) => {
    const row = document.createElement('div');
    row.className = 'source-usage-row';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'source-usage-link';
    const details = [
      task.status === 'done' ? 'Hotová' : task.priority === 'high' ? 'Vysoká priorita' : 'Úloha',
      task.dueDate ? `do ${task.dueDate}` : ''
    ].filter(Boolean).join(' · ');
    open.textContent = details ? `${task.title} · ${details}` : task.title;
    open.title = `Otvoriť úlohu ${task.title}`;
    open.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('task-open', { detail: { taskId: task.id } }));
    });
    row.append(open);
    dom.sourceTasksList.append(row);
  });
}

function calendarEventTiming(event) {
  if (event.allDay) return event.startDate === event.endDate ? event.startDate : `${event.startDate} - ${event.endDate}`;
  const start = event.startTime ? `${event.startDate} ${event.startTime}` : event.startDate;
  const end = event.endTime ? `${event.endDate} ${event.endTime}` : event.endDate;
  return start === end ? start : `${start} - ${end}`;
}

function renderSourceCalendarEvents() {
  const events = selectedSource?.calendarEvents || [];
  dom.sourceCalendarCount.textContent = events.length ? String(events.length) : '';
  dom.sourceCalendarCount.hidden = !events.length;
  dom.sourceCalendarList.replaceChildren();
  if (!events.length) {
    const empty = document.createElement('p');
    empty.className = 'source-usage-empty';
    empty.textContent = 'Zatiaľ nie je pripojený k žiadnej udalosti.';
    dom.sourceCalendarList.append(empty);
    return;
  }
  events.forEach((event) => {
    const row = document.createElement('div');
    row.className = 'source-usage-row';
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'source-usage-link';
    open.textContent = `${event.title} · ${calendarEventTiming(event)}`;
    open.title = `Otvoriť udalosť ${event.title}`;
    open.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('calendar-open-event', { detail: { eventId: event.id } }));
    });
    row.append(open);
    dom.sourceCalendarList.append(row);
  });
}

export async function refreshElementSourceLinks() {
  const elementId = state.activeLibraryElementId;
  if (!elementId) {
    closeEditorSourceMenu();
    dom.editorSourceLinks.hidden = true;
    dom.editorSourceMenu.replaceChildren();
    return;
  }
  try {
    const result = await apiRequest(`/elements/${encodeURIComponent(elementId)}/sources`);
    closeEditorSourceMenu();
    dom.editorSourceMenu.replaceChildren();
    if (!result.sources.length) {
      dom.editorSourceLinks.hidden = true;
      return;
    }
    dom.editorSourceToggleLabel.textContent = `Zdroje (${result.sources.length})`;
    result.sources.forEach((source) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'editor-source-chip';
      const isAnnotation = source.relationType === 'annotation';
      button.classList.toggle('is-annotation', isAnnotation);
      const copy = document.createElement('span');
      copy.className = 'editor-source-chip-copy';
      const title = document.createElement('strong');
      title.textContent = source.title;
      const meta = document.createElement('small');
      meta.textContent = [relationLabels[source.relationType] || source.relationType, source.sourceFileName, source.locator]
        .filter(Boolean)
        .join(' · ');
      copy.append(title, meta);
      if (isAnnotation && source.label) {
        const quote = document.createElement('small');
        quote.className = 'editor-source-chip-quote';
        quote.textContent = source.label.length > 100 ? `„${source.label.slice(0, 97)}...“` : `„${source.label}“`;
        quote.title = source.label;
        copy.append(quote);
      }
      button.append(createAppIcon(isAnnotation ? 'quote' : 'link', 'editor-source-chip-icon'), copy);
      button.title = isAnnotation ? 'Otvoriť anotovaný zdroj' : 'Otvoriť detail zdroja';
      button.addEventListener('click', () => {
        const libraryId = state.activeDetailLibraryId || state.activeLibraryId;
        const elementId = state.activeLibraryElementId;
        const title = activeElementTitle();
        closeEditorSourceMenu();
        window.dispatchEvent(
          new CustomEvent('source-open-request', {
            detail: {
              sourceId: source.id,
              returnTarget: libraryId && elementId && title ? { libraryId, elementId, title } : null
            }
          })
        );
      });
      dom.editorSourceMenu.append(button);
    });
    dom.editorSourceLinks.hidden = false;
  } catch {
    closeEditorSourceMenu();
    dom.editorSourceLinks.hidden = true;
  }
}

export function initializeSources() {
  syncSourceReturnButton();
  initializeSourceTransfer({
    saveCurrent: saveSourceDraft,
    onImported: async (sourceId) => {
      await refreshSourceCatalog();
      await selectSource(sourceId);
      refreshTagSuggestions();
      notifySourcesChanged();
    }
  });
  initializeSourceCollectionTransfer({
    saveCurrent: saveSourceDraft,
    onImported: async (collectionId) => {
      await refreshSourceCatalog();
      await openSourceCollection(collectionId);
      refreshTagSuggestions();
      notifySourcesChanged();
    }
  });
  dom.sourcePreviewCloseButton.addEventListener('click', closeSourcePreview);
  dom.sourcePreviewFullscreen.addEventListener('click', toggleSourcePreviewFullscreen);
  dom.sourcePreviewAnnotateButton.addEventListener('pointerdown', captureSourcePreviewSelection);
  dom.sourcePreviewAnnotateButton.addEventListener('click', openSourceAnnotationForm);
  dom.sourcePreviewAnnotationCancelButton.addEventListener('click', clearSourcePreviewAnnotationForm);
  dom.sourcePreviewAnnotationForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveSourceAnnotation();
  });
  dom.sourcePreviewAnnotationQuote.addEventListener('input', () => {
    dom.sourcePreviewAnnotationQuote.setCustomValidity('');
    setSourcePreviewAnnotationStatus('');
  });
  dom.sourcePreviewAnnotationNote.addEventListener('input', () => {
    dom.sourcePreviewAnnotationQuote.setCustomValidity('');
    setSourcePreviewAnnotationStatus('');
  });
  dom.sourcePreviewText.addEventListener('mouseup', captureSourcePreviewSelection);
  dom.sourcePreviewText.addEventListener('keyup', captureSourcePreviewSelection);
  dom.editorSourceToggle.addEventListener('click', () => setEditorSourceMenuOpen(!editorSourceMenuOpen));
  document.addEventListener('pointerdown', (event) => {
    if (editorSourceMenuOpen && !dom.editorSourceLinks.contains(event.target)) closeEditorSourceMenu();
  });
  dom.sourceCreateButton.addEventListener('click', startNewSource);
  dom.sourceCollectionCreateButton.addEventListener('click', () => {
    showSourceBrowser();
    showSourceCollectionForm('create');
  });
  dom.sourceCatalogRoot.addEventListener('click', () => void openSourceCatalogRoot());
  dom.sourceCatalogHomeButton.addEventListener('click', () => void openSourceCatalogRoot());
  dom.sourceCatalogUpButton.addEventListener('click', () => void openParentSourceCollection());
  dom.sourceCollectionTransferExportButton.addEventListener('click', () => {
    exportSourceCollectionPackage(sourceCollectionById(activeSourceCollectionId));
  });
  dom.sourceCollectionRenameButton.addEventListener('click', () => showSourceCollectionForm('rename'));
  dom.sourceCollectionDeleteButton.addEventListener('click', () => void deleteActiveSourceCollection());
  dom.sourceCollectionCancelButton.addEventListener('click', hideSourceCollectionForm);
  dom.sourceCollectionForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveSourceCollectionForm();
  });
  dom.sourceBrowserList.addEventListener('pointerup', handleSourceBrowserAction);
  dom.sourceBrowserList.addEventListener('click', handleSourceBrowserAction);
  dom.sourceDetailBack.addEventListener('click', () => {
    closeSourceDetail();
  });
  dom.sourceReturnButton.addEventListener('click', () => {
    if (!state.sourceReturnTarget) return;
    window.dispatchEvent(new CustomEvent('source-return-request', { detail: state.sourceReturnTarget }));
  });
  dom.sourceTitle.addEventListener('input', () => dom.sourceTitle.setCustomValidity(''));
  dom.sourceCollectionName.addEventListener('input', () => dom.sourceCollectionName.setCustomValidity(''));
  dom.sourceSearch.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => void loadSources(), 180);
  });
  dom.sourceForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void saveSourceDraft();
  });
  dom.sourceDeleteButton.addEventListener('click', () => {
    if (!selectedSource) return;
    void deleteSource(selectedSource.id, selectedSource.title);
  });
  dom.sourceRelationshipsButton.addEventListener('click', () => {
    if (selectedSource) void openRelationships({ targetType: 'source', targetId: selectedSource.id });
  });
  dom.sourceTransferExportButton.addEventListener('click', () => {
    if (selectedSource) openSourceExportDialog(selectedSource);
  });
  dom.sourceUploadButton.addEventListener('click', () => dom.sourceFileInput.click());
  dom.sourceFileDropzone.addEventListener('click', () => {
    if (!sourceFilesAreBusy()) dom.sourceFileInput.click();
  });
  dom.sourceFileDropzone.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    if (!sourceFilesAreBusy()) dom.sourceFileInput.click();
  });
  dom.sourceFileDropzone.addEventListener('dragenter', (event) => {
    event.preventDefault();
    sourceFileDropDepth += 1;
    dom.sourceFileDropzone.classList.add('is-dragging');
  });
  dom.sourceFileDropzone.addEventListener('dragover', (event) => event.preventDefault());
  dom.sourceFileDropzone.addEventListener('dragleave', (event) => {
    event.preventDefault();
    sourceFileDropDepth = Math.max(0, sourceFileDropDepth - 1);
    if (!sourceFileDropDepth) dom.sourceFileDropzone.classList.remove('is-dragging');
  });
  dom.sourceFileDropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    sourceFileDropDepth = 0;
    dom.sourceFileDropzone.classList.remove('is-dragging');
    if (!sourceFilesAreBusy()) void addSourceFiles(event.dataTransfer?.files);
  });
  dom.sourceFileInput.addEventListener('change', () => {
    const files = [...dom.sourceFileInput.files];
    dom.sourceFileInput.value = '';
    void addSourceFiles(files);
  });
  dom.sourceCollectionLinkButton.addEventListener('click', async () => {
    if (!selectedSource || !dom.sourceCollectionSelect.value) return;
    await apiRequest(
      `/source-collections/${encodeURIComponent(dom.sourceCollectionSelect.value)}/sources/${encodeURIComponent(selectedSource.id)}`,
      { method: 'PUT', body: {} }
    );
    const refreshed = await apiRequest(`/sources/${encodeURIComponent(selectedSource.id)}`);
    selectedSource = refreshed.source;
    renderSourceDetail();
    await refreshSourceCatalog();
  });
  dom.sourceLibraryLinkButton.addEventListener('click', async () => {
    if (!selectedSource || !dom.sourceLibrarySelect.value) return;
    await flushWorkspaceSync();
    const result = await apiRequest(`/sources/${selectedSource.id}/libraries/${dom.sourceLibrarySelect.value}`, {
      method: 'PUT',
      body: {}
    });
    selectedSource = result.source;
    renderSourceDetail();
    await refreshSourceCatalog();
    notifySourcesChanged();
  });
  dom.sourceElementLinkButton.addEventListener('click', async () => {
    if (!selectedSource || !state.activeLibraryElementId) return;
    await flushWorkspaceSync();
    const result = await apiRequest(`/sources/${selectedSource.id}/element-links`, {
      method: 'POST',
      body: {
        id: crypto.randomUUID(),
        elementId: state.activeLibraryElementId,
        sourceFileId: dom.sourceFileSelect.value,
        relationType: dom.sourceRelationType.value,
        locator: dom.sourceLocator.value.trim()
      }
    });
    selectedSource = result.source;
    dom.sourceLocator.value = '';
    renderSourceDetail();
    await refreshElementSourceLinks();
    await refreshSourceCatalog();
  });
  window.addEventListener('tasks-changed', () => {
    if (isSourcesPanelOpen() && selectedSource && !hasUnsavedSourceChanges()) void selectSource(selectedSource.id);
  });
  window.addEventListener('calendar-changed', () => {
    if (isSourcesPanelOpen() && selectedSource && !hasUnsavedSourceChanges()) void selectSource(selectedSource.id);
  });
}
