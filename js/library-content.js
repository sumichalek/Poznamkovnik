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
import { createAppIcon, setAppIcon } from './app-icons.js';
import { createLibraryItemIcon } from './library-icons.js';
import { refreshElementSourceLinks } from './sources.js';
import { refreshElementTaskLinks } from './tasks.js';
import { refreshElementCalendarLinks } from './calendar.js';
import { apiRequest } from './api.js';
import { readTagField, setTagField } from './tags.js';
import { downloadLibraryElementMarkdown } from './markdown-export.js';

window.addEventListener('sources-changed', () => renderLibraryDetailPanel());
window.addEventListener('tasks-changed', () => renderLibraryDetailPanel());
window.addEventListener('calendar-changed', () => renderLibraryDetailPanel());

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

function updateLibraryPathControls() {
  const library = detailLibrary();
  const pathItems = activeFolderPathItems(library?.id);
  const pathLabels = pathItems.map(elementTitle);
  const rootLabel = library?.name || 'Knižnica';
  const visiblePath = [rootLabel, ...pathLabels].join(' / ');

  dom.libraryDetailTitle.textContent = visiblePath;
  dom.libraryDetailTitle.title = visiblePath;
  dom.folderHomeButton.disabled = !state.activeFolderPath.length;
  dom.folderUpButton.disabled = !state.activeFolderPath.length;
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
  setAppIcon(dom.libraryEditorFullscreen.querySelector('.app-icon'), isFullscreen ? 'minimize' : 'maximize');
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
  if (action === 'rename') {
    startFolderRename(elementId);
    return;
  }
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

  const icon = createLibraryItemIcon(item.type);

  const title = document.createElement('span');
  title.className = 'library-item-title';
  title.textContent = elementTitle(item);

  const meta = document.createElement('span');
  meta.className = 'library-item-meta';
  const childCount = item.type === 'folder' ? elementsForLibrary().filter((child) => child.parentId === item.id).length : 0;
  const typeMeta = item.type === 'folder' ? `${elementTypeLabels[item.type]} · ${childCount}` : elementTypeLabels[item.type];
  const tagMeta = (item.tags || []).slice(0, 2).map((tag) => `#${tag}`).join(' ');
  meta.textContent = [typeMeta, tagMeta].filter(Boolean).join(' · ');

  openButton.append(windowBar, icon, title, meta);

  const actions = document.createElement('div');
  actions.className = 'library-item-actions';

  const editButton = document.createElement('button');
  const editAction = item.type === 'folder' ? 'rename' : 'edit';
  editButton.type = 'button';
  editButton.className = 'library-item-action';
  editButton.dataset.itemAction = editAction;
  editButton.append(createAppIcon('pencil'));
  editButton.title = item.type === 'folder' ? 'Premenovať priečinok' : 'Upraviť prvok';
  editButton.setAttribute(
    'aria-label',
    item.type === 'folder'
      ? `Premenovať priečinok ${elementTitle(item)}`
      : `Upraviť ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`
  );
  editButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, editAction));
  editButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, editAction));
  editButton.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, editAction);
  });
  actions.append(editButton);

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.className = 'library-item-action danger';
  deleteButton.dataset.itemAction = 'delete';
  deleteButton.append(createAppIcon('trash'));
  deleteButton.title = 'Zmazať prvok';
  deleteButton.setAttribute('aria-label', `Zmazať ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`);
  deleteButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, 'delete');
  });
  actions.append(deleteButton);

  if (item.type === 'folder' && state.editingFolderId === item.id) {
    card.classList.add('is-renaming');
    openButton.classList.add('is-renaming');
    const renameForm = document.createElement('form');
    renameForm.className = 'library-folder-rename';
    renameForm.dataset.folderRenameForm = item.id;
    const renameInput = document.createElement('input');
    renameInput.type = 'text';
    renameInput.maxLength = 120;
    renameInput.required = true;
    renameInput.value = elementTitle(item);
    renameInput.dataset.folderRenameInput = item.id;
    renameInput.setAttribute('aria-label', `Nový názov priečinka ${elementTitle(item)}`);
    renameInput.addEventListener('input', () => renameInput.setCustomValidity(''));
    renameInput.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      cancelFolderRename();
      renderLibraryDetailPanel();
    });
    const saveButton = document.createElement('button');
    saveButton.type = 'submit';
    saveButton.className = 'library-folder-rename-action primary';
    saveButton.append(createAppIcon('check'));
    saveButton.title = 'Potvrdiť nový názov';
    saveButton.setAttribute('aria-label', 'Potvrdiť nový názov');
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'library-folder-rename-action';
    cancelButton.append(createAppIcon('close'));
    cancelButton.title = 'Zrušiť premenovanie';
    cancelButton.setAttribute('aria-label', 'Zrušiť premenovanie');
    cancelButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      cancelFolderRename();
      renderLibraryDetailPanel();
    });
    renameForm.addEventListener('click', (event) => event.stopPropagation());
    renameForm.addEventListener('submit', (event) => {
      event.preventDefault();
      event.stopPropagation();
      renameFolder(item.id, renameInput);
    });
    renameForm.append(renameInput, saveButton, cancelButton);
    card.append(openButton, actions, renameForm);
    window.requestAnimationFrame(() => {
      renameInput.focus();
      renameInput.select();
    });
  } else {
    card.append(openButton, actions);
  }
  return card;
}

export function handleLibraryItemClick(event) {
  const card = event.target.closest('.library-item-card');
  if (!card || !dom.libraryItemsList.contains(card)) return;
  if (event.target.closest('.library-folder-rename')) return;

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
      button.addEventListener('click', () => {
        window.dispatchEvent(
          new CustomEvent('source-open-request', {
            detail: {
              sourceId: source.id,
              returnTarget: { libraryId, title: library.name }
            }
          })
        );
      });
      list.append(button);
    });
    dom.librarySourceLinks.append(heading, list);
    dom.librarySourceLinks.hidden = false;
  } catch {
    dom.librarySourceLinks.hidden = true;
  }
}

async function renderLibraryTaskLinks(libraryId) {
  dom.libraryTaskLinks.hidden = true;
  dom.libraryTaskLinks.replaceChildren();
  if (state.activeFolderPath.length) return;
  try {
    const result = await apiRequest(`/task-links/library/${encodeURIComponent(libraryId)}`);
    if (state.activeDetailLibraryId !== libraryId || state.activeFolderPath.length || !result.tasks.length) return;
    const heading = document.createElement('h3');
    heading.textContent = 'Úlohy v knižnici';
    const list = document.createElement('div');
    list.className = 'library-task-list';
    result.tasks.forEach((task) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-task-link';
      button.classList.toggle('is-done', task.status === 'done');
      button.textContent = task.title;
      button.title = 'Otvoriť úlohu';
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('task-open', { detail: { taskId: task.id } }));
      });
      list.append(button);
    });
    dom.libraryTaskLinks.append(heading, list);
    dom.libraryTaskLinks.hidden = false;
  } catch {
    dom.libraryTaskLinks.hidden = true;
  }
}

function calendarEventMeta(event) {
  if (event.allDay) return event.startDate === event.endDate ? event.startDate : `${event.startDate} - ${event.endDate}`;
  const start = event.startTime ? `${event.startDate} ${event.startTime}` : event.startDate;
  const end = event.endTime ? `${event.endDate} ${event.endTime}` : event.endDate;
  return start === end ? start : `${start} - ${end}`;
}

async function renderLibraryCalendarLinks(libraryId) {
  dom.libraryCalendarLinks.hidden = true;
  dom.libraryCalendarLinks.replaceChildren();
  if (state.activeFolderPath.length) return;
  try {
    const result = await apiRequest(`/calendar-event-links/library/${encodeURIComponent(libraryId)}`);
    if (state.activeDetailLibraryId !== libraryId || state.activeFolderPath.length || !result.events.length) return;
    const heading = document.createElement('h3');
    heading.textContent = 'Udalosti v kalendári';
    const list = document.createElement('div');
    list.className = 'library-calendar-list';
    result.events.forEach((event) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-calendar-link';
      button.textContent = `${event.title} · ${calendarEventMeta(event)}`;
      button.title = 'Otvoriť udalosť';
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('calendar-open-event', { detail: { eventId: event.id } }));
      });
      list.append(button);
    });
    dom.libraryCalendarLinks.append(heading, list);
    dom.libraryCalendarLinks.hidden = false;
  } catch {
    dom.libraryCalendarLinks.hidden = true;
  }
}

export function closeLibraryElementEditor({ render = true } = {}) {
  state.activeLibraryElementId = '';
  state.editorLayout = 'closed';
  dom.libraryDetailPanel.classList.remove('is-editing');
  dom.libraryBrowser.hidden = false;
  syncEditorDock();
  dom.libraryEditorTitle.value = '';
  setTagField(dom.libraryEditorTags, dom.libraryEditorTagChips, []);
  clearArticleEditor();
  void refreshElementSourceLinks();
  void refreshElementTaskLinks();
  void refreshElementCalendarLinks();
  if (render) renderLibraryDetailPanel();
}

export function renderLibraryDetailPanel() {
  const library = detailLibrary();
  if (!library) {
    dom.libraryDetailTitle.textContent = 'Koreň';
    dom.folderHomeButton.disabled = true;
    dom.folderUpButton.disabled = true;
    dom.libraryRelationshipsButton.disabled = true;
    return;
  }
  dom.libraryRelationshipsButton.disabled = false;
  normalizeActiveFolderPath();
  updateLibraryPathControls();
  if (state.activeLibraryElementId && !activeLibraryElement()) {
    closeLibraryElementEditor({ render: false });
    updateLibraryPathControls();
  }
  renderLibraryItems();
  void renderLibrarySourceLinks(library.id);
  void renderLibraryTaskLinks(library.id);
  void renderLibraryCalendarLinks(library.id);
}

export function createLibraryElement(type) {
  const library = detailLibrary();
  if (!library || !elementTypes.has(type)) return;

  state.librariesPanelPinned = true;
  state.libraryDetailPanelPinned = true;
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'libraries' } }));
  const item = {
    id: crypto.randomUUID(),
    type,
    parentId: currentFolderId(),
    title: nextElementTitle(type),
    content: '',
    tags: [],
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

  if (item.type === 'folder') {
    closeLibraryElementEditor({ render: false });
    state.activeFolderPath = [...folderPathTo(item.parentId || ''), item.id];
    state.activeLibraryElementId = '';
    renderLibraryDetailPanel();
    updateTopbarVisibility();
    return;
  }

  state.librariesPanelPinned = true;
  state.libraryDetailPanelPinned = true;
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'libraries' } }));
  state.activeLibraryElementId = item.id;
  state.editorLayout = 'docked';
  dom.libraryDetailPanel.classList.add('is-editing');
  dom.libraryBrowser.hidden = false;
  dom.libraryEditorTitle.value = elementTitle(item);
  setTagField(dom.libraryEditorTags, dom.libraryEditorTagChips, item.tags || []);
  setArticleEditorContent(item.content, item.type === 'article' ? 'Píšte článok...' : 'Píšte poznámku...');
  dom.libraryEditor.dataset.elementType = item.type;
  updateEditorDockAxis();
  syncEditorDock();
  renderLibraryDetailPanel();
  void refreshElementSourceLinks();
  void refreshElementTaskLinks();
  void refreshElementCalendarLinks();
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
    tags: readTagField(dom.libraryEditorTags),
    updatedAt: new Date().toISOString()
  };

  setElementsForLibrary(library.id, nextItems);
  saveLibraryElements();
  if (renderItems) renderLibraryItems();
}

export function exportActiveLibraryElementMarkdown() {
  const library = detailLibrary();
  if (!library || !state.activeLibraryElementId) return;
  updateActiveElementFromEditor();
  const element = activeLibraryElement();
  if (!element || !['article', 'note'].includes(element.type)) return;
  downloadLibraryElementMarkdown(element, library);
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

function folderRenameInput(folderId = state.editingFolderId) {
  return [...dom.libraryItemsList.querySelectorAll('[data-folder-rename-input]')].find(
    (input) => input.dataset.folderRenameInput === folderId
  );
}

export function startFolderRename(folderId) {
  const folder = elementsForLibrary().find((item) => item.id === folderId && item.type === 'folder');
  if (!folder || state.activeLibraryElementId) return;
  state.librariesPanelPinned = true;
  state.libraryDetailPanelPinned = true;
  window.dispatchEvent(new CustomEvent('workspace-activate', { detail: { section: 'libraries' } }));
  state.editingFolderId = folder.id;
  renderLibraryItems();
}

export function cancelFolderRename() {
  state.editingFolderId = '';
}

export function hasUnsavedFolderRename() {
  const folder = elementsForLibrary().find((item) => item.id === state.editingFolderId && item.type === 'folder');
  const input = folderRenameInput();
  return Boolean(folder && input && input.value.trim() !== elementTitle(folder));
}

export function discardFolderRenameDraft() {
  cancelFolderRename();
}

export function saveFolderRenameDraft() {
  const input = folderRenameInput();
  if (!input) return true;
  return renameFolder(state.editingFolderId, input);
}

function renameFolder(folderId, input) {
  const library = detailLibrary();
  const nextTitle = input.value.trim();
  const itemIndex = elementsForLibrary(library?.id).findIndex((item) => item.id === folderId && item.type === 'folder');
  if (!library || itemIndex === -1 || state.editingFolderId !== folderId) {
    cancelFolderRename();
    renderLibraryDetailPanel();
    return false;
  }
  if (!nextTitle) {
    input.setCustomValidity('Názov priečinka je povinný.');
    input.reportValidity();
    return false;
  }

  const nextItems = [...elementsForLibrary(library.id)];
  nextItems[itemIndex] = { ...nextItems[itemIndex], title: nextTitle, updatedAt: new Date().toISOString() };
  setElementsForLibrary(library.id, nextItems);
  saveLibraryElements();
  cancelFolderRename();
  renderLibraryDetailPanel();
  return true;
}
