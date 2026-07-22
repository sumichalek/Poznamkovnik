import {
  elementTypeLabels,
  elementTypes,
  HORIZONTAL_EDITOR_MIN_RATIO,
  HORIZONTAL_EDITOR_MIN_WIDTH
} from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';
import {
  detailLibrary,
  elementsForLibrary,
  saveLibraryElements,
  setElementsForLibrary
} from './storage.js';
import { updateTopbarVisibility } from './topbar.js';
import {
  articleEditorContent,
  clearArticleEditor,
  focusArticleEditor,
  setArticleEditorContent
} from './article-editor.js';
import { refreshEditorResizeHandle } from './editor-resize.js';
import { openSourcesPanel, refreshElementSourceLinks } from './sources.js';
import { apiRequest } from './api.js';

window.addEventListener('sources-changed', () => renderLibraryDetailPanel());

export function currentFolderId() {
  return state.activeFolderPath.at(-1) || '';
}

export function currentFolderItems(libraryId = state.activeDetailLibraryId) {
  const folderId = currentFolderId();
  return elementsForLibrary(libraryId).filter((item) => (item.parentId || '') === folderId);
}

export function activeFolderPathItems(libraryId = state.activeDetailLibraryId) {
  const itemsById = new Map(elementsForLibrary(libraryId).map((item) => [item.id, item]));
  return state.activeFolderPath.map((folderId) => itemsById.get(folderId)).filter(Boolean);
}

function activeFolder() {
  return activeFolderPathItems().at(-1) || null;
}

export function elementTitle(item) {
  if (item?.title) return item.title;
  if (item?.type === 'folder') return 'Nový priečinok';
  return item?.type === 'article' ? 'Nový článok' : 'Nová poznámka';
}

function nextElementTitle(type) {
  const baseTitle = type === 'folder' ? 'Nový priečinok' : type === 'article' ? 'Nový článok' : 'Nová poznámka';
  const existingTitles = new Set(currentFolderItems().map((item) => item.title));
  if (!existingTitles.has(baseTitle)) return baseTitle;

  let counter = 2;
  while (existingTitles.has(`${baseTitle} ${counter}`)) counter += 1;
  return `${baseTitle} ${counter}`;
}

function folderPathTo(folderId) {
  const itemsById = new Map(elementsForLibrary().map((item) => [item.id, item]));
  const path = [];
  const seenIds = new Set();
  let nextId = folderId;

  while (nextId) {
    const folder = itemsById.get(nextId);
    if (!folder || folder.type !== 'folder' || seenIds.has(folder.id)) return [];
    path.unshift(folder.id);
    seenIds.add(folder.id);
    nextId = folder.parentId || '';
  }

  return path;
}

function normalizeActiveFolderPath() {
  const itemsById = new Map(elementsForLibrary().map((item) => [item.id, item]));
  const normalizedPath = [];
  let expectedParentId = '';

  for (const folderId of state.activeFolderPath) {
    const folder = itemsById.get(folderId);
    if (!folder || folder.type !== 'folder' || (folder.parentId || '') !== expectedParentId) break;
    normalizedPath.push(folder.id);
    expectedParentId = folder.id;
  }

  state.activeFolderPath = normalizedPath;
}

function resetFolderRenameForm() {
  state.editingFolderId = '';
  dom.folderRenameForm.hidden = true;
  dom.libraryDetailTitle.hidden = false;
  dom.folderRenameInput.value = '';
  dom.folderRenameInput.setCustomValidity('');
}

function updateLibraryPathControls() {
  const library = detailLibrary();
  const pathItems = activeFolderPathItems(library?.id);
  const pathLabels = pathItems.map(elementTitle);
  const rootLabel = library?.name || 'Knižnica';
  const visiblePath = [rootLabel, ...pathLabels].join(' / ');
  const fullPath = visiblePath;
  const folder = pathItems.at(-1) || null;
  const folderActionsVisible = Boolean(folder && !state.activeLibraryElementId);

  dom.libraryDetailTitle.textContent = visiblePath;
  dom.libraryDetailTitle.title = fullPath;
  dom.folderHomeButton.disabled = !state.activeFolderPath.length;
  dom.folderUpButton.disabled = !state.activeFolderPath.length;
  dom.folderRenameButton.hidden = !folderActionsVisible;
  dom.folderDeleteButton.hidden = !folderActionsVisible;

  if (!folder || state.editingFolderId !== folder.id) resetFolderRenameForm();
}

function descendantElementIds(folderId) {
  const ids = new Set([folderId]);
  let changed = true;

  while (changed) {
    changed = false;
    elementsForLibrary().forEach((item) => {
      if (!ids.has(item.id) && ids.has(item.parentId)) {
        ids.add(item.id);
        changed = true;
      }
    });
  }

  return ids;
}

function activeLibraryElement() {
  return elementsForLibrary().find((item) => item.id === state.activeLibraryElementId) || null;
}

function syncEditorDock() {
  const editorIsOpen = state.editorLayout !== 'closed' && Boolean(activeLibraryElement());
  if (!editorIsOpen) state.editorLayout = 'closed';

  dom.libraryEditorDock.classList.toggle('is-open', editorIsOpen);
  dom.libraryEditorDock.setAttribute('aria-hidden', String(!editorIsOpen));
  if (editorIsOpen) {
    document.body.dataset.editorLayout = state.editorLayout;
  } else {
    delete document.body.dataset.editorLayout;
  }

  const isFullscreen = state.editorLayout === 'fullscreen';
  dom.libraryEditorFullscreen.dataset.mode = isFullscreen ? 'restore' : 'maximize';
  dom.libraryEditorFullscreen.title = isFullscreen ? 'Zobraziť vedľa obsahu' : 'Celá plocha';
  dom.libraryEditorFullscreen.setAttribute(
    'aria-label',
    isFullscreen ? 'Zobraziť editor vedľa obsahu' : 'Otvoriť editor na celej ploche'
  );
  dom.editorResizeHandle.setAttribute('aria-hidden', String(!editorIsOpen || isFullscreen));
  dom.editorResizeHandle.tabIndex = editorIsOpen && !isFullscreen ? 0 : -1;
}

export function updateEditorDockAxis() {
  const viewport = window.visualViewport;
  const width = viewport?.width || window.innerWidth;
  const height = viewport?.height || window.innerHeight;
  state.editorAxis =
    width >= HORIZONTAL_EDITOR_MIN_WIDTH && width / Math.max(height, 1) >= HORIZONTAL_EDITOR_MIN_RATIO
      ? 'horizontal'
      : 'vertical';
  document.body.dataset.editorAxis = state.editorAxis;
  refreshEditorResizeHandle();
}

export function toggleEditorFullscreen() {
  if (!activeLibraryElement()) return;
  state.editorLayout = state.editorLayout === 'fullscreen' ? 'docked' : 'fullscreen';
  syncEditorDock();
  updateTopbarVisibility();
  focusArticleEditor();
}

export function exitEditorFullscreen() {
  if (state.editorLayout !== 'fullscreen') return false;
  state.editorLayout = 'docked';
  syncEditorDock();
  updateTopbarVisibility();
  focusArticleEditor();
  return true;
}

function runLibraryItemAction(elementId, action) {
  const now = window.performance.now();
  if (
    state.lastLibraryItemAction &&
    state.lastLibraryItemAction.elementId === elementId &&
    state.lastLibraryItemAction.action === action &&
    now - state.lastLibraryItemAction.at < 350
  ) {
    return;
  }

  state.lastLibraryItemAction = { elementId, action, at: now };
  if (action === 'delete') {
    deleteLibraryElement(elementId);
    return;
  }

  openLibraryElement(elementId, { focusTitle: action === 'edit' });
}

function stopAndRunLibraryItemAction(event, elementId, action) {
  event.preventDefault();
  event.stopPropagation();
  runLibraryItemAction(elementId, action);
}

function createLibraryItemCard(item) {
  const card = document.createElement('article');
  const cardClasses = ['library-item-card', `${item.type}-item`];
  if (item.id === state.activeLibraryElementId) cardClasses.push('active');
  if (state.activeFolderPath.includes(item.id)) cardClasses.push('folder-open');
  card.className = cardClasses.join(' ');
  card.dataset.elementId = item.id;

  const openButton = document.createElement('button');
  openButton.type = 'button';
  openButton.className = 'library-item-open';
  openButton.dataset.itemAction = 'open';
  openButton.setAttribute('aria-label', `Otvoriť ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`);
  openButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, 'open'));
  openButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, 'open'));
  openButton.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, 'open');
  });

  const windowBar = document.createElement('span');
  windowBar.className = 'library-item-window-bar';
  for (let dotIndex = 0; dotIndex < 3; dotIndex += 1) {
    windowBar.append(document.createElement('span'));
  }

  const icon = document.createElement('span');
  icon.className = `library-item-icon ${item.type}-icon`;
  icon.setAttribute('aria-hidden', 'true');

  const title = document.createElement('span');
  title.className = 'library-item-title';
  title.textContent = elementTitle(item);

  const meta = document.createElement('span');
  meta.className = 'library-item-meta';
  const childCount = item.type === 'folder' ? elementsForLibrary().filter((child) => child.parentId === item.id).length : 0;
  meta.textContent = item.type === 'folder' ? `${elementTypeLabels[item.type]} · ${childCount}` : elementTypeLabels[item.type];

  openButton.append(windowBar, icon, title, meta);

  const actions = document.createElement('div');
  actions.className = 'library-item-actions';

  if (item.type !== 'folder') {
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'library-item-action';
    editButton.dataset.itemAction = 'edit';
    editButton.textContent = '✎';
    editButton.title = 'Upraviť prvok';
    editButton.setAttribute('aria-label', `Upraviť ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`);
    editButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, 'edit'));
    editButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, 'edit'));
    editButton.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, 'edit');
    });
    actions.append(editButton);
  }

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.className = 'library-item-action danger';
  deleteButton.dataset.itemAction = 'delete';
  deleteButton.textContent = '×';
  deleteButton.title = 'Zmazať prvok';
  deleteButton.setAttribute('aria-label', `Zmazať ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`);
  deleteButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, 'delete');
  });
  actions.append(deleteButton);

  card.append(openButton, actions);
  return card;
}

export function handleLibraryItemClick(event) {
  const card = event.target.closest('.library-item-card');
  if (!card || !dom.libraryItemsList.contains(card)) return;

  const elementId = card.dataset.elementId;
  if (!elementId) return;

  event.preventDefault();
  const action = event.target.closest('[data-item-action]')?.dataset.itemAction || 'open';
  runLibraryItemAction(elementId, action);
}

function renderLibraryItems() {
  dom.libraryItemsList.innerHTML = '';
  const library = detailLibrary();
  if (!library) return;

  const typeOrder = { folder: 0, note: 1, article: 2 };
  const items = currentFolderItems(library.id).sort(
    (first, second) =>
      typeOrder[first.type] - typeOrder[second.type] ||
      elementTitle(first).localeCompare(elementTitle(second), 'sk', { sensitivity: 'base' })
  );

  if (!items.length) {
    const empty = document.createElement('p');
    empty.className = 'library-items-empty';
    empty.textContent = 'Prázdne.';
    dom.libraryItemsList.append(empty);
    return;
  }

  items.forEach((item) => {
    dom.libraryItemsList.append(createLibraryItemCard(item));
  });
}

async function renderLibrarySourceLinks(libraryId) {
  dom.librarySourceLinks.hidden = true;
  dom.librarySourceLinks.replaceChildren();
  if (state.activeFolderPath.length) return;
  try {
    const result = await apiRequest(`/libraries/${encodeURIComponent(libraryId)}/sources`);
    if (state.activeDetailLibraryId !== libraryId || state.activeFolderPath.length || !result.sources.length) return;
    const heading = document.createElement('h3');
    heading.textContent = 'Zdroje v knižnici';
    const list = document.createElement('div');
    list.className = 'library-source-list';
    result.sources.forEach((source) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-source-link';
      button.textContent = source.note ? `${source.title} — ${source.note}` : source.title;
      button.title = 'Otvoriť zdroj';
      button.addEventListener('click', () => void openSourcesPanel({ sourceId: source.id, pinned: true }));
      list.append(button);
    });
    dom.librarySourceLinks.append(heading, list);
    dom.librarySourceLinks.hidden = false;
  } catch {
    dom.librarySourceLinks.hidden = true;
  }
}

export function closeLibraryElementEditor({ render = true } = {}) {
  state.activeLibraryElementId = '';
  state.editorLayout = 'closed';
  dom.libraryDetailPanel.classList.remove('is-editing');
  dom.libraryBrowser.hidden = false;
  syncEditorDock();
  dom.libraryEditorTitle.value = '';
  clearArticleEditor();
  void refreshElementSourceLinks();
  if (render) renderLibraryDetailPanel();
}

export function renderLibraryDetailPanel() {
  const library = detailLibrary();
  if (!library) {
    dom.libraryDetailTitle.textContent = 'Koreň';
    dom.folderHomeButton.disabled = true;
    dom.folderUpButton.disabled = true;
    dom.folderRenameButton.hidden = true;
    dom.folderDeleteButton.hidden = true;
    resetFolderRenameForm();
    return;
  }
  normalizeActiveFolderPath();
  updateLibraryPathControls();
  if (state.activeLibraryElementId && !activeLibraryElement()) {
    closeLibraryElementEditor({ render: false });
    updateLibraryPathControls();
  }
  renderLibraryItems();
  void renderLibrarySourceLinks(library.id);
}

export function createLibraryElement(type) {
  const library = detailLibrary();
  if (!library || !elementTypes.has(type)) return;

  state.librariesPanelPinned = true;
  state.libraryDetailPanelPinned = true;
  const item = {
    id: crypto.randomUUID(),
    type,
    parentId: currentFolderId(),
    title: nextElementTitle(type),
    content: '',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };

  setElementsForLibrary(library.id, [item, ...elementsForLibrary(library.id)]);
  saveLibraryElements();
  closeLibraryElementEditor({ render: false });
  renderLibraryDetailPanel();
  updateTopbarVisibility();
}

export function openLibraryElement(elementId, { focusTitle = false } = {}) {
  const item = elementsForLibrary().find((element) => element.id === elementId);
  if (!item) return;

  state.librariesPanelPinned = true;
  state.libraryDetailPanelPinned = true;

  if (item.type === 'folder') {
    closeLibraryElementEditor({ render: false });
    state.activeFolderPath = [...folderPathTo(item.parentId || ''), item.id];
    state.activeLibraryElementId = '';
    renderLibraryDetailPanel();
    updateTopbarVisibility();
    return;
  }

  state.activeLibraryElementId = item.id;
  state.editorLayout = 'docked';
  dom.libraryDetailPanel.classList.add('is-editing');
  dom.libraryBrowser.hidden = false;
  dom.libraryEditorTitle.value = elementTitle(item);
  setArticleEditorContent(item.content, item.type === 'article' ? 'Píšte článok...' : 'Píšte poznámku...');
  dom.libraryEditor.dataset.elementType = item.type;
  updateEditorDockAxis();
  syncEditorDock();
  renderLibraryDetailPanel();
  void refreshElementSourceLinks();
  updateTopbarVisibility();
  if (focusTitle) {
    dom.libraryEditorTitle.focus();
    dom.libraryEditorTitle.select();
  } else {
    focusArticleEditor();
  }
}

export function updateActiveElementFromEditor({ renderItems = false } = {}) {
  const library = detailLibrary();
  if (!library || !state.activeLibraryElementId) return;

  const items = elementsForLibrary(library.id);
  const itemIndex = items.findIndex((item) => item.id === state.activeLibraryElementId);
  if (itemIndex === -1) return;

  const nextItems = [...items];
  nextItems[itemIndex] = {
    ...nextItems[itemIndex],
    title: dom.libraryEditorTitle.value.trim(),
    content: articleEditorContent(),
    updatedAt: new Date().toISOString()
  };

  setElementsForLibrary(library.id, nextItems);
  saveLibraryElements();
  if (renderItems) renderLibraryItems();
}

export function deleteLibraryElement(elementId = state.activeLibraryElementId) {
  const library = detailLibrary();
  const item = elementsForLibrary(library?.id).find((element) => element.id === elementId);
  if (!library || !item) return;

  const deletedIds = item.type === 'folder' ? descendantElementIds(item.id) : new Set([item.id]);
  const message =
    item.type === 'folder'
      ? `Zmazať priečinok "${elementTitle(item)}" aj celý jeho obsah?`
      : `Zmazať ${elementTypeLabels[item.type].toLowerCase()} "${elementTitle(item)}"?`;
  if (!confirm(message)) return;

  setElementsForLibrary(
    library.id,
    elementsForLibrary(library.id).filter((element) => !deletedIds.has(element.id))
  );
  saveLibraryElements();

  if (deletedIds.has(state.activeLibraryElementId)) {
    closeLibraryElementEditor({ render: false });
  }
  const deletedFolderIndex = state.activeFolderPath.findIndex((folderId) => deletedIds.has(folderId));
  if (deletedFolderIndex !== -1) {
    state.activeFolderPath = state.activeFolderPath.slice(0, deletedFolderIndex);
  }
  renderLibraryDetailPanel();
}

export function openLibraryRoot() {
  if (!state.activeFolderPath.length) return;
  closeLibraryElementEditor({ render: false });
  state.activeFolderPath = [];
  state.activeLibraryElementId = '';
  renderLibraryDetailPanel();
  updateTopbarVisibility();
}

export function openParentFolder() {
  if (!state.activeFolderPath.length) return;
  closeLibraryElementEditor({ render: false });
  state.activeFolderPath = state.activeFolderPath.slice(0, -1);
  state.activeLibraryElementId = '';
  renderLibraryDetailPanel();
  updateTopbarVisibility();
}

export function startFolderRename() {
  const folder = activeFolder();
  if (!folder || state.activeLibraryElementId) return;

  const pathLabels = activeFolderPathItems().slice(0, -1).map(elementTitle);
  state.editingFolderId = folder.id;
  dom.folderRenamePrefix.textContent = `${[detailLibrary()?.name || 'Knižnica', ...pathLabels].join(' / ')} /`;
  dom.folderRenameInput.value = elementTitle(folder);
  dom.libraryDetailTitle.hidden = true;
  dom.folderRenameForm.hidden = false;
  dom.folderRenameInput.focus();
  dom.folderRenameInput.select();
}

export function cancelFolderRename() {
  if (dom.folderRenameForm.hidden) return;
  resetFolderRenameForm();
}

export function renameCurrentFolder() {
  const folder = activeFolder();
  const nextTitle = dom.folderRenameInput.value.trim();
  if (!folder || state.editingFolderId !== folder.id) {
    cancelFolderRename();
    return;
  }
  if (!nextTitle) {
    dom.folderRenameInput.setCustomValidity('Názov priečinka je povinný.');
    dom.folderRenameInput.reportValidity();
    return;
  }

  const items = elementsForLibrary();
  const itemIndex = items.findIndex((item) => item.id === folder.id);
  if (itemIndex === -1) return;

  const nextItems = [...items];
  nextItems[itemIndex] = { ...nextItems[itemIndex], title: nextTitle, updatedAt: new Date().toISOString() };
  setElementsForLibrary(detailLibrary().id, nextItems);
  saveLibraryElements();
  state.editingFolderId = '';
  renderLibraryDetailPanel();
}

export function deleteCurrentFolder() {
  const folder = activeFolder();
  if (!folder || state.activeLibraryElementId) return;
  cancelFolderRename();
  deleteLibraryElement(folder.id);
}
