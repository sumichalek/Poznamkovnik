import { elementTypes, storageKeys, themes } from './config.js';
import { dom } from './dom.js';
import { state } from './state.js';

export function normalizeLibraries(value) {
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

export function normalizeLibraryElementList(value) {
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

export function normalizeLibraryElements(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};

  return Object.fromEntries(
    Object.entries(value)
      .map(([libraryId, items]) => [libraryId, normalizeLibraryElementList(items)])
      .filter(([, items]) => items.length)
  );
}

export function applyTheme(theme) {
  const nextTheme = themes.has(theme) ? theme : 'focus';
  document.documentElement.dataset.theme = nextTheme;
  dom.themeSelect.value = nextTheme;
  localStorage.setItem(storageKeys.theme, nextTheme);
}

export function loadLibraries() {
  try {
    state.libraries = normalizeLibraries(JSON.parse(localStorage.getItem(storageKeys.libraries) || '[]'));
  } catch {
    state.libraries = [];
  }
  state.activeLibraryId = localStorage.getItem(storageKeys.activeLibrary) || state.libraries[0]?.id || '';
  if (!state.libraries.some((library) => library.id === state.activeLibraryId)) {
    state.activeLibraryId = state.libraries[0]?.id || '';
  }
  saveLibraries();
}

export function loadLibraryElements() {
  try {
    state.libraryElements = normalizeLibraryElements(JSON.parse(localStorage.getItem(storageKeys.libraryElements) || '{}'));
  } catch {
    state.libraryElements = {};
  }
  saveLibraryElements();
}

export function saveLibraries() {
  state.libraries = normalizeLibraries(state.libraries);
  localStorage.setItem(storageKeys.libraries, JSON.stringify(state.libraries));
  if (state.activeLibraryId) {
    localStorage.setItem(storageKeys.activeLibrary, state.activeLibraryId);
  } else {
    localStorage.removeItem(storageKeys.activeLibrary);
  }
}

export function saveLibraryElements() {
  state.libraryElements = normalizeLibraryElements(state.libraryElements);
  localStorage.setItem(storageKeys.libraryElements, JSON.stringify(state.libraryElements));
}

export function currentLibrary() {
  return state.libraries.find((library) => library.id === state.activeLibraryId) || null;
}

export function detailLibrary() {
  return state.libraries.find((library) => library.id === state.activeDetailLibraryId) || null;
}

export function elementsForLibrary(libraryId = state.activeDetailLibraryId) {
  return state.libraryElements[libraryId] || [];
}

export function setElementsForLibrary(libraryId, items) {
  const normalizedItems = normalizeLibraryElementList(items);
  if (normalizedItems.length) {
    state.libraryElements[libraryId] = normalizedItems;
  } else {
    delete state.libraryElements[libraryId];
  }
}
