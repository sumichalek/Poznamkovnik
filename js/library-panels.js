import { dom } from './dom.js';
import { state } from './state.js';
import {
  cancelFolderRename,
  closeLibraryElementEditor,
  renderLibraryDetailPanel
} from './library-content.js';
import {
  currentLibrary,
  saveLibraries,
  saveLibraryElements
} from './storage.js';
import { updateTopbarVisibility } from './topbar.js';

function updateWorkspaceVisibility() {
  document.body.classList.toggle(
    'is-library-workspace-active',
    dom.librariesPanel.classList.contains('is-open') || dom.libraryDetailPanel.classList.contains('is-open')
  );
}

export function syncLibraryRowsDetailState() {
  dom.librariesList.querySelectorAll('.library-row').forEach((row) => {
    row.classList.toggle(
      'detail-open',
      row.dataset.libraryId === state.activeDetailLibraryId && dom.libraryDetailPanel.classList.contains('is-open')
    );
  });
}

export function showLibraryForm(library = null) {
  if (library?.id === state.activeDetailLibraryId && !state.libraryDetailPanelPinned) {
    closeLibraryDetailPanel({ force: true });
  }
  state.editingLibraryId = library?.id || '';
  dom.libraryNameInput.value = library?.name || '';
  dom.libraryForm.hidden = false;
  openLibrariesPanel({ pinned: true });
  renderLibraries();
  dom.libraryNameInput.focus();
}

export function hideLibraryForm() {
  state.editingLibraryId = '';
  dom.libraryForm.reset();
  dom.libraryForm.hidden = true;
  renderLibraries();
}

export function renderLibraries() {
  dom.librariesList.innerHTML = '';
  const library = currentLibrary();
  dom.workspaceTitle.textContent = library ? library.name : 'Pôjdeme pomaly.';

  if (state.activeDetailLibraryId && !state.libraries.some((item) => item.id === state.activeDetailLibraryId)) {
    closeLibraryDetailPanel({ force: true });
  } else {
    renderLibraryDetailPanel();
  }

  if (!state.libraries.length) {
    dom.librariesList.innerHTML = '<p class="libraries-empty">Zatiaľ žiadne knižnice.</p>';
    return;
  }

  const visibleLibraries = state.libraries.filter((item) => item.id !== state.editingLibraryId);
  visibleLibraries.forEach((item) => {
    const row = document.createElement('article');
    const rowClasses = ['library-row'];
    if (item.id === state.activeLibraryId) rowClasses.push('active');
    if (item.id === state.activeDetailLibraryId && dom.libraryDetailPanel.classList.contains('is-open')) {
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
        state.libraryDetailPanelPinned &&
        state.activeDetailLibraryId === item.id &&
        dom.libraryDetailPanel.classList.contains('is-open');

      state.activeLibraryId = item.id;
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
    dom.librariesList.append(row);
  });
}

export function upsertLibrary(name) {
  const cleanName = name.trim();
  if (!cleanName) return;

  if (state.editingLibraryId) {
    state.libraries = state.libraries.map((library) =>
      library.id === state.editingLibraryId ? { ...library, name: cleanName } : library
    );
  } else {
    const library = {
      id: crypto.randomUUID(),
      name: cleanName,
      createdAt: new Date().toISOString()
    };
    state.libraries = [library, ...state.libraries];
    state.activeLibraryId = library.id;
  }

  saveLibraries();
  hideLibraryForm();
  renderLibraries();
}

export function deleteLibrary(id) {
  const library = state.libraries.find((item) => item.id === id);
  if (!library || !confirm(`Zmazať knižnicu "${library.name}"?`)) return;

  state.libraries = state.libraries.filter((item) => item.id !== id);
  if (state.activeLibraryId === id) {
    state.activeLibraryId = state.libraries[0]?.id || '';
  }
  if (state.activeDetailLibraryId === id) {
    closeLibraryDetailPanel({ force: true });
  }
  delete state.libraryElements[id];
  saveLibraries();
  saveLibraryElements();
  if (state.editingLibraryId === id) hideLibraryForm();
  renderLibraries();
}

export function openLibrariesPanel({ pinned = false } = {}) {
  window.clearTimeout(state.librariesHideTimer);
  if (pinned) state.librariesPanelPinned = true;
  dom.librariesPanel.classList.add('is-open');
  dom.librariesButton.setAttribute('aria-expanded', 'true');
  updateWorkspaceVisibility();
  updateTopbarVisibility();
}

export function closeLibrariesPanel({ force = false } = {}) {
  if (state.librariesPanelPinned && !force) return;
  state.librariesPanelPinned = false;
  dom.librariesPanel.classList.remove('is-open');
  dom.librariesButton.setAttribute('aria-expanded', 'false');
  closeLibraryDetailPanel({ force: true });
  updateWorkspaceVisibility();
  updateTopbarVisibility();
}

export function openLibraryDetailPanel(libraryId, { pinned = false } = {}) {
  if (!state.libraries.some((library) => library.id === libraryId)) return;
  if (state.libraryDetailPanelPinned && !pinned && state.activeDetailLibraryId && state.activeDetailLibraryId !== libraryId) return;
  window.clearTimeout(state.libraryDetailHideTimer);
  if (state.activeDetailLibraryId !== libraryId) {
    cancelFolderRename();
    closeLibraryElementEditor({ render: false });
    state.activeFolderPath = [];
  }
  state.activeDetailLibraryId = libraryId;
  if (pinned) state.libraryDetailPanelPinned = true;
  renderLibraryDetailPanel();
  dom.libraryDetailPanel.classList.add('is-open');
  dom.libraryDetailPanel.setAttribute('aria-hidden', 'false');
  syncLibraryRowsDetailState();
  updateWorkspaceVisibility();
  updateTopbarVisibility();
}

export function closeLibraryDetailPanel({ force = false } = {}) {
  if (state.libraryDetailPanelPinned && !force) return;
  window.clearTimeout(state.libraryDetailHideTimer);
  state.libraryDetailPanelPinned = false;
  state.activeDetailLibraryId = '';
  state.activeFolderPath = [];
  cancelFolderRename();
  closeLibraryElementEditor({ render: false });
  dom.libraryDetailPanel.classList.remove('is-open');
  dom.libraryDetailPanel.setAttribute('aria-hidden', 'true');
  syncLibraryRowsDetailState();
  updateWorkspaceVisibility();
  updateTopbarVisibility();
}

export function isTextInput(element) {
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(element?.tagName) || element?.isContentEditable;
}

export function scheduleLibrariesPanelClose() {
  window.clearTimeout(state.librariesHideTimer);
  state.librariesHideTimer = window.setTimeout(() => {
    const hoveringPanel = dom.librariesPanel.matches(':hover');
    const hoveringDetailPanel = dom.libraryDetailPanel.matches(':hover');
    const hoveringButton = dom.librariesButton.matches(':hover');
    const focusedPanel = dom.librariesPanel.contains(document.activeElement);
    const focusedDetailPanel = dom.libraryDetailPanel.contains(document.activeElement);
    const focusedButton = dom.librariesButton === document.activeElement;

    if (
      !state.librariesPanelPinned &&
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

export function scheduleLibraryDetailPanelClose() {
  window.clearTimeout(state.libraryDetailHideTimer);
  state.libraryDetailHideTimer = window.setTimeout(() => {
    const hoveringDetailPanel = dom.libraryDetailPanel.matches(':hover');
    const focusedDetailPanel = dom.libraryDetailPanel.contains(document.activeElement);
    const activeLibraryRow = Boolean(dom.librariesList.querySelector('.library-row:hover, .library-row:focus-within'));

    if (!state.libraryDetailPanelPinned && !hoveringDetailPanel && !focusedDetailPanel && !activeLibraryRow) {
      closeLibraryDetailPanel();
    }
  }, 160);
}
