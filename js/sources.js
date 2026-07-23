import { apiRequest, uploadSourceFile } from './api.js';
import { dom } from './dom.js';
import { state } from './state.js';
import { flushWorkspaceSync } from './storage.js';
import { updateTopbarVisibility } from './topbar.js';

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
  derived: 'Vychádza zo zdroja'
};

const TEXT_PREVIEW_MAX_BYTES = 2 * 1024 * 1024;

let sources = [];
let selectedSource = null;
let searchTimer = 0;
let panelHideTimer = 0;
let panelPinned = false;
let previewSourceId = '';
let previewRequestId = 0;
let loadedSourcesQuery = null;
let loadingSourcesQuery = null;
let sourcesLoadPromise = null;
let sourcesLoadRequestId = 0;

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

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceFileUrl(file, { download = false } = {}) {
  const suffix = download ? '?download=1' : '';
  return `/api/files/${encodeURIComponent(file.id)}${suffix}`;
}

function setSourcePreviewOpen(open) {
  dom.sourcePreviewDock.classList.toggle('is-open', open);
  dom.sourcePreviewDock.setAttribute('aria-hidden', String(!open));
  updateTopbarVisibility();
}

export function isSourcePreviewOpen() {
  return dom.sourcePreviewDock.classList.contains('is-open');
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

function showSourcePreviewFallback(message) {
  hideSourcePreviewViews();
  dom.sourcePreviewFallbackMessage.textContent = message;
  dom.sourcePreviewFallback.hidden = false;
}

export function closeSourcePreview() {
  previewRequestId += 1;
  previewSourceId = '';
  hideSourcePreviewViews();
  setSourcePreviewOpen(false);
}

async function openSourceFile(file) {
  if (!selectedSource) return;

  const requestId = ++previewRequestId;
  const fileUrl = sourceFileUrl(file);
  previewSourceId = selectedSource.id;
  dom.sourcePreviewSource.textContent = selectedSource.title;
  dom.sourcePreviewTitle.textContent = file.originalName;
  dom.sourcePreviewMeta.textContent = `${file.mimeType} · ${formatFileSize(file.sizeBytes)}`;
  dom.sourcePreviewExternal.href = fileUrl;
  dom.sourcePreviewDownload.href = sourceFileUrl(file, { download: true });
  dom.sourcePreviewDownload.download = file.originalName;
  setSourcePreviewOpen(true);
  hideSourcePreviewViews();

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

  showSourcePreviewFallback(
    file.sizeBytes > TEXT_PREVIEW_MAX_BYTES && file.mimeType.startsWith('text/')
      ? 'Textový súbor je na vstavaný náhľad príliš veľký. Otvor ho v novom okne alebo stiahni.'
      : 'Pre tento formát zatiaľ nemáme vstavaný náhľad. Otvor ho v novom okne alebo stiahni.'
  );
}

function setPanelOpen(open) {
  dom.sourcesPanel.classList.toggle('is-open', open);
  dom.sourcesPanel.setAttribute('aria-hidden', String(!open));
  dom.sourcesButton.setAttribute('aria-expanded', String(open));
  updateTopbarVisibility();
}

export function isSourcesPanelOpen() {
  return dom.sourcesPanel.classList.contains('is-open');
}

export function closeSourcesPanel({ force = false } = {}) {
  if (panelPinned && !force) return;
  window.clearTimeout(panelHideTimer);
  panelPinned = false;
  setPanelOpen(false);
}

export async function openSourcesPanel({ sourceId = '', pinned = false } = {}) {
  window.clearTimeout(panelHideTimer);
  if (pinned) panelPinned = true;
  setPanelOpen(true);
  await loadSources();
  if (sourceId) await selectSource(sourceId);
}

function scheduleSourcesPanelClose() {
  window.clearTimeout(panelHideTimer);
  panelHideTimer = window.setTimeout(() => {
    const hoveringPanel = dom.sourcesPanel.matches(':hover');
    const hoveringButton = dom.sourcesButton.matches(':hover');
    const focusedPanel = dom.sourcesPanel.contains(document.activeElement);
    const focusedButton = dom.sourcesButton === document.activeElement;
    if (!panelPinned && !hoveringPanel && !hoveringButton && !focusedPanel && !focusedButton) {
      closeSourcesPanel();
    }
  }, 160);
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
      renderSourceList();
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

function renderSourceList() {
  dom.sourcesList.replaceChildren();
  if (!sources.length) {
    const empty = document.createElement('p');
    empty.className = 'sources-empty';
    empty.textContent = dom.sourceSearch.value.trim() ? 'Nenašli sa žiadne zdroje.' : 'Zatiaľ žiadne zdroje.';
    dom.sourcesList.append(empty);
    return;
  }
  sources.forEach((source) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'source-list-item';
    button.classList.toggle('is-active', source.id === selectedSource?.id);
    button.addEventListener('click', () => void selectSource(source.id));

    const title = document.createElement('span');
    title.className = 'source-list-title';
    title.textContent = source.title;
    const meta = document.createElement('span');
    meta.className = 'source-list-meta';
    const usage = [
      source.fileCount ? `${source.fileCount} súb.` : '',
      source.libraryCount ? `${source.libraryCount} kn.` : '',
      source.elementCount ? `${source.elementCount} prv.` : ''
    ]
      .filter(Boolean)
      .join(' · ');
    meta.textContent = [kindLabels[source.kind] || 'Zdroj', usage].filter(Boolean).join(' · ');
    button.append(title, meta);
    dom.sourcesList.append(button);
  });
}

async function selectSource(sourceId) {
  if (previewSourceId && previewSourceId !== sourceId) closeSourcePreview();
  const result = await apiRequest(`/sources/${encodeURIComponent(sourceId)}`);
  selectedSource = result.source;
  renderSourceList();
  renderSourceDetail();
}

function startNewSource() {
  closeSourcePreview();
  selectedSource = null;
  dom.sourceForm.reset();
  dom.sourceKind.value = 'source';
  dom.sourceFormTitle.textContent = 'Nový zdroj';
  dom.sourceDeleteButton.hidden = true;
  dom.sourceDetailEmpty.hidden = true;
  dom.sourceForm.hidden = false;
  hideSourceSections();
  dom.sourceTitle.focus();
  renderSourceList();
}

function hideSourceSections() {
  dom.sourceFilesSection.hidden = true;
  dom.sourceLibrarySection.hidden = true;
  dom.sourceElementSection.hidden = true;
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
  dom.sourceTitle.value = selectedSource.title;
  dom.sourceKind.value = selectedSource.kind in kindLabels ? selectedSource.kind : 'source';
  dom.sourceYear.value = metadata.year || '';
  dom.sourceAuthor.value = metadata.author || '';
  dom.sourceUrl.value = metadata.url || '';
  dom.sourceDescription.value = selectedSource.description || '';
  dom.sourceFilesSection.hidden = false;
  dom.sourceLibrarySection.hidden = false;
  dom.sourceElementSection.hidden = false;
  renderFiles();
  renderLibraries();
  renderElements();
}

function renderFiles() {
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
    const meta = document.createElement('span');
    meta.textContent = `${file.mimeType} · ${formatFileSize(file.sizeBytes)}`;
    const download = document.createElement('a');
    download.className = 'source-file-download';
    download.href = sourceFileUrl(file, { download: true });
    download.download = file.originalName;
    download.textContent = '↓';
    download.title = `Stiahnuť ${file.originalName}`;
    download.setAttribute('aria-label', `Stiahnuť ${file.originalName}`);
    const copy = document.createElement('div');
    copy.className = 'source-file-copy';
    copy.append(name, meta);
    row.append(copy, download);
    dom.sourceFilesList.append(row);
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
    remove.textContent = '×';
    remove.title = `Odobrať z knižnice ${library.name}`;
    remove.setAttribute('aria-label', `Odobrať z knižnice ${library.name}`);
    remove.addEventListener('click', async () => {
      const result = await apiRequest(`/sources/${selectedSource.id}/libraries/${library.id}`, { method: 'DELETE' });
      selectedSource = result.source;
      renderSourceDetail();
      await loadSources({ force: true });
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
    label.textContent = `${element.libraryName} / ${element.title} · ${relationLabels[element.relationType] || element.relationType}${locator}`;
    label.title = `Otvoriť ${element.title}`;
    label.addEventListener('click', () => {
      window.dispatchEvent(
        new CustomEvent('source-open-element', { detail: { libraryId: element.libraryId, elementId: element.id } })
      );
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'source-unlink-button';
    remove.textContent = '×';
    remove.title = `Odpojiť od ${element.title}`;
    remove.setAttribute('aria-label', `Odpojiť od ${element.title}`);
    remove.addEventListener('click', async () => {
      const result = await apiRequest(`/sources/${selectedSource.id}/element-links/${element.linkId}`, { method: 'DELETE' });
      selectedSource = result.source;
      renderSourceDetail();
      await refreshElementSourceLinks();
      await loadSources({ force: true });
    });
    row.append(label, remove);
    dom.sourceElementsList.append(row);
  });
}

export async function refreshElementSourceLinks() {
  const elementId = state.activeLibraryElementId;
  if (!elementId) {
    dom.editorSourceLinks.hidden = true;
    dom.editorSourceLinks.replaceChildren();
    return;
  }
  try {
    const result = await apiRequest(`/elements/${encodeURIComponent(elementId)}/sources`);
    dom.editorSourceLinks.replaceChildren();
    if (!result.sources.length) {
      dom.editorSourceLinks.hidden = true;
      return;
    }
    const label = document.createElement('span');
    label.className = 'editor-source-label';
    label.textContent = 'Zdroje';
    dom.editorSourceLinks.append(label);
    result.sources.forEach((source) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'editor-source-chip';
      button.textContent = source.locator ? `${source.title} · ${source.locator}` : source.title;
      button.title = 'Otvoriť detail zdroja';
      button.addEventListener('click', () => void openSourcesPanel({ sourceId: source.id, pinned: true }));
      dom.editorSourceLinks.append(button);
    });
    dom.editorSourceLinks.hidden = false;
  } catch {
    dom.editorSourceLinks.hidden = true;
  }
}

export function initializeSources() {
  dom.sourcesButton.addEventListener('click', () => {
    if (panelPinned && isSourcesPanelOpen()) {
      closeSourcesPanel({ force: true });
      dom.sourcesButton.blur();
      return;
    }
    void openSourcesPanel({ pinned: true });
  });
  dom.sourcesButton.addEventListener('pointerenter', () => void openSourcesPanel());
  dom.sourcesButton.addEventListener('pointerleave', scheduleSourcesPanelClose);
  dom.sourcesButton.addEventListener('focus', () => void openSourcesPanel());
  dom.sourcesPanel.addEventListener('pointerenter', () => void openSourcesPanel());
  dom.sourcesPanel.addEventListener('pointerleave', scheduleSourcesPanelClose);
  dom.sourcesPanel.addEventListener('focusin', () => void openSourcesPanel());
  dom.sourcesPanel.addEventListener('focusout', scheduleSourcesPanelClose);
  dom.sourcesCloseButton.addEventListener('click', () => closeSourcesPanel({ force: true }));
  dom.sourcePreviewCloseButton.addEventListener('click', closeSourcePreview);
  dom.sourceCreateButton.addEventListener('click', startNewSource);
  dom.sourceSearch.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => void loadSources(), 180);
  });
  dom.sourceForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = {
      title: dom.sourceTitle.value,
      kind: dom.sourceKind.value,
      description: dom.sourceDescription.value,
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
    renderSourceDetail();
    await loadSources({ force: true });
    notifySourcesChanged();
  });
  dom.sourceDeleteButton.addEventListener('click', async () => {
    if (!selectedSource || !confirm(`Zmazať zdroj "${selectedSource.title}" aj jeho súbory?`)) return;
    if (previewSourceId === selectedSource.id) closeSourcePreview();
    await apiRequest(`/sources/${selectedSource.id}`, { method: 'DELETE' });
    selectedSource = null;
    renderSourceDetail();
    await loadSources({ force: true });
    await refreshElementSourceLinks();
    notifySourcesChanged();
  });
  dom.sourceUploadButton.addEventListener('click', () => dom.sourceFileInput.click());
  dom.sourceFileInput.addEventListener('change', async () => {
    if (!selectedSource) return;
    const files = [...dom.sourceFileInput.files];
    for (const file of files) {
      const result = await uploadSourceFile(selectedSource.id, file);
      selectedSource = result.source;
    }
    dom.sourceFileInput.value = '';
    renderSourceDetail();
    await loadSources({ force: true });
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
    await loadSources({ force: true });
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
        relationType: dom.sourceRelationType.value,
        locator: dom.sourceLocator.value.trim()
      }
    });
    selectedSource = result.source;
    dom.sourceLocator.value = '';
    renderSourceDetail();
    await refreshElementSourceLinks();
    await loadSources({ force: true });
  });
}
