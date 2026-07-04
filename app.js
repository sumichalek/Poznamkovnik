const settingsButton = document.getElementById('settings-button');
const settingsDialog = document.getElementById('settings-dialog');
const settingsClose = document.getElementById('settings-close');
const themeSelect = document.getElementById('theme-select');
const themeToggle = document.getElementById('theme-toggle');
const topbar = document.querySelector('.topbar');
const librariesButton = document.getElementById('libraries-button');
const librariesPanel = document.getElementById('libraries-panel');
const libraryDetailPanel = document.getElementById('library-detail-panel');
const libraryDetailTitle = document.getElementById('library-detail-title');
const folderHomeButton = document.getElementById('folder-home-button');
const folderUpButton = document.getElementById('folder-up-button');
const createFolderButton = document.getElementById('create-folder-button');
const createNoteButton = document.getElementById('create-note-button');
const createArticleButton = document.getElementById('create-article-button');
const libraryBrowser = document.getElementById('library-browser');
const libraryItemsList = document.getElementById('library-items-list');
const libraryEditor = document.getElementById('library-editor');
const libraryEditorBack = document.getElementById('library-editor-back');
const libraryEditorTitle = document.getElementById('library-editor-title');
const libraryEditorDelete = document.getElementById('library-editor-delete');
const libraryEditorBody = document.getElementById('library-editor-body');
const editorFormatButtons = document.querySelectorAll('[data-format-command]');
const libraryCreateButton = document.getElementById('library-create-button');
const libraryForm = document.getElementById('library-form');
const libraryNameInput = document.getElementById('library-name');
const libraryCancelButton = document.getElementById('library-cancel-button');
const librariesList = document.getElementById('libraries-list');
const workspaceTitle = document.getElementById('workspace-title');
const appVersion = document.getElementById('app-version');

const APP_VERSION = '0.1.1';
const THEME_KEY = 'knowledge-theme';
const LIBRARIES_KEY = 'knowledge-libraries';
const ACTIVE_LIBRARY_KEY = 'knowledge-active-library';
const LIBRARY_ELEMENTS_KEY = 'knowledge-library-elements';
const TOPBAR_REVEAL_DISTANCE = 72;
const themes = new Set(['focus', 'paper', 'dark', 'contrast']);
const elementTypes = new Set(['folder', 'note', 'article']);
const elementTypeLabels = {
  folder: 'Priečinok',
  note: 'Poznámka',
  article: 'Článok'
};
let pointerNearTop = true;
let librariesPanelPinned = false;
let libraryDetailPanelPinned = false;
let libraries = [];
let libraryElements = {};
let activeLibraryId = '';
let activeDetailLibraryId = '';
let activeLibraryElementId = '';
let activeFolderPath = [];
let editingLibraryId = '';
let lastLibraryItemAction = null;
let hideTimer = 0;
let librariesHideTimer = 0;
let libraryDetailHideTimer = 0;

function normalizeLibraries(value) {
  if (!Array.isArray(value)) return [];

  const seenIds = new Set();
  return value
    .map((library) => ({
      id: library?.id || crypto.randomUUID(),
      name: String(library?.name || '').trim(),
      createdAt: library?.createdAt || new Date().toISOString()
    }))
    .filter((library) => {
      if (!library.name || seenIds.has(library.id)) return false;
      seenIds.add(library.id);
      return true;
    });
}

function normalizeLibraryElementList(value) {
  if (!Array.isArray(value)) return [];

  const seenIds = new Set();
  const normalizedItems = value
    .map((item) => ({
      id: item?.id || crypto.randomUUID(),
      type: elementTypes.has(item?.type) ? item.type : 'note',
      parentId: typeof item?.parentId === 'string' ? item.parentId : '',
      title: String(item?.title || '').trim(),
      content: String(item?.content || ''),
      createdAt: item?.createdAt || new Date().toISOString(),
      updatedAt: item?.updatedAt || item?.createdAt || new Date().toISOString()
    }))
    .filter((item) => {
      if (seenIds.has(item.id)) return false;
      seenIds.add(item.id);
      return true;
    });
  const folderIds = new Set(normalizedItems.filter((item) => item.type === 'folder').map((item) => item.id));
  return normalizedItems.map((item) =>
    item.parentId && (!folderIds.has(item.parentId) || item.parentId === item.id) ? { ...item, parentId: '' } : item
  );
}

function normalizeLibraryElements(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};

  return Object.fromEntries(
    Object.entries(value)
      .map(([libraryId, items]) => [libraryId, normalizeLibraryElementList(items)])
      .filter(([, items]) => items.length)
  );
}

function applyTheme(theme) {
  const nextTheme = themes.has(theme) ? theme : 'focus';
  document.documentElement.dataset.theme = nextTheme;
  themeSelect.value = nextTheme;
  themeToggle.checked = nextTheme === 'dark';
  localStorage.setItem(THEME_KEY, nextTheme);
}

function loadLibraries() {
  try {
    libraries = normalizeLibraries(JSON.parse(localStorage.getItem(LIBRARIES_KEY) || '[]'));
  } catch {
    libraries = [];
  }
  activeLibraryId = localStorage.getItem(ACTIVE_LIBRARY_KEY) || libraries[0]?.id || '';
  if (!libraries.some((library) => library.id === activeLibraryId)) {
    activeLibraryId = libraries[0]?.id || '';
  }
  saveLibraries();
}

function loadLibraryElements() {
  try {
    libraryElements = normalizeLibraryElements(JSON.parse(localStorage.getItem(LIBRARY_ELEMENTS_KEY) || '{}'));
  } catch {
    libraryElements = {};
  }
  saveLibraryElements();
}

function saveLibraries() {
  libraries = normalizeLibraries(libraries);
  localStorage.setItem(LIBRARIES_KEY, JSON.stringify(libraries));
  if (activeLibraryId) {
    localStorage.setItem(ACTIVE_LIBRARY_KEY, activeLibraryId);
  } else {
    localStorage.removeItem(ACTIVE_LIBRARY_KEY);
  }
}

function saveLibraryElements() {
  libraryElements = normalizeLibraryElements(libraryElements);
  localStorage.setItem(LIBRARY_ELEMENTS_KEY, JSON.stringify(libraryElements));
}

function currentLibrary() {
  return libraries.find((library) => library.id === activeLibraryId) || null;
}

function detailLibrary() {
  return libraries.find((library) => library.id === activeDetailLibraryId) || null;
}

function elementsForLibrary(libraryId = activeDetailLibraryId) {
  return libraryElements[libraryId] || [];
}

function setElementsForLibrary(libraryId, items) {
  const normalizedItems = normalizeLibraryElementList(items);
  if (normalizedItems.length) {
    libraryElements[libraryId] = normalizedItems;
  } else {
    delete libraryElements[libraryId];
  }
}

function activeLibraryElement() {
  return elementsForLibrary().find((item) => item.id === activeLibraryElementId) || null;
}

function currentFolderId() {
  return activeFolderPath.at(-1) || '';
}

function currentFolderItems(libraryId = activeDetailLibraryId) {
  const folderId = currentFolderId();
  return elementsForLibrary(libraryId).filter((item) => (item.parentId || '') === folderId);
}

function activeFolderPathItems(libraryId = activeDetailLibraryId) {
  const itemsById = new Map(elementsForLibrary(libraryId).map((item) => [item.id, item]));
  return activeFolderPath.map((folderId) => itemsById.get(folderId)).filter(Boolean);
}

function elementTitle(item) {
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
  const items = elementsForLibrary();
  const itemsById = new Map(items.map((item) => [item.id, item]));
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

  for (const folderId of activeFolderPath) {
    const folder = itemsById.get(folderId);
    if (!folder || folder.type !== 'folder' || (folder.parentId || '') !== expectedParentId) break;
    normalizedPath.push(folder.id);
    expectedParentId = folder.id;
  }

  activeFolderPath = normalizedPath;
}

function updateLibraryPathControls() {
  const library = detailLibrary();
  const pathLabels = activeFolderPathItems(library?.id).map(elementTitle);
  const visiblePath = ['Koreň', ...pathLabels].join(' / ');
  const fullPath = [library?.name, ...pathLabels].filter(Boolean).join(' / ') || 'Koreň';

  libraryDetailTitle.textContent = visiblePath;
  libraryDetailTitle.title = fullPath;
  folderHomeButton.disabled = !activeFolderPath.length;
  folderUpButton.disabled = !activeFolderPath.length;
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

function syncLibraryRowsDetailState() {
  librariesList.querySelectorAll('.library-row').forEach((row) => {
    row.classList.toggle(
      'detail-open',
      row.dataset.libraryId === activeDetailLibraryId && libraryDetailPanel.classList.contains('is-open')
    );
  });
}

function runLibraryItemAction(elementId, action) {
  const now = window.performance.now();
  if (
    lastLibraryItemAction &&
    lastLibraryItemAction.elementId === elementId &&
    lastLibraryItemAction.action === action &&
    now - lastLibraryItemAction.at < 350
  ) {
    return;
  }

  lastLibraryItemAction = { elementId, action, at: now };
  if (action === 'delete') {
    deleteLibraryElement(elementId);
    return;
  }

  openLibraryElement(elementId);
}

function stopAndRunLibraryItemAction(event, elementId, action) {
  event.preventDefault();
  event.stopPropagation();
  runLibraryItemAction(elementId, action);
}

function createLibraryItemCard(item) {
  const card = document.createElement('article');
  const cardClasses = ['library-item-card', `${item.type}-item`];
  if (item.id === activeLibraryElementId) cardClasses.push('active');
  if (activeFolderPath.includes(item.id)) cardClasses.push('folder-open');
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

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.className = 'library-item-delete';
  deleteButton.dataset.itemAction = 'delete';
  deleteButton.textContent = '×';
  deleteButton.title = 'Zmazať prvok';
  deleteButton.setAttribute('aria-label', `Zmazať ${elementTypeLabels[item.type].toLowerCase()} ${elementTitle(item)}`);
  deleteButton.addEventListener('pointerup', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('click', (event) => stopAndRunLibraryItemAction(event, item.id, 'delete'));
  deleteButton.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') stopAndRunLibraryItemAction(event, item.id, 'delete');
  });

  card.append(openButton, deleteButton);
  return card;
}

function handleLibraryItemClick(event) {
  const card = event.target.closest('.library-item-card');
  if (!card || !libraryItemsList.contains(card)) return;

  const elementId = card.dataset.elementId;
  if (!elementId) return;

  event.preventDefault();
  const action = event.target.closest('[data-item-action="delete"]') ? 'delete' : 'open';
  runLibraryItemAction(elementId, action);
}

function renderLibraryItems() {
  libraryItemsList.innerHTML = '';
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
    libraryItemsList.append(empty);
    return;
  }

  items.forEach((item) => {
    libraryItemsList.append(createLibraryItemCard(item));
  });
}

function closeLibraryElementEditor({ render = true } = {}) {
  activeLibraryElementId = '';
  libraryDetailPanel.classList.remove('is-editing');
  libraryBrowser.hidden = false;
  libraryEditor.hidden = true;
  libraryEditorTitle.value = '';
  libraryEditorBody.innerHTML = '';
  if (render) renderLibraryDetailPanel();
}

function renderLibraryDetailPanel() {
  const library = detailLibrary();
  if (!library) {
    libraryDetailTitle.textContent = 'Koreň';
    folderHomeButton.disabled = true;
    folderUpButton.disabled = true;
    return;
  }
  normalizeActiveFolderPath();
  updateLibraryPathControls();
  if (activeLibraryElementId && !activeLibraryElement()) {
    closeLibraryElementEditor({ render: false });
  }
  renderLibraryItems();
  syncLibraryRowsDetailState();
}

function createLibraryElement(type) {
  const library = detailLibrary();
  if (!library || !elementTypes.has(type)) return;

  librariesPanelPinned = true;
  libraryDetailPanelPinned = true;
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

function openLibraryElement(elementId) {
  const item = elementsForLibrary().find((element) => element.id === elementId);
  if (!item) return;

  librariesPanelPinned = true;
  libraryDetailPanelPinned = true;

  if (item.type === 'folder') {
    closeLibraryElementEditor({ render: false });
    activeFolderPath = [...folderPathTo(item.parentId || ''), item.id];
    activeLibraryElementId = '';
    renderLibraryDetailPanel();
    updateTopbarVisibility();
    return;
  }

  activeLibraryElementId = item.id;
  libraryDetailPanel.classList.add('is-editing');
  libraryBrowser.hidden = true;
  libraryEditor.hidden = false;
  libraryEditorTitle.value = elementTitle(item);
  libraryEditorBody.innerHTML = item.content;
  libraryEditorBody.dataset.placeholder = item.type === 'article' ? 'Píšte článok...' : 'Píšte poznámku...';
  renderLibraryItems();
  updateTopbarVisibility();
  libraryEditorBody.focus();
}

function updateActiveElementFromEditor({ renderItems = false } = {}) {
  const library = detailLibrary();
  if (!library || !activeLibraryElementId) return;

  const items = elementsForLibrary(library.id);
  const itemIndex = items.findIndex((item) => item.id === activeLibraryElementId);
  if (itemIndex === -1) return;

  const nextItems = [...items];
  nextItems[itemIndex] = {
    ...nextItems[itemIndex],
    title: libraryEditorTitle.value.trim(),
    content: libraryEditorBody.innerHTML,
    updatedAt: new Date().toISOString()
  };

  setElementsForLibrary(library.id, nextItems);
  saveLibraryElements();
  if (renderItems) renderLibraryItems();
}

function deleteLibraryElement(elementId = activeLibraryElementId) {
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

  if (deletedIds.has(activeLibraryElementId)) {
    closeLibraryElementEditor({ render: false });
  }
  const deletedFolderIndex = activeFolderPath.findIndex((folderId) => deletedIds.has(folderId));
  if (deletedFolderIndex !== -1) {
    activeFolderPath = activeFolderPath.slice(0, deletedFolderIndex);
  }
  renderLibraryDetailPanel();
}

function openLibraryRoot() {
  if (!activeFolderPath.length) return;
  closeLibraryElementEditor({ render: false });
  activeFolderPath = [];
  activeLibraryElementId = '';
  renderLibraryDetailPanel();
  updateTopbarVisibility();
}

function openParentFolder() {
  if (!activeFolderPath.length) return;
  closeLibraryElementEditor({ render: false });
  activeFolderPath = activeFolderPath.slice(0, -1);
  activeLibraryElementId = '';
  renderLibraryDetailPanel();
  updateTopbarVisibility();
}

function showLibraryForm(library = null) {
  if (library?.id === activeDetailLibraryId && !libraryDetailPanelPinned) {
    closeLibraryDetailPanel({ force: true });
  }
  editingLibraryId = library?.id || '';
  libraryNameInput.value = library?.name || '';
  libraryForm.hidden = false;
  openLibrariesPanel({ pinned: true });
  renderLibraries();
  libraryNameInput.focus();
}

function hideLibraryForm() {
  editingLibraryId = '';
  libraryForm.reset();
  libraryForm.hidden = true;
  renderLibraries();
}

function renderLibraries() {
  librariesList.innerHTML = '';
  const library = currentLibrary();
  workspaceTitle.textContent = library ? library.name : 'Pôjdeme pomaly.';

  if (activeDetailLibraryId && !libraries.some((item) => item.id === activeDetailLibraryId)) {
    closeLibraryDetailPanel({ force: true });
  } else {
    renderLibraryDetailPanel();
  }

  if (!libraries.length) {
    librariesList.innerHTML = '<p class="libraries-empty">Zatiaľ žiadne knižnice.</p>';
    return;
  }

  const visibleLibraries = libraries.filter((item) => item.id !== editingLibraryId);
  visibleLibraries.forEach((item) => {
    const row = document.createElement('article');
    const rowClasses = ['library-row'];
    if (item.id === activeLibraryId) rowClasses.push('active');
    if (item.id === activeDetailLibraryId && libraryDetailPanel.classList.contains('is-open')) {
      rowClasses.push('detail-open');
    }
    row.className = rowClasses.join(' ');
    row.dataset.libraryId = item.id;
    row.addEventListener('pointerenter', () => openLibraryDetailPanel(item.id));
    row.addEventListener('pointerleave', scheduleLibraryDetailPanelClose);
    row.addEventListener('focusin', () => openLibraryDetailPanel(item.id));
    row.addEventListener('focusout', scheduleLibraryDetailPanelClose);

    const selectButton = document.createElement('button');
    selectButton.type = 'button';
    selectButton.className = 'library-select';
    selectButton.textContent = item.name;
    selectButton.addEventListener('click', () => {
      const shouldCloseDetail =
        libraryDetailPanelPinned &&
        activeDetailLibraryId === item.id &&
        libraryDetailPanel.classList.contains('is-open');

      activeLibraryId = item.id;
      saveLibraries();

      if (shouldCloseDetail) {
        closeLibraryDetailPanel({ force: true });
      } else {
        openLibrariesPanel({ pinned: true });
        openLibraryDetailPanel(item.id, { pinned: true });
      }

      renderLibraries();
    });

    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'panel-icon-button';
    editButton.textContent = '✎';
    editButton.title = 'Upraviť knižnicu';
    editButton.setAttribute('aria-label', `Upraviť knižnicu ${item.name}`);
    editButton.addEventListener('click', () => showLibraryForm(item));

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'panel-icon-button danger';
    deleteButton.textContent = '×';
    deleteButton.title = 'Zmazať knižnicu';
    deleteButton.setAttribute('aria-label', `Zmazať knižnicu ${item.name}`);
    deleteButton.addEventListener('click', () => deleteLibrary(item.id));

    row.append(selectButton, editButton, deleteButton);
    librariesList.append(row);
  });
}

function upsertLibrary(name) {
  const cleanName = name.trim();
  if (!cleanName) return;

  if (editingLibraryId) {
    libraries = libraries.map((library) =>
      library.id === editingLibraryId ? { ...library, name: cleanName } : library
    );
  } else {
    const library = {
      id: crypto.randomUUID(),
      name: cleanName,
      createdAt: new Date().toISOString()
    };
    libraries = [library, ...libraries];
    activeLibraryId = library.id;
  }

  saveLibraries();
  hideLibraryForm();
  renderLibraries();
}

function deleteLibrary(id) {
  const library = libraries.find((item) => item.id === id);
  if (!library || !confirm(`Zmazať knižnicu "${library.name}"?`)) return;

  libraries = libraries.filter((library) => library.id !== id);
  if (activeLibraryId === id) {
    activeLibraryId = libraries[0]?.id || '';
  }
  if (activeDetailLibraryId === id) {
    closeLibraryDetailPanel({ force: true });
  }
  delete libraryElements[id];
  saveLibraries();
  saveLibraryElements();
  if (editingLibraryId === id) hideLibraryForm();
  renderLibraries();
}

function topbarShouldStayVisible() {
  return (
    pointerNearTop ||
    settingsDialog.open ||
    librariesPanel.classList.contains('is-open') ||
    libraryDetailPanel.classList.contains('is-open') ||
    topbar.matches(':hover') ||
    topbar.contains(document.activeElement)
  );
}

function updateTopbarVisibility() {
  window.clearTimeout(hideTimer);
  if (topbarShouldStayVisible()) {
    topbar.classList.remove('is-hidden');
    return;
  }

  hideTimer = window.setTimeout(() => {
    if (!topbarShouldStayVisible()) topbar.classList.add('is-hidden');
  }, 240);
}

function hideTopbarImmediately() {
  window.clearTimeout(hideTimer);
  pointerNearTop = false;
  if (topbar.contains(document.activeElement) && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
  topbar.classList.add('is-hidden');
}

function openLibrariesPanel({ pinned = false } = {}) {
  window.clearTimeout(librariesHideTimer);
  if (pinned) librariesPanelPinned = true;
  librariesPanel.classList.add('is-open');
  librariesButton.setAttribute('aria-expanded', 'true');
  updateTopbarVisibility();
}

function closeLibrariesPanel({ force = false } = {}) {
  if (librariesPanelPinned && !force) return;
  librariesPanelPinned = false;
  librariesPanel.classList.remove('is-open');
  librariesButton.setAttribute('aria-expanded', 'false');
  closeLibraryDetailPanel({ force: true });
  updateTopbarVisibility();
}

function openLibraryDetailPanel(libraryId, { pinned = false } = {}) {
  if (!libraries.some((library) => library.id === libraryId)) return;
  if (libraryDetailPanelPinned && !pinned && activeDetailLibraryId && activeDetailLibraryId !== libraryId) return;
  window.clearTimeout(libraryDetailHideTimer);
  if (activeDetailLibraryId !== libraryId) {
    closeLibraryElementEditor({ render: false });
    activeFolderPath = [];
  }
  activeDetailLibraryId = libraryId;
  if (pinned) libraryDetailPanelPinned = true;
  renderLibraryDetailPanel();
  libraryDetailPanel.classList.add('is-open');
  libraryDetailPanel.setAttribute('aria-hidden', 'false');
  syncLibraryRowsDetailState();
  updateTopbarVisibility();
}

function closeLibraryDetailPanel({ force = false } = {}) {
  if (libraryDetailPanelPinned && !force) return;
  window.clearTimeout(libraryDetailHideTimer);
  libraryDetailPanelPinned = false;
  activeDetailLibraryId = '';
  activeFolderPath = [];
  closeLibraryElementEditor({ render: false });
  libraryDetailPanel.classList.remove('is-open');
  libraryDetailPanel.setAttribute('aria-hidden', 'true');
  syncLibraryRowsDetailState();
  updateTopbarVisibility();
}

function isTextInput(element) {
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(element?.tagName) || element?.isContentEditable;
}

function scheduleLibrariesPanelClose() {
  window.clearTimeout(librariesHideTimer);
  librariesHideTimer = window.setTimeout(() => {
    const hoveringPanel = librariesPanel.matches(':hover');
    const hoveringDetailPanel = libraryDetailPanel.matches(':hover');
    const hoveringButton = librariesButton.matches(':hover');
    const focusedPanel = librariesPanel.contains(document.activeElement);
    const focusedDetailPanel = libraryDetailPanel.contains(document.activeElement);
    const focusedButton = librariesButton === document.activeElement;

    if (
      !librariesPanelPinned &&
      !hoveringPanel &&
      !hoveringDetailPanel &&
      !hoveringButton &&
      !focusedPanel &&
      !focusedDetailPanel &&
      !focusedButton
    ) {
      closeLibrariesPanel();
    }
  }, 160);
}

function scheduleLibraryDetailPanelClose() {
  window.clearTimeout(libraryDetailHideTimer);
  libraryDetailHideTimer = window.setTimeout(() => {
    const hoveringDetailPanel = libraryDetailPanel.matches(':hover');
    const focusedDetailPanel = libraryDetailPanel.contains(document.activeElement);
    const activeLibraryRow = Boolean(librariesList.querySelector('.library-row:hover, .library-row:focus-within'));

    if (!libraryDetailPanelPinned && !hoveringDetailPanel && !focusedDetailPanel && !activeLibraryRow) {
      closeLibraryDetailPanel();
    }
  }, 160);
}

document.addEventListener('pointermove', (event) => {
  pointerNearTop = event.clientY <= TOPBAR_REVEAL_DISTANCE;
  updateTopbarVisibility();
});
topbar.addEventListener('pointerenter', () => {
  pointerNearTop = true;
  updateTopbarVisibility();
});
topbar.addEventListener('pointerleave', () => {
  pointerNearTop = false;
  updateTopbarVisibility();
});
topbar.addEventListener('focusin', updateTopbarVisibility);
topbar.addEventListener('focusout', updateTopbarVisibility);

librariesButton.addEventListener('pointerenter', () => openLibrariesPanel());
librariesButton.addEventListener('pointerleave', scheduleLibrariesPanelClose);
librariesButton.addEventListener('focus', () => openLibrariesPanel());
librariesButton.addEventListener('click', () => {
  if (librariesPanelPinned && librariesPanel.classList.contains('is-open')) {
    closeLibrariesPanel({ force: true });
    librariesButton.blur();
    return;
  }

  openLibrariesPanel({ pinned: true });
});
librariesPanel.addEventListener('pointerenter', () => openLibrariesPanel());
librariesPanel.addEventListener('pointerleave', scheduleLibrariesPanelClose);
librariesPanel.addEventListener('focusin', () => openLibrariesPanel());
librariesPanel.addEventListener('focusout', scheduleLibrariesPanelClose);
libraryDetailPanel.addEventListener('pointerenter', () => {
  if (activeDetailLibraryId) openLibraryDetailPanel(activeDetailLibraryId);
});
libraryDetailPanel.addEventListener('pointerleave', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});
libraryDetailPanel.addEventListener('focusin', () => {
  if (activeDetailLibraryId) openLibraryDetailPanel(activeDetailLibraryId);
});
libraryDetailPanel.addEventListener('focusout', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});

libraryCreateButton.addEventListener('click', () => showLibraryForm());
libraryCancelButton.addEventListener('click', hideLibraryForm);
libraryForm.addEventListener('submit', (event) => {
  event.preventDefault();
  upsertLibrary(libraryNameInput.value);
});
folderHomeButton.addEventListener('click', openLibraryRoot);
folderUpButton.addEventListener('click', openParentFolder);
createFolderButton.addEventListener('click', () => createLibraryElement('folder'));
createNoteButton.addEventListener('click', () => createLibraryElement('note'));
createArticleButton.addEventListener('click', () => createLibraryElement('article'));
libraryItemsList.addEventListener('pointerup', handleLibraryItemClick);
libraryItemsList.addEventListener('click', handleLibraryItemClick);
libraryEditorBack.addEventListener('click', () => closeLibraryElementEditor());
libraryEditorDelete.addEventListener('click', () => deleteLibraryElement());
libraryEditorTitle.addEventListener('input', () => updateActiveElementFromEditor({ renderItems: true }));
libraryEditorBody.addEventListener('input', () => updateActiveElementFromEditor());
editorFormatButtons.forEach((button) => {
  button.addEventListener('click', () => {
    libraryEditorBody.focus();
    document.execCommand(button.dataset.formatCommand, false, null);
    updateActiveElementFromEditor();
  });
});

document.addEventListener('pointerdown', (event) => {
  if (!librariesPanelPinned && !libraryDetailPanelPinned) return;
  if (topbar.contains(event.target) || librariesPanel.contains(event.target) || libraryDetailPanel.contains(event.target)) {
    return;
  }
  closeLibrariesPanel({ force: true });
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    if (settingsDialog.open) return;

    if (libraryDetailPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibraryDetailPanel({ force: true });
      return;
    }

    if (librariesPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibrariesPanel({ force: true });
      hideTopbarImmediately();
      return;
    }

    if (!topbar.classList.contains('is-hidden')) {
      event.preventDefault();
      hideTopbarImmediately();
    }
    return;
  }

  if (!event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
  if (event.key.toLowerCase() !== 'k') return;
  if (isTextInput(event.target)) return;

  event.preventDefault();
  openLibrariesPanel({ pinned: true });
  librariesButton.focus();
});

settingsButton.addEventListener('click', () => {
  settingsDialog.showModal();
  updateTopbarVisibility();
});
settingsClose.addEventListener('click', () => {
  settingsDialog.close();
  updateTopbarVisibility();
});
themeSelect.addEventListener('change', () => applyTheme(themeSelect.value));
themeToggle.addEventListener('change', () => applyTheme(themeToggle.checked ? 'dark' : 'focus'));
settingsDialog.addEventListener('click', (event) => {
  if (event.target === settingsDialog) settingsDialog.close();
  updateTopbarVisibility();
});
settingsDialog.addEventListener('close', updateTopbarVisibility);

document.documentElement.dataset.appVersion = APP_VERSION;
if (appVersion) appVersion.textContent = `Verzia ${APP_VERSION}`;
applyTheme(localStorage.getItem(THEME_KEY) || 'focus');
loadLibraries();
loadLibraryElements();
renderLibraries();
librariesButton.setAttribute('aria-expanded', 'false');
updateTopbarVisibility();
