import { APP_VERSION, TOPBAR_REVEAL_DISTANCE, storageKeys } from './config.js';
import {
  focusArticleEditor,
  initializeArticleEditor,
  insertArticleFile,
  closeMathDialog,
  openMathDialog,
  resetMathDialog,
  runArticleEditorAction,
  submitMathDialog,
  updateMathPreview
} from './article-editor.js';
import { initializeEditorResizing } from './editor-resize.js';
import { dom } from './dom.js';
import { initializeLogin, isAuthenticated } from './login.js';
import { state } from './state.js';
import {
  cancelFolderRename,
  closeLibraryElementEditor,
  createLibraryElement,
  deleteCurrentFolder,
  deleteLibraryElement,
  exitEditorFullscreen,
  handleLibraryItemClick,
  openLibraryRoot,
  openParentFolder,
  renameCurrentFolder,
  startFolderRename,
  toggleEditorFullscreen,
  updateEditorDockAxis,
  updateActiveElementFromEditor
} from './library-content.js';
import {
  closeLibrariesPanel,
  closeLibraryDetailPanel,
  hideLibraryForm,
  isTextInput,
  openLibraryDetailPanel,
  openLibrariesPanel,
  renderLibraries,
  scheduleLibrariesPanelClose,
  scheduleLibraryDetailPanelClose,
  showLibraryForm,
  upsertLibrary
} from './library-panels.js';
import { applyTheme, loadLibraries, loadLibraryElements } from './storage.js';
import { hideTopbarImmediately, updateTopbarVisibility } from './topbar.js';

document.addEventListener('pointermove', (event) => {
  if (!isAuthenticated()) return;
  state.pointerNearTop = event.clientY <= TOPBAR_REVEAL_DISTANCE;
  updateTopbarVisibility();
});
dom.topbar.addEventListener('pointerenter', () => {
  state.pointerNearTop = true;
  updateTopbarVisibility();
});
dom.topbar.addEventListener('pointerleave', () => {
  state.pointerNearTop = false;
  updateTopbarVisibility();
});
dom.topbar.addEventListener('focusin', updateTopbarVisibility);
dom.topbar.addEventListener('focusout', updateTopbarVisibility);

dom.librariesButton.addEventListener('pointerenter', () => openLibrariesPanel());
dom.librariesButton.addEventListener('pointerleave', scheduleLibrariesPanelClose);
dom.librariesButton.addEventListener('focus', () => openLibrariesPanel());
dom.librariesButton.addEventListener('click', () => {
  if (state.librariesPanelPinned && dom.librariesPanel.classList.contains('is-open')) {
    closeLibrariesPanel({ force: true });
    dom.librariesButton.blur();
    return;
  }

  openLibrariesPanel({ pinned: true });
});
dom.librariesPanel.addEventListener('pointerenter', () => openLibrariesPanel());
dom.librariesPanel.addEventListener('pointerleave', scheduleLibrariesPanelClose);
dom.librariesPanel.addEventListener('focusin', () => openLibrariesPanel());
dom.librariesPanel.addEventListener('focusout', scheduleLibrariesPanelClose);
dom.libraryDetailPanel.addEventListener('pointerenter', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});
dom.libraryDetailPanel.addEventListener('pointerleave', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});
dom.libraryDetailPanel.addEventListener('focusin', () => {
  if (state.activeDetailLibraryId) openLibraryDetailPanel(state.activeDetailLibraryId);
});
dom.libraryDetailPanel.addEventListener('focusout', () => {
  scheduleLibraryDetailPanelClose();
  scheduleLibrariesPanelClose();
});

dom.libraryCreateButton.addEventListener('click', () => showLibraryForm());
dom.libraryCancelButton.addEventListener('click', hideLibraryForm);
dom.libraryForm.addEventListener('submit', (event) => {
  event.preventDefault();
  upsertLibrary(dom.libraryNameInput.value);
});
dom.folderHomeButton.addEventListener('click', openLibraryRoot);
dom.folderUpButton.addEventListener('click', openParentFolder);
dom.folderRenameButton.addEventListener('click', startFolderRename);
dom.folderDeleteButton.addEventListener('click', deleteCurrentFolder);
dom.folderRenameForm.addEventListener('submit', (event) => {
  event.preventDefault();
  renameCurrentFolder();
});
dom.folderRenameInput.addEventListener('input', () => dom.folderRenameInput.setCustomValidity(''));
dom.createFolderButton.addEventListener('click', () => createLibraryElement('folder'));
dom.createNoteButton.addEventListener('click', () => createLibraryElement('note'));
dom.createArticleButton.addEventListener('click', () => createLibraryElement('article'));
dom.libraryItemsList.addEventListener('pointerup', handleLibraryItemClick);
dom.libraryItemsList.addEventListener('click', handleLibraryItemClick);
dom.libraryEditorBack.addEventListener('click', () => closeLibraryElementEditor());
dom.libraryEditorFullscreen.addEventListener('click', toggleEditorFullscreen);
dom.libraryEditorDelete.addEventListener('click', () => deleteLibraryElement());
dom.libraryEditorTitle.addEventListener('input', () => updateActiveElementFromEditor({ renderItems: true }));
dom.libraryEditorTitle.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  updateActiveElementFromEditor({ renderItems: true });
  focusArticleEditor();
});
dom.libraryEditorBody.addEventListener('input', () => updateActiveElementFromEditor());

function openCitationDialog() {
  if (!state.activeLibraryElementId) return;
  dom.citationForm.reset();
  dom.citationDialog.showModal();
  dom.citationSourceInput.focus();
}

function selectEditorFile(kind) {
  dom.editorFileInput.value = '';
  dom.editorFileInput.dataset.insertKind = kind;
  dom.editorFileInput.accept = kind === 'image' ? 'image/*' : '*/*';
  dom.editorFileInput.click();
}

dom.editorFormatButtons.forEach((button) => {
  button.addEventListener('pointerdown', (event) => event.preventDefault());
  button.addEventListener('click', () => {
    const action = button.dataset.editorAction;
    if (!action) return;
    if (action === 'citation') {
      openCitationDialog();
      return;
    }
    if (action === 'math-inline' || action === 'math-block') {
      openMathDialog({ kind: action === 'math-block' ? 'block' : 'inline' });
      return;
    }
    if (action === 'image' || action === 'attachment') {
      selectEditorFile(action);
      return;
    }
    if (action === 'link') {
      const href = window.prompt('Adresa odkazu');
      if (!href) return;
      if (runArticleEditorAction(action, { href })) updateActiveElementFromEditor();
      return;
    }
    if (runArticleEditorAction(action)) updateActiveElementFromEditor();
  });
});
dom.editorFileInput.addEventListener('change', async () => {
  const [file] = dom.editorFileInput.files || [];
  const kind = dom.editorFileInput.dataset.insertKind;
  if (file && (kind === 'image' || kind === 'attachment')) {
    if (await insertArticleFile(file, kind)) updateActiveElementFromEditor();
  }
  dom.editorFileInput.value = '';
  delete dom.editorFileInput.dataset.insertKind;
});
dom.citationCancelButton.addEventListener('click', () => dom.citationDialog.close());
dom.citationForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const inserted = runArticleEditorAction('citation', {
    source: dom.citationSourceInput.value,
    locator: dom.citationLocatorInput.value
  });
  if (inserted) {
    updateActiveElementFromEditor();
    dom.citationDialog.close();
  }
});
dom.citationDialog.addEventListener('click', (event) => {
  if (event.target === dom.citationDialog) dom.citationDialog.close();
});
dom.mathCancelButton.addEventListener('click', closeMathDialog);
dom.mathLatex.addEventListener('input', updateMathPreview);
dom.mathForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (submitMathDialog()) updateActiveElementFromEditor();
});
dom.mathDialog.addEventListener('click', (event) => {
  if (event.target === dom.mathDialog) closeMathDialog();
});
dom.mathDialog.addEventListener('close', resetMathDialog);

document.addEventListener('pointerdown', (event) => {
  if (!isAuthenticated()) return;
  if (!state.librariesPanelPinned && !state.libraryDetailPanelPinned) return;
  if (
    dom.topbar.contains(event.target) ||
    dom.librariesPanel.contains(event.target) ||
    dom.libraryDetailPanel.contains(event.target) ||
    dom.libraryEditorDock.contains(event.target)
  ) {
    return;
  }
  closeLibrariesPanel({ force: true });
});

document.addEventListener('keydown', (event) => {
  if (!isAuthenticated()) return;
  if (event.key === 'Escape') {
    if (dom.settingsDialog.open || dom.citationDialog.open || dom.mathDialog.open) return;

    if (exitEditorFullscreen()) {
      event.preventDefault();
      return;
    }

    if (!dom.folderRenameForm.hidden) {
      event.preventDefault();
      cancelFolderRename();
      return;
    }

    if (dom.libraryDetailPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibraryDetailPanel({ force: true });
      return;
    }

    if (dom.librariesPanel.classList.contains('is-open')) {
      event.preventDefault();
      closeLibrariesPanel({ force: true });
      hideTopbarImmediately();
      return;
    }

    if (!dom.topbar.classList.contains('is-hidden')) {
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
  dom.librariesButton.focus();
});

dom.settingsButton.addEventListener('click', () => {
  dom.settingsDialog.showModal();
  updateTopbarVisibility();
});
dom.settingsClose.addEventListener('click', () => {
  dom.settingsDialog.close();
  updateTopbarVisibility();
});
dom.themeSelect.addEventListener('change', () => applyTheme(dom.themeSelect.value));
dom.settingsDialog.addEventListener('click', (event) => {
  if (event.target === dom.settingsDialog) dom.settingsDialog.close();
  updateTopbarVisibility();
});
dom.settingsDialog.addEventListener('close', updateTopbarVisibility);

window.addEventListener('resize', updateEditorDockAxis);
window.visualViewport?.addEventListener('resize', updateEditorDockAxis);

document.documentElement.dataset.appVersion = APP_VERSION;
if (dom.appVersion) dom.appVersion.textContent = `Verzia ${APP_VERSION}`;
initializeArticleEditor({ onUpdate: () => updateActiveElementFromEditor() });
initializeEditorResizing();
applyTheme(localStorage.getItem(storageKeys.theme) || 'focus');
loadLibraries();
loadLibraryElements();
updateEditorDockAxis();
renderLibraries();
dom.librariesButton.setAttribute('aria-expanded', 'false');
updateTopbarVisibility();
initializeLogin({
  onAuthenticated: () => {
    state.pointerNearTop = true;
    updateTopbarVisibility();
  }
});
